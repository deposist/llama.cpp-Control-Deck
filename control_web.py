"""Local FastAPI control panel for llama.cpp Control Deck."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import shutil
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import llama_cpp_release
from config import (
    APP_DIR,
    LOG_DIR,
    PROFILE_ORDER,
    RUNTIME_KEYS,
    _has_llama_shared_libraries,
    active_profile,
    apply_runtime_autodetect,
    get_profile,
    load_config,
    save_config,
)
from llama_server_manager import LlamaServerManager, ProcessResult, tail_file

TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
INDEX_TEMPLATE = TEMPLATES_DIR / "index.html"
STATE_PLACEHOLDER = "__CONTROL_DECK_INITIAL_STATE__"
SUPPORTED_LANGUAGES = {"ru", "en"}
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8765
PATH_KINDS = {"python", "llama_server", "directory", "library_dir", "model", "mmproj", "preset", "file"}
PRESET_SUFFIXES = {".json", ".yaml", ".yml"}
PYTHON_NAME_RE = re.compile(r"^python(?:\d+(?:\.\d+)?)?(?:\.exe)?$")
LLAMA_SERVER_NAMES = {"llama-server", "llama-server.exe"}

REQUIRED_I18N_KEYS = [
    "app_title",
    "advanced",
    "auto_detect",
    "beginner",
    "copy",
    "devices",
    "download",
    "download_status",
    "diagnostics",
    "language",
    "logs",
    "model",
    "openai_url",
    "proxy",
    "refresh",
    "restart",
    "save",
    "server",
    "start",
    "status",
    "stop",
    "runtime_updates",
    "services",
    "add_service",
    "edit",
    "duplicate",
    "delete",
    "command_preview",
]

I18N: dict[str, dict[str, str]] = {
    "ru": {
        "app_title": "llama.cpp Control Deck",
        "advanced": "Расширенные настройки",
        "auto_detect": "Найти окружение",
        "beginner": "Быстрый запуск",
        "copy": "Копировать",
        "devices": "GPU / устройства",
        "download": "Скачать llama-server",
        "download_status": "Статус скачивания",
        "diagnostics": "Диагностика",
        "language": "Язык",
        "logs": "Логи",
        "model": "Модель GGUF",
        "openai_url": "OpenAI URL",
        "proxy": "Ollama proxy",
        "refresh": "Обновить",
        "restart": "Перезапустить",
        "save": "Сохранить",
        "server": "Сервер",
        "start": "Запустить",
        "status": "Статус",
        "stop": "Остановить",
        "runtime_updates": "Окружение и обновления",
        "services": "Сервисы",
        "add_service": "Добавить сервис",
        "edit": "Редактировать",
        "duplicate": "Дублировать",
        "delete": "Удалить",
        "command_preview": "Команда запуска",
    },
    "en": {
        "app_title": "llama.cpp Control Deck",
        "advanced": "Advanced settings",
        "auto_detect": "Auto-detect runtime",
        "beginner": "Quick start",
        "copy": "Copy",
        "devices": "GPU / devices",
        "download": "Download llama-server",
        "download_status": "Download status",
        "diagnostics": "Diagnostics",
        "language": "Language",
        "logs": "Logs",
        "model": "GGUF model",
        "openai_url": "OpenAI URL",
        "proxy": "Ollama proxy",
        "refresh": "Refresh",
        "restart": "Restart",
        "save": "Save",
        "server": "Server",
        "start": "Start",
        "status": "Status",
        "stop": "Stop",
        "runtime_updates": "Runtime & updates",
        "services": "Services",
        "add_service": "Add service",
        "edit": "Edit",
        "duplicate": "Duplicate",
        "delete": "Delete",
        "command_preview": "Command preview",
    },
}

INSTANCE_EDIT_KEYS = {
    "id",
    "name",
    "enabled",
    "profile",
    "model_path",
    "mmproj_path",
    "models_dir",
    "models_preset",
    "host",
    "port",
    "alias",
    "api_key",
    "n_ctx",
    "n_threads",
    "n_threads_batch",
    "n_gpu_layers",
    "main_gpu",
    "split_mode",
    "tensor_split",
    "n_batch",
    "n_ubatch",
    "flash_attn",
    "models_max",
    "extra_args",
    "use_mmap",
    "use_mlock",
    "webui",
    "cont_batching",
    "metrics",
    "slots",
    "models_autoload",
}

RESTART_REQUIRED_KEYS = {
    "profile",
    "model_path",
    "mmproj_path",
    "models_dir",
    "models_preset",
    "host",
    "port",
    "api_key",
    "n_ctx",
    "n_threads",
    "n_threads_batch",
    "n_gpu_layers",
    "main_gpu",
    "split_mode",
    "tensor_split",
    "n_batch",
    "n_ubatch",
    "flash_attn",
    "models_max",
    "extra_args",
    "use_mmap",
    "use_mlock",
    "webui",
    "cont_batching",
    "metrics",
    "slots",
    "models_autoload",
}

_DOWNLOAD_LOCK = threading.Lock()
_DOWNLOAD_JOB: dict[str, Any] = {
    "status": "idle",
    "message": "No download running.",
    "started_at": None,
    "finished_at": None,
    "lines": [],
    "result": None,
    "error": "",
}


class ConfigPatch(BaseModel):
    ui_language: str | None = None
    active_profile: str | None = None
    runtime: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    proxy: dict[str, Any] | None = None


class InstancePayload(BaseModel):
    instance: dict[str, Any]
    start: bool = False


class PathValidatePayload(BaseModel):
    path: str
    kind: str


class _ProgressWriter:
    def __init__(self, limit: int = 120):
        self.limit = limit
        self._buffer = ""

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                _download_log(line)
        return len(text)

    def flush(self) -> None:
        line = self._buffer.strip()
        if line:
            _download_log(line)
            self._buffer = ""


def _download_log(message: str) -> None:
    with _DOWNLOAD_LOCK:
        _DOWNLOAD_JOB["message"] = message
        lines = list(_DOWNLOAD_JOB.get("lines") or [])
        lines.append(message)
        _DOWNLOAD_JOB["lines"] = lines[-120:]


def _set_download_job(**updates: Any) -> None:
    with _DOWNLOAD_LOCK:
        _DOWNLOAD_JOB.update(updates)


def download_job_status() -> dict[str, Any]:
    with _DOWNLOAD_LOCK:
        return deepcopy(_DOWNLOAD_JOB)


def _manager() -> LlamaServerManager:
    return LlamaServerManager(load_config())


def _language(config: dict[str, Any]) -> str:
    language = str(config.get("ui_language") or "ru").lower()
    return language if language in SUPPORTED_LANGUAGES else "ru"


def _coerce_port(value: Any, default: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default


def _connect_host(host: str) -> str:
    host = (host or "127.0.0.1").strip()
    return "127.0.0.1" if host in {"0.0.0.0", "::", "*"} else host


def _result_payload(result: ProcessResult, next_action: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": result.ok,
        "message": result.message,
        "next_action": next_action,
    }
    details = {
        "pid": result.pid,
        "log_path": result.log_path,
        "command": result.command,
    }
    payload["details"] = {key: value for key, value in details.items() if value}
    return payload


def _friendly_status(kind: str, status: dict[str, Any], language: str) -> str:
    if language == "en":
        if status.get("running") and status.get("healthy"):
            return f"{kind} is ready"
        if status.get("running"):
            return f"{kind} is starting or not healthy yet"
        return f"{kind} is stopped"
    if status.get("running") and status.get("healthy"):
        return f"{kind} готов к работе"
    if status.get("running"):
        return f"{kind} запускается или пока не отвечает"
    return f"{kind} остановлен"


def _path_exists(value: Any, directory: bool = False) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    path = Path(text).expanduser()
    return path.is_dir() if directory else path.exists()


def _expanded_user_path(value: Any) -> Path:
    return Path(str(value or "")).expanduser()


def _existing_directory(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = _expanded_user_path(text)
    if path.is_file():
        path = path.parent
    return path.resolve() if path.is_dir() else None


def _dedupe_existing_dirs(paths: list[Any]) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()
    for value in paths:
        directory = _existing_directory(value)
        if not directory:
            continue
        key = str(directory)
        if key in seen:
            continue
        seen.add(key)
        results.append(directory)
    return results


def _path_roots(config: dict[str, Any]) -> list[dict[str, str]]:
    profile = active_profile(config)
    roots: list[tuple[str, Any]] = [
        ("Project", APP_DIR),
        ("Project parent", APP_DIR.parent),
        ("Home", Path.home()),
    ]
    for label, key in [
        ("Python directory", "python_path"),
        ("llama-server directory", "llama_server_binary"),
        ("Working directory", "llama_server_cwd"),
        ("LD library path", "llama_server_library_path"),
    ]:
        roots.append((label, config.get(key)))
    for label, key in [
        ("Current model directory", "model_path"),
        ("Current models directory", "models_dir"),
        ("Current preset directory", "models_preset"),
    ]:
        roots.append((label, profile.get(key)))
    for instance in config.get("instances") or []:
        name = str(instance.get("name") or instance.get("id") or "Service")
        for key in ["model_path", "mmproj_path", "models_dir", "models_preset"]:
            roots.append((f"{name} {key}", instance.get(key)))
    for item in (os.environ.get("LLAMA_CPP_SEARCH_ROOTS") or "").split(os.pathsep):
        if item.strip():
            roots.append(("Search root", item))

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for label, value in roots:
        directory = _existing_directory(value)
        if not directory:
            continue
        path = str(directory)
        if path in seen:
            continue
        seen.add(path)
        result.append({"label": label, "path": path})
    return result


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _selectable_for_kind(path: Path, kind: str) -> bool:
    if kind not in PATH_KINDS:
        return False
    if kind in {"directory", "library_dir"}:
        return path.is_dir()
    if path.is_dir():
        return False
    suffix = path.suffix.lower()
    name = path.name.lower()
    if kind == "python":
        return _is_executable(path) and bool(PYTHON_NAME_RE.match(name))
    if kind == "llama_server":
        return _is_executable(path) and name in LLAMA_SERVER_NAMES
    if kind in {"model", "mmproj"}:
        return path.is_file() and suffix == ".gguf"
    if kind == "preset":
        return path.is_file() and suffix in PRESET_SUFFIXES
    if kind == "file":
        return path.is_file()
    return False


def _entry_allowed(path: Path, kind: str) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return True
    if kind in {"directory", "library_dir"}:
        return False
    return _selectable_for_kind(path, kind)


def _path_entry(path: Path, kind: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "type": "directory" if path.is_dir() else "file",
        "selectable": _selectable_for_kind(path, kind),
    }
    if path.is_file():
        with contextlib.suppress(OSError):
            entry["size"] = path.stat().st_size
        entry["executable"] = _is_executable(path)
    if path.is_dir() and kind == "library_dir":
        entry["has_llama_libs"] = _has_llama_shared_libraries(path)
    return entry


def list_path_entries(path: Any, kind: str) -> dict[str, Any]:
    if kind not in PATH_KINDS:
        raise HTTPException(status_code=400, detail="Unsupported path picker kind")
    directory = _expanded_user_path(path)
    if directory.is_file():
        directory = directory.parent
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    directory = directory.resolve()
    entries: list[dict[str, Any]] = []
    with os.scandir(directory) as iterator:
        for item in iterator:
            entry_path = Path(item.path)
            if not _entry_allowed(entry_path, kind):
                continue
            entries.append(_path_entry(entry_path, kind))
    entries.sort(key=lambda entry: (entry["type"] != "directory", entry["name"].lower()))
    parent = directory.parent if directory.parent != directory else None
    return {
        "path": str(directory),
        "parent": str(parent) if parent else "",
        "entries": entries,
    }


def validate_path_choice(path: Any, kind: str) -> dict[str, Any]:
    if kind not in PATH_KINDS:
        return {"ok": False, "message": "Unknown path type.", "details": {"kind": kind}}
    text = str(path or "").strip()
    if not text:
        return {"ok": False, "message": "Path is empty.", "details": {"path": text, "kind": kind}}
    candidate = _expanded_user_path(text)
    details: dict[str, Any] = {"path": str(candidate), "kind": kind}
    if not candidate.exists():
        return {"ok": False, "message": "Path does not exist.", "details": details}
    if kind == "library_dir":
        if not candidate.is_dir():
            return {"ok": False, "message": "Existing folder is required.", "details": details}
        details["has_llama_libs"] = _has_llama_shared_libraries(candidate)
        return {"ok": True, "message": "Path is valid.", "details": details}
    if kind == "directory":
        if candidate.is_dir():
            return {"ok": True, "message": "Path is valid.", "details": details}
        return {"ok": False, "message": "Existing folder is required.", "details": details}
    if kind == "python" and not _selectable_for_kind(candidate, kind):
        return {"ok": False, "message": "Executable Python path is required.", "details": details}
    if kind == "llama_server" and not _selectable_for_kind(candidate, kind):
        return {"ok": False, "message": "Executable llama-server path is required.", "details": details}
    if kind in {"model", "mmproj"} and not _selectable_for_kind(candidate, kind):
        return {"ok": False, "message": "A .gguf file is required.", "details": details}
    if kind == "preset" and not _selectable_for_kind(candidate, kind):
        return {"ok": False, "message": "A .json, .yaml, or .yml file is required.", "details": details}
    if kind == "file" and not candidate.is_file():
        return {"ok": False, "message": "Existing file is required.", "details": details}
    return {"ok": True, "message": "Path is valid.", "details": details}


def validate_config(config: dict[str, Any]) -> list[dict[str, str]]:
    """Return user-facing preflight warnings without mutating config."""
    warnings: list[dict[str, str]] = []
    profile = active_profile(config)
    profile_type = str(profile.get("profile_type") or config.get("active_profile") or "chat")

    binary = str(config.get("llama_server_binary") or "").strip()
    if not binary:
        warnings.append(
            {
                "code": "missing_binary",
                "message": "llama-server path is empty.",
                "next_action": "Run Auto-detect runtime or download llama-server.",
            }
        )
    elif not Path(binary).expanduser().exists() and not shutil.which(binary):
        warnings.append(
            {
                "code": "missing_binary",
                "message": f"llama-server not found: {binary}",
                "next_action": "Run Auto-detect runtime or select the correct binary.",
            }
        )

    model_path = str(profile.get("model_path") or "").strip()
    if profile_type != "router":
        if not model_path:
            warnings.append(
                {
                    "code": "missing_model",
                    "message": "Model .gguf is not selected.",
                    "next_action": "Set the GGUF model path, then save.",
                }
            )
        elif not Path(model_path).expanduser().exists():
            warnings.append(
                {
                    "code": "missing_model",
                    "message": f"Model file not found: {model_path}",
                    "next_action": "Select an existing .gguf model file.",
                }
            )

    for key in ["llama_server_cwd", "llama_server_library_path"]:
        value = str(config.get(key) or "").strip()
        if value and not _path_exists(value, directory=True):
            warnings.append(
                {
                    "code": f"missing_{key}",
                    "message": f"{key} directory does not exist: {value}",
                    "next_action": "Run Auto-detect runtime or select an existing directory.",
                }
            )

    host = str(profile.get("host") or "127.0.0.1")
    port = profile.get("port") or 8081
    try:
        port_number = int(port)
        if port_number < 1 or port_number > 65535:
            raise ValueError
    except (TypeError, ValueError):
        warnings.append(
            {
                "code": "invalid_port",
                "message": f"Port is invalid: {port}",
                "next_action": "Use a number from 1 to 65535.",
            }
        )
        port_number = 8081

    numeric_fields = [
        "n_ctx",
        "n_threads",
        "n_threads_batch",
        "main_gpu",
        "n_batch",
        "n_ubatch",
        "models_max",
    ]
    for key in numeric_fields:
        value = profile.get(key)
        if value in {None, ""}:
            continue
        try:
            int(value)
        except (TypeError, ValueError):
            warnings.append(
                {
                    "code": f"invalid_{key}",
                    "message": f"{key} must be a number.",
                    "next_action": "Fix the value in Advanced settings.",
                }
            )

    gpu_layers = profile.get("n_gpu_layers")
    if gpu_layers not in {None, "", "all"}:
        try:
            int(gpu_layers)
        except (TypeError, ValueError):
            warnings.append(
                {
                    "code": "invalid_n_gpu_layers",
                    "message": "GPU layers must be a number or 'all'.",
                    "next_action": "Use 'all' or a numeric layer count.",
                }
            )

    manager = _manager()
    server = manager.server_status()
    server_owns_port = (
        server.get("running")
        and str(server.get("host") or host) == host
        and int(server.get("port") or 0) == port_number
    )
    owner = None if server_owns_port else manager.port_owner(host, port_number)
    if owner:
        warnings.append(
            {
                "code": "busy_port",
                "message": f"Port {port_number} is busy.",
                "next_action": "Choose another port or stop the process that uses it.",
            }
        )
    return warnings


def _safe_instance_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "_.-" else "-" for ch in value.strip().lower())
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "service"


def _instance_id(instance: dict[str, Any]) -> str:
    raw = str(instance.get("id") or instance.get("name") or "").strip()
    if raw:
        return raw
    return f"{instance.get('profile') or 'chat'}-{instance.get('port') or '8081'}"


def _instance_index(config: dict[str, Any], instance_id: str) -> int | None:
    for index, instance in enumerate(config.get("instances") or []):
        if _instance_id(instance) == instance_id:
            return index
        fallback = f"{instance.get('profile') or 'chat'}-{instance.get('port') or '8081'}"
        if fallback == instance_id:
            return index
    return None


def _next_free_port(config: dict[str, Any], start: int = 8081) -> int:
    used = set()
    manager = LlamaServerManager(config)
    for instance in config.get("instances") or []:
        try:
            used.add(int(instance.get("port")))
        except (TypeError, ValueError):
            pass
    for profile in (config.get("profiles") or {}).values():
        try:
            used.add(int(profile.get("port")))
        except (TypeError, ValueError):
            pass
    for port in range(start, 65536):
        if port in used:
            continue
        if not manager.port_owner("127.0.0.1", port):
            return port
    return start


def _service_defaults(config: dict[str, Any], profile_name: str = "chat") -> dict[str, Any]:
    profile_name = profile_name if profile_name in PROFILE_ORDER else "chat"
    profile = deepcopy(get_profile(config, profile_name))
    port = _next_free_port(config, _coerce_port(profile.get("port"), 8081))
    service_id = _unique_instance_id(config, f"{profile_name}-{port}")
    name = f"{profile_name.capitalize()} {port}"
    defaults = {key: profile.get(key) for key in INSTANCE_EDIT_KEYS if key in profile}
    defaults.update(
        {
            "id": service_id,
            "name": name,
            "enabled": True,
            "profile": profile_name,
            "host": profile.get("host") or "127.0.0.1",
            "port": port,
            "alias": profile.get("alias") or f"local-{profile_name}",
        }
    )
    return _clean_instance(defaults)


def _unique_instance_id(config: dict[str, Any], base: str) -> str:
    existing = {_instance_id(instance) for instance in config.get("instances") or []}
    safe = _safe_instance_id(base)
    if safe not in existing:
        return safe
    suffix = 2
    while f"{safe}-{suffix}" in existing:
        suffix += 1
    return f"{safe}-{suffix}"


def _clean_instance(instance: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in instance.items() if key in INSTANCE_EDIT_KEYS}
    cleaned["id"] = _safe_instance_id(str(cleaned.get("id") or cleaned.get("name") or "service"))
    cleaned["name"] = str(cleaned.get("name") or cleaned["id"]).strip()
    cleaned["profile"] = str(cleaned.get("profile") or "chat").strip() or "chat"
    cleaned["enabled"] = bool(cleaned.get("enabled", True))
    for key in [
        "use_mmap",
        "use_mlock",
        "webui",
        "cont_batching",
        "metrics",
        "slots",
        "models_autoload",
    ]:
        if key in cleaned:
            cleaned[key] = bool(cleaned[key])
    return cleaned


def _port_owner_is_self(
    config: dict[str, Any],
    instance_id: str | None,
    host: str,
    port: int,
) -> bool:
    if not instance_id:
        return False
    status = LlamaServerManager(config).instance_status({"id": instance_id, "host": host, "port": port})
    return bool(status.get("running")) and int(status.get("port") or 0) == port


def validate_instance(
    config: dict[str, Any],
    instance: dict[str, Any],
    original_id: str | None = None,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    cleaned = _clean_instance(instance)
    instance_id = cleaned.get("id", "")
    profile_name = str(cleaned.get("profile") or "")

    if not cleaned.get("name"):
        warnings.append({"code": "missing_name", "message": "Service name is required.", "next_action": "Enter a name."})
    if profile_name not in PROFILE_ORDER:
        warnings.append(
            {
                "code": "invalid_profile",
                "message": f"Unknown service type: {profile_name}",
                "next_action": "Choose a supported profile.",
            }
        )

    existing_ids = {_instance_id(item) for item in config.get("instances") or []}
    if instance_id in existing_ids and instance_id != original_id:
        warnings.append(
            {
                "code": "duplicate_id",
                "message": f"Service id already exists: {instance_id}",
                "next_action": "Use a different id or duplicate the service.",
            }
        )

    host = str(cleaned.get("host") or "127.0.0.1")
    try:
        port = int(cleaned.get("port"))
        if port < 1 or port > 65535:
            raise ValueError
    except (TypeError, ValueError):
        warnings.append(
            {
                "code": "invalid_port",
                "message": f"Port is invalid: {cleaned.get('port')}",
                "next_action": "Use a number from 1 to 65535.",
            }
        )
        port = 0

    if port:
        owner = LlamaServerManager(config).port_owner(host, port)
        if owner and not _port_owner_is_self(config, original_id, host, port):
            warnings.append(
                {
                    "code": "busy_port",
                    "message": f"Port {port} is busy.",
                    "next_action": "Choose another port or stop the process that uses it.",
                }
            )

    model_path = str(cleaned.get("model_path") or "").strip()
    if profile_name != "router":
        if not model_path:
            warnings.append(
                {
                    "code": "missing_model",
                    "message": "Model .gguf is not selected.",
                    "next_action": "Set an existing GGUF model path.",
                }
            )
        elif not Path(model_path).expanduser().exists():
            warnings.append(
                {
                    "code": "missing_model",
                    "message": f"Model file not found: {model_path}",
                    "next_action": "Select an existing .gguf model.",
                }
            )
    elif not any(str(cleaned.get(key) or "").strip() for key in ["model_path", "models_dir", "models_preset"]):
        warnings.append(
            {
                "code": "missing_router_source",
                "message": "Router needs model, models directory, or models preset.",
                "next_action": "Set at least one router model source.",
            }
        )

    mmproj = str(cleaned.get("mmproj_path") or "").strip()
    if profile_name == "multimodal" and mmproj and not Path(mmproj).expanduser().exists():
        warnings.append(
            {
                "code": "missing_mmproj",
                "message": f"MMProj file not found: {mmproj}",
                "next_action": "Select an existing MMProj file or leave it empty.",
            }
        )

    for key in ["n_ctx", "n_threads", "n_threads_batch", "main_gpu", "n_batch", "n_ubatch", "models_max"]:
        value = cleaned.get(key)
        if value in {None, ""}:
            continue
        try:
            int(value)
        except (TypeError, ValueError):
            warnings.append(
                {
                    "code": f"invalid_{key}",
                    "message": f"{key} must be a number.",
                    "next_action": "Fix the value or leave it empty.",
                }
            )

    gpu_layers = cleaned.get("n_gpu_layers")
    if gpu_layers not in {None, "", "all", "-1", -1}:
        try:
            int(gpu_layers)
        except (TypeError, ValueError):
            warnings.append(
                {
                    "code": "invalid_n_gpu_layers",
                    "message": "GPU layers must be a number, 'all', or -1.",
                    "next_action": "Use 'all', -1, or a numeric layer count.",
                }
            )

    try:
        shlex.split(str(cleaned.get("extra_args") or ""))
    except ValueError as exc:
        warnings.append(
            {
                "code": "invalid_extra_args",
                "message": f"Extra args are invalid: {exc}",
                "next_action": "Fix quotes or remove extra args.",
            }
        )
    return warnings


def _instance_changed_requires_restart(old: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    if not old:
        return False
    return any(str(old.get(key, "")) != str(new.get(key, "")) for key in RESTART_REQUIRED_KEYS)


def _service_details(config: dict[str, Any], instance: dict[str, Any]) -> dict[str, Any]:
    manager = LlamaServerManager(config)
    status = manager.instance_status(instance)
    command: list[str] = []
    command_error = ""
    try:
        command = manager.build_server_command(
            str(instance.get("profile") or "chat"),
            {key: value for key, value in instance.items() if key in INSTANCE_EDIT_KEYS},
        )
    except Exception as exc:
        command_error = str(exc)
    return {
        "instance": deepcopy(instance),
        "status": status,
        "command": command,
        "command_error": command_error,
        "validation": validate_instance(config, instance, _instance_id(instance)),
    }


def _public_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "ui_language": _language(config),
        "active_profile": config.get("active_profile"),
        "runtime": {key: config.get(key, "") for key in RUNTIME_KEYS},
        "llama_cpp_release_backend": config.get("llama_cpp_release_backend", "auto"),
        "profile": deepcopy(active_profile(config)),
        "profiles": deepcopy(config.get("profiles") or {}),
        "profile_order": list(PROFILE_ORDER),
        "instances": deepcopy(config.get("instances") or []),
        "proxy": deepcopy(config.get("ollama_proxy") or {}),
    }


def build_state() -> dict[str, Any]:
    config = load_config()
    manager = LlamaServerManager(config)
    language = _language(config)
    server = manager.server_status()
    proxy = manager.proxy_status()
    return {
        "config": _public_config(config),
        "i18n": I18N[language],
        "i18n_all": I18N,
        "server": server,
        "proxy": proxy,
        "instances": manager.instances_status(),
        "friendly": {
            "server": _friendly_status("Server", server, language),
            "proxy": _friendly_status("Proxy", proxy, language),
        },
        "validation": validate_config(config),
        "urls": {
            "openai": server.get("openai_url"),
            "ollama": proxy.get("url"),
        },
        "download": download_job_status(),
    }


def _run_release_download(backend: str) -> None:
    _set_download_job(
        status="running",
        message="Starting llama-server download.",
        started_at=time.time(),
        finished_at=None,
        lines=["Starting llama-server download."],
        result=None,
        error="",
    )
    writer = _ProgressWriter()
    try:
        with contextlib.redirect_stdout(writer):
            result = llama_cpp_release.install_latest_release(backend=backend)
        writer.flush()
        config = load_config()
        config["llama_server_binary"] = str(result.get("binary_path") or config.get("llama_server_binary") or "")
        config["llama_server_cwd"] = str(result.get("install_dir") or config.get("llama_server_cwd") or "")
        config["llama_server_library_path"] = str(
            result.get("library_path") or config.get("llama_server_library_path") or ""
        )
        save_config(config)
        _set_download_job(
            status="succeeded",
            message="llama-server downloaded and runtime paths updated.",
            finished_at=time.time(),
            result=result,
        )
        _download_log("llama-server downloaded and runtime paths updated.")
    except Exception as exc:
        _set_download_job(
            status="failed",
            message=str(exc),
            finished_at=time.time(),
            error=str(exc),
        )
        _download_log(f"Failed: {exc}")


def _merge_config_patch(config: dict[str, Any], patch: ConfigPatch) -> dict[str, Any]:
    if patch.ui_language is not None:
        language = patch.ui_language.lower()
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=400, detail="Unsupported ui_language")
        config["ui_language"] = language

    if patch.active_profile is not None:
        if patch.active_profile not in (config.get("profiles") or {}):
            raise HTTPException(status_code=400, detail="Unknown profile")
        config["active_profile"] = patch.active_profile

    if patch.runtime:
        for key, value in patch.runtime.items():
            if key in RUNTIME_KEYS or key == "llama_cpp_release_backend":
                config[key] = value

    profile_name = str(config.get("active_profile") or "chat")
    if patch.profile:
        profile = (config.get("profiles") or {}).setdefault(profile_name, {})
        for key, value in patch.profile.items():
            profile[key] = value

    if patch.proxy:
        proxy = config.setdefault("ollama_proxy", {})
        for key, value in patch.proxy.items():
            proxy[key] = value
    return config


def create_app() -> FastAPI:
    app = FastAPI(title="llama.cpp Control Deck Web UI")
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        template = INDEX_TEMPLATE.read_text(encoding="utf-8")
        state_json = json.dumps(build_state(), ensure_ascii=False)
        return HTMLResponse(template.replace(STATE_PLACEHOLDER, state_json))

    @app.get("/api/state")
    def api_state() -> dict[str, Any]:
        return build_state()

    @app.post("/api/config")
    def api_save_config(patch: ConfigPatch) -> dict[str, Any]:
        config = _merge_config_patch(load_config(), patch)
        save_config(config)
        return {"ok": True, "message": "Configuration saved.", "details": build_state()}

    @app.post("/api/runtime/autodetect")
    def api_runtime_autodetect() -> dict[str, Any]:
        config = load_config()
        apply_runtime_autodetect(config, override=True, deep_search=True)
        save_config(config)
        return {
            "ok": True,
            "message": "Runtime paths updated.",
            "details": {key: config.get(key, "") for key in RUNTIME_KEYS},
        }

    @app.get("/api/paths/roots")
    def api_path_roots() -> dict[str, Any]:
        return {"ok": True, "message": "Path roots loaded.", "details": _path_roots(load_config())}

    @app.get("/api/paths/list")
    def api_path_list(path: str, kind: str = "file") -> dict[str, Any]:
        return {"ok": True, "message": "Path entries loaded.", "details": list_path_entries(path, kind)}

    @app.post("/api/paths/validate")
    def api_path_validate(payload: PathValidatePayload) -> dict[str, Any]:
        return validate_path_choice(payload.path, payload.kind)

    @app.post("/api/server/start")
    def api_server_start() -> dict[str, Any]:
        return _result_payload(_manager().start_server(), "Open Logs if startup fails.")

    @app.post("/api/server/stop")
    def api_server_stop() -> dict[str, Any]:
        return _result_payload(_manager().stop_server())

    @app.post("/api/server/restart")
    def api_server_restart() -> dict[str, Any]:
        return _result_payload(_manager().restart_server(), "Wait for status to become ready.")

    @app.get("/api/instances")
    def api_instances() -> dict[str, Any]:
        config = load_config()
        details = [_service_details(config, instance) for instance in config.get("instances") or []]
        return {"ok": True, "message": "Services loaded.", "details": details}

    @app.get("/api/instances/defaults")
    def api_instance_defaults(profile: str = "chat") -> dict[str, Any]:
        config = load_config()
        instance = _service_defaults(config, profile)
        return {"ok": True, "message": "Service defaults loaded.", "details": _service_details(config, instance)}

    @app.post("/api/instances/validate")
    def api_instance_validate(payload: InstancePayload) -> dict[str, Any]:
        config = load_config()
        instance = _clean_instance(payload.instance)
        original_id = str(payload.instance.get("_original_id") or instance.get("id") or "")
        warnings = validate_instance(config, instance, original_id)
        command: list[str] = []
        command_error = ""
        try:
            command = LlamaServerManager(config).build_server_command(
                str(instance.get("profile") or "chat"),
                {key: value for key, value in instance.items() if key in INSTANCE_EDIT_KEYS},
            )
        except Exception as exc:
            command_error = str(exc)
        return {
            "ok": not warnings and not command_error,
            "message": "Service is valid." if not warnings and not command_error else "Service needs changes.",
            "details": {"validation": warnings, "command": command, "command_error": command_error},
        }

    @app.post("/api/instances")
    def api_instance_create(payload: InstancePayload) -> dict[str, Any]:
        config = load_config()
        raw_id = str(payload.instance.get("id") or "").strip()
        instance = _clean_instance(payload.instance)
        if not raw_id:
            instance["id"] = _unique_instance_id(config, str(instance.get("name") or "service"))
        warnings = validate_instance(config, instance)
        if warnings:
            return {
                "ok": False,
                "message": "Service was not created.",
                "details": {"validation": warnings, "instance": instance},
                "next_action": "Fix validation warnings and try again.",
            }
        config.setdefault("instances", []).append(instance)
        save_config(config)
        details = _service_details(config, instance)
        if payload.start:
            start_result = LlamaServerManager(config).start_instance(instance)
            response = _result_payload(start_result, "Open Diagnostics if startup fails.")
            response["details"]["service"] = details
            return response
        return {"ok": True, "message": "Service created.", "details": details}

    @app.get("/api/instances/{instance_id}")
    def api_instance_get(instance_id: str) -> dict[str, Any]:
        config = load_config()
        instance = _find_instance(config, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Service not found")
        return {"ok": True, "message": "Service loaded.", "details": _service_details(config, instance)}

    @app.patch("/api/instances/{instance_id}")
    def api_instance_update(instance_id: str, payload: InstancePayload) -> dict[str, Any]:
        config = load_config()
        index = _instance_index(config, instance_id)
        if index is None:
            raise HTTPException(status_code=404, detail="Service not found")
        old = deepcopy(config["instances"][index])
        instance = _clean_instance({**old, **payload.instance})
        if instance["id"] != instance_id and _instance_index(config, instance["id"]) is not None:
            return {
                "ok": False,
                "message": "Service was not saved.",
                "details": {
                    "validation": [
                        {
                            "code": "duplicate_id",
                            "message": f"Service id already exists: {instance['id']}",
                            "next_action": "Use a different id.",
                        }
                    ]
                },
            }
        warnings = validate_instance(config, instance, instance_id)
        if warnings:
            return {
                "ok": False,
                "message": "Service was not saved.",
                "details": {"validation": warnings, "instance": instance},
                "next_action": "Fix validation warnings and try again.",
            }
        config["instances"][index] = instance
        save_config(config)
        details = _service_details(config, instance)
        restart_required = _instance_changed_requires_restart(old, instance) and bool(details["status"].get("running"))
        details["restart_required"] = restart_required
        return {
            "ok": True,
            "message": "Service saved." + (" Restart required." if restart_required else ""),
            "details": details,
            "next_action": "Restart this service to apply changes." if restart_required else "",
        }

    @app.delete("/api/instances/{instance_id}")
    def api_instance_delete(instance_id: str, stop: bool = False) -> dict[str, Any]:
        config = load_config()
        index = _instance_index(config, instance_id)
        if index is None:
            raise HTTPException(status_code=404, detail="Service not found")
        manager = LlamaServerManager(config)
        status = manager.instance_status(config["instances"][index])
        if status.get("running") and not stop:
            return {
                "ok": False,
                "message": "Service is running.",
                "next_action": "Stop the service first or delete with stop=true.",
                "details": {"status": status},
            }
        if status.get("running") and stop:
            manager.stop_instance(instance_id)
        removed = config["instances"].pop(index)
        save_config(config)
        return {"ok": True, "message": "Service deleted.", "details": {"instance": removed}}

    @app.post("/api/instances/{instance_id}/duplicate")
    def api_instance_duplicate(instance_id: str) -> dict[str, Any]:
        config = load_config()
        instance = _find_instance(config, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Service not found")
        duplicate = deepcopy(instance)
        port = _next_free_port(config, _coerce_port(duplicate.get("port"), 8081) + 1)
        duplicate["port"] = port
        duplicate["id"] = _unique_instance_id(config, f"{duplicate.get('profile') or 'service'}-{port}")
        duplicate["name"] = f"{duplicate.get('name') or duplicate['id']} copy"
        warnings = validate_instance(config, duplicate)
        if warnings:
            return {
                "ok": False,
                "message": "Service was not duplicated.",
                "details": {"validation": warnings, "instance": duplicate},
            }
        config.setdefault("instances", []).append(duplicate)
        save_config(config)
        return {"ok": True, "message": "Service duplicated.", "details": _service_details(config, duplicate)}

    @app.post("/api/instances/{instance_id}/start")
    def api_instance_start(instance_id: str) -> dict[str, Any]:
        config = load_config()
        instance = _find_instance(config, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        return _result_payload(LlamaServerManager(config).start_instance(instance))

    @app.post("/api/instances/{instance_id}/stop")
    def api_instance_stop(instance_id: str) -> dict[str, Any]:
        return _result_payload(_manager().stop_instance(instance_id))

    @app.post("/api/instances/{instance_id}/restart")
    def api_instance_restart(instance_id: str) -> dict[str, Any]:
        config = load_config()
        instance = _find_instance(config, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        return _result_payload(LlamaServerManager(config).restart_instance(instance))

    @app.post("/api/proxy/start")
    def api_proxy_start() -> dict[str, Any]:
        return _result_payload(_manager().start_proxy())

    @app.post("/api/proxy/stop")
    def api_proxy_stop() -> dict[str, Any]:
        return _result_payload(_manager().stop_proxy())

    @app.get("/api/logs")
    def api_logs(kind: str = "latest", lines: int = Query(200, ge=1, le=2000)) -> dict[str, Any]:
        log_path = _select_log_path(kind)
        return {"ok": True, "path": str(log_path) if log_path else "", "text": tail_file(log_path, lines)}

    @app.get("/api/devices")
    def api_devices() -> dict[str, Any]:
        result = _manager().list_devices()
        return _result_payload(result)

    @app.get("/api/release/status")
    def api_release_status() -> dict[str, Any]:
        config = load_config()
        binary = str(config.get("llama_server_binary") or "")
        library = str(config.get("llama_server_library_path") or "")
        try:
            status = llama_cpp_release.update_status(binary_path=binary, library_path=library)
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Could not check release status: {exc}",
                "next_action": "Check internet access or try again later.",
            }
        return {"ok": True, "message": "Release status loaded.", "details": status}

    @app.get("/api/release/download/status")
    def api_release_download_status() -> dict[str, Any]:
        return {"ok": True, "message": "Download status loaded.", "details": download_job_status()}

    @app.post("/api/release/download")
    def api_release_download() -> dict[str, Any]:
        config = load_config()
        backend = str(config.get("llama_cpp_release_backend") or "auto")
        with _DOWNLOAD_LOCK:
            if _DOWNLOAD_JOB.get("status") == "running":
                return {
                    "ok": True,
                    "message": "llama-server download is already running.",
                    "details": deepcopy(_DOWNLOAD_JOB),
                }
        thread = threading.Thread(target=_run_release_download, args=(backend,), daemon=True)
        thread.start()
        return {
            "ok": True,
            "message": "llama-server download started.",
            "details": download_job_status(),
            "next_action": "Keep this page open and watch Download status.",
        }

    @app.post("/api/release/download/reset")
    def api_release_download_reset() -> dict[str, Any]:
        with _DOWNLOAD_LOCK:
            if _DOWNLOAD_JOB.get("status") == "running":
                return {
                    "ok": False,
                    "message": "Download is still running.",
                    "next_action": "Wait for the current download to finish.",
                }
        _set_download_job(
            status="idle",
            message="No download running.",
            started_at=None,
            finished_at=None,
            lines=[],
            result=None,
            error="",
        )
        return {"ok": True, "message": "Download status reset.", "details": download_job_status()}

    @app.post("/api/release/download/sync")
    def api_release_download_sync() -> dict[str, Any]:
        """Test/debug helper: run the same release install path synchronously."""
        config = load_config()
        backend = str(config.get("llama_cpp_release_backend") or "auto")
        try:
            _run_release_download(backend)
        except Exception as exc:
            return {
                "ok": False,
                "message": str(exc),
                "next_action": "Check network access and selected backend.",
            }
        status = download_job_status()
        return {"ok": status.get("status") == "succeeded", "message": status.get("message", ""), "details": status}

    return app


def _find_instance(config: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
    for instance in config.get("instances") or []:
        if str(instance.get("id") or instance.get("name") or "") == instance_id:
            return instance
        fallback = f"{instance.get('profile') or 'chat'}-{instance.get('port') or '8081'}"
        if fallback == instance_id:
            return instance
    return None


def _select_log_path(kind: str) -> Path | None:
    manager = _manager()
    if kind == "server":
        value = manager.server_status().get("log_path")
        return Path(value) if value else None
    if kind == "proxy":
        value = manager.proxy_status().get("log_path")
        return Path(value) if value else None

    logs = sorted(LOG_DIR.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local llama.cpp Control Deck web UI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default=DEFAULT_WEB_HOST, help="host/interface for the web UI")
    parser.add_argument("--port", type=int, default=DEFAULT_WEB_PORT, help="port for the web UI")
    parser.add_argument("--reload", action="store_true", help="enable uvicorn reload")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    uvicorn.run("control_web:create_app", host=args.host, port=args.port, reload=args.reload, factory=True)
    return 0


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
