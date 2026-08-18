"""Golden regression for the kitchen island footprint (plan Appendix A's
original probe, reproduced through the real pipeline)."""
from __future__ import annotations

from pathlib import Path

from ingest import PyMuPdfBackend
from extract import (
    TextClass,
    classify_text_line,
    harvest_paths,
    harvest_text_lines,
    reassemble_lines,
)
from extract.casework import find_casework_footprints
from units import NM_PER_INCH, ParseError, parse_feet_inches

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/garrigan-261-grove/source/garrigan-main-set.pdf"
NOMINAL_IN_PER_PT = 12 / 18


def _footprints():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        paths = harvest_paths(h, 1, suppress_text_masks=False)
        text_lines = reassemble_lines(harvest_text_lines(h, 1))

    dim_lines = [l for l in text_lines if classify_text_line(l) == TextClass.DIMENSION_STRING]
    lines_and_values = []
    for line in dim_lines:
        try:
            lines_and_values.append((line, parse_feet_inches(line.text.strip())))
        except ParseError:
            continue
    return find_casework_footprints(paths, lines_and_values, NOMINAL_IN_PER_PT, page_index=1)


def test_kitchen_island_footprint_matches_labelled_dimensions():
    footprints = _footprints()
    island = max(footprints, key=lambda f: f.width_nm * f.depth_nm)
    assert island.width_text.strip() == "8' - 7\""
    assert island.depth_text.strip() == "4' - 3\""
    assert round(island.width_nm / NM_PER_INCH) == 103  # 8'-7"
    assert round(island.depth_nm / NM_PER_INCH) == 51  # 4'-3"
    assert island.width_error_in < 0.5
    assert island.depth_error_in < 1.0


def test_footprints_require_corroboration_on_both_axes():
    # Every returned match must actually have found both a width and a
    # depth label near it — the function should never guess a rectangle's
    # dimensions from unrelated nearby text.
    for f in _footprints():
        assert f.width_text
        assert f.depth_text
