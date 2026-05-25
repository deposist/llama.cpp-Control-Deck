"""Configuration defaults and helpers for the local llama.cpp manager.

Run ``python config.py --help`` for a small diagnostic command-line reference.

Defaults can be overridden via environment variables:
- LLAMA_CPP_BINARY: path to llama-server binary
- LLAMA_CPP_CWD / LLAMA_CPP_WORKDIR: working directory for llama-server
- LLAMA_CPP_LIB_DIR: directory with llama.cpp shared libraries
- LLAMA_CPP_PYTHON: path to Python runtime
- LLAMA_CPP_MODELS_DIR: directory containing .gguf models
- LLAMA_CPP_SEARCH_ROOTS: extra deep-search roots separated by os.pathsep
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
LOG_DIR = APP_DIR / "logs"
RUNTIME_DIR = APP_DIR / "runtime"
RUNTIME_KEYS = (
    "python_path",
    "llama_server_binary",
    "llama_server_cwd",
    "llama_server_library_path",
)


def _expanded_path(value: str | Path | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(os.path.expandvars(os.path.expanduser(text)))


def _is_executable_file(path: str | Path | None) -> bool:
    item = _expanded_path(path)
    return bool(item and item.is_file() and os.access(item, os.X_OK))


def _is_existing_dir(path: str | Path | None) -> bool:
    item = _expanded_path(path)
    return bool(item and item.is_dir())


def _path_list_has_existing_dir(value: str | Path | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return any(_is_existing_dir(part) for part in text.split(os.pathsep) if part.strip())


def _dedupe_paths(paths: list[Path | str | None]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for raw in paths:
        path = _expanded_path(raw)
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _iter_sibling_venv_pythons() -> list[Path]:
    candidates: list[Path] = []
    roots = _dedupe_paths([APP_DIR, APP_DIR.parent])
    for root in roots:
        for venv_name in (".venv", "venv", "env"):
            candidates.extend(
                [
                    root / venv_name / "bin" / "python",
                    root / venv_name / "bin" / "python3",
                ]
            )
        try:
            children = sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name)
        except Exception:
            children = []
        for child in children:
            for venv_name in (".venv", "venv"):
                candidates.extend(
                    [
                        child / venv_name / "bin" / "python",
                        child / venv_name / "bin" / "python3",
                    ]
                )
    return candidates


def _walk_for_files(roots: list[Path], names: set[str], max_depth: int = 5) -> list[Path]:
    results: list[Path] = []
    skip_dirs = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "logs",
        "lost+found",
        "node_modules",
        "runtime",
    }
    for root in _dedupe_paths(roots):
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _exc: None):
            current = Path(dirpath)
            try:
                depth = len(current.relative_to(root).parts)
            except ValueError:
                depth = 0
            if depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [name for name in dirnames if name not in skip_dirs]
            for name in names:
                if name in filenames:
                    results.append(current / name)
    return results


def _has_llama_shared_libraries(path: str | Path | None) -> bool:
    directory = _expanded_path(path)
    if not directory or not directory.is_dir():
        return False
    return (directory / "libllama.so").exists() or any(directory.glob("libggml*.so"))


def _walk_for_library_dirs(roots: list[Path], max_depth: int = 5) -> list[Path]:
    results: list[Path] = []
    for file_path in _walk_for_files(roots, {"libllama.so", "libggml.so"}, max_depth=max_depth):
        parent = file_path.parent
        if _has_llama_shared_libraries(parent):
            results.append(parent)
    return _dedupe_paths(results)


def _candidate_roots() -> list[Path]:
    return _dedupe_paths(
        [
            APP_DIR,
            APP_DIR.parent,
            Path.cwd(),
            Path.home(),
        ]
    )


def _deep_runtime_roots() -> list[Path]:
    env_roots = [
        item
        for item in (os.environ.get("LLAMA_CPP_SEARCH_ROOTS") or "").split(os.pathsep)
        if item.strip()
    ]
    roots: list[Path | str | None] = [
        *env_roots,
        APP_DIR,
        APP_DIR / "llama.cpp",
        APP_DIR.parent / "llama.cpp",
        Path.cwd(),
        Path.cwd() / "llama.cpp",
        Path.cwd().parent / "llama.cpp",
        Path.home() / "llama.cpp",
    ]
    return _dedupe_paths(roots)


def runtime_value_is_usable(key: str, value: Any) -> bool:
    if key in {"python_path", "llama_server_binary"}:
        return _is_executable_file(value)
    if key == "llama_server_cwd":
        return _is_existing_dir(value)
    if key == "llama_server_library_path":
        return _path_list_has_existing_dir(value)
    return bool(str(value or "").strip())


def _detect_llama_server_binary(
    config: dict[str, Any] | None = None,
    *,
    prefer_existing: bool = True,
    deep_search: bool = False,
) -> Path:
    """Detect llama-server binary path.

    Priority:
    1. LLAMA_CPP_BINARY environment variable
    2. Existing config value, when requested and usable
    3. llama-server in PATH
    4. Common build locations relative to project/search roots
    5. Optional bounded search below the project directory
    6. Fallback: "llama-server" (assumed to be in PATH at runtime)
    """
    candidates: list[Path | str | None] = [os.environ.get("LLAMA_CPP_BINARY")]
    if prefer_existing and config:
        candidates.append(config.get("llama_server_binary"))

    which_path = shutil.which("llama-server")
    if which_path:
        candidates.append(which_path)

    roots = _candidate_roots()
    for root in roots:
        candidates.extend(
            [
                root / "llama.cpp" / "build-cuda" / "bin" / "llama-server",
                root / "llama.cpp" / "build" / "bin" / "llama-server",
                root / "build-cuda" / "bin" / "llama-server",
                root / "build" / "bin" / "llama-server",
                root / "bin" / "llama-server",
            ]
        )

    if deep_search:
        candidates.extend(_walk_for_files(_deep_runtime_roots(), {"llama-server"}, max_depth=5))

    if not prefer_existing and config:
        candidates.append(config.get("llama_server_binary"))

    for candidate in _dedupe_paths(candidates):
        if _is_executable_file(candidate):
            return candidate

    return Path("llama-server")


def _detect_python_runtime(
    config: dict[str, Any] | None = None,
    *,
    prefer_existing: bool = True,
    deep_search: bool = False,
) -> Path:
    """Detect Python runtime path.

    Priority:
    1. LLAMA_CPP_PYTHON environment variable
    2. Existing config value, when requested and usable
    3. Local/sibling virtual environments
    4. Current Python interpreter
    5. python3/python in PATH
    6. Optional bounded search below the project directory
    """
    candidates: list[Path | str | None] = [os.environ.get("LLAMA_CPP_PYTHON")]
    for venv_name in (".venv", "venv", "env"):
        candidates.extend(
            [
                APP_DIR / venv_name / "bin" / "python",
                APP_DIR / venv_name / "bin" / "python3",
            ]
        )
    if config:
        candidates.append(config.get("python_path"))
    candidates.append(sys.executable)
    candidates.extend([shutil.which("python3"), shutil.which("python")])
    candidates.extend(_iter_sibling_venv_pythons())
    if deep_search:
        versioned = f"python{sys.version_info.major}.{sys.version_info.minor}"
        candidates.extend(_walk_for_files([APP_DIR], {"python", "python3", versioned}, max_depth=5))

    for candidate in _dedupe_paths(candidates):
        if _is_executable_file(candidate):
            return candidate
    return Path(sys.executable)


def _detect_models_dir() -> str:
    """Detect models directory.

    Priority:
    1. LLAMA_CPP_MODELS_DIR environment variable
    2. ~/models if it exists
    3. Empty string (user must configure)
    """
    env_path = os.environ.get("LLAMA_CPP_MODELS_DIR")
    if env_path:
        return env_path

    home_models = Path.home() / "models"
    if home_models.exists():
        return str(home_models)

    return ""


def _detect_cwd(
    binary_path: Path,
    config: dict[str, Any] | None = None,
    *,
    prefer_existing: bool = True,
) -> str:
    env_path = os.environ.get("LLAMA_CPP_CWD") or os.environ.get("LLAMA_CPP_WORKDIR")
    candidates: list[Path | str | None] = [env_path]
    if prefer_existing and config:
        candidates.append(config.get("llama_server_cwd"))
    if binary_path and binary_path.parent and str(binary_path.parent) not in {".", ""}:
        candidates.append(binary_path.parent)
    if not prefer_existing and config:
        candidates.append(config.get("llama_server_cwd"))
    for candidate in _dedupe_paths(candidates):
        if candidate.is_dir():
            return str(candidate)
    parent = binary_path.parent if binary_path and str(binary_path.parent) not in {".", ""} else APP_DIR
    return str(parent if parent else APP_DIR)


def _detect_lib_dir(
    binary_path: Path,
    config: dict[str, Any] | None = None,
    *,
    prefer_existing: bool = True,
    deep_search: bool = False,
) -> str:
    """Detect llama.cpp library directory.

    Priority:
    1. LLAMA_CPP_LIB_DIR environment variable
    2. Existing config value, when requested and usable
    3. Directory containing llama-server binary when it has llama.cpp .so files
    4. Optional bounded search below the project directory
    5. Directory containing llama-server binary (if it's an absolute path)
    """
    candidates: list[Path | str | None] = [os.environ.get("LLAMA_CPP_LIB_DIR")]
    if prefer_existing and config:
        candidates.append(config.get("llama_server_library_path"))
    parent = binary_path.parent if binary_path else Path("")
    parent_is_inferable = str(parent) not in (".", "") and parent.is_absolute()
    if parent_is_inferable and _has_llama_shared_libraries(parent):
        candidates.append(parent)
    if deep_search:
        candidates.extend(_walk_for_library_dirs(_deep_runtime_roots(), max_depth=5))
    if parent_is_inferable:
        candidates.append(parent)
    if not prefer_existing and config:
        candidates.append(config.get("llama_server_library_path"))

    for candidate in _dedupe_paths(candidates):
        if candidate.is_dir():
            return str(candidate)
    # If parent is "." or non-absolute, lib dir cannot be reliably inferred
    if not parent_is_inferable:
        return ""
    return str(parent)


def detect_runtime_paths(
    config: dict[str, Any] | None = None,
    *,
    prefer_existing: bool = True,
    deep_search: bool = True,
) -> dict[str, str]:
    """Return best-effort runtime paths for Python and llama.cpp."""
    python_path = _detect_python_runtime(config, prefer_existing=prefer_existing, deep_search=deep_search)
    binary = _detect_llama_server_binary(config, prefer_existing=prefer_existing, deep_search=deep_search)
    cwd = _detect_cwd(binary, config, prefer_existing=prefer_existing)
    lib_dir = _detect_lib_dir(binary, config, prefer_existing=prefer_existing, deep_search=deep_search)
    return {
        "python_path": str(python_path),
        "llama_server_binary": str(binary),
        "llama_server_cwd": cwd,
        "llama_server_library_path": lib_dir,
    }


def apply_runtime_autodetect(
    config: dict[str, Any],
    *,
    override: bool = False,
    deep_search: bool = False,
) -> dict[str, str]:
    """Fill missing/stale runtime values in config and return detected values."""
    detected = detect_runtime_paths(config, prefer_existing=not override, deep_search=deep_search)
    for key in RUNTIME_KEYS:
        current = config.get(key)
        value = detected.get(key, "")
        if value and runtime_value_is_usable(key, value) and (override or not runtime_value_is_usable(key, current)):
            config[key] = value
    return detected


LLAMA_SERVER_BINARY = _detect_llama_server_binary(deep_search=False)
LLAMA_SERVER_DIR = LLAMA_SERVER_BINARY.parent
VENV_PYTHON = _detect_python_runtime(deep_search=False)
DEFAULT_MODELS_DIR = _detect_models_dir()
DEFAULT_CWD = _detect_cwd(LLAMA_SERVER_BINARY)
DEFAULT_LIB_DIR = _detect_lib_dir(LLAMA_SERVER_BINARY, deep_search=False)


PROFILE_ORDER = ["chat", "embeddings", "rerank", "multimodal", "router"]


def _first_existing(paths: list[str]) -> str:
    for path in paths:
        if path and Path(path).exists():
            return path
    return ""


def _scan_models_dir(models_dir: str, patterns: list[str]) -> str:
    """Scan models directory for first matching .gguf file."""
    if not models_dir:
        return ""
    base = Path(models_dir)
    if not base.exists():
        return ""
    for pattern in patterns:
        matches = list(base.rglob(f"*{pattern}*.gguf"))
        if matches:
            return str(matches[0])
    return ""


DEFAULT_CHAT_MODEL = _scan_models_dir(
    DEFAULT_MODELS_DIR,
    ["llama", "qwen", "gemma", "mistral", "gigachat"],
)

DEFAULT_EMBED_MODEL = _scan_models_dir(
    DEFAULT_MODELS_DIR,
    ["bge", "nomic", "gte"],
)

DEFAULT_MMPROJ = _scan_models_dir(
    DEFAULT_MODELS_DIR,
    ["mmproj"],
)


COMMON_PROFILE: dict[str, Any] = {
    "profile_type": "chat",
    "model_path": DEFAULT_CHAT_MODEL,
    "mmproj_path": "",
    "host": "127.0.0.1",
    "port": 8081,
    "alias": "local-llama",
    "api_key": "",
    "n_ctx": 8192,
    "n_threads": 6,
    "n_threads_batch": "",
    "n_gpu_layers": "all",
    "main_gpu": 0,
    "split_mode": "layer",
    "tensor_split": "",
    "n_batch": 2048,
    "n_ubatch": 512,
    "flash_attn": "auto",
    "use_mmap": True,
    "use_mlock": False,
    "webui": True,
    "cont_batching": True,
    "metrics": False,
    "slots": True,
    "extra_args": "",
    "models_dir": DEFAULT_MODELS_DIR,
    "models_preset": "",
    "models_max": 2,
    "models_autoload": True,
}


def _profile(**overrides: Any) -> dict[str, Any]:
    profile = deepcopy(COMMON_PROFILE)
    profile.update(overrides)
    return profile


DEFAULT_INSTANCES: list[dict[str, Any]] = [
    {
        "id": "chat-8081",
        "name": "Chat 8081",
        "enabled": True,
        "profile": "chat",
        "model_path": DEFAULT_CHAT_MODEL,
        "host": "127.0.0.1",
        "port": 8081,
        "alias": "local-llama",
        "api_key": "",
        "extra_args": "",
    },
    {
        "id": "embeddings-8082",
        "name": "Embeddings 8082",
        "enabled": False,
        "profile": "embeddings",
        "model_path": DEFAULT_EMBED_MODEL or DEFAULT_CHAT_MODEL,
        "host": "127.0.0.1",
        "port": 8082,
        "alias": "local-embeddings",
        "api_key": "",
        "n_ctx": 8192,
        "n_batch": 8192,
        "n_ubatch": 8192,
        "n_gpu_layers": "all",
        "split_mode": "none",
        "flash_attn": "auto",
        "extra_args": "--pooling cls",
    },
    {
        "id": "rerank-8083",
        "name": "Rerank 8083",
        "enabled": False,
        "profile": "rerank",
        "model_path": DEFAULT_EMBED_MODEL or DEFAULT_CHAT_MODEL,
        "host": "127.0.0.1",
        "port": 8083,
        "alias": "local-rerank",
        "api_key": "",
        "extra_args": "",
    },
]


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "python_path": str(VENV_PYTHON),
    "llama_server_binary": str(LLAMA_SERVER_BINARY),
    "llama_server_cwd": str(DEFAULT_CWD),
    "llama_server_library_path": str(DEFAULT_LIB_DIR),
    "llama_cpp_release_backend": "auto",
    "active_profile": "chat",
    "profiles": {
        "chat": _profile(profile_type="chat", port=8081),
        "embeddings": _profile(
            profile_type="embeddings",
            model_path=DEFAULT_EMBED_MODEL or DEFAULT_CHAT_MODEL,
            alias="local-embeddings",
            port=8082,
            n_ctx=8192,
            n_batch=8192,
            n_ubatch=8192,
            n_gpu_layers="all",
            split_mode="none",
            extra_args="--pooling cls",
        ),
        "rerank": _profile(
            profile_type="rerank",
            model_path=DEFAULT_EMBED_MODEL or DEFAULT_CHAT_MODEL,
            alias="local-rerank",
            port=8083,
        ),
        "multimodal": _profile(
            profile_type="multimodal",
            port=8084,
            mmproj_path=DEFAULT_MMPROJ,
            alias="local-vision",
        ),
        "router": _profile(
            profile_type="router",
            model_path="",
            alias="local-router",
            port=8085,
            models_dir=DEFAULT_MODELS_DIR,
            models_preset="",
            models_max=2,
            models_autoload=True,
        ),
    },
    "instances": DEFAULT_INSTANCES,
    "ollama_proxy": {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 11435,
        "target_base_url": "",
        "target_api_key": "",
        "model": "",
    },
}


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def merge_defaults(value: Any, default: Any) -> Any:
    if isinstance(default, dict):
        merged = deepcopy(default)
        if isinstance(value, dict):
            for key, item in value.items():
                merged[key] = merge_defaults(item, default.get(key))
        return merged
    if value is None:
        return deepcopy(default)
    return value


def load_config() -> dict[str, Any]:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        config = deepcopy(DEFAULT_CONFIG)
        save_config(config)
        return config

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
    except Exception:
        loaded = {}

    config = merge_defaults(loaded, DEFAULT_CONFIG)
    profiles = config.setdefault("profiles", {})
    for name in PROFILE_ORDER:
        profiles[name] = merge_defaults(profiles.get(name), DEFAULT_CONFIG["profiles"][name])
    apply_runtime_autodetect(config, override=False, deep_search=False)
    return config


def save_config(config: dict[str, Any]) -> None:
    ensure_dirs()
    tmp_path = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
    os.replace(tmp_path, CONFIG_PATH)


def active_profile(config: dict[str, Any]) -> dict[str, Any]:
    name = str(config.get("active_profile") or "chat")
    return get_profile(config, name)


def get_profile(config: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    profile_name = name or str(config.get("active_profile") or "chat")
    profiles = config.setdefault("profiles", {})
    if profile_name not in profiles:
        profile_name = "chat"
    return profiles[profile_name]


def profile_display_name(name: str) -> str:
    labels = {
        "chat": "Chat / OpenAI API",
        "embeddings": "Embeddings",
        "rerank": "Rerank",
        "multimodal": "Multimodal",
        "router": "Router / multi-model",
    }
    return labels.get(name, name)


def model_name_from_path(path: str) -> str:
    if not path:
        return "local-llama"
    return Path(path).stem or "local-llama"


def profile_model_name(profile: dict[str, Any]) -> str:
    alias = str(profile.get("alias") or "").strip()
    if alias:
        return alias
    return model_name_from_path(str(profile.get("model_path") or ""))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show llama.cpp Control Deck configuration information.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dump", action="store_true", help="print the merged config.json as JSON")
    parser.add_argument("--paths", action="store_true", help="print important filesystem paths")
    parser.add_argument("--profiles", action="store_true", help="print configured profile names and model aliases")
    parser.add_argument("--detect-runtime", action="store_true", help="search and print runtime paths")
    parser.add_argument(
        "--apply-runtime",
        action="store_true",
        help="search runtime paths, update config.json, and print the result",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config()

    if args.detect_runtime or args.apply_runtime:
        detected = detect_runtime_paths(config, prefer_existing=False, deep_search=True)
        if args.apply_runtime:
            apply_runtime_autodetect(config, override=True, deep_search=True)
            save_config(config)
            detected = {key: str(config.get(key) or "") for key in RUNTIME_KEYS}
        print(json.dumps(detected, ensure_ascii=False, indent=2))
        return 0

    if args.dump:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    show_paths = args.paths or not args.profiles
    show_profiles = args.profiles or not args.paths

    if show_paths:
        print(f"app_dir: {APP_DIR}")
        print(f"config_path: {CONFIG_PATH}")
        print(f"log_dir: {LOG_DIR}")
        print(f"runtime_dir: {RUNTIME_DIR}")
        print(f"python_path: {config.get('python_path')}")
        print(f"llama_server_binary: {config.get('llama_server_binary')}")
        print(f"llama_server_cwd: {config.get('llama_server_cwd')}")
        print(f"llama_server_library_path: {config.get('llama_server_library_path')}")

    if show_paths and show_profiles:
        print()

    if show_profiles:
        print(f"active_profile: {config.get('active_profile')}")
        profiles = config.get("profiles") or {}
        for name in PROFILE_ORDER:
            profile = profiles.get(name) or {}
            print(
                f"{name}: {profile_display_name(name)} | "
                f"alias={profile_model_name(profile)} | "
                f"port={profile.get('port', '')} | "
                f"model={profile.get('model_path', '')}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
