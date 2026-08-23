"""Locates the repo root and the Garrigan fixture's source PDFs, mirroring
`server.repo_paths` — kept as its own tiny module rather than a
cross-package import, since both are single-function, ten-line concerns
scoped to their own package."""
from __future__ import annotations

from pathlib import Path


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "fixtures").is_dir() and (candidate / "packages").is_dir():
            return candidate
    raise RuntimeError("could not locate repo root (no ancestor has both fixtures/ and packages/)")


REPO_ROOT = find_repo_root()
FIXTURE_SOURCE_DIR = REPO_ROOT / "fixtures" / "garrigan-261-grove" / "source"
MAIN_SET_PDF = FIXTURE_SOURCE_DIR / "garrigan-main-set.pdf"
