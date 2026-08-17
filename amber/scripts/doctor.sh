#!/usr/bin/env bash
# Record a doctor report for the feasibility results. Run this first on the
# target Mac, before any Gate A work.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p docs
amber doctor
amber doctor --json > docs/doctor-report.json || true
echo
echo "Wrote docs/doctor-report.json"
