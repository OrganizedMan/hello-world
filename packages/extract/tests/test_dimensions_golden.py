"""Golden extraction regression (plan §16 Tier 2 / Stage 1 gate, plan §14).

These run against the real, pinned Garrigan PDFs — not synthetic
fixtures — because the whole point of Stage 1 is measured performance on
an actual document, not a canned example. The per-sheet thresholds below
are the currently-achieved baseline (see fixture PR / commit history for
the numbers this replaced): a regression below these values means the
matcher got worse, not that the constants were arbitrary targets to hit.

The family-room assertions are the ones that matter most: they are the
exact two-wall regression subject of `fixtures_garrigan.family_room`
(plan §22's proof-of-concept), and Stage 1's gate is specifically that
extraction reproduces the Stage-0 hand-traced model within 1 inch.
"""
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
from extract.dimensions import match_dimensions_on_page
from units import parse_feet_inches, ParseError, NM_PER_INCH

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/garrigan-261-grove/source/garrigan-main-set.pdf"
NOMINAL_IN_PER_PT = 12 / 18  # "1/4" = 1'-0"" per the title block (plan Appendix A)


def _matches_for_page(page_index: int):
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        paths = harvest_paths(h, page_index, suppress_text_masks=False)
        text_lines = reassemble_lines(harvest_text_lines(h, page_index))

    dim_lines = [l for l in text_lines if classify_text_line(l) == TextClass.DIMENSION_STRING]
    lines_and_values = []
    for line in dim_lines:
        try:
            lines_and_values.append((line, parse_feet_inches(line.text.strip())))
        except ParseError:
            continue

    matches = match_dimensions_on_page(lines_and_values, paths, NOMINAL_IN_PER_PT)
    return dim_lines, matches


def _under(matches, tol_in):
    return [m for m in matches if m.error_in < tol_in]


def test_a1_first_floor_meets_baseline_match_rate():
    dim_lines, matches = _matches_for_page(1)
    assert len(dim_lines) >= 50
    under_1in = _under(matches, 1.0)
    # Currently achieved: 40/55. Guard against regressing below 65%.
    assert len(under_1in) / len(dim_lines) >= 0.65


def test_a2_second_floor_meets_baseline_match_rate():
    dim_lines, matches = _matches_for_page(2)
    under_1in = _under(matches, 1.0)
    assert len(under_1in) / len(dim_lines) >= 0.65


def test_family_room_east_wall_dimensions_match_hand_traced_fixture():
    """The exact regression subject of fixtures_garrigan.family_room: the
    window offset and the mudroom-opening offset on LIVING_ROOM.EAST."""
    _, matches = _matches_for_page(1)
    # Two separate dimension rows run up the east wall (offset from the
    # wall face by different amounts, as chained dimensions typically
    # are): 3'-8" (the window) at x~2007.2, 7'-4" (to the mudroom
    # opening) at x~2022.07. Match by proximity, not exact float equality.
    window_offset = next((m for m in matches if m.text.strip() == "3' - 8\"" and abs(m.perp_pt - 2007.2) < 1), None)
    mudroom_offset = next((m for m in matches if m.text.strip() == "7' - 4\"" and abs(m.perp_pt - 2022.07) < 1), None)
    assert window_offset is not None, "3'-8\" east-wall offset not matched at all"
    assert mudroom_offset is not None, "7'-4\" east-wall offset not matched at all"
    assert window_offset.error_in < 1.0
    assert mudroom_offset.error_in < 1.0


def test_family_room_south_wall_chain_matches_hand_traced_fixture():
    """The 3'-1" | 5'-0" | 3'-1" chain, south wall — the wall the
    5'-0" cased opening actually belongs to (Appendix A / the original
    reported failure this whole project exists to prevent)."""
    _, matches = _matches_for_page(1)
    # The chain's two symmetric 3'-1" callouts sit on two slightly
    # different (but both real) dimension rows near the opening; the
    # 5'-0" itself is unambiguous. Match by text + a generous perp
    # window around the family room rather than one exact row.
    south_wall_matches = [
        m for m in matches
        if 880 < m.perp_pt < 915 and m.text.strip() in ("3' - 1\"", "5' - 0\"")
    ]
    values = sorted(round(m.value_nm / NM_PER_INCH) for m in south_wall_matches)
    # 37in, 37in, 60in = 3'-1", 3'-1", 5'-0"
    assert values == [37, 37, 60]
    assert all(m.error_in < 1.0 for m in south_wall_matches)
