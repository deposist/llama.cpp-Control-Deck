"""Download and inspect prebuilt llama.cpp release binaries.

This module intentionally uses only the Python standard library so it can run
before project dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import RUNTIME_DIR

LLAMA_CPP_REPO = "ggml-org/llama.cpp"
LATEST_RELEASE_API = f"https://api.github.com/repos/{LLAMA_CPP_REPO}/releases/latest"
MANIFEST_PATH = RUNTIME_DIR / "llama_cpp_release.json"
DEFAULT_INSTALL_ROOT = RUNTIME_DIR / "llama.cpp"
BACKEND_CHOICES = ("auto", "cpu", "vulkan", "rocm", "openvino", "sycl-fp16", "sycl-fp32")
BACKEND_MARKERS = ("vulkan", "rocm", "openvino", "sycl", "cuda", "hip", "aclgraph")


@dataclass
class SelectedAsset:
    name: str
    url: str
    size: int
    backend: str
    tag_name: str


def _request_json(url: str, timeout: float = 25.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "llama.cpp-control-deck",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_latest_release(timeout: float = 25.0) -> dict[str, Any]:
    data = _request_json(LATEST_RELEASE_API, timeout=timeout)
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise RuntimeError("GitHub release response did not include tag_name")
    return data


def arch_token() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    if machine == "s390x":
        return "s390x"
    return machine


def platform_token() -> str:
    system = platform.system().lower()
    if system == "linux":
        return "ubuntu"
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "win"
    return system


def _asset_backend(name: str) -> str:
    lowered = name.lower()
    if "vulkan" in lowered:
        return "vulkan"
    if "rocm" in lowered:
        return "rocm"
    if "openvino" in lowered:
        return "openvino"
    if "sycl-fp16" in lowered:
        return "sycl-fp16"
    if "sycl-fp32" in lowered:
        return "sycl-fp32"
    if "sycl" in lowered:
        return "sycl"
    if "cuda" in lowered:
        return "cuda"
    if "hip" in lowered:
        return "hip"
    if not any(marker in lowered for marker in BACKEND_MARKERS):
        return "cpu"
    return "other"


def _is_candidate_asset(name: str, os_name: str, arch: str) -> bool:
    lowered = name.lower()
    if not (lowered.endswith(".tar.gz") or lowered.endswith(".zip")):
        return False
    if not lowered.startswith("llama-") or "-bin-" not in lowered:
        return False
    if os_name not in lowered or arch not in lowered:
        return False
    if os_name == "ubuntu" and any(token in lowered for token in ("win-", "macos", "android", "openeuler")):
        return False
    return True


def select_release_asset(
    release: dict[str, Any],
    backend: str = "auto",
    os_name: str | None = None,
    arch: str | None = None,
) -> SelectedAsset:
    backend = (backend or "auto").strip().lower()
    if backend not in BACKEND_CHOICES:
        raise ValueError(f"Unknown backend: {backend}")
    os_name = os_name or platform_token()
    arch = arch or arch_token()
    tag = str(release.get("tag_name") or "")
    assets = release.get("assets") or []
    candidates: list[dict[str, Any]] = [
        asset
        for asset in assets
        if isinstance(asset, dict) and _is_candidate_asset(str(asset.get("name") or ""), os_name, arch)
    ]
    if not candidates:
        raise RuntimeError(f"No llama.cpp release assets found for {os_name}/{arch}")

    desired = "cpu" if backend == "auto" else backend
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for asset in candidates:
        name = str(asset.get("name") or "")
        asset_backend = _asset_backend(name)
        score = 100
        if asset_backend == desired:
            score = 0
        elif backend == "auto" and asset_backend == "vulkan":
            score = 10
        elif backend == "auto":
            score = 20
        ranked.append((score, name, asset))

    ranked.sort(key=lambda item: (item[0], item[1]))
    score, name, selected = ranked[0]
    selected_backend = _asset_backend(name)
    if score >= 100:
        available = ", ".join(sorted({str(asset.get("name") or "") for asset in candidates}))
        raise RuntimeError(f"No {backend} asset found for {os_name}/{arch}. Available: {available}")
    return SelectedAsset(
        name=name,
        url=str(selected.get("browser_download_url") or ""),
        size=int(selected.get("size") or 0),
        backend=selected_backend,
        tag_name=tag,
    )


def safe_install_name(tag_name: str, asset_name: str) -> str:
    base = asset_name
    for suffix in (".tar.gz", ".zip"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    raw = f"{tag_name}-{base}"
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", raw)


def download_file(url: str, destination: Path, expected_size: int = 0) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "llama.cpp-control-deck"})
    downloaded = 0
    last_report = 0.0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as fh:
        size = expected_size or int(response.headers.get("Content-Length") or 0)
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            downloaded += len(chunk)
            now = time.time()
            if now - last_report >= 1.0:
                last_report = now
                if size:
                    print(f"Downloaded {downloaded / 1024 / 1024:.1f} / {size / 1024 / 1024:.1f} MiB", flush=True)
                else:
                    print(f"Downloaded {downloaded / 1024 / 1024:.1f} MiB", flush=True)


def extract_archive(archive_path: Path, install_dir: Path) -> None:
    tmp_dir = install_dir.with_suffix(".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        if archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                try:
                    archive.extractall(tmp_dir, filter="data")
                except TypeError:
                    archive.extractall(tmp_dir)
        elif archive_path.name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp_dir)
        else:
            raise RuntimeError(f"Unsupported archive type: {archive_path.name}")

        if install_dir.exists():
            shutil.rmtree(install_dir)
        tmp_dir.replace(install_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def find_llama_server(root: Path) -> Path:
    executable_names = ["llama-server.exe"] if sys.platform == "win32" else ["llama-server"]
    for name in executable_names:
        matches = sorted(root.rglob(name))
        for match in matches:
            if match.is_file():
                try:
                    mode = match.stat().st_mode
                    match.chmod(mode | 0o755)
                except Exception:
                    pass
                return match
    raise RuntimeError(f"Could not find llama-server inside {root}")


def run_server_version(binary_path: str | Path, library_path: str | Path | None = None, timeout: float = 20.0) -> str:
    binary = Path(str(binary_path)).expanduser()
    if not binary.exists():
        raise FileNotFoundError(f"llama-server not found: {binary}")
    binary = binary.resolve()
    env = os.environ.copy()
    lib_dir = str(Path(str(library_path)).expanduser().resolve() if library_path else binary.parent)
    if lib_dir:
        current = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = lib_dir + (f":{current}" if current else "")
    completed = subprocess.run(
        [str(binary), "--version"],
        cwd=str(binary.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    return completed.stdout.strip()


def parse_release_tag_from_text(value: str) -> str:
    match = re.search(r"\bb\d{3,}\b", value or "")
    return match.group(0) if match else ""


def read_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_manifest(data: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def install_latest_release(
    backend: str = "auto",
    install_root: Path = DEFAULT_INSTALL_ROOT,
    keep_archive: bool = False,
) -> dict[str, Any]:
    release = fetch_latest_release()
    asset = select_release_asset(release, backend=backend)
    if not asset.url:
        raise RuntimeError(f"Release asset has no download URL: {asset.name}")

    install_root.mkdir(parents=True, exist_ok=True)
    install_dir = install_root / safe_install_name(asset.tag_name, asset.name)
    downloads_dir = RUNTIME_DIR / "downloads"
    archive_path = downloads_dir / asset.name

    print(f"Latest release: {asset.tag_name}", flush=True)
    print(f"Selected asset: {asset.name} ({asset.backend})", flush=True)
    print(f"Downloading from: {asset.url}", flush=True)
    download_file(asset.url, archive_path, expected_size=asset.size)
    print(f"Extracting to: {install_dir}", flush=True)
    extract_archive(archive_path, install_dir)
    binary_path = find_llama_server(install_dir)
    library_path = binary_path.parent
    print(f"llama-server: {binary_path}", flush=True)

    version_output = ""
    try:
        version_output = run_server_version(binary_path, library_path=library_path)
        print(version_output, flush=True)
    except Exception as exc:
        print(f"Could not run --version: {exc}", flush=True)

    manifest = {
        "repo": LLAMA_CPP_REPO,
        "tag_name": asset.tag_name,
        "asset_name": asset.name,
        "asset_backend": asset.backend,
        "asset_url": asset.url,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "install_dir": str(install_dir),
        "binary_path": str(binary_path),
        "library_path": str(library_path),
        "version_output": version_output,
    }
    write_manifest(manifest)
    if not keep_archive:
        try:
            archive_path.unlink()
        except FileNotFoundError:
            pass
    print("Install complete.", flush=True)
    return manifest


def update_status(
    binary_path: str | Path | None = None,
    backend: str = "auto",
    library_path: str | Path | None = None,
) -> dict[str, Any]:
    release = fetch_latest_release()
    asset = select_release_asset(release, backend=backend)
    manifest = read_manifest()
    local_version = ""
    local_tag = str(manifest.get("tag_name") or "")
    if binary_path:
        try:
            local_version = run_server_version(binary_path, library_path=library_path)
            local_tag = parse_release_tag_from_text(local_version) or local_tag
        except Exception as exc:
            local_version = f"Could not run --version: {exc}"
    latest_tag = str(release.get("tag_name") or "")
    update_available: bool | None
    if local_tag:
        update_available = local_tag != latest_tag
    else:
        update_available = None
    return {
        "latest_tag": latest_tag,
        "latest_name": release.get("name") or "",
        "selected_asset": asset.__dict__,
        "manifest": manifest,
        "local_tag": local_tag,
        "local_version": local_version,
        "update_available": update_available,
    }


def print_status(status: dict[str, Any]) -> None:
    print(f"Latest release: {status.get('latest_tag')}")
    asset = status.get("selected_asset") or {}
    print(f"Selected asset: {asset.get('name')} ({asset.get('backend')})")
    manifest = status.get("manifest") or {}
    if manifest:
        print(f"Managed install: {manifest.get('tag_name')} | {manifest.get('binary_path')}")
    else:
        print("Managed install: none")
    local_version = str(status.get("local_version") or "").strip()
    if local_version:
        print("Local llama-server --version:")
        print(local_version)
    local_tag = status.get("local_tag") or ""
    if local_tag:
        print(f"Detected local tag: {local_tag}")
    update_available = status.get("update_available")
    if update_available is True:
        print("Update: available")
    elif update_available is False:
        print("Update: installed release is current")
    else:
        print("Update: unknown (local build tag was not detected)")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download and inspect prebuilt llama.cpp release binaries.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--backend", choices=BACKEND_CHOICES, default="auto", help="release backend to prefer")
    subparsers = parser.add_subparsers(dest="command")

    latest = subparsers.add_parser("latest", help="show latest llama.cpp release and selected asset")
    latest.add_argument("--backend", choices=BACKEND_CHOICES, default=argparse.SUPPRESS, help="release backend to prefer")

    install = subparsers.add_parser("install", help="download and install the selected latest release")
    install.add_argument("--backend", choices=BACKEND_CHOICES, default=argparse.SUPPRESS, help="release backend to prefer")

    version = subparsers.add_parser("version", help="run llama-server --version")
    version.add_argument("--binary", default="", help="path to llama-server")
    version.add_argument("--library", default="", help="LD library path for llama-server")

    check = subparsers.add_parser("check", help="check installed version against latest release")
    check.add_argument("--binary", default="", help="path to llama-server")
    check.add_argument("--library", default="", help="LD library path for llama-server")
    check.add_argument("--backend", choices=BACKEND_CHOICES, default=argparse.SUPPRESS, help="release backend to prefer")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    command = args.command or "latest"

    try:
        if command == "latest":
            release = fetch_latest_release()
            asset = select_release_asset(release, backend=args.backend)
            print(f"Latest release: {asset.tag_name}")
            print(f"Selected asset: {asset.name} ({asset.backend})")
            print(f"Download URL: {asset.url}")
            return 0
        if command == "install":
            install_latest_release(backend=args.backend)
            return 0
        if command == "version":
            if not args.binary:
                print("--binary is required", file=sys.stderr)
                return 2
            print(run_server_version(args.binary, library_path=args.library or None))
            return 0
        if command == "check":
            status = update_status(
                binary_path=args.binary or None,
                backend=args.backend,
                library_path=args.library or None,
            )
            print_status(status)
            return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
