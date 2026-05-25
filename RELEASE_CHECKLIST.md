# Release Checklist

Use this before tagging a public release.

## Preflight

- Update `CHANGELOG.md`.
- Update version in `pyproject.toml`.
- Confirm `README.md` quick start works on a clean checkout.
- Confirm `config.example.json` is valid and does not contain local paths.
- Confirm no local files are staged: `config.json`, `logs/`, `runtime/`, models,
  virtualenvs, caches, API keys.

## Checks

```bash
ruff check .
python3 -m pytest -q
python3 -m py_compile config.py llama_cpp_gui.py llama_server_manager.py ollama_proxy.py
python3 config.py --detect-runtime
```

## Tag

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## GitHub Release Notes

Include:

- What changed.
- Installation command.
- Known limitations.
- Upgrade notes for `config.json`, if any.
