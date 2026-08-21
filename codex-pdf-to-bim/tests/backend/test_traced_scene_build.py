"""Exercise the traced Blender builders without Blender.

`build_scene.py` can only run inside Blender, so this substitutes recording
stubs for `bpy` and `blender_builders` and drives the traced builders against
the committed A-1 scene spec. It cannot prove the render looks right, but it
does catch the failures that actually bit this checkpoint: missing spec keys,
wrong builder signatures, geometry placed outside the traced envelope, and
required scene nodes that never get created.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / "spikes/tour_quality/a1_kitchen_scene_spec.json"
pytestmark = pytest.mark.skipif(not SPEC_PATH.is_file(), reason="scene spec missing")

FT = 0.3048


class _FakeContract:
    """Only the camera presets `_build_lighting_and_cameras` reads."""

    def __init__(self, spec: dict) -> None:
        names = {"KITCHEN": "kitchen_overview", "LIVING_ROOM": "walk_start", "PLAN": "overhead"}
        self.camera_presets = [
            types.SimpleNamespace(
                name=names[c["name"]],
                position=tuple(c["location"]),
                target=tuple(c["target"]),
            )
            for c in spec["cameras"] if c["name"] in names
        ]


class _Obj(dict):
    """Stands in for a bpy object; records custom properties by key."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name


def _install_stubs(record: list[tuple]) -> None:
    bpy = types.ModuleType("bpy")
    bpy.types = types.SimpleNamespace(Object=_Obj, Material=object)
    bpy.app = types.SimpleNamespace(version=(5, 2, 0), version_string="5.2.0")
    # The sun is built with the raw bpy.data API rather than a builder helper.
    class _Sun:
        def __init__(self, name, *_a, **_k):
            self.name = name
            self.energy = 0.0
            self.angle = 0.0
            self.color = (1.0, 1.0, 1.0)
            self.rotation_euler = (0.0, 0.0, 0.0)
            self.parent = None

    bpy.data = types.SimpleNamespace(
        lights=types.SimpleNamespace(new=lambda name, type=None: _Sun(name)),
        objects=types.SimpleNamespace(new=lambda name, data: _Sun(name)),
    )
    bpy.ops = types.SimpleNamespace()
    bpy.context = types.SimpleNamespace(
        collection=types.SimpleNamespace(objects=types.SimpleNamespace(link=lambda obj: None))
    )
    sys.modules["bpy"] = bpy
    sys.modules["mathutils"] = types.ModuleType("mathutils")

    builders = types.ModuleType("blender_builders")

    def _maker(kind):
        def call(*args, **kwargs):
            # Builders take the name either positionally or as a keyword.
            if "name" in kwargs:
                name = kwargs["name"]
                rest = args
            elif args and isinstance(args[0], str):
                name, rest = args[0], args[1:]
            else:
                name, rest = f"<{kind}>", args
            record.append((kind, name, rest, kwargs))
            return _Obj(name)
        return call

    for fn in (
        "add_area_light", "add_camera", "add_point_light", "create_box",
        "create_cabinet_unit", "create_curve_tube", "create_cylinder",
        "create_mesh_plane", "create_pbr_material", "create_principled_material",
        "create_root", "create_shaker_front", "create_sofa", "create_sphere",
        "create_stool", "import_gltf_asset", "tag_contract_boundary",
    ):
        setattr(builders, fn, _maker(fn))
    sys.modules["blender_builders"] = builders


@pytest.fixture(scope="module")
def built():
    record: list[tuple] = []
    _install_stubs(record)
    sys.path.insert(0, str(REPO / "spikes/tour_quality"))
    import build_scene  # noqa: E402  (import after stubbing bpy)

    spec = json.loads(SPEC_PATH.read_text())
    materials = {
        key: object() for key in (
            "black", "bronze", "bulb", "cabinet", "cabinet_body", "ceramic",
            "floor", "glass", "leaf", "linen", "navigation", "oak", "plaster",
            "rug", "screen", "steel", "stone", "trim",
        )
    }
    root = _Obj("HV_ARCHITECTURE")
    build_scene._build_traced_architecture(spec, materials, root)
    build_scene._build_traced_kitchen(spec, materials, _Obj("HV_CABINETRY"))
    build_scene._build_traced_living(spec, Path("/assets"), materials, _Obj("HV_FURNITURE"))
    build_scene._build_lighting_and_cameras(
        Path("/assets"), materials, _Obj("HV_LIGHTING"), _Obj("HV_NAVIGATION"),
        _FakeContract(spec), spec,
    )
    return spec, record


def _boxes(record):
    return [(name, args, kwargs) for kind, name, args, kwargs in record if kind == "create_box"]


def test_traced_builders_run_without_error(built) -> None:
    _spec, record = built
    assert record, "traced builders produced no geometry"


def test_required_named_nodes_are_created(built) -> None:
    _spec, record = built
    names = {name for _kind, name, _args, _kwargs in record}

    # These names are what validate_artifact looks for in the exported GLB.
    assert "HV_FLOOR" in names
    assert "HV_ISLAND_STRUCTURE" in names


def test_island_geometry_matches_its_printed_size(built) -> None:
    _spec, record = built
    name, args, _kwargs = next(b for b in _boxes(record) if b[0] == "HV_ISLAND_STRUCTURE")
    size = args[0]

    assert size[0] / FT == pytest.approx(8 + 7 / 12, abs=0.1)
    assert size[1] / FT == pytest.approx(4 + 3 / 12, abs=0.1)


def test_all_geometry_stays_inside_the_traced_envelope(built) -> None:
    spec, record = built
    envelope = spec["envelope"]
    margin = 0.6  # wall bodies sit outside the interior face

    for name, args, _kwargs in _boxes(record):
        if len(args) < 2:
            continue
        (sx, sy, _sz), (cx, cy, _cz) = args[0], args[1]
        assert -margin <= cx - sx / 2, f"{name} escapes west"
        assert cx + sx / 2 <= envelope["span"] + margin, f"{name} escapes east"
        assert -margin <= cy - sy / 2, f"{name} escapes north"
        assert cy + sy / 2 <= envelope["arm_south"] + margin, f"{name} escapes south"


def test_appliances_are_placed_at_the_traced_stations(built) -> None:
    spec, record = built
    west = spec["kitchen"]["west_run"]
    calls = {name: (args, kwargs) for _k, name, args, kwargs in record}

    # _create_range_and_hood/_create_refrigerator take a run start, not a centre.
    assert "HV_RANGE_BODY" in calls
    assert "HV_REFRIGERATOR_BODY" in calls
    range_centre = calls["HV_RANGE_BODY"][0][1][1]
    fridge_centre = calls["HV_REFRIGERATOR_BODY"][0][1][1]
    assert range_centre == pytest.approx(west["range"]["center_y"], abs=0.02)
    assert fridge_centre == pytest.approx(west["fridge"]["center_y"], abs=0.02)
    # The range must sit north of the refrigerator, as drawn.
    assert range_centre < fridge_centre


def test_sink_and_dishwasher_follow_the_printed_callouts(built) -> None:
    spec, record = built
    north = spec["kitchen"]["north_run"]
    calls = {name: args for _k, name, args, _kw in record}

    assert calls["HV_SINK_RIM"][1][0] == pytest.approx(north["sink"]["center_x"], abs=0.02)
    dishwasher_centre = calls["HV_DISHWASHER_BODY"][1][0]
    assert dishwasher_centre == pytest.approx(north["dishwasher"]["center_x"], abs=0.02)
    assert dishwasher_centre < calls["HV_SINK_RIM"][1][0]


def test_every_opening_gets_glazing(built) -> None:
    spec, record = built
    roots = {name for kind, name, _a, _k in record if kind == "create_root"}

    for item in [*spec["windows"], *spec["doors"]]:
        assert f"HV_OPENING_{item['name']}" in roots


def _inside(point, rect) -> bool:
    x0, y0, x1, y1 = rect
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def test_no_eye_level_camera_sits_inside_the_island(built) -> None:
    """A camera inside a solid renders a blank frame — the failure we hit."""
    spec, record = built
    island = spec["kitchen"]["island"]

    for _kind, name, _args, kwargs in record:
        if not name.startswith("HV_CAMERA"):
            continue
        position = kwargs.get("position")
        if position and position[2] < 2.2:
            assert not _inside(position, island), f"{name} is inside the island"


def test_cameras_are_created_for_every_preset(built) -> None:
    _spec, record = built
    cameras = {name for kind, name, _a, _k in record if kind == "add_camera"}

    assert "HV_CAMERA_HERO" in cameras
    for preset in ("KITCHEN_OVERVIEW", "WALK_START", "OVERHEAD"):
        assert f"HV_CAMERA_{preset}" in cameras


def test_pendants_hang_over_the_island(built) -> None:
    spec, record = built
    x0, y0, x1, y1 = spec["kitchen"]["island"]

    bulbs = [
        kwargs["location"]
        for kind, name, _a, kwargs in record
        if name.startswith("HV_PENDANT_BULB")
    ]
    assert len(bulbs) == 3
    for location in bulbs:
        assert x0 <= location[0] <= x1, "pendant is off the island"
        assert y0 - 0.1 <= location[1] <= y1 + 0.1


def test_living_staging_stays_in_the_clear_area(built) -> None:
    spec, record = built
    x0, y0, x1, y1 = spec["living"]["clear_area"]
    margin = 0.8

    for kind, name, args, kwargs in record:
        if name not in ("HV_LIVING_RUG", "HV_LINEN_SOFA", "HV_IMPORTED_MODERN_COFFEE_TABLE_01"):
            continue
        point = kwargs.get("location") or kwargs.get("floor_center") or (args[1] if len(args) > 1 else None)
        assert point is not None, name
        assert x0 - margin <= point[0] <= x1 + margin, f"{name} outside clear area in x"
        assert y0 - margin <= point[1] <= y1 + margin, f"{name} outside clear area in y"


def test_tv_hangs_on_the_east_wall_at_the_marked_height(built) -> None:
    spec, record = built
    span = spec["envelope"]["span"]
    tv = spec["living"]["tv"]
    args = next(a for kind, name, a, _k in record if name == "HV_TV_SCREEN")

    assert args[1][0] == pytest.approx(span - 0.08, abs=0.01)
    assert args[1][1] == pytest.approx(tv["center_y"], abs=0.02)
