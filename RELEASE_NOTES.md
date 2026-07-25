# Release Notes — llama.cpp Control Deck v1.1.0

**Release date:** 2026-07-25

## Highlights

v1.1.0 unifies server control around one service-based workflow shared by the
browser panel, the Tkinter GUI, and the CLI. It adds primary-service shortcuts,
brings the web launcher up to feature parity with the GUI launcher, and improves
Windows Git Bash Python discovery.

## Service-Based Workflow

- Every `llama-server` now starts and stops as a service from the shared
  `config.json` service list.
- A `primary_instance` setting identifies the default service used by dashboard
  actions, logs, copied URLs, and proxy defaults.
- The Tkinter GUI opens on **Services** and provides **Start primary**,
  **Restart primary**, **Open primary**, and **Copy OpenAI URL** actions.
- **Stop all** also cleans up a legacy single-server process from older versions.

## Launchers And Setup

- `start_web.sh` now supports `--setup`, `--help`, dependency checks, and the
  `LLAMA_CPP_PYTHON` override, matching `start_gui.sh`.
- Windows Git Bash launchers reject non-functional Python aliases and try the
  first runnable Python 3.10+ from `python3`, `python`, and `py`.
- Local virtual environments are detected in both `.venv/bin/python` and the
  Windows `.venv/Scripts/python.exe` layout.

## Interface Improvements

- The old Tkinter **Server** tab is now **Runtime and defaults** and no longer
  duplicates service start/stop controls.
- Logs fall back to the primary service when no table row is selected.
- Service table widths and long help banners were adjusted to avoid clipping.
- Household help and the README now describe the same service-based workflow.

## Configuration

- `config.example.json` includes `primary_instance`, `ui_language`, the managed
  release backend, and the rerank service shipped by current defaults.
- Existing configuration files remain compatible and are merged with the new
  defaults automatically.

## Upgrade Notes

No breaking changes. Existing `config.json` files remain compatible.

If you use the Web UI, refresh the page after upgrading to load the new CSS and
JavaScript assets.

## Files Changed

- `config.py`
- `control_web.py`
- `llama_cpp_gui.py`
- `static/control.css`
- `static/control.js`
- `templates/index.html`
- `start_gui.sh`
- `start_web.sh`
- `CHANGELOG.md`
- `README.md`
- `pyproject.toml`
- `config.example.json`
- `llama_server_manager.py`

## Compatibility

| Component | Minimum | Tested |
|-----------|---------|--------|
| Python | 3.10 | 3.12 |
| OS | Linux | Ubuntu 22.04/24.04 |
| Browser | any modern | Chromium 136, Firefox 139 |

---

Full changelog: [CHANGELOG.md](CHANGELOG.md)
