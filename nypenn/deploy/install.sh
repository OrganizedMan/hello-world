#!/usr/bin/env bash
#
# Install nypenn on a Raspberry Pi. Idempotent — safe to re-run after a pull.

set -euo pipefail

NYPENN_DIR="${NYPENN_DIR:-/home/pi/nypenn}"
SERVICE_USER="${SERVICE_USER:-pi}"

cd "$NYPENN_DIR"

# sqlite3 is not a Node dependency — the nightly backup shells out to it.
# Better to fail here than at 04:15 three weeks from now.
if ! command -v sqlite3 > /dev/null; then
  echo "sqlite3 is required for backups. Install it with: sudo apt install -y sqlite3" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and fill it in first." >&2
  exit 1
fi

# Dev dependencies are required here, not optional: tsc and vite live there
# and the build cannot run without them. Prune afterwards, once dist/ exists.
echo "==> Installing dependencies"
npm install --no-audit --no-fund

echo "==> Building"
npm run build

# A half-built tree starts cleanly and then fails at runtime, which is a far
# worse way to find out. Check the artifacts now.
echo "==> Verifying build output"
for artifact in shared/dist/index.js collector/dist/index.js \
                collector/dist/schema.sql server/dist/index.js \
                client/dist/index.html; do
  if [ ! -f "$artifact" ]; then
    echo "Build incomplete: $artifact is missing. Fix the build before deploying." >&2
    exit 1
  fi
done

echo "==> Removing build tooling"
npm prune --omit=dev

echo "==> Installing systemd units"
for unit in nypenn-collector.service nypenn-server.service \
            nypenn-backup.service nypenn-backup.timer; do
  sed -e "s#/home/pi/nypenn#$NYPENN_DIR#g" -e "s#^User=pi#User=$SERVICE_USER#" \
    "deploy/$unit" | sudo tee "/etc/systemd/system/$unit" > /dev/null
done

echo "==> Capping journald, so logs do not outgrow the SD card"
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/nypenn.conf > /dev/null <<'CONF'
[Journal]
SystemMaxUse=50M
RuntimeMaxUse=16M
CONF
sudo systemctl restart systemd-journald

sudo systemctl daemon-reload

# `enable --now` starts a stopped unit but is a no-op on a running one, so on
# every re-run after the first it left the old processes serving the previous
# build. You would pull a fix, watch the build succeed, and still be running
# the code you were trying to replace. restart is unconditional.
#
# reset-failed first: a unit parked in failed (by an earlier crash loop, say)
# stays there, and restart alone will not clear it.
echo "==> Starting services"
sudo systemctl enable nypenn-collector.service nypenn-server.service nypenn-backup.timer
sudo systemctl reset-failed nypenn-collector.service nypenn-server.service 2> /dev/null || true
sudo systemctl restart nypenn-collector.service nypenn-server.service
sudo systemctl restart nypenn-backup.timer

# The install is not finished because systemd said "started" -- it is finished
# when the port answers. Both of those have disagreed here before.
echo "==> Verifying the board is answering"
PORT="${PORT:-3005}"
for attempt in $(seq 1 15); do
  if curl -fsS --max-time 2 "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
    answered=yes
    break
  fi
  sleep 2
done

if [ "${answered:-no}" != yes ]; then
  echo
  echo "The server is not answering on localhost:$PORT after 30s." >&2
  echo "  systemctl status nypenn-server --no-pager" >&2
  echo "  journalctl -u nypenn-server -n 40 --no-pager" >&2
  exit 1
fi

echo
echo "==> Done. Collector and server are running."
echo "  Board:      http://localhost:$PORT"
echo "  Health:     curl -s localhost:$PORT/api/health"
echo
echo "  From another device, use the Pi's address rather than localhost, and"
echo "  type the http:// prefix explicitly -- browsers try https first for a"
echo "  bare host:port, and nothing is listening for TLS on $PORT."
