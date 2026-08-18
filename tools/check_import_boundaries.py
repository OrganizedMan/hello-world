#!/usr/bin/env python3
"""Import-boundary lint (plan §15).

The deterministic/probabilistic separation is enforced here, not by
convention: `propose` (AI proposers), `render_blender`, and `viewer` must
never import `geometry` or `constraints` — the deterministic geometry
core. Today this passes vacuously, since none of those packages exist
yet; it starts doing real work the moment Stage 1+ adds them, and CI
should run it on every commit from here on so the boundary can never
regress silently.
"""
from __future__ import annotations

import ast
import pathlib
import sys

FORBIDDEN: dict[str, set[str]] = {
    "propose": {"geometry", "constraints"},
    "render_blender": {"geometry", "constraints"},
    "viewer": {"geometry", "constraints"},
}


def imported_top_level_names(py_file: pathlib.Path) -> set[str]:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    violations: list[str] = []
    checked_packages: list[str] = []

    for pkg_name, forbidden in FORBIDDEN.items():
        pkg_src = root / "packages" / pkg_name / "src"
        if not pkg_src.exists():
            continue
        checked_packages.append(pkg_name)
        for py_file in pkg_src.rglob("*.py"):
            hit = imported_top_level_names(py_file) & forbidden
            if hit:
                violations.append(
                    f"{py_file.relative_to(root)}: imports forbidden module(s) {sorted(hit)}"
                )

    if violations:
        print("Import-boundary violations (plan §15):")
        for v in violations:
            print(f"  {v}")
        return 1

    if checked_packages:
        print(f"Import-boundary check passed for: {', '.join(checked_packages)}")
    else:
        print(
            "Import-boundary check passed (vacuously — none of propose/"
            "render_blender/viewer exist yet)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
