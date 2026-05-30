# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-05-30

### Fixed
- **Web UI performance**: synchronous file I/O (`read_text`, `tail_file`) in FastAPI
  endpoints now runs in a threadpool to prevent blocking the async event loop.
- **Tkinter reliability**: removed the unused `HealthCheckWorker` background thread
  that started on every `refresh_status()` tick, leaked queue memory, and never
  processed results.
- **Web UI XSS safety**: `renderInstances` rewritten to use DOM API
  (`createElement` + `textContent`) instead of `innerHTML` with unsanitised
  `config.json` strings.
- **Web UI request flooding**: `refresh()` now drops overlapping poll requests
  instead of queueing unlimited concurrent `/api/state` calls.
- **Accessibility contrast**: `.warning` text colour changed from `#9a6700` to
  `#6e5000` to meet WCAG AA (5.96:1).
- **HTML `lang` attribute**: default changed from hardcoded `ru` to `en`; the
  JavaScript i18n system still switches it dynamically based on user selection.

### Changed
- README now documents the web control panel in the Russian section and adds
  security/troubleshooting notes for both languages.

## [1.0.1] - 2026-05-28

### Added
- Local FastAPI web control panel (`control_web.py`) with a browser-based
  beginner flow, RU/EN language toggle, status polling, validation warnings,
  logs/devices/release endpoints, and no Electron/Node dependency.
- Dedicated web UI **Runtime & updates** section for `llama-server` release
  checks/downloads, including background download status and progress log
  polling instead of placing update controls in the logs area.
- Web UI **Services** management for adding, editing, validating, duplicating,
  deleting, starting, stopping, and restarting configured `instances` without
  editing `config.json` by hand.
- Server-side **Browse** path picker in the web UI for Python, `llama-server`,
  working/library directories, GGUF models, MMProj files, model directories,
  and preset files.
- `start_web.sh` launcher and `llama-control-deck-web` entry point for the new
  web UI while keeping the Tkinter GUI as a legacy fallback.
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
- `pyproject.toml` packaging metadata.
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
- `config.example.json` template, `.gitignore`, and `LICENSE`.

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
