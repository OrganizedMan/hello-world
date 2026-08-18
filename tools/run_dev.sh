#!/usr/bin/env bash
# Runs the Stage 0 product locally: the FastAPI backend (packages/server)
# and the Vite/React/Three.js frontend (packages/ui) together. Ctrl-C
# stops both. See packages/README.md for first-time setup.
set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

cleanup() {
  echo
  echo "Stopping…"
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
