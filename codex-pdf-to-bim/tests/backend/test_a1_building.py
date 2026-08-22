"""Four sheets into one building: shared horizontal datum, stacked vertically.

The two failure modes here are opposite. Horizontally the storeys must *not*
each start at their own origin, or every south-west corner piles up regardless
of where the storey sits. Vertically they must each start at their own floor,
or everything collapses onto the datum storey.
"""

from __future__ import annotations

import pytest

from hearthview.a1_building import (
    ASSUMED_FLOOR_ASSEMBLY_INCHES,
    DATUM_SHEET,
    build_building,
)
from hearthview.a1_extract import POINTS_PER_FOOT, extract_a1
from hearthview.a1_massing import build_a1_massing
from hearthview.drawings import SHEET_PAGES, a1_source
from hearthview.units import TICKS_PER_INCH

_SOURCE = a1_source()
pytestmark = pytest.mark.skipif(_SOURCE is None, reason="no drawing set available")


@pytest.fixture(scope="module")
def building():
    return build_building(_SOURCE)


def test_every_drawn_storey_is_present(building) -> None:
    assert [s.sheet for s in building.storeys] == ["A-0", "A-1", "A-2", "A-3"]


def test_the_datum_storey_sits_at_zero(building) -> None:
    assert building.storey(DATUM_SHEET).base_inches == 0.0


def test_storeys_stack_in_order_without_intersecting(building) -> None:
    """Each floor is above the one below, by that one's ceiling plus assembly."""
    for lower, upper in zip(building.storeys, building.storeys[1:]):
        rise = upper.base_inches - lower.base_inches
        assert rise == pytest.approx(lower.ceiling_inches + ASSUMED_FLOOR_ASSEMBLY_INCHES)
        assert rise > 0, "a storey must sit above the one beneath it"


def test_each_storey_is_built_at_its_own_elevation(building) -> None:
    """The bug this catches put every storey's slab back at z = 0."""
    for storey in building.storeys:
        floor_ticks = storey.base_inches * TICKS_PER_INCH
        lowest = min(p.z0_ticks for p in storey.primitives)
        highest = max(p.z1_ticks for p in storey.primitives)

        # Nothing sits more than a slab thickness below its own floor.
        assert lowest >= floor_ticks - 12 * TICKS_PER_INCH
        assert highest == pytest.approx(
            floor_ticks + storey.ceiling_inches * TICKS_PER_INCH, abs=TICKS_PER_INCH
        )


def test_the_datum_moves_the_model_without_changing_it(building) -> None:
    """A datum is a position, not a filter.

    Building a storey on another storey's origin must translate it and nothing
    more. When the datum was also used as the storey's extent it silently
    changed which openings counted as exterior, dropping seven window sills from
    A-2 and seven from A-3 with no error anywhere.
    """
    datum = extract_a1(_SOURCE, page_number=SHEET_PAGES[DATUM_SHEET]).footprint

    for sheet in ("A-0", "A-2", "A-3"):
        extraction = extract_a1(_SOURCE, page_number=SHEET_PAGES[sheet])
        alone = build_a1_massing(extraction)
        shifted = build_a1_massing(extraction, datum=datum)

        assert {p.element_id for p in alone.primitives} == {
            p.element_id for p in shifted.primitives
        }, f"{sheet} gained or lost geometry when the datum changed"


def test_the_storeys_agree_where_the_drawings_say_they_should(building) -> None:
    """Vertical alignment, which nothing checked before.

    The basement is under the first floor, so their east and west walls should
    land on each other. They agree to well under an inch, which is what makes
    one shared datum defensible in the first place.
    """
    basement = building.storey("A-0").extraction.footprint
    first = building.storey("A-1").extraction.footprint

    assert abs(basement.x0 - first.x0) / POINTS_PER_FOOT < 0.1
    assert abs(basement.x1 - first.x1) / POINTS_PER_FOOT < 0.1


def test_the_floor_assembly_is_declared_an_assumption() -> None:
    """No section exists in the set, so this thickness is a convention."""
    assert ASSUMED_FLOOR_ASSEMBLY_INCHES > 0
