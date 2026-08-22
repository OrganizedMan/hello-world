"""Where the drawing set lives.

The A-1 sheet used to be supplied out of band through ``HEARTHVIEW_A1_PDF``, so
every test that needed it skipped wherever the file was absent -- 32 of them, CI
included, which is how the whole-floor path stayed unchecked. The drawings are
committed now, so the environment variable becomes an override for working
against a different revision rather than the only way to run anything.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DRAWINGS = REPO / "drawings"

A1_SHEET = DRAWINGS / "Garrigan-261-Grove-Street-2026-08-17.pdf"
ATTIC_OPTION_SHEET = DRAWINGS / "Garrigan-261-Grove-Street-attic-idea.pdf"

# 1-based page numbers within A1_SHEET, keyed by the sheet number printed on it.
# Every sheet carries both an existing and a proposed view; the extractor picks
# the proposed one.
SHEET_PAGES = {
    "A-0": 1,   # basement
    "A-1": 2,   # first floor
    "A-2": 3,   # second floor
    "A-3": 4,   # third floor / attic
}


def a1_source() -> Path | None:
    """The drawing to work from, or None when nothing readable is configured.

    ``HEARTHVIEW_A1_PDF`` still wins when set, so a different revision of the
    set can be pointed at without editing anything.
    """
    override = os.environ.get("HEARTHVIEW_A1_PDF")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() else None
    return A1_SHEET if A1_SHEET.is_file() else None
