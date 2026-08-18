#!/usr/bin/env python3
"""Assertion-suite runner (plan §16 Tier 3, Sprint 1 item 5).

Every assertion in fixtures/*/assertions/*.yaml currently reports FAILED
with a clear, specific reason instead of a stack trace: there is no model
builder yet — that arrives with the constraint solver in Sprint 2. This
is deliberate. The plan calls these files "the project's north star,
written out now, failing" — the harness must fail *cleanly and
informatively*, never crash, and never silently pass.

Once a real model builder exists, each assertion kind below gets a real
implementation and this file stops being a glorified counter.
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import yaml

NOT_YET_IMPLEMENTED = "no model builder implemented yet (Sprint 2)"


def iter_assertion_files(root: Path):
    yield from sorted(Path(p) for p in glob.glob(str(root / "fixtures" / "*" / "assertions" / "*.yaml")))


def run_file(path: Path) -> tuple[int, int]:
    doc = yaml.safe_load(path.read_text())
    assertions = doc.get("assertions", [])
    level = doc.get("level", "?")
    print(f"\n{path}  (level={level!r})")

    passed = 0
    failed = 0
    for a in assertions:
        name = next(iter(a))
        # Every assertion is unimplemented at Sprint 1: fail with a named,
        # specific reason rather than skip silently or raise.
        print(f"  FAIL  {name:<36} — {NOT_YET_IMPLEMENTED}")
        failed += 1
    return passed, failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", type=Path)
    args = ap.parse_args()

    files = list(iter_assertion_files(args.root))
    if not files:
        print("No assertion files found under fixtures/*/assertions/*.yaml", file=sys.stderr)
        return 2

    total_passed = total_failed = 0
    for path in files:
        p, f = run_file(path)
        total_passed += p
        total_failed += f

    total = total_passed + total_failed
    print(f"\n{total_passed} passed, {total_failed} failed, {total} total")
    if total_failed:
        print(
            "\nThis is the expected state at Sprint 1: the assertion suite runs "
            "cleanly and fails informatively because the deterministic geometry "
            "core does not exist yet. It should turn green incrementally as "
            "Sprint 2 builds the constraint solver and wall/opening authoring."
        )
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
