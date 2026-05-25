# Contributing

Thanks for considering a contribution to `llama.cpp Control Deck`.

This project is intentionally small: a Tkinter GUI, a process manager, a
FastAPI proxy, and plain JSON configuration. Contributions are welcome when
they keep that shape understandable.

## Good First Contributions

- Improve setup instructions for a Linux distribution.
- Add a troubleshooting note with a real error message and fix.
- Add tests for config/runtime detection.
- Improve CLI output or error messages.
- Document a client integration, for example Open WebUI, Continue, or a RAG app.

## Development Setup

```bash
git clone https://github.com/deposist/llama.cpp-Control-Deck.git
cd llama.cpp-Control-Deck

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Linux is the supported platform. The GUI uses Tkinter; the proxy uses FastAPI.

## Checks

Run these before opening a pull request:

```bash
ruff check .
python3 -m pytest -q
python3 -m py_compile config.py llama_cpp_gui.py llama_server_manager.py ollama_proxy.py
```

For process-manager changes, also inspect generated commands:

```bash
python3 llama_server_manager.py status
python3 llama_server_manager.py server-command
python3 llama_server_manager.py instance-command chat-8081
python3 llama_server_manager.py proxy-command
```

## Pull Request Guidelines

- Keep each PR focused on one topic.
- Explain the user-facing behavior change.
- Update `README.md` when setup, configuration, or workflows change.
- Add or update tests for config, command generation, proxy mapping, or other
  logic that can run without a GPU.
- Do not commit local config, logs, runtime state, models, API keys, or large
  generated files.

## Issue Reports

For bugs, please include:

- OS and desktop environment.
- Python version.
- `llama.cpp` commit or release, plus build flags such as CUDA/CPU-only.
- Output of `python3 config.py --detect-runtime`.
- Output of `python3 llama_server_manager.py status`.
- Relevant log lines from `logs/`.
- Steps to reproduce.

## Security

Do not paste real API keys, private hostnames, production model paths, or logs
containing sensitive user prompts into issues. See `SECURITY.md`.
