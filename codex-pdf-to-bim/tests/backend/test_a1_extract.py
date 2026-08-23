"""Extraction tests that run against the real A-1 sheet.

The source drawing is not committed, so these skip unless it is supplied via
``HEARTHVIEW_A1_PDF``. They assert against measurements printed on the sheet,
not against values copied out of the extractor.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hearthview.a1_extract import POINTS_PER_FOOT, extract_a1

from hearthview.drawings import a1_source

_SOURCE = a1_source()
pytestmark = pytest.mark.skipif(
    _SOURCE is None,
    reason="No drawing set: commit drawings/ or set HEARTHVIEW_A1_PDF.",
)


@pytest.fixture(scope="module")
def extraction():
    return extract_a1(Path(_SOURCE))


def test_view_is_located_from_wall_poche_not_fixed_coordinates(extraction) -> None:
    footprint = extraction.footprint

    assert extraction.page_number == 2
    # The proposed view sits in the right half of the sheet.
    assert footprint.x0 > extraction.page_width_points / 2
    width_feet = (footprint.x1 - footprint.x0) / POINTS_PER_FOOT
    depth_feet = (footprint.y1 - footprint.y0) / POINTS_PER_FOOT
    assert 30.0 < width_feet < 50.0
    assert 35.0 < depth_feet < 55.0


def test_walls_are_split_by_legend_class(extraction) -> None:
    assert extraction.layer("wall_new")
    assert extraction.layer("wall_existing")
    # New work is the smaller part of this renovation.
    assert len(extraction.layer("wall_new")) < len(extraction.layer("wall_existing"))


def test_island_matches_its_printed_dimension(extraction) -> None:
    """The island is printed as 8'-7" x 4'-3"; extraction must land within an inch."""
    candidates = [
        (
            (s.bounds.x1 - s.bounds.x0) / POINTS_PER_FOOT,
            (s.bounds.y1 - s.bounds.y0) / POINTS_PER_FOOT,
        )
        for s in extraction.layer("counter")
    ]
    island = [wh for wh in candidates if 8.4 < wh[0] < 8.8 and 4.1 < wh[1] < 4.5]

    assert island, f"no island-sized counter run found among {candidates}"
    width, depth = island[0]
    assert abs(width - (8 + 7 / 12)) < 1 / 12
    assert abs(depth - (4 + 3 / 12)) < 1 / 12


def test_openings_are_door_and_window_sized(extraction) -> None:
    widths = sorted(o.width_feet for o in extraction.openings)

    assert widths
    assert min(widths) >= 0.2
    assert max(widths) <= 11.0
    # A renovation of this size has several nominal 3'-0" doorways.
    assert sum(1 for w in widths if 2.9 <= w <= 3.1) >= 3


def test_room_labels_come_from_the_text_layer(extraction) -> None:
    texts = {label.text for label in extraction.labels}

    assert {"KITCHEN", "MUDROOM", "POWDER", "NEW DECK"} <= texts
    # Ceiling-height notes and dimensions are annotation, not architecture.
    assert not any("CLG" in text for text in texts)
    assert not any(text.endswith('"') and "-" in text for text in texts)


def test_every_shape_lies_inside_the_proposed_view(extraction) -> None:
    view = extraction.view

    for shape in extraction.shapes:
        b = shape.bounds
        assert view.x0 <= b.x0 and b.x1 <= view.x1, f"{shape.layer} escapes the view"
        assert view.y0 <= b.y0 and b.y1 <= view.y1, f"{shape.layer} escapes the view"


def test_treads_drawn_as_paired_strokes_are_read_as_one(extraction) -> None:
    """A-0 and A-2 draw each tread as two lines an inch and a half apart.

    The ladder search wants a constant riser, so on those sheets it measured
    10.5, then 1.5, and gave up after two steps -- which is how two storeys of
    a four-storey house came to have no stairs at all. Collapsing the pairs is
    safe because no riser is that shallow: at this sheet's scale 1.5 points is
    an inch.
    """
    from hearthview.a1_extract import _one_line_per_tread

    spans = {y: (100.0, 150.0) for y in (900.0, 901.5, 911.0, 912.5, 922.0, 923.5)}
    collapsed = _one_line_per_tread(sorted(spans), spans)

    assert len(collapsed) == 3
    steps = [round(collapsed[i + 1] - collapsed[i], 2) for i in range(len(collapsed) - 1)]
    assert steps == [11.0, 11.0]


def test_a_stair_found_twice_is_kept_once(extraction) -> None:
    """Treads are grouped by where their midpoint falls, so a flight whose
    treads vary by an inch in width straddles two groups and comes back twice.
    The massing stacked both into one impossible climb."""
    from hearthview.a1_extract import _distinct_flights

    first = [((100.0, y), (150.0, y)) for y in (900.0, 912.0, 924.0, 936.0)]
    second = [((101.0, y), (152.0, y)) for y in (901.0, 913.0, 925.0)]
    apart = [((400.0, y), (450.0, y)) for y in (900.0, 912.0, 924.0, 936.0)]

    assert len(_distinct_flights([first, second])) == len(first)
    assert len(_distinct_flights([first, apart])) == len(first) + len(apart)
