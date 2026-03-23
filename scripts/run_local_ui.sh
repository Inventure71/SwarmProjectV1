#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Run the Hydra local Tk UI on the current machine.

Usage:
  ./scripts/run_local_ui.sh [options]

Options:
  --repo-root <path>        Repo root (default: auto-detected)
  --python <binary>         Python binary (default: python3)
  --background              Run in background and write logs to local/ui.log
  -h, --help                Show this help
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="python3"
BACKGROUND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --background) BACKGROUND=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

LOCAL_DIR="$REPO_ROOT/local"
if [[ ! -d "$LOCAL_DIR" ]]; then
  echo "local directory not found: $LOCAL_DIR" >&2
  exit 1
fi

if [[ "$BACKGROUND" == "1" ]]; then
  cd "$LOCAL_DIR"
  nohup "$PYTHON_BIN" frontend_app.py > ui.log 2>&1 < /dev/null &
  echo $! > ui.pid
  echo "UI started in background (pid=$(cat ui.pid))"
  echo "log: $LOCAL_DIR/ui.log"
else
  cd "$LOCAL_DIR"
  exec "$PYTHON_BIN" frontend_app.py
fi
