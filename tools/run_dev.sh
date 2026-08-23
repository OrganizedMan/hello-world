#!/usr/bin/env bash
# Runs the Stage 0 product locally: the FastAPI backend (packages/server)
# and the Vite/React/Three.js frontend (packages/ui) together. Ctrl-C
# stops both. See packages/README.md for first-time setup.
set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Fail fast with a clear message on a stale install (e.g. a git pull that
# added a new package) instead of letting uvicorn's reloader crash-loop
# silently in the background while vite spews proxy-timeout errors at
# every request.
if ! PYTHONPATH="packages/server/src" python3 -c "import server" 2>/tmp/pdf3d_import_check.log; then
  echo
  echo "Backend failed to import 'server' -- your installed packages are probably out of date."
  echo "Run ./tools/install_dev.sh first, then re-run this script."
  echo
  echo "Import error:"
  cat /tmp/pdf3d_import_check.log
  exit 1
fi

cleanup() {
  echo
  echo "Stopping..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python3 -m uvicorn server:app --app-dir packages/server/src \
  --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

(cd packages/ui && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

echo
echo "Backend:  http://127.0.0.1:$BACKEND_PORT/api/health"
echo "Frontend: http://127.0.0.1:$FRONTEND_PORT/"
echo "Ctrl-C to stop both."
echo

wait
