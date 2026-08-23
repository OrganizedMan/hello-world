#!/usr/bin/env bash
# Installs all pdf3d-* packages in dependency order.
#
# `pip install -e packages/*/` (alphabetical glob order) does NOT work:
# "constraints" sorts before "core_schema" alphabetically but depends on
# it, so pip fails on that step -- and historically (before these packages
# were namespaced pdf3d-*) failed *silently*, by falling back to an
# unrelated public PyPI package that happened to share the bare name
# "constraints". This script installs in actual dependency order instead
# of relying on directory sort order ever matching it by luck.
set -euo pipefail
cd "$(dirname "$0")/.."

for pkg in units core_schema ingest extract store constraints geometry validate fixtures_garrigan server; do
  echo "Installing packages/$pkg..."
  pip install -e "packages/$pkg"
done

echo
echo "All pdf3d-* packages installed. Next: cd packages/ui && npm install"
