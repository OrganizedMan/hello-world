"""Locates the repo root regardless of where the server process is
started from, so `pip install -e` editable installs and any working
directory both find the fixture PDFs."""
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
