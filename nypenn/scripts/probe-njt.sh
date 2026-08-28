#!/usr/bin/env bash
#
# Ask NJT's getToken which request shape it accepts.
#
# The endpoint contract is the one part of this project never tested against
# the live API (see README, "Confirming the feed contract"). A 500 rather than
# a 404 means the endpoint is there and the handler is failing -- typically
# because the body is not in the form it binds to, which is a shape problem
# rather than a credentials one.
#
# Reads .env, so no secrets are typed on the command line. Prints status codes
# and error bodies only; a token is reported as received, never displayed.
#
#   ./scripts/probe-njt.sh

set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "No .env here. Run this from the nypenn directory." >&2; exit 1; }
set -a; . ./.env; set +a
: "${NJT_USERNAME:?NJT_USERNAME is not set in .env}"
: "${NJT_PASSWORD:?NJT_PASSWORD is not set in .env}"

BASE="${NJT_BASE_URL:-https://raildata.njtransit.com/api/TrainData}"
BASE="${BASE%/}"
body=$(mktemp); trap 'rm -f "$body"' EXIT

report() {
  local label="$1" code="$2"
  if [ "$code" = 200 ] && grep -qi 'token\|authorization' "$body"; then
    echo "  $label -> HTTP 200, token received.  <== this is the shape to use"
  else
    echo "  $label -> HTTP $code"
    if [ -s "$body" ]; then
      tr -d '\r' < "$body" | tr '\n' ' ' | cut -c1-220 | sed 's/^/       /'
      echo
    fi
  fi
}

echo "POST $BASE/getToken as ${NJT_USERNAME}"
echo

report "A urlencoded (what the collector sends today)" "$(curl -sS -o "$body" -w '%{http_code}' \
  --max-time 20 -X POST "$BASE/getToken" -H 'Accept: application/json' \
  --data-urlencode "username=$NJT_USERNAME" --data-urlencode "password=$NJT_PASSWORD")"

report "B multipart/form-data" "$(curl -sS -o "$body" -w '%{http_code}' \
  --max-time 20 -X POST "$BASE/getToken" -H 'Accept: application/json' \
  -F "username=$NJT_USERNAME" -F "password=$NJT_PASSWORD")"

report "C JSON" "$(curl -sS -o "$body" -w '%{http_code}' \
  --max-time 20 -X POST "$BASE/getToken" \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  --data "$(printf '{"username":"%s","password":"%s"}' "$NJT_USERNAME" "$NJT_PASSWORD")")"

report "D query string" "$(curl -sS -o "$body" -w '%{http_code}' \
  --max-time 20 -X POST -G "$BASE/getToken" -H 'Accept: application/json' \
  --data-urlencode "username=$NJT_USERNAME" --data-urlencode "password=$NJT_PASSWORD")"

echo
echo "Send me the labels and statuses. Do not paste a token."
