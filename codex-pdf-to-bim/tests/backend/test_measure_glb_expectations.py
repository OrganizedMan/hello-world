"""The artifact-versus-trace expectations must come from the spec, not memory.

`measure_glb --spec` is the only check in the pipeline that reads the exported
GLB rather than the plan that produced it. These tests pin the part of it that
can be exercised without Blender: that every landmark position it expects is
derived from the committed A-1 spec, and lands where the drawing says.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / "spikes/tour_quality/a1_kitchen_scene_spec.json"
pytestmark = pytest.mark.skipif(not SPEC_PATH.is_file(), reason="scene spec missing")

sys.path.insert(0, str(REPO / "scripts"))


@pytest.fixture(scope="module")
def expected():
    from measure_glb import expected_from_spec

    return expected_from_spec(json.loads(SPEC_PATH.read_text()))


@pytest.fixture(scope="module")
def spec():
    return json.loads(SPEC_PATH.read_text())


def test_every_measured_landmark_has_a_traced_position(expected) -> None:
    from measure_glb import WANTED

    assert set(expected) == set(WANTED)


def test_landmarks_land_on_the_walls_the_sheet_puts_them_on(expected, spec) -> None:
    """glTF ground plane: +x is east and -z is north."""
    span = spec["envelope"]["span"]
    arm_north = spec["envelope"]["arm_north"]

    # Sink and dishwasher on the north wall: z just inside -arm_north.
    for name in ("HV_SINK_RIM", "HV_DISHWASHER_BODY"):
        assert expected[name][1] < -(arm_north - 0.75), f"{name} is off the north wall"
    # Range and refrigerator on the west wall: x just inside 0.
    for name in ("HV_RANGE_BODY", "HV_REFRIGERATOR_BODY"):
        assert 0.0 < expected[name][0] < 0.75, f"{name} is off the west wall"
    # The TV is on the opposite (east) wall.
    assert expected["HV_TV_SCREEN"][0] > span - 0.2


def test_the_island_sits_between_the_two_runs(expected) -> None:
    sink_x = expected["HV_SINK_RIM"][0]
    island_x, island_z = expected["HV_ISLAND_STRUCTURE"]
    range_z = expected["HV_RANGE_BODY"][1]

    assert island_x > expected["HV_RANGE_BODY"][0], "island is west of the range"
    assert island_z > expected["HV_SINK_RIM"][1], "island is north of the sink run"
    assert island_x > sink_x or island_z > range_z


def test_expectations_track_the_spec_rather_than_hardcoded_numbers() -> None:
    """Move the island in the spec and the expectation must move with it."""
    from measure_glb import expected_from_spec

    spec = json.loads(SPEC_PATH.read_text())
    before = expected_from_spec(spec)["HV_ISLAND_STRUCTURE"]
    spec["kitchen"]["island"] = [v + 1.0 for v in spec["kitchen"]["island"]]
    after = expected_from_spec(spec)["HV_ISLAND_STRUCTURE"]

    assert after[0] == pytest.approx(before[0] + 1.0)
    assert after[1] == pytest.approx(before[1] - 1.0)
