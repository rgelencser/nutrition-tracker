#!/usr/bin/env bash
# NutriTool launcher (Linux, and macOS if run directly). See README.md "Quick Start".
# On macOS, double-clicking run.command (a thin wrapper around this script) is
# usually more convenient -- see README for the Gatekeeper note there.
set -u
cd "$(dirname "$0")"

echo "============================================"
echo " NutriTool - starting local server..."
echo "============================================"
echo

# --- locate a Python 3 interpreter (try python3, then python) ---
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "[ERROR] Python 3 was not found on this computer."
  echo
  echo "Install it from https://www.python.org/downloads/ and try again."
  echo "(On Linux, your distro's package manager also works, e.g.:"
  echo "  sudo apt install python3 python3-pip)"
  echo
  read -r -p "Press Enter to close..." _ || true
  exit 1
fi

echo "Using Python: $PY ($("$PY" --version 2>&1))"

# --- check dependencies; only install if something's missing (no silent internet use) ---
if "$PY" -c "import flask" >/dev/null 2>&1; then
  echo "Required packages already installed -- skipping install."
else
  echo "Installing required packages (one-time, needs internet)..."
  if ! "$PY" -m pip install -r requirements.txt; then
    echo
    echo "[ERROR] Failed to install required packages."
    echo "Check your internet connection and try again, or run manually:"
    echo "  $PY -m pip install -r requirements.txt"
    echo
    read -r -p "Press Enter to close..." _ || true
    exit 1
  fi
fi

PORT="${PORT:-5000}"

port_open() {
  (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null && { exec 3<&- 3>&- 2>/dev/null; return 0; } || return 1
}

# --- refuse to start if the port is already taken, with a clear message ---
if port_open; then
  echo
  echo "[ERROR] Port ${PORT} is already in use on this computer."
  echo "Another program (maybe another copy of NutriTool) is already using it."
  echo "Close that program, or run with a different port:"
  echo "  PORT=5050 ./run.sh"
  echo
  read -r -p "Press Enter to close..." _ || true
  exit 1
fi

# --- open the browser automatically once the server responds (no premature "can't be reached" flash) ---
open_when_ready() {
  local url="http://localhost:${PORT}/"
  local i
  for i in $(seq 1 60); do
    if port_open; then
      if [ "$(uname -s)" = "Darwin" ]; then
        open "$url" >/dev/null 2>&1
      elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1
      else
        echo "NutriTool is ready -- open this in your browser: $url"
      fi
      return
    fi
    sleep 0.5
  done
  echo "NutriTool didn't respond in time -- open this in your browser once it's ready: $url"
}
open_when_ready &

echo
echo "Starting server... your browser will open automatically once it's ready."
echo "(Leave this window open while using NutriTool. Close it, or press Ctrl+C, to stop the server.)"
echo

PORT="$PORT" "$PY" app.py
EXITCODE=$?

if [ "$EXITCODE" -ne 0 ]; then
  echo
  echo "[ERROR] NutriTool's server stopped unexpectedly (exit code $EXITCODE)."
  echo "If this keeps happening, try running it manually to see the full error:"
  echo "  $PY app.py"
  echo
  read -r -p "Press Enter to close..." _ || true
fi
