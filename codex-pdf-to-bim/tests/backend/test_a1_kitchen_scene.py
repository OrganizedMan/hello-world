"""Scene-spec tests: the Blender build plan must match what A-1 prints.

Assertions are against measurements printed on the sheet or measured from its
drawn symbols — the exact values the hand-built spike got wrong.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hearthview.a1_extract import extract_a1

_SOURCE = os.environ.get("HEARTHVIEW_A1_PDF")
pytestmark = pytest.mark.skipif(
    not (_SOURCE and Path(_SOURCE).is_file()),
    reason="Set HEARTHVIEW_A1_PDF to the Garrigan A-1 drawing to run scene-spec tests.",
)

FT = 0.3048


@pytest.fixture(scope="module")
def spec():
    from hearthview.a1_kitchen_scene import build_kitchen_scene_spec

    source = Path(_SOURCE)
    return build_kitchen_scene_spec(extract_a1(source), source)


def test_envelope_matches_the_printed_dimensions(spec) -> None:
    envelope = spec["envelope"]

    assert envelope["span"] / FT == pytest.approx(28.87, abs=0.1)
    assert envelope["depth_east"] / FT == pytest.approx(15.92, abs=0.35)
    # The west kitchen run is printed 19'-7"; the spike cut it to 15'-11".
    assert envelope["arm_south"] / FT == pytest.approx(19.58, abs=0.15)


def test_range_and_fridge_sit_where_the_sheet_puts_them(spec) -> None:
    west = spec["kitchen"]["west_run"]

    # Interior-face frame: the sheet's callouts measured from the inside of
    # the 6" north wall (burner glyph 6.90 ft, fridge label 13.70 ft).
    assert west["range"]["center_y"] / FT == pytest.approx(6.90, abs=0.2)
    assert west["fridge"]["center_y"] / FT == pytest.approx(13.70, abs=0.25)
    # Order down the west wall: uppers, range, uppers, refrigerator.
    uppers = sorted(u["center_y"] for u in west["uppers"])
    assert len(uppers) == 2
    assert uppers[0] < west["range"]["center_y"] < uppers[1] < west["fridge"]["center_y"]


def test_north_wall_stations_follow_the_printed_callouts(spec) -> None:
    north = spec["kitchen"]["north_run"]

    assert north["sink"]["center_x"] / FT == pytest.approx(7.17, abs=0.2)
    assert north["dishwasher"]["center_x"] / FT == pytest.approx(4.38, abs=0.2)
    assert north["trash"]["center_x"] / FT == pytest.approx(9.90, abs=0.2)
    towers = sorted(t["center_x"] for t in north["towers"])
    assert len(towers) == 2
    # tower / DW / sink / trash / tower, west to east
    assert towers[0] < north["dishwasher"]["center_x"] < north["sink"]["center_x"]
    assert north["sink"]["center_x"] < north["trash"]["center_x"] < towers[1]


def test_island_matches_its_printed_size(spec) -> None:
    x0, y0, x1, y1 = spec["kitchen"]["island"]

    assert (x1 - x0) / FT == pytest.approx(8 + 7 / 12, abs=0.1)
    assert (y1 - y0) / FT == pytest.approx(4 + 3 / 12, abs=0.1)


def test_openings_are_typed_from_the_drawing(spec) -> None:
    window_names = {w["name"] for w in spec["windows"]}
    door_kinds = {(d["name"], d["kind"]) for d in spec["doors"]}

    # Triple window over the sink plus two more east on the north wall.
    assert sum(1 for n in window_names if n.startswith("HV_NORTH")) == 5
    assert any(n.startswith("HV_WEST") for n in window_names)
    assert any(n.startswith("HV_EAST") for n in window_names)
    # One deck door; the mudroom and both south openings are cased, not doors.
    assert ("HV_NORTH_DOOR_3", "door") in door_kinds
    assert sum(1 for _, kind in door_kinds if kind == "cased") == 4


def test_sink_is_centred_under_the_middle_window(spec) -> None:
    middle = next(w for w in spec["windows"] if w["name"] == "HV_NORTH_WINDOW_1")
    sink_x = spec["kitchen"]["north_run"]["sink"]["center_x"]

    assert middle["start"] < sink_x < middle["end"]


def test_every_wall_box_stays_on_the_region_boundary(spec) -> None:
    envelope = spec["envelope"]
    margin = 0.30  # thickest wall is 9"

    for box in spec["wall_boxes"]:
        (sx, sy, _), (cx, cy, _) = box["size"], box["loc"]
        assert -margin <= cx - sx / 2 and cx + sx / 2 <= envelope["span"] + margin, box["name"]
        assert -margin <= cy - sy / 2 and cy + sy / 2 <= envelope["arm_south"] + margin, box["name"]


def test_cameras_stand_clear_of_the_island(spec) -> None:
    x0, y0, x1, y1 = spec["kitchen"]["island"]

    for camera in spec["cameras"]:
        cx, cy, cz = camera["location"]
        if cz < 2.2:  # eye-level cameras only
            inside = x0 <= cx <= x1 and y0 <= cy <= y1
            assert not inside, f"{camera['name']} is inside the island"
    names = {c["name"] for c in spec["manifest_cameras"]}
    assert {"kitchen_overview", "walk_start", "overhead"} <= names
