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
sudo systemctl enable --now nypenn-collector.service nypenn-server.service
sudo systemctl enable --now nypenn-backup.timer

echo
echo "==> Done. Collector and server are running."
echo "  Check it is collecting:  curl -s localhost:${PORT:-3005}/api/health"
echo "  Open the board:          http://localhost:${PORT:-3005}"
