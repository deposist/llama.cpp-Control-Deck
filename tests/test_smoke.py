"""Smoke tests: imports work and core helpers behave as expected.

These tests do not require llama-server or a GPU.
"""

from __future__ import annotations

import json
import sys

import pytest


def test_imports():
    """All public modules import without side effects."""
    import config  # noqa: F401
    import llama_server_manager  # noqa: F401
    import ollama_proxy  # noqa: F401


def test_config_defaults_loadable():
    import config

    cfg = config.load_config()
    assert "profiles" in cfg
    assert "instances" in cfg
    assert "ollama_proxy" in cfg
    for name in config.PROFILE_ORDER:
        assert name in cfg["profiles"]


def test_runtime_detection_returns_expected_keys():
    import config

    detected = config.detect_runtime_paths({}, prefer_existing=False, deep_search=False)
    for key in config.RUNTIME_KEYS:
        assert key in detected
    assert config.runtime_value_is_usable("python_path", detected["python_path"])


def test_runtime_autodetect_repairs_stale_python_path():
    import config

    cfg = {"python_path": "/missing/python"}
    config.apply_runtime_autodetect(cfg, override=False, deep_search=False)
    assert cfg["python_path"] == sys.executable or config.runtime_value_is_usable(
        "python_path", cfg["python_path"]
    )


def test_merge_defaults():
    from config import DEFAULT_CONFIG, merge_defaults

    user_cfg = {"active_profile": "embeddings"}
    merged = merge_defaults(user_cfg, DEFAULT_CONFIG)
    assert merged["active_profile"] == "embeddings"
    # Default keys preserved
    assert "profiles" in merged
    assert "ollama_proxy" in merged


def test_profile_model_name_fallback():
    from config import profile_model_name

    assert profile_model_name({"alias": "test-alias"}) == "test-alias"
    assert profile_model_name({"model_path": "/x/foo.gguf"}) == "foo"
    assert profile_model_name({}) == "local-llama"


def test_format_uptime():
    from llama_server_manager import format_uptime

    assert format_uptime(0) == "0s"
    assert format_uptime(45) == "45s"
    assert format_uptime(125) == "2m 5s"
    assert format_uptime(3725) == "1h 2m 5s"


def test_build_server_command_requires_binary():
    from llama_server_manager import LlamaServerManager

    config = {
        "llama_server_binary": "",
        "active_profile": "chat",
        "profiles": {"chat": {"profile_type": "chat", "model_path": "/x/m.gguf", "port": 8081}},
    }
    manager = LlamaServerManager(config)
    with pytest.raises(ValueError, match="llama_server_binary"):
        manager.build_server_command()


def test_build_server_command_basic():
    from llama_server_manager import LlamaServerManager

    config = {
        "llama_server_binary": "/usr/bin/llama-server",
        "active_profile": "chat",
        "profiles": {
            "chat": {
                "profile_type": "chat",
                "model_path": "/models/test.gguf",
                "host": "127.0.0.1",
                "port": 8081,
                "alias": "test-model",
                "n_ctx": 4096,
            }
        },
    }
    manager = LlamaServerManager(config)
    cmd = manager.build_server_command()
    assert cmd[0] == "/usr/bin/llama-server"
    assert "--model" in cmd
    assert "/models/test.gguf" in cmd
    assert "--port" in cmd
    assert "8081" in cmd


def test_proxy_options_mapping():
    from ollama_proxy import options_to_openai

    payload = {
        "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 256},
    }
    mapped = options_to_openai(payload)
    assert mapped["temperature"] == 0.7
    assert mapped["top_p"] == 0.9
    assert mapped["max_tokens"] == 256


def test_config_example_json_is_valid():
    """config.example.json must be parseable and contain required keys."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "config.example.json"
    with path.open() as fh:
        data = json.load(fh)
    assert "profiles" in data
    assert "instances" in data
    assert "ollama_proxy" in data
