#!/usr/bin/env bash
#
# One getToken call, reported in full.
#
# getToken is capped at 10 calls per day and the account is locked out until
# midnight past that -- so this deliberately makes a single call and prints
# everything it got back, rather than trying variations. The request shape is
# no longer in question: multipart/form-data, per NJTRANSIT_RailData_API_V2.
#
# Reads .env, so no credential is typed at a prompt. A token is reported as
# received and never printed, so the output is safe to paste.
#
#   ./scripts/probe-njt.sh                 # the NJT_BASE_URL from .env
#   ./scripts/probe-njt.sh test            # NJT's test environment
#   ./scripts/probe-njt.sh https://...     # an explicit base URL

set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "No .env here. Run this from the nypenn directory." >&2; exit 1; }
set -a; . ./.env; set +a
: "${NJT_USERNAME:?NJT_USERNAME is not set in .env}"
: "${NJT_PASSWORD:?NJT_PASSWORD is not set in .env}"

case "${1:-}" in
  '')     BASE="${NJT_BASE_URL:-https://raildata.njtransit.com/api/TrainData}" ;;
  test)   BASE="https://testraildata.njtransit.com/api/TrainData" ;;
  prod)   BASE="https://raildata.njtransit.com/api/TrainData" ;;
  *)      BASE="$1" ;;
esac
BASE="${BASE%/}"

echo "POST $BASE/getToken"
echo "  username: $NJT_USERNAME"
echo "  password: ${#NJT_PASSWORD} characters"
echo
echo "This spends one of the account's 10 getToken calls for today."
echo

body=$(mktemp); trap 'rm -f "$body"' EXIT
code=$(curl -sS -o "$body" -w '%{http_code}' --max-time 20 \
  -X POST "$BASE/getToken" -H 'accept: text/plain' \
  --form-string "username=$NJT_USERNAME" \
  --form-string "password=$NJT_PASSWORD") || code=000

echo "HTTP $code"
if grep -qi 'usertoken\|authorization' "$body" && ! grep -qi '"UserToken": *""' "$body"; then
  echo 'Token received. These credentials work against this base URL.'
  echo 'Set NJT_BASE_URL to it in .env if it is not already, and restart the collector.'
else
  tr -d '\r' < "$body" | tr '\n' ' ' | cut -c1-300 | sed 's/^/  /'
  echo
  cat <<'GUIDE'

Reading it:
  "Missing user account."   The API cannot find this account. The request shape
                            is right, so this is the account itself: check that
                            NJT_USERNAME is the portal username rather than the
                            email you sign in with, and that these credentials
                            match this environment -- NJT issues separate Test
                            and Production sets. Try: ./scripts/probe-njt.sh test
  "Authenticated": "False"  The account exists; the password is wrong.
  "Daily usage limit..."    Locked out until midnight. Stop and wait.
GUIDE
fi
