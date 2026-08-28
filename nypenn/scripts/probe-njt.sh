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

# Each probe truncates this first. curl does not write the file when it fails
# before receiving a response, and a stale body read as the current one is
# worse than no body at all.
probe() { : > "$body"; curl -sS -o "$body" -w '%{http_code}' --max-time 20 "$@" || echo 000; }

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

report "A urlencoded (what the collector sends today)" "$(probe -X POST "$BASE/getToken" -H 'Accept: application/json' \
  --data-urlencode "username=$NJT_USERNAME" --data-urlencode "password=$NJT_PASSWORD")"

report "B multipart/form-data" "$(probe -X POST "$BASE/getToken" -H 'Accept: application/json' \
  --form-string "username=$NJT_USERNAME" --form-string "password=$NJT_PASSWORD")"

report "C JSON" "$(probe -X POST "$BASE/getToken" \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  --data "$(printf '{"username":"%s","password":"%s"}' "$NJT_USERNAME" "$NJT_PASSWORD")")"

report "D query string" "$(probe -X POST -G "$BASE/getToken" -H 'Accept: application/json' \
  --data-urlencode "username=$NJT_USERNAME" --data-urlencode "password=$NJT_PASSWORD")"


# The shape probes above cannot tell two very different failures apart, because
# both plausibly answer "Missing user account.": the API not finding a field
# named `username` at all, and it finding one whose value matches no account.
# These two controls separate them, and neither can succeed by accident.
echo
echo "Controls, to read the error above:"

report "E no username field at all" "$(probe -X POST "$BASE/getToken" -H 'Accept: application/json' \
  --data-urlencode "password=$NJT_PASSWORD")"

report "F username present but certainly wrong" "$(probe -X POST "$BASE/getToken" -H 'Accept: application/json' \
  --data-urlencode "username=nnnnnnnn-no-such-account" --data-urlencode "password=$NJT_PASSWORD")"

cat <<'GUIDE'

How to read E and F against A:
  A == F, and E differs   -> the field name is right; that account is not found.
                             Check the username at developer.njtransit.com --
                             it is the portal username, which is often not the
                             email address -- and that the account is approved
                             for the rail data API.
  A == E                  -> the API never saw our username field. The field
                             name in NjtClient is wrong; send this output.
GUIDE

echo
echo "Send me the labels and statuses. Do not paste a token."
