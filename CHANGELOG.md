# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GUI release-management controls for prebuilt `llama.cpp` binaries:
  **Check server version**, **Check updates**, and **Download llama-server**.
- `llama_cpp_release.py` helper for querying GitHub Releases, selecting a
  Linux backend asset, downloading/extracting it, writing a managed install
  manifest, and checking update status.
- Runtime backend selector for `auto`, `cpu`, `vulkan`, `rocm`, `openvino`,
  `sycl-fp16`, and `sycl-fp32`.

## [1.0.0] - 2026-05-25

### Added
- Project renamed and documented publicly as `llama.cpp Control Deck`.
- Full bilingual README with English documentation first and Russian
  documentation below.
- Connection pooling in Ollama proxy via FastAPI `lifespan` (single
  `httpx.AsyncClient` for the lifetime of the app).
- Background `HealthCheckWorker` (threading + queue) so the GUI no longer
  blocks on HTTP health checks.
- Graceful shutdown dialog when closing the GUI window (offers to stop
  running services).
- `pyproject.toml` with ruff, black, and pytest configuration.
- Structured logging in `llama_server_manager` (`logs/llama_server_manager.log`).
- Auto-detection of `llama-server` binary, Python runtime, and models
  directory via `LLAMA_CPP_BINARY`, `LLAMA_CPP_PYTHON`, `LLAMA_CPP_LIB_DIR`,
  `LLAMA_CPP_MODELS_DIR` environment variables.
- Runtime re-detection from the GUI and CLI, including Python, `llama-server`,
  working directory, and `LD_LIBRARY_PATH`.
- Beginner setup flow through `./start_gui.sh --setup` and the GUI
  **Beginner setup** button for creating `.venv` and installing dependencies.
- GUI buttons for installing Python dependencies from `requirements.txt` and
  system Tkinter/Python packages through the detected package manager.
- `config.example.json` template, `.gitignore`, `LICENSE`, `CONTRIBUTING.md`.
- `requirements-dev.txt` for development dependencies.

### Changed
- `start_gui.sh` now resolves Python via `LLAMA_CPP_PYTHON`, then local
  `.venv/bin/python`, then `python3` from `PATH`.
- File browse dialogs default to `~` instead of a hardcoded path.
- README rewritten with a clearer description of purpose and architecture.
- `llama_server_manager.py` now creates `logs/` before configuring file logging,
  so clean checkouts import and test correctly.

## [0.1.0] - initial

- Tkinter GUI with Server, Instances, Ollama proxy, GPU, Logs, Help tabs.
- Multi-instance support with per-instance state files in `runtime/instances/`.
- Profiles: chat, embeddings, rerank, multimodal, router.
- Ollama-compatible FastAPI proxy with chat, generate, embeddings endpoints
  and SSE streaming.
- CLI subcommands: `status`, `server-command`, `instance-command`,
  `proxy-command`, `devices`.
