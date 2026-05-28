#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${LLAMA_CPP_PYTHON:-}"

if [[ -z "$PYTHON" ]]; then
  if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
  else
    PYTHON="$(command -v python3 || true)"
  fi
fi

if [[ -z "$PYTHON" ]]; then
  echo "Python runtime not found. Set LLAMA_CPP_PYTHON or install python3." >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/control_web.py" "$@"
