"""Process manager and diagnostics for local llama.cpp server instances.

Run ``python llama_server_manager.py --help`` to inspect commands, status, and
device detection without opening the GUI.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from config import (
    APP_DIR,
    LOG_DIR,
    PROFILE_ORDER,
    RUNTIME_DIR,
    active_profile,
    load_config,
    profile_model_name,
)

# Configure logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "llama_server_manager.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("llama_server_manager")


@dataclass
class ProcessResult:
    ok: bool
    message: str
    pid: int | None = None
    log_path: str | None = None
    command: list[str] | None = None


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return bool(value)


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_value_arg(command: list[str], flag: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return
    command.extend([flag, text])


def _connect_host(host: str) -> str:
    host = (host or "127.0.0.1").strip()
    if host in {"0.0.0.0", "::", "*"}:
        return "127.0.0.1"
    return host


INSTANCE_OVERRIDE_KEYS = {
    "model_path",
    "mmproj_path",
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
    "use_mmap",
    "use_mlock",
    "webui",
    "cont_batching",
    "metrics",
    "slots",
    "extra_args",
    "models_dir",
    "models_preset",
    "models_max",
    "models_autoload",
}


def _safe_state_id(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", value.strip())
    return safe or "instance"


def http_json(url: str, timeout: float = 2.0) -> tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return True, {}
            return True, json.loads(raw)
    except Exception as exc:
        return False, str(exc)


def tail_file(path: str | Path | None, max_lines: int = 120) -> str:
    if not path:
        return ""
    log_path = Path(path)
    if not log_path.exists():
        return ""
    try:
        size = log_path.stat().st_size
        with log_path.open("rb") as fh:
            fh.seek(max(0, size - 256_000))
            data = fh.read().decode("utf-8", errors="replace")
        return "\n".join(data.splitlines()[-max_lines:])
    except Exception as exc:
        return f"Could not read log: {exc}"


class LlamaServerManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config

    def _resolve_program_path(self, value: str) -> Path:
        path = Path(value)
        if path.exists():
            return path
        found = shutil.which(value)
        if found:
            return Path(found)
        return path

    def _server_cwd(self, binary: Path) -> str:
        configured = Path(str(self.config.get("llama_server_cwd") or "")).expanduser()
        if configured.is_dir():
            return str(configured)
        if binary.parent.is_dir():
            return str(binary.parent)
        return str(APP_DIR)

    @property
    def server_state_path(self) -> Path:
        return RUNTIME_DIR / "llama_server_state.json"

    @property
    def instance_state_dir(self) -> Path:
        return RUNTIME_DIR / "instances"

    @property
    def proxy_state_path(self) -> Path:
        return RUNTIME_DIR / "ollama_proxy_state.json"

    def instance_state_path(self, instance_id: str) -> Path:
        return self.instance_state_dir / f"{_safe_state_id(instance_id)}.json"

    def build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        lib_path = str(self.config.get("llama_server_library_path") or "").strip()
        if lib_path:
            current = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = lib_path + (f":{current}" if current else "")
        return env

    def _effective_profile(
        self,
        profile_name: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        profiles = self.config.get("profiles") or {}
        name = profile_name or str(self.config.get("active_profile") or "chat")
        profile = deepcopy(profiles.get(name) or active_profile(self.config))
        if overrides:
            for key, value in overrides.items():
                if key not in INSTANCE_OVERRIDE_KEYS:
                    continue
                if value == "" and key not in {"model_path", "mmproj_path", "models_preset", "tensor_split", "api_key"}:
                    continue
                profile[key] = value
        return name, profile

    def build_server_command(
        self,
        profile_name: str | None = None,
        profile_overrides: dict[str, Any] | None = None,
    ) -> list[str]:
        name, profile = self._effective_profile(profile_name, profile_overrides)
        profile_type = str(profile.get("profile_type") or name)
        binary = str(self.config.get("llama_server_binary") or "").strip()
        if not binary:
            raise ValueError("llama_server_binary is empty")

        command = [binary]
        model_path = str(profile.get("model_path") or "").strip()
        models_dir = str(profile.get("models_dir") or "").strip()
        models_preset = str(profile.get("models_preset") or "").strip()

        if model_path:
            command.extend(["--model", model_path])
        elif profile_type != "router" and name != "router":
            raise ValueError("Model path is required for this profile")

        _append_value_arg(command, "--host", profile.get("host", "127.0.0.1"))
        _append_value_arg(command, "--port", profile.get("port", 8081))
        _append_value_arg(command, "--alias", profile.get("alias"))
        _append_value_arg(command, "--api-key", profile.get("api_key"))
        _append_value_arg(command, "--ctx-size", profile.get("n_ctx"))
        _append_value_arg(command, "--threads", profile.get("n_threads"))
        _append_value_arg(command, "--threads-batch", profile.get("n_threads_batch"))
        _append_value_arg(command, "--batch-size", profile.get("n_batch"))
        _append_value_arg(command, "--ubatch-size", profile.get("n_ubatch"))
        _append_value_arg(command, "--gpu-layers", profile.get("n_gpu_layers"))
        _append_value_arg(command, "--main-gpu", profile.get("main_gpu"))
        split_mode = str(profile.get("split_mode") or "").strip().lower()
        _append_value_arg(command, "--split-mode", profile.get("split_mode"))
        tensor_split = str(profile.get("tensor_split") or "").strip()
        if tensor_split and split_mode != "none":
            command.extend(["--tensor-split", tensor_split])

        flash_attn = str(profile.get("flash_attn") or "").strip().lower()
        if flash_attn in {"on", "off", "auto"}:
            command.extend(["--flash-attn", flash_attn])

        command.append("--mmap" if _as_bool(profile.get("use_mmap", True)) else "--no-mmap")
        if _as_bool(profile.get("use_mlock", False)):
            command.append("--mlock")
        if not _as_bool(profile.get("webui", True)):
            command.append("--no-webui")
        if not _as_bool(profile.get("cont_batching", True)):
            command.append("--no-cont-batching")
        if _as_bool(profile.get("metrics", False)):
            command.append("--metrics")
        if not _as_bool(profile.get("slots", True)):
            command.append("--no-slots")

        if profile_type == "embeddings":
            command.append("--embedding")
        elif profile_type == "rerank":
            command.append("--reranking")
        elif profile_type == "multimodal":
            _append_value_arg(command, "--mmproj", profile.get("mmproj_path"))
        elif profile_type == "router":
            _append_value_arg(command, "--models-dir", models_dir)
            _append_value_arg(command, "--models-preset", models_preset)
            _append_value_arg(command, "--models-max", profile.get("models_max"))
            if not _as_bool(profile.get("models_autoload", True)):
                command.append("--no-models-autoload")
            if not model_path and not models_dir and not models_preset:
                raise ValueError("Router profile requires model_path, models_dir, or models_preset")

        extra_args = str(profile.get("extra_args") or "").strip()
        if extra_args:
            command.extend(shlex.split(extra_args))
        return command

    def _load_state(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_state(self, path: Path, state: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _clear_state(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _process_from_state(self, state_path: Path, expected_token: str) -> psutil.Process | None:
        state = self._load_state(state_path)
        pid = _as_int(state.get("pid"))
        if not pid or not psutil.pid_exists(pid):
            return None
        try:
            proc = psutil.Process(pid)
            cmdline = " ".join(proc.cmdline())
            if expected_token in cmdline:
                return proc
        except Exception:
            return None
        return None

    def port_owner(self, host: str, port: int) -> dict[str, Any] | None:
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status != psutil.CONN_LISTEN or not conn.laddr:
                    continue
                if int(conn.laddr.port) != int(port):
                    continue
                pid = conn.pid
                name = ""
                cmdline = ""
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        name = proc.name()
                        cmdline = " ".join(proc.cmdline())
                    except Exception:
                        pass
                return {
                    "pid": pid,
                    "name": name,
                    "cmdline": cmdline,
                    "host": conn.laddr.ip,
                    "port": conn.laddr.port,
                }
        except Exception:
            pass

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            result = sock.connect_ex((_connect_host(host), int(port)))
            if result == 0:
                return {"pid": None, "name": "", "cmdline": "unknown", "host": host, "port": port}
        return None

    def start_server(self) -> ProcessResult:
        running = self._process_from_state(self.server_state_path, "llama-server")
        if running and running.is_running():
            return ProcessResult(True, "llama-server is already running", running.pid)

        profile = active_profile(self.config)
        host = str(profile.get("host") or "127.0.0.1")
        port = int(profile.get("port") or 8081)
        owner = self.port_owner(host, port)
        if owner:
            return ProcessResult(
                False,
                f"Port {port} is busy by PID {owner.get('pid')}: {owner.get('cmdline') or owner.get('name')}",
            )

        try:
            command = self.build_server_command()
        except Exception as exc:
            return ProcessResult(False, str(exc))

        binary = self._resolve_program_path(command[0])
        if not binary.exists():
            return ProcessResult(False, f"llama-server not found: {binary}")

        cwd = self._server_cwd(binary)
        log_path = LOG_DIR / f"llama-server-{self.config.get('active_profile', 'chat')}-{_now_stamp()}.log"
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab", buffering=0) as log_fh:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=self.build_env(),
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=(sys.platform != "win32"),
                )
            state = {
                "pid": process.pid,
                "kind": "llama-server",
                "profile": self.config.get("active_profile", "chat"),
                "started_at": time.time(),
                "log_path": str(log_path),
                "command": command,
                "host": host,
                "port": port,
            }
            self._save_state(self.server_state_path, state)
            time.sleep(0.5)
            if process.poll() is not None:
                self._clear_state(self.server_state_path)
                return ProcessResult(
                    False,
                    "llama-server exited immediately:\n" + tail_file(log_path, 60),
                    log_path=str(log_path),
                    command=command,
                )
            return ProcessResult(True, "llama-server started", process.pid, str(log_path), command)
        except Exception as exc:
            return ProcessResult(False, f"Could not start llama-server: {exc}")

    def _instance_id(self, instance: dict[str, Any]) -> str:
        raw = str(instance.get("id") or instance.get("name") or "").strip()
        if raw:
            return raw
        profile = str(instance.get("profile") or "chat")
        port = str(instance.get("port") or "8081")
        return f"{profile}-{port}"

    def _instance_profile_name(self, instance: dict[str, Any]) -> str:
        return str(instance.get("profile") or "chat").strip() or "chat"

    def _instance_overrides(self, instance: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in instance.items() if key in INSTANCE_OVERRIDE_KEYS}

    def _instance_effective_profile(self, instance: dict[str, Any]) -> dict[str, Any]:
        _, profile = self._effective_profile(
            self._instance_profile_name(instance),
            self._instance_overrides(instance),
        )
        return profile

    def _instance_process(self, instance_id: str) -> psutil.Process | None:
        return self._process_from_state(self.instance_state_path(instance_id), "llama-server")

    def start_instance(self, instance: dict[str, Any]) -> ProcessResult:
        instance_id = self._instance_id(instance)
        running = self._instance_process(instance_id)
        if running and running.is_running():
            return ProcessResult(True, f"Instance {instance_id} is already running", running.pid)

        profile_name = self._instance_profile_name(instance)
        overrides = self._instance_overrides(instance)
        profile = self._instance_effective_profile(instance)
        host = str(profile.get("host") or "127.0.0.1")
        port = int(profile.get("port") or 8081)
        owner = self.port_owner(host, port)
        if owner:
            return ProcessResult(
                False,
                f"Port {port} is busy by PID {owner.get('pid')}: {owner.get('cmdline') or owner.get('name')}",
            )

        try:
            command = self.build_server_command(profile_name, overrides)
        except Exception as exc:
            return ProcessResult(False, str(exc))

        binary = self._resolve_program_path(command[0])
        if not binary.exists():
            return ProcessResult(False, f"llama-server not found: {binary}")

        cwd = self._server_cwd(binary)
        safe_id = _safe_state_id(instance_id)
        log_path = LOG_DIR / f"llama-server-{safe_id}-{_now_stamp()}.log"
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab", buffering=0) as log_fh:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=self.build_env(),
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=(sys.platform != "win32"),
                )
            state = {
                "pid": process.pid,
                "kind": "llama-server-instance",
                "instance_id": instance_id,
                "instance_name": instance.get("name") or instance_id,
                "profile": profile_name,
                "started_at": time.time(),
                "log_path": str(log_path),
                "command": command,
                "host": host,
                "port": port,
                "alias": profile_model_name(profile),
            }
            self._save_state(self.instance_state_path(instance_id), state)
            time.sleep(0.5)
            if process.poll() is not None:
                self._clear_state(self.instance_state_path(instance_id))
                return ProcessResult(
                    False,
                    f"Instance {instance_id} exited immediately:\n" + tail_file(log_path, 60),
                    log_path=str(log_path),
                    command=command,
                )
            return ProcessResult(True, f"Instance {instance_id} started", process.pid, str(log_path), command)
        except Exception as exc:
            return ProcessResult(False, f"Could not start instance {instance_id}: {exc}")

    def _terminate_process(self, proc: psutil.Process, timeout: float = 8.0) -> bool:
        try:
            children = proc.children(recursive=True)
        except Exception:
            children = []
        targets = children + [proc]
        for item in targets:
            try:
                item.terminate()
            except Exception:
                pass
        gone, alive = psutil.wait_procs(targets, timeout=timeout)
        if alive:
            for item in alive:
                try:
                    item.kill()
                except Exception:
                    pass
            psutil.wait_procs(alive, timeout=3)
        try:
            return not proc.is_running()
        except Exception:
            return True

    def stop_server(self) -> ProcessResult:
        proc = self._process_from_state(self.server_state_path, "llama-server")
        if not proc:
            self._clear_state(self.server_state_path)
            return ProcessResult(True, "llama-server is not running")
        pid = proc.pid
        ok = self._terminate_process(proc)
        self._clear_state(self.server_state_path)
        return ProcessResult(ok, "llama-server stopped" if ok else "Could not stop llama-server", pid)

    def stop_instance(self, instance_id: str) -> ProcessResult:
        proc = self._instance_process(instance_id)
        state_path = self.instance_state_path(instance_id)
        if not proc:
            self._clear_state(state_path)
            return ProcessResult(True, f"Instance {instance_id} is not running")
        pid = proc.pid
        ok = self._terminate_process(proc)
        self._clear_state(state_path)
        return ProcessResult(ok, f"Instance {instance_id} stopped" if ok else f"Could not stop {instance_id}", pid)

    def restart_instance(self, instance: dict[str, Any]) -> ProcessResult:
        self.stop_instance(self._instance_id(instance))
        return self.start_instance(instance)

    def stop_all_instances(self) -> list[ProcessResult]:
        results: list[ProcessResult] = []
        for instance in self.config.get("instances") or []:
            results.append(self.stop_instance(self._instance_id(instance)))
        return results

    def restart_server(self) -> ProcessResult:
        self.stop_server()
        return self.start_server()

    def server_status(self) -> dict[str, Any]:
        state = self._load_state(self.server_state_path)
        proc = self._process_from_state(self.server_state_path, "llama-server")
        profile = active_profile(self.config)
        host = str(state.get("host") or profile.get("host") or "127.0.0.1")
        port = int(state.get("port") or profile.get("port") or 8081)
        url = f"http://{_connect_host(host)}:{port}/v1/models"
        healthy, data = http_json(url, timeout=1.5) if proc else (False, "not running")
        started_at = float(state.get("started_at") or 0)
        return {
            "running": bool(proc),
            "healthy": healthy,
            "health": data,
            "pid": proc.pid if proc else None,
            "host": host,
            "port": port,
            "url": f"http://{_connect_host(host)}:{port}",
            "openai_url": f"http://{_connect_host(host)}:{port}/v1",
            "uptime": max(0, time.time() - started_at) if proc and started_at else 0,
            "log_path": state.get("log_path"),
            "command": state.get("command"),
        }

    def instance_status(self, instance: dict[str, Any]) -> dict[str, Any]:
        instance_id = self._instance_id(instance)
        state = self._load_state(self.instance_state_path(instance_id))
        proc = self._instance_process(instance_id)
        profile = self._instance_effective_profile(instance)
        host = str(state.get("host") or profile.get("host") or "127.0.0.1")
        port = int(state.get("port") or profile.get("port") or 8081)
        url = f"http://{_connect_host(host)}:{port}/v1/models"
        healthy, data = http_json(url, timeout=1.0) if proc else (False, "not running")
        owner = None
        if not proc:
            owner = self.port_owner(host, port)
        started_at = float(state.get("started_at") or 0)
        return {
            "id": instance_id,
            "name": instance.get("name") or instance_id,
            "profile": self._instance_profile_name(instance),
            "enabled": _as_bool(instance.get("enabled", True)),
            "running": bool(proc),
            "healthy": healthy,
            "health": data,
            "pid": proc.pid if proc else None,
            "host": host,
            "port": port,
            "url": f"http://{_connect_host(host)}:{port}",
            "openai_url": f"http://{_connect_host(host)}:{port}/v1",
            "uptime": max(0, time.time() - started_at) if proc and started_at else 0,
            "log_path": state.get("log_path"),
            "command": state.get("command"),
            "alias": state.get("alias") or profile_model_name(profile),
            "main_gpu": profile.get("main_gpu", ""),
            "n_ctx": profile.get("n_ctx", ""),
            "port_owner": owner,
        }

    def instances_status(self) -> list[dict[str, Any]]:
        return [self.instance_status(instance) for instance in self.config.get("instances") or []]

    def build_proxy_command(self) -> list[str]:
        proxy = self.config.get("ollama_proxy") or {}
        python_path = str(self.config.get("python_path") or sys.executable)
        host = str(proxy.get("host") or "127.0.0.1")
        port = str(proxy.get("port") or 11435)
        target = str(proxy.get("target_base_url") or "").strip()
        if not target:
            server = self.server_status()
            target = server.get("openai_url") or "http://127.0.0.1:8081/v1"
        model = str(proxy.get("model") or "").strip() or profile_model_name(active_profile(self.config))
        command = [
            python_path,
            str(APP_DIR / "ollama_proxy.py"),
            "--host",
            host,
            "--port",
            port,
            "--target-base-url",
            target,
            "--model",
            model,
        ]
        target_api_key = str(proxy.get("target_api_key") or "").strip()
        if not target_api_key:
            target_api_key = str(active_profile(self.config).get("api_key") or "").strip()
        if target_api_key:
            command.extend(["--target-api-key", target_api_key])
        return command

    def start_proxy(self) -> ProcessResult:
        running = self._process_from_state(self.proxy_state_path, "ollama_proxy.py")
        if running and running.is_running():
            return ProcessResult(True, "Ollama proxy is already running", running.pid)

        proxy = self.config.get("ollama_proxy") or {}
        host = str(proxy.get("host") or "127.0.0.1")
        port = int(proxy.get("port") or 11435)
        owner = self.port_owner(host, port)
        if owner:
            return ProcessResult(
                False,
                f"Proxy port {port} is busy by PID {owner.get('pid')}: {owner.get('cmdline') or owner.get('name')}",
            )

        command = self.build_proxy_command()
        python_path = Path(command[0])
        if not python_path.exists():
            return ProcessResult(False, f"Python runtime not found: {python_path}")

        log_path = LOG_DIR / f"ollama-proxy-{_now_stamp()}.log"
        try:
            with log_path.open("ab", buffering=0) as log_fh:
                process = subprocess.Popen(
                    command,
                    cwd=str(APP_DIR),
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=(sys.platform != "win32"),
                )
            state = {
                "pid": process.pid,
                "kind": "ollama-proxy",
                "started_at": time.time(),
                "log_path": str(log_path),
                "command": command,
                "host": host,
                "port": port,
            }
            self._save_state(self.proxy_state_path, state)
            time.sleep(0.5)
            if process.poll() is not None:
                self._clear_state(self.proxy_state_path)
                return ProcessResult(
                    False,
                    "Ollama proxy exited immediately:\n" + tail_file(log_path, 60),
                    log_path=str(log_path),
                    command=command,
                )
            return ProcessResult(True, "Ollama proxy started", process.pid, str(log_path), command)
        except Exception as exc:
            return ProcessResult(False, f"Could not start Ollama proxy: {exc}")

    def stop_proxy(self) -> ProcessResult:
        proc = self._process_from_state(self.proxy_state_path, "ollama_proxy.py")
        if not proc:
            self._clear_state(self.proxy_state_path)
            return ProcessResult(True, "Ollama proxy is not running")
        pid = proc.pid
        ok = self._terminate_process(proc)
        self._clear_state(self.proxy_state_path)
        return ProcessResult(ok, "Ollama proxy stopped" if ok else "Could not stop Ollama proxy", pid)

    def proxy_status(self) -> dict[str, Any]:
        state = self._load_state(self.proxy_state_path)
        proc = self._process_from_state(self.proxy_state_path, "ollama_proxy.py")
        proxy = self.config.get("ollama_proxy") or {}
        host = str(state.get("host") or proxy.get("host") or "127.0.0.1")
        port = int(state.get("port") or proxy.get("port") or 11435)
        url = f"http://{_connect_host(host)}:{port}/api/tags"
        healthy, data = http_json(url, timeout=1.5) if proc else (False, "not running")
        started_at = float(state.get("started_at") or 0)
        return {
            "running": bool(proc),
            "healthy": healthy,
            "health": data,
            "pid": proc.pid if proc else None,
            "host": host,
            "port": port,
            "url": f"http://{_connect_host(host)}:{port}",
            "uptime": max(0, time.time() - started_at) if proc and started_at else 0,
            "log_path": state.get("log_path"),
            "command": state.get("command"),
        }

    def list_devices(self, timeout: float = 10.0) -> ProcessResult:
        binary = str(self.config.get("llama_server_binary") or "").strip()
        if not binary:
            return ProcessResult(False, "llama_server_binary is empty")
        binary_path = self._resolve_program_path(binary)
        if not binary_path.exists():
            return ProcessResult(False, f"llama-server not found: {binary}")
        try:
            completed = subprocess.run(
                [binary, "--list-devices"],
                cwd=self._server_cwd(binary_path),
                env=self.build_env(),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            ok = completed.returncode == 0
            return ProcessResult(ok, completed.stdout.strip())
        except Exception as exc:
            return ProcessResult(False, str(exc))


def format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect llama.cpp server manager state and generated commands.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="show server, proxy, and instance status as JSON")

    server_command = subparsers.add_parser("server-command", help="print the llama-server command")
    server_command.add_argument("--profile", choices=PROFILE_ORDER, help="profile to use instead of the active profile")

    instance_command = subparsers.add_parser("instance-command", help="print the command for one configured instance")
    instance_command.add_argument("instance_id", help="instance id from config.json")

    subparsers.add_parser("proxy-command", help="print the Ollama-compatible proxy command")
    subparsers.add_parser("devices", help="run llama-server --list-devices")
    return parser


def _find_instance(config: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
    for instance in config.get("instances") or []:
        if str(instance.get("id") or "") == instance_id:
            return instance
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config()
    manager = LlamaServerManager(config)
    command = args.command or "status"

    if command == "status":
        data = {
            "server": manager.server_status(),
            "proxy": manager.proxy_status(),
            "instances": manager.instances_status(),
        }
        logger.info(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return 0

    if command == "server-command":
        logger.info(shlex.join(manager.build_server_command(profile_name=args.profile)))
        return 0

    if command == "instance-command":
        instance = _find_instance(config, args.instance_id)
        if instance is None:
            logger.error(f"Unknown instance id: {args.instance_id}")
            return 2
        logger.info(
            shlex.join(
                manager.build_server_command(
                    manager._instance_profile_name(instance),
                    manager._instance_overrides(instance),
                )
            )
        )
        return 0

    if command == "proxy-command":
        logger.info(shlex.join(manager.build_proxy_command()))
        return 0

    if command == "devices":
        result = manager.list_devices()
        if result.ok:
            logger.info(result.message)
        else:
            logger.error(result.message)
        return 0 if result.ok else 1

    return 2


class HealthCheckWorker:
    """Background worker for health checks using threading and queue."""

    def __init__(self, manager: LlamaServerManager, result_queue: queue.Queue):
        self.manager = manager
        self.result_queue = result_queue
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def submit_instance_check(self, instance: dict[str, Any]) -> None:
        """Submit an instance for health check."""
        self.result_queue.put(("instance", instance))

    def submit_server_check(self) -> None:
        """Submit server for health check."""
        self.result_queue.put(("server", None))

    def _run(self) -> None:
        """Background thread main loop."""
        while not self._stop_event.is_set():
            try:
                item = self.result_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                item_type, data = item
                if item_type == "instance" and data:
                    status = self.manager.instance_status(data)
                    self.result_queue.put(("instance_result", status))
                elif item_type == "server":
                    status = self.manager.server_status()
                    self.result_queue.put(("server_result", status))
            except Exception as exc:
                self.result_queue.put(("error", str(exc)))
            finally:
                self.result_queue.task_done()


if __name__ == "__main__":
    raise SystemExit(main())
