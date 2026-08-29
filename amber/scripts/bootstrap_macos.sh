#!/usr/bin/env bash
# Bootstrap a clean Apple-silicon Mac for Amber development.
#
# Versions are intentionally NOT pinned here yet: M0 Gate A records the exact
# versions it proves, and those become the pins. Installing "latest" and then
# recording what you got is honest; inventing a pin before measuring is not.
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi

echo "Installing FFmpeg and COLMAP..."
brew install ffmpeg colmap

echo
echo "Brush and SplatTransform are not in Homebrew. Install them manually:"
echo "  Brush:          https://github.com/ArthurBrussee/brush"
echo "  SplatTransform: https://github.com/playcanvas/splat-transform"
echo

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev]'

echo
echo "Now run: ./scripts/doctor.sh"
echo "Record every reported version in docs/feasibility-results.md before Gate A."
