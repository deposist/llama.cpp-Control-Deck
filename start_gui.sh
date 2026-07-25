#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETUP=0
GUI_ARGS=()

python_is_usable() {
  local candidate="$1"
  [[ -n "$candidate" && -x "$candidate" ]] &&
    "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1
}

find_system_python() {
  local command_name candidate
  for command_name in python3 python py; do
    if command -v "$command_name" >/dev/null 2>&1; then
      candidate="$(command -v "$command_name")"
      if python_is_usable "$candidate"; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

find_venv_python() {
  local candidate
  for candidate in "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/.venv/Scripts/python.exe"; do
    if python_is_usable "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

usage() {
  cat <<'EOF'
Usage: start_gui.sh [--setup] [GUI options]

Starts the llama.cpp Control Deck GUI.

Beginner path:
  ./start_gui.sh --setup   Create/update .venv, install requirements, then start.

Environment variables:
  LLAMA_CPP_PYTHON       Path to Python interpreter (overrides default)
  LLAMA_CPP_BOOTSTRAP_PYTHON
                          Python used for --setup (default: first working Python in PATH)
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
    BOOTSTRAP_PYTHON="$(find_system_python || true)"
  fi
  if ! python_is_usable "$BOOTSTRAP_PYTHON"; then
    echo "Python 3.10+ not found. Set LLAMA_CPP_BOOTSTRAP_PYTHON to a working interpreter." >&2
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
  PYTHON="$(find_venv_python || true)"
  if [[ -z "$PYTHON" ]]; then
    echo "Virtual environment Python was not created in $SCRIPT_DIR/.venv." >&2
    exit 1
  fi
  "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
  export LLAMA_CPP_PYTHON="$PYTHON"
else
  # Python runtime resolution priority:
  #   1. LLAMA_CPP_PYTHON environment variable
  #   2. local .venv (POSIX or Windows layout)
  #   3. first working python3, python, or py command in PATH
  PYTHON="${LLAMA_CPP_PYTHON:-}"

  if [[ -z "$PYTHON" ]]; then
    PYTHON="$(find_venv_python || true)"
  fi
  if [[ -z "$PYTHON" ]]; then
    PYTHON="$(find_system_python || true)"
  fi
fi

if ! python_is_usable "$PYTHON"; then
  echo "Python 3.10+ runtime not found. Set LLAMA_CPP_PYTHON to a working interpreter." >&2
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
