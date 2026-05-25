#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETUP=0
GUI_ARGS=()

usage() {
  cat <<'EOF'
Usage: start_gui.sh [--setup] [GUI options]

Starts the llama.cpp Control Deck GUI.

Beginner path:
  ./start_gui.sh --setup   Create/update .venv, install requirements, then start.

Environment variables:
  LLAMA_CPP_PYTHON       Path to Python interpreter (overrides default)
  LLAMA_CPP_BOOTSTRAP_PYTHON
                          Python used for --setup (default: python3 in PATH)
  LLAMA_CPP_BINARY       Path to llama-server binary
  LLAMA_CPP_CWD          Working directory for llama-server
  LLAMA_CPP_LIB_DIR      Directory with llama.cpp shared libraries
  LLAMA_CPP_MODELS_DIR   Directory containing .gguf models
  LLAMA_CPP_SEARCH_ROOTS Extra runtime search roots separated by ':'

Useful options:
  -h, --help              Show this help.
  --setup                 Create/update local .venv and install Python dependencies.
  --geometry GEOMETRY     Initial Tk window size, for example 1180x820.
  --skip-device-refresh   Do not run llama-server --list-devices at startup.

All options except -h/--help and --setup are passed to llama_cpp_gui.py.
EOF
}

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      usage
      exit 0
      ;;
    --setup|--beginner-setup)
      SETUP=1
      ;;
    *)
      GUI_ARGS+=("$arg")
      ;;
  esac
done

if [[ "$SETUP" -eq 1 ]]; then
  BOOTSTRAP_PYTHON="${LLAMA_CPP_BOOTSTRAP_PYTHON:-}"
  if [[ -z "$BOOTSTRAP_PYTHON" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      BOOTSTRAP_PYTHON="$(command -v python3)"
    else
      echo "python3 not found. Install python3 first." >&2
      exit 1
    fi
  fi
  if [[ ! -x "$BOOTSTRAP_PYTHON" ]]; then
    echo "Bootstrap Python is not executable: $BOOTSTRAP_PYTHON" >&2
    exit 1
  fi
  echo "Creating/updating local virtual environment: $SCRIPT_DIR/.venv"
  if ! "$BOOTSTRAP_PYTHON" -m venv "$SCRIPT_DIR/.venv"; then
    cat >&2 <<'EOF'
Could not create .venv. Install the venv package and retry:
  Debian/Ubuntu: sudo apt install python3-venv python3-pip
  Fedora:        sudo dnf install python3 python3-pip
  Arch:          sudo pacman -S python python-pip
EOF
    exit 1
  fi
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
  "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
  export LLAMA_CPP_PYTHON="$PYTHON"
else
  # Python runtime resolution priority:
  #   1. LLAMA_CPP_PYTHON environment variable
  #   2. ./.venv/bin/python (local virtual environment)
  #   3. python3 in PATH
  PYTHON="${LLAMA_CPP_PYTHON:-}"

  if [[ -z "$PYTHON" ]]; then
    if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
      PYTHON="$SCRIPT_DIR/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON="$(command -v python3)"
    fi
  fi
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "Python runtime not found. Set LLAMA_CPP_PYTHON or install python3." >&2
  exit 1
fi

if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  echo "Tkinter is not available in this Python runtime. Install python3-tk." >&2
  exit 1
fi

if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import fastapi
import httpx
import psutil
import uvicorn
PY
then
  cat >&2 <<EOF
Python dependencies are not installed for:
  $PYTHON

For beginners, run:
  ./start_gui.sh --setup

Or install manually:
  "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
EOF
  exit 1
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" "$SCRIPT_DIR/llama_cpp_gui.py" "${GUI_ARGS[@]}"
