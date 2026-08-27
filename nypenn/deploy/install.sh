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

echo "==> Installing dependencies"
npm ci --omit=dev || npm install

echo "==> Building"
npm run build

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
echo "Done. Check it is collecting:"
echo "  systemctl status nypenn-collector"
echo "  curl -s localhost:\${PORT:-3005}/api/health"
