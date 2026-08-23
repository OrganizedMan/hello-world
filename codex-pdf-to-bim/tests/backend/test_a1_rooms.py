"""Rooms come from the drawing's own labels, grown out to the walls."""

from __future__ import annotations

import pytest

from hearthview.a1_extract import extract_a1
from hearthview.a1_rooms import classify, detect_rooms
from hearthview.drawings import SHEET_PAGES, a1_source

_SOURCE = a1_source()
pytestmark = pytest.mark.skipif(_SOURCE is None, reason="no drawing set available")


@pytest.fixture(scope="module")
def first_floor():
    return detect_rooms(extract_a1(_SOURCE, page_number=SHEET_PAGES["A-1"]))


def test_every_storey_finds_rooms() -> None:
    for sheet, page in SHEET_PAGES.items():
        rooms = detect_rooms(extract_a1(_SOURCE, page_number=page))
        assert rooms, f"{sheet} found no rooms at all"


def test_the_first_floor_finds_the_rooms_the_sheet_names(first_floor) -> None:
    kinds = {room.kind for room in first_floor}
    names = {room.name.upper() for room in first_floor}

    assert "kitchen" in kinds
    assert "KITCHEN" in names
    assert {"DINING ROOM", "LIVING ROOM", "MUDROOM"} <= names


def test_rooms_are_a_plausible_size(first_floor) -> None:
    """A room smaller than a cupboard or larger than the house is a bad fill."""
    for room in first_floor:
        assert 8.0 <= room.area_square_feet <= 900.0, f"{room.name} is {room.area_square_feet} sq ft"


def test_notes_and_dimensions_are_not_rooms() -> None:
    for text in ("3 RISERS", 'HEIGHT OF RISERS: 7"', '1/4" = 1\'-0"', "REMODEL", "2 TREADS"):
        assert classify(text) is None, f"{text!r} was read as a room"


def test_a_fireplace_is_not_a_room() -> None:
    """It is a feature standing inside a room.

    Seeded as its own room it grew to 170 sq ft and took half the living room
    with it, which is how a plausible-looking plan hides a wrong one.
    """
    assert classify("(E) FIREPLACE") is None


def test_the_longest_matching_name_wins() -> None:
    """Otherwise DINING ROOM is filed as a bare ROOM and WALK-IN as a bedroom."""
    assert classify("DINING ROOM") == "dining"
    assert classify("(E) LIVING ROOM") == "living"
    assert classify("STUDY ROOM") == "office"
    assert classify("WALK-IN") == "storage"
    assert classify("POWDER ROOM") == "bathroom"


def test_labels_that_wrap_are_read_as_one_name() -> None:
    """A-2 prints OFFICE / over BEDROOM 4; read apart it becomes a room called 4."""
    rooms = detect_rooms(extract_a1(_SOURCE, page_number=SHEET_PAGES["A-2"]))
    names = {room.name.upper() for room in rooms}

    assert any("BEDROOM 4" in name for name in names)
    assert not any(name.strip() in {"ROOM", "/"} for name in names)


def test_existing_rooms_are_marked_as_such(first_floor) -> None:
    """The (E) prefix means the proposal leaves the room alone."""
    existing = {room.name.upper() for room in first_floor if room.existing}
    proposed = {room.name.upper() for room in first_floor if not room.existing}

    assert existing, "the sheet marks several rooms (E)"
    assert "KITCHEN" in proposed, "the kitchen is the thing being remodelled"
    assert not any(name.startswith("(E)") for name in existing | proposed)


def test_upper_floors_are_bedrooms_and_the_first_is_not() -> None:
    second = detect_rooms(extract_a1(_SOURCE, page_number=SHEET_PAGES["A-2"]))
    bedrooms = [room for room in second if room.kind == "bedroom"]

    assert len(bedrooms) >= 3, "A-2 names bedrooms 1 through 4"
