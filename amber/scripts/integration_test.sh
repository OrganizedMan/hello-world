#!/usr/bin/env bash
# Run the test suite, then optionally a full pipeline against a real video.
#
#   ./scripts/integration_test.sh                     # tests only
#   ./scripts/integration_test.sh /path/to/clip.MOV   # tests + full run
#
# Keep private captures outside this repository. Pass the path; do not copy the
# file in.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== unit tests =="
python -m pytest tests/unit -q

echo
echo "== integration tests =="
python -m pytest tests/integration -q

VIDEO="${1:-}"
if [[ -z "$VIDEO" ]]; then
  echo
  echo "No video given; skipping the full pipeline run."
  echo "Tool-dependent tests skip themselves when the toolchain is absent."
  exit 0
fi

if [[ ! -f "$VIDEO" ]]; then
  echo "No such video: $VIDEO" >&2
  exit 2
fi

echo
echo "== doctor =="
amber doctor || { echo "Toolchain incomplete; cannot run the pipeline." >&2; exit 1; }

LIBRARY="$(mktemp -d)/amber-library"
mkdir -p "$LIBRARY"

echo
echo "== process =="
amber process "$VIDEO" --library "$LIBRARY" --title "Integration run"

SCENE="$(find "$LIBRARY" -mindepth 1 -maxdepth 1 -type d | head -n1)"

echo
echo "== inspect + verify =="
amber inspect "$SCENE" --verify

echo
echo "== prune dry run =="
amber prune "$SCENE" --dry-run

echo
echo "== prune working =="
amber prune "$SCENE" --working

echo
echo "== verify archival core survived =="
amber inspect "$SCENE" --verify

echo
echo "Scene: $SCENE"
