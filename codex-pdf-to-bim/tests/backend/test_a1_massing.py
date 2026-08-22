"""Massing tests: what the drawing measures vs. what the model assumes.

Like the extraction tests these need the real sheet, supplied via
``HEARTHVIEW_A1_PDF``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hearthview.a1_extract import POINTS_PER_FOOT, extract_a1
from hearthview.a1_massing import (
    ASSUMED_DOOR_HEAD_INCHES,
    A1MassingError,
    build_a1_massing,
    parse_ceiling_height,
)
from hearthview.units import TICKS_PER_INCH

from hearthview.drawings import a1_source

_SOURCE = a1_source()
pytestmark = pytest.mark.skipif(
    _SOURCE is None,
    reason="No drawing set: commit drawings/ or set HEARTHVIEW_A1_PDF.",
)


@pytest.fixture(scope="module")
def massing():
    return build_a1_massing(extract_a1(Path(_SOURCE)))


def test_ceiling_height_is_read_from_the_printed_note(massing) -> None:
    """A-1 prints CLG HT - 8' 5" on every labelled room."""
    assert massing.ceiling.provenance == "dimension_verified"
    assert massing.ceiling.inches == pytest.approx(8 * 12 + 5)


def test_a_missing_ceiling_note_is_refused_not_guessed() -> None:
    with pytest.raises(A1MassingError):
        parse_ceiling_height(())


def test_no_solid_rises_above_the_printed_ceiling(massing) -> None:
    ceiling_ticks = int(round(massing.ceiling.inches * TICKS_PER_INCH))

    assert massing.primitives

    # The printed CLG HT is the *finished* ceiling, meaning the underside of the
    # board. So the ceiling slab is the one solid that legitimately sits above
    # it, and its underside has to land exactly on the printed height -- which
    # is a stronger claim than the blanket ceiling this test used to make.
    ceilings = [p for p in massing.primitives if p.part_kind == "ceiling"]
    assert ceilings, "a storey needs a ceiling, or its rooms light as open courtyards"
    for item in ceilings:
        assert item.z0_ticks == ceiling_ticks
        assert item.z1_ticks > ceiling_ticks

    assert all(
        p.z1_ticks <= ceiling_ticks
        for p in massing.primitives
        if p.part_kind != "ceiling"
    )
    # Walls start at floor level; only the floor and deck slabs sit below it.
    for item in massing.primitives:
        if item.part_kind in ("floor", "deck"):
            assert item.z0_ticks < 0 <= item.z1_ticks
        else:
            assert item.z0_ticks >= 0


def test_assumed_heights_are_flagged_and_are_the_minority(massing) -> None:
    """Sills and lintels rest on convention; walls rest on the printed note."""
    assert massing.assumed_primitive_ids
    assert all(
        pid.startswith(("sill.", "lintel.", "counter.", "fixture.", "stair."))
        for pid in massing.assumed_primitive_ids
    )
    # Walls and slabs carry measured dimensions and outnumber the rest.
    assert massing.verified_fraction > 0.5


def test_lintels_sit_at_the_assumed_head_height(massing) -> None:
    head_ticks = int(round(ASSUMED_DOOR_HEAD_INCHES * TICKS_PER_INCH))
    lintels = [p for p in massing.primitives if p.element_id.startswith("lintel.")]

    assert lintels
    assert all(p.z0_ticks == head_ticks for p in lintels)


def test_wall_extents_survive_the_extrusion(massing) -> None:
    """Wall solids must match the traced plan, not drift from it.

    The deck legitimately reaches north of the wall footprint, so it is excluded
    here and covered by the tour envelope test instead.
    """
    extraction = extract_a1(Path(_SOURCE))
    plan_width = (extraction.footprint.x1 - extraction.footprint.x0) / POINTS_PER_FOOT
    plan_depth = (extraction.footprint.y1 - extraction.footprint.y0) / POINTS_PER_FOOT

    walls = [p for p in massing.primitives if p.part_kind == "wall"]
    model_width = max(p.x1_ticks for p in walls) / TICKS_PER_INCH / 12
    model_depth = max(p.y1_ticks for p in walls) / TICKS_PER_INCH / 12

    assert model_width == pytest.approx(plan_width, abs=0.05)
    assert model_depth == pytest.approx(plan_depth, abs=0.05)


def test_the_deck_extends_beyond_the_wall_footprint(massing) -> None:
    """The deck is north of the building line; losing it would be a silent bug."""
    decks = [p for p in massing.primitives if p.part_kind == "deck"]
    walls = [p for p in massing.primitives if p.part_kind == "wall"]

    assert decks
    assert max(p.y1_ticks for p in decks) > max(p.y1_ticks for p in walls)


def test_openings_are_classified_and_doors_have_swings(massing) -> None:
    kinds = {o.kind for o in massing.openings}

    assert kinds <= {"door", "window", "cased_opening"}
    assert any(o.kind == "door" for o in massing.openings)
    # Every window must sit on the building's perimeter.
    assert all(o.on_exterior for o in massing.openings if o.kind == "window")


def test_the_whole_floor_mapping_is_right_handed() -> None:
    """The whole-floor path was never checked for this, and the kitchen's wasn't either.

    `a1_massing` predates all three frame fixes and nothing here imported
    `chirality` until now. Its tests passing said nothing about handedness --
    which is precisely the state the kitchen's suite was in while the model it
    produced was a reflection of the drawing.
    """
    from hearthview.a1_massing import plan_from_pdf
    from hearthview.chirality import mapping_preserves_handedness

    extraction = extract_a1(Path(_SOURCE))

    assert mapping_preserves_handedness(plan_from_pdf(extraction.footprint))


def test_north_in_the_model_is_north_on_the_sheet() -> None:
    """Handedness alone allows a 180 turn; pin the direction too."""
    from hearthview.a1_massing import plan_from_pdf

    extraction = extract_a1(Path(_SOURCE))
    to_plan = plan_from_pdf(extraction.footprint)
    footprint = extraction.footprint

    # PDF y grows downward, so the footprint's smaller y is its north edge.
    _, north_edge = to_plan(footprint.x0, footprint.y0)
    _, south_edge = to_plan(footprint.x0, footprint.y1)

    assert north_edge > south_edge, "plan north must increase with model +y"
    assert south_edge == 0.0, "the south edge anchors the frame origin"
