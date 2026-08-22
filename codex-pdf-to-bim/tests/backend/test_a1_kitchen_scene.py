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
    assert envelope["arm_north"] / FT == pytest.approx(19.58, abs=0.15)


def test_range_and_fridge_sit_where_the_sheet_puts_them(spec) -> None:
    west = spec["kitchen"]["west_run"]
    arm_north = spec["envelope"]["arm_north"]

    def from_north_wall(center_y: float) -> float:
        """Feet south of the north wall's interior face, as the sheet reads."""
        return (arm_north - center_y) / FT

    # The sheet's callouts measured from the inside of the 6" north wall
    # (burner glyph 6.90 ft, fridge label 13.70 ft).
    assert from_north_wall(west["range"]["center_y"]) == pytest.approx(6.90, abs=0.2)
    assert from_north_wall(west["fridge"]["center_y"]) == pytest.approx(13.70, abs=0.25)
    # Order down the west wall: uppers, range, uppers, refrigerator.
    uppers = sorted(from_north_wall(u["center_y"]) for u in west["uppers"])
    assert len(uppers) == 2
    assert (uppers[0] < from_north_wall(west["range"]["center_y"]) < uppers[1]
            < from_north_wall(west["fridge"]["center_y"]))


def test_north_wall_stations_follow_the_printed_callouts(spec) -> None:
    """Model x is feet east of the west wall -- the same direction the sheet reads."""
    north = spec["kitchen"]["north_run"]

    def plan_x(value: float) -> float:
        return value / FT

    assert plan_x(north["sink"]["center_x"]) == pytest.approx(7.17, abs=0.2)
    assert plan_x(north["dishwasher"]["center_x"]) == pytest.approx(4.38, abs=0.2)
    assert plan_x(north["trash"]["center_x"]) == pytest.approx(9.90, abs=0.2)
    towers = sorted(plan_x(t["center_x"]) for t in north["towers"])
    assert len(towers) == 2
    # tower / DW / sink / trash / tower, west to east on the sheet
    assert towers[0] < plan_x(north["dishwasher"]["center_x"]) < plan_x(north["sink"]["center_x"])
    assert plan_x(north["sink"]["center_x"]) < plan_x(north["trash"]["center_x"]) < towers[1]


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
        assert -margin <= cy - sy / 2 and cy + sy / 2 <= envelope["arm_north"] + margin, box["name"]


def test_cameras_stand_clear_of_the_island(spec) -> None:
    x0, y0, x1, y1 = spec["kitchen"]["island"]

    for camera in spec["cameras"]:
        cx, cy, cz = camera["location"]
        if cz < 2.2:  # eye-level cameras only
            inside = x0 <= cx <= x1 and y0 <= cy <= y1
            assert not inside, f"{camera['name']} is inside the island"
    names = {c["name"] for c in spec["manifest_cameras"]}
    assert {"kitchen_overview", "walk_start", "overhead"} <= names


def _three(x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
    """Blender plan coords to glTF Y-up, matching Blender's export_yup."""
    return (x, z, -y)


def _side_of(viewer, facing, point) -> float:
    """Positive when `point` is to the viewer's right."""
    right = (-facing[2], 0.0, facing[0])
    offset = (point[0] - viewer[0], 0.0, point[2] - viewer[2])
    return offset[0] * right[0] + offset[2] * right[2]


def test_standing_at_the_mudroom_the_sink_is_on_the_right(spec) -> None:
    """The orientation invariant, stated by the homeowner from the drawing.

    Back to the mudroom with the island ahead: the sink wall is on the right and
    the passage to the pantry, powder room and dining room is on the left. This
    failed while the scene was authored left-handed, which mirrored the whole
    world; it is the cheapest guard against that returning.
    """
    kitchen = spec["kitchen"]
    mudroom = next(d for d in spec["doors"] if d["kind"] == "cased" and d["axis"] == "v")
    viewer = _three(mudroom["line"] + mudroom["outward"] * 0.6,
                    (mudroom["start"] + mudroom["end"]) / 2)
    island = kitchen["island"]
    target = _three((island[0] + island[2]) / 2, (island[1] + island[3]) / 2)
    facing = (target[0] - viewer[0], 0.0, target[2] - viewer[2])

    sink = _three(kitchen["north_run"]["sink"]["center_x"],
                  spec["envelope"]["arm_north"] - 0.37)
    assert _side_of(viewer, facing, sink) > 0, "the sink must be on the right"

    arm_opening = next(d for d in spec["doors"] if d["name"].startswith("HV_SOUTH_ARM"))
    passage = _three((arm_opening["start"] + arm_opening["end"]) / 2, arm_opening["line"])
    assert _side_of(viewer, facing, passage) < 0, "the pantry passage must be on the left"


def test_facing_the_sink_wall_the_range_is_on_the_left(spec) -> None:
    """Second, independent orientation check on a different pair of walls.

    Stand at the island facing the sink wall (north): the range and
    refrigerator wall is to the left. A mirrored world puts it on the right.
    """
    assert spec["frame"]["handedness"] == "right"
    kitchen = spec["kitchen"]
    arm_north = spec["envelope"]["arm_north"]
    island = kitchen["island"]
    viewer = _three((island[0] + island[2]) / 2, (island[1] + island[3]) / 2)
    sink = _three(kitchen["north_run"]["sink"]["center_x"], arm_north - 0.37)
    facing = (sink[0] - viewer[0], 0.0, sink[2] - viewer[2])

    # The west wall's interior face is x = 0; the range stands just inside it.
    range_point = _three(0.33, kitchen["west_run"]["range"]["center_y"])
    assert _side_of(viewer, facing, range_point) < 0, "the range wall must be on the left"


def test_eye_level_cameras_stay_inside_the_envelope(spec) -> None:
    """A camera outside a wall shoots through it; KITCHEN was 0.54 ft out."""
    envelope = spec["envelope"]

    for camera in spec["cameras"]:
        x, y, z = camera["location"]
        if z >= 2.6:  # plan and axonometric sit above the model on purpose
            continue
        assert -0.1 <= x <= envelope["span"] + 0.1, f"{camera['name']} outside in x"
        assert -0.1 <= y <= envelope["arm_north"] + 0.1, f"{camera['name']} outside in y"
