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

_SOURCE = os.environ.get("HEARTHVIEW_A1_PDF")
pytestmark = pytest.mark.skipif(
    not (_SOURCE and Path(_SOURCE).is_file()),
    reason="Set HEARTHVIEW_A1_PDF to the Garrigan A-1 drawing to run extraction tests.",
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
