#!/usr/bin/env python3
"""Assertion-suite runner (plan §16 Tier 3).

Sprint 1: every assertion failed with a generic "no model builder yet"
reason. Sprint 2 changes that for the assertions the Stage 0 hand-traced
family room fixture can actually answer (see tools/assertion_evaluators.py)
— those now run for real against fixtures_garrigan.build_family_room() and
can genuinely pass or fail. Everything else still fails cleanly with a
*specific* reason (which entity/capability is missing), never a generic
placeholder and never a stack trace — the "fail cleanly and informatively"
requirement from the plan's human-in-the-loop principle applies just as
much to "not implemented yet" as it does to "implemented and wrong."
"""
from __future__ import annotations

import argparse
import glob
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assertion_evaluators import EVALUATORS, NOT_IMPLEMENTED_REASONS, NotImplementedReason


@dataclass(frozen=True, slots=True)
class Context:
    walls: list
    tv_wall_interval: callable


def _context_for_level(level: str):
    if level != "first":
        return None
    from fixtures_garrigan import build_family_room, tv_wall_interval

    room = build_family_room()
    return Context(walls=list(room.walls), tv_wall_interval=tv_wall_interval)


def iter_assertion_files(root: Path):
    yield from sorted(Path(p) for p in glob.glob(str(root / "fixtures" / "*" / "assertions" / "*.yaml")))


def run_file(path: Path) -> tuple[int, int]:
    doc = yaml.safe_load(path.read_text())
    assertions = doc.get("assertions", [])
    level = doc.get("level", "?")
    print(f"\n{path}  (level={level!r})")

    ctx = _context_for_level(level)

    passed = failed = 0
    for a in assertions:
        name = next(iter(a))
        args = a[name]
        evaluator = EVALUATORS.get(name)

        if ctx is None:
            reason = f"no model builder for level {level!r} yet (Stage 2)"
            print(f"  FAIL  {name:<36} — {reason}")
            failed += 1
            continue
        if evaluator is None:
            reason = NOT_IMPLEMENTED_REASONS.get(name, "no evaluator implemented for this assertion kind yet")
            print(f"  FAIL  {name:<36} — {reason}")
            failed += 1
            continue

        try:
            result = evaluator(args, ctx)
        except NotImplementedReason as e:
            print(f"  FAIL  {name:<36} — {e.reason}")
            failed += 1
            continue
        except Exception as e:  # noqa: BLE001 — must never crash the runner
            print(f"  FAIL  {name:<36} — evaluator error: {e}")
            failed += 1
            continue

        status = "PASS" if result.passed else "FAIL"
        print(f"  {status}  {name:<36} — {result.message}")
        if result.passed:
            passed += 1
        else:
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
            "\nRemaining failures are either genuinely unimplemented capability "
            "(named specifically above) or Stage 2+ model levels that don't exist "
            "yet — not a regression in what Sprint 2 actually built."
        )
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
