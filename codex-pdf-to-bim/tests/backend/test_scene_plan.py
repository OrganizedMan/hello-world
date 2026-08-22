from __future__ import annotations

import importlib
import math

import pytest


def scene_plan_module():
    return importlib.import_module("services.blender.scene_plan")


def representative_bounds():
    module = scene_plan_module()
    return {
        "floor": module.Bounds(1.7, -0.3, 0.0, 9.6, 6.1, 0.0),
        "island": module.Bounds(2.0, 1.8, 0.0, 4.65, 3.12, 0.92),
        "tv": module.Bounds(9.09, 1.67, 1.07, 9.15, 3.20, 1.93),
    }


def test_living_furniture_faces_the_verified_tv_without_overlapping_the_island() -> None:
    module = scene_plan_module()
    plan = module.build_warm_scene_plan(**representative_bounds())
    by_name = {item.name: item for item in plan.furnishings}

    seat = by_name["Linen sofa seat"]
    back = by_name["Linen sofa back"]
    rug = by_name["Wool living-room rug"]
    island = representative_bounds()["island"]

    assert seat.scale[0] < seat.scale[1]
    assert back.location[0] < seat.location[0]
    assert seat.location[0] - seat.scale[0] > island.max_x
    assert rug.location[0] > seat.location[0]
    assert back.location[2] + back.scale[2] <= representative_bounds()["floor"].max_z + 1.0


def test_stools_and_pendants_follow_the_verified_island() -> None:
    module = scene_plan_module()
    bounds = representative_bounds()
    plan = module.build_warm_scene_plan(**bounds)
    island = bounds["island"]
    by_name = {item.name: item for item in plan.furnishings}

    countertop = by_name["Honed stone island top"]
    assert countertop.location[:2] == pytest.approx(island.center[:2])
    assert countertop.location[2] > island.max_z
    assert countertop.scale[0] > (island.max_x - island.min_x) / 2
    assert countertop.scale[1] > (island.max_y - island.min_y) / 2

    cabinet_panels = [
        item for item in plan.furnishings if item.name.startswith("Island cabinet panel")
    ]
    assert len(cabinet_panels) == 3
    assert all(island.min_x < item.location[0] < island.max_x for item in cabinet_panels)
    assert all(item.location[1] < island.min_y for item in cabinet_panels)
    assert all(item.material == "cabinetry" for item in cabinet_panels)

    for name in ("Oak island stool 1", "Oak island stool 2"):
        item = by_name[name]
        assert island.min_x < item.location[0] < island.max_x
        assert item.location[1] < island.min_y

    for name in ("Island pendant 1", "Island pendant 2"):
        item = by_name[name]
        assert island.min_x < item.location[0] < island.max_x
        assert item.location[1] == pytest.approx(island.center[1])
        assert item.location[2] > island.max_z


def test_room_cameras_frame_the_features_their_labels_promise() -> None:
    module = scene_plan_module()
    bounds = representative_bounds()
    plan = module.build_warm_scene_plan(**bounds)
    cameras = {camera.name: camera for camera in plan.cameras}
    furnishings = {item.name: item for item in plan.furnishings}
    sofa = furnishings["Linen sofa seat"]
    planter = furnishings["Ceramic planter"]

    assert cameras["KITCHEN"].target[:2] == pytest.approx(bounds["island"].center[:2])
    assert cameras["KITCHEN"].target[2] > bounds["island"].max_z
    assert 30.0 <= cameras["KITCHEN"].lens <= 36.0
    assert cameras["KITCHEN"].location[0] < bounds["island"].min_x
    assert cameras["KITCHEN"].location[0] < bounds["floor"].min_x
    assert cameras["KITCHEN"].location[1] < bounds["floor"].min_y
    assert cameras["LIVING_ROOM"].location[0] > sofa.location[0]
    assert cameras["LIVING_ROOM"].location[0] < bounds["tv"].min_x
    assert cameras["LIVING_ROOM"].location[1] > bounds["floor"].max_y - 0.60
    assert cameras["LIVING_ROOM"].target[0] == pytest.approx(sofa.location[0])
    assert cameras["LIVING_ROOM"].target[2] < sofa.location[2] + 0.25
    assert cameras["LIVING_ROOM"].lens <= 32.0
    assert math.dist(cameras["LIVING_ROOM"].location[:2], planter.location[:2]) > 1.5
    assert cameras["PLAN"].orthographic_scale is not None

    assert math.dist(cameras["KITCHEN"].location, cameras["KITCHEN"].target) > 4.0
    assert math.dist(cameras["LIVING_ROOM"].location, cameras["LIVING_ROOM"].target) > 2.0
