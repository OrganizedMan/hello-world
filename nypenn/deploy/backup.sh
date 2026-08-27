#!/usr/bin/env bash
#
# Back up the departure history.
#
# `departures` is the only unrecoverable thing here: it can only be rebuilt by
# waiting weeks for the collector to see those trains again. Everything else
# in this project can be rebuilt from git in a minute.
#
# Uses sqlite3's .backup rather than cp, which is the difference between a
# consistent snapshot and a torn file: the collector writes while this runs.

set -euo pipefail

NYPENN_DIR="${NYPENN_DIR:-/home/pi/nypenn}"
DB="${NYPENN_DB:-$NYPENN_DIR/data/nypenn.db}"
DEST="${BACKUP_DIR:-$NYPENN_DIR/backups}"
KEEP="${BACKUP_KEEP:-7}"

if [ ! -f "$DB" ]; then
  echo "No database at $DB — nothing to back up." >&2
  exit 1
fi

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d)"
OUT="$DEST/nypenn-$STAMP.db"

sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"

# Prove the backup is readable before trusting it. An unverified backup is
# not a backup, and a silent failure here is only discovered when it is too
# late to matter.
ROWS=$(zcat "$OUT.gz" > /tmp/nypenn-verify.db && \
       sqlite3 /tmp/nypenn-verify.db "SELECT COUNT(*) FROM departures;")
rm -f /tmp/nypenn-verify.db

if [ "$ROWS" -eq 0 ]; then
  echo "Backup verified empty — departures table has no rows. Check the collector." >&2
  exit 1
fi

# Keep the newest N and drop the rest.
ls -1t "$DEST"/nypenn-*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "Backed up $ROWS departures to $OUT.gz"

# Optional off-Pi copy: set BACKUP_REMOTE to an rsync target and a card
# failure stops being able to take the history with it.
if [ -n "${BACKUP_REMOTE:-}" ]; then
  rsync -a "$OUT.gz" "$BACKUP_REMOTE" && echo "Mirrored to $BACKUP_REMOTE"
fi
