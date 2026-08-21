from __future__ import annotations

from dataclasses import replace
import json

import pytest


def scene_contract_module():
    from spikes.tour_quality import scene_contract

    return scene_contract


def test_manifest_exposes_the_hand_derived_printed_dimensions_in_meters() -> None:
    """Break caught: a Blender consumer receives a wrong A-1 measurement."""
    module = scene_contract_module()

    manifest = module.build_scene_contract().to_manifest()

    assert manifest["schema"] == "hearthview-tour-spike/v1"
    assert manifest["label"] == "Quality spike · visual staging"
    assert manifest["printed_dimensions"] == [
        {"name": "span", "meters": 9.1694, "source": "A-1 printed dimension"},
        {"name": "room_depth", "meters": 4.8514, "source": "A-1 printed dimension"},
        {"name": "counter_zone_depth", "meters": 0.6604, "source": "A-1 derived dimension"},
        {"name": "ceiling", "meters": 2.5654, "source": "A-1 printed dimension"},
        {"name": "island_width", "meters": 2.6162, "source": "A-1 printed dimension"},
        {"name": "island_depth", "meters": 1.2954, "source": "A-1 printed dimension"},
        {"name": "west_clearance", "meters": 1.0668, "source": "A-1 printed dimension"},
        {"name": "north_clearance", "meters": 1.0668, "source": "A-1 printed dimension"},
        {"name": "south_transition", "meters": 1.8288, "source": "A-1 printed dimension"},
        {"name": "living_clear_width", "meters": 4.4958, "source": "A-1 printed dimension"},
        {"name": "eye_height", "meters": 1.65, "source": "tour navigation requirement"},
    ]
    assert manifest["canonical_geometry"] is False
    assert manifest["counter_zone_depth_meters"] == 0.6604
    assert manifest["envelope"]["max_y"] == 4.8514
    assert manifest["island_footprint"]["min_x"] == 1.7272
    assert manifest["island_footprint"]["min_y"] == 1.7272


def test_manifest_is_json_safe_and_preserves_contract_order() -> None:
    """Break caught: nondeterministic or non-JSON manifest data reaches Blender/browser tools."""
    module = scene_contract_module()

    manifest = module.build_scene_contract().to_manifest()

    assert json.loads(json.dumps(manifest)) == manifest
    assert [item["name"] for item in manifest["wall_openings"]] == [
        "kitchen_window_group",
        "deck_door_group",
        "mudroom_opening",
        "south_living_opening",
    ]
    assert [item["name"] for item in manifest["cabinet_appliance_order"]] == [
        "north_sink_wall",
        "west_wall",
        "north_glazing",
        "east_south_transitions",
    ]


def test_manifest_marks_only_the_required_visual_staging_categories_as_provisional() -> None:
    """Break caught: a staging choice is accidentally presented as a measured claim."""
    module = scene_contract_module()

    assert module.build_scene_contract().to_manifest()["provisional_categories"] == [
        "cabinetry_detail",
        "hardware",
        "finishes",
        "furniture",
        "decor",
        "undimensioned_offsets",
    ]


@pytest.mark.parametrize(
    ("dimension_name", "wrong_value"),
    [
        ("span", 9.1730),
        ("room_depth", 4.8550),
        ("counter_zone_depth", 0.6640),
        ("ceiling", 2.5690),
        ("island_width", 2.6200),
        ("island_depth", 1.3000),
        ("west_clearance", 1.0700),
        ("north_clearance", 1.0700),
        ("south_transition", 1.8330),
        ("living_clear_width", 4.5000),
        ("eye_height", 1.6540),
    ],
)
def test_validation_rejects_every_printed_dimension_that_drifts_over_three_millimeters(
    dimension_name: str, wrong_value: float
) -> None:
    """Break caught: an authoritative dimension drifts by more than the 3 mm tolerance."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    dimensions = tuple(
        replace(dimension, meters=wrong_value)
        if dimension.name == dimension_name
        else dimension
        for dimension in contract.printed_dimensions
    )

    errors = module.validate_scene_contract(replace(contract, printed_dimensions=dimensions))

    assert any(dimension_name in error and "0.003" in error for error in errors)


@pytest.mark.parametrize(
    ("field_name", "replacement", "error_fragment"),
    [
        ("wall_openings", (), "wall opening"),
        ("walkable_polygon", (), "walkable polygon"),
        ("collision_rectangles", (), "collision rectangle"),
        ("camera_presets", (), "camera preset"),
    ],
)
def test_validation_rejects_missing_required_scene_objects(
    field_name: str, replacement: tuple[object, ...], error_fragment: str
) -> None:
    """Break caught: the display scene lacks geometry/navigation metadata a consumer needs."""
    module = scene_contract_module()
    contract = module.build_scene_contract()

    errors = module.validate_scene_contract(replace(contract, **{field_name: replacement}))

    assert any(error_fragment in error for error in errors)


@pytest.mark.parametrize(
    "opening_name",
    [
        "kitchen_window_group",
        "deck_door_group",
        "mudroom_opening",
        "south_living_opening",
    ],
)
def test_validation_names_each_missing_required_opening(opening_name: str) -> None:
    """Break caught: one named A-1 opening disappears while other openings remain."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    openings = tuple(
        opening for opening in contract.wall_openings if opening.name != opening_name
    )

    errors = module.validate_scene_contract(replace(contract, wall_openings=openings))

    assert f"missing wall opening {opening_name}" in errors


@pytest.mark.parametrize("collider_name", ["west_counter", "north_counter", "island", "tv_wall"])
def test_validation_names_each_missing_required_collision_rectangle(
    collider_name: str,
) -> None:
    """Break caught: one collision barrier disappears while the rest remain."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    colliders = tuple(
        collider
        for collider in contract.collision_rectangles
        if collider.name != collider_name
    )

    errors = module.validate_scene_contract(
        replace(contract, collision_rectangles=colliders)
    )

    assert f"missing collision rectangle {collider_name}" in errors


@pytest.mark.parametrize("camera_name", ["kitchen_overview", "walk_start", "overhead"])
def test_validation_names_each_missing_required_camera_preset(camera_name: str) -> None:
    """Break caught: one recovery/view camera disappears while the rest remain."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    cameras = tuple(
        camera for camera in contract.camera_presets if camera.name != camera_name
    )

    errors = module.validate_scene_contract(replace(contract, camera_presets=cameras))

    assert f"missing camera preset {camera_name}" in errors


@pytest.mark.parametrize("invalid_envelope", [None, "not-a-bounds"])
def test_validation_reports_an_invalid_envelope_without_dereferencing_it(
    invalid_envelope: object,
) -> None:
    """Break caught: malformed scene input crashes validation instead of returning errors."""
    module = scene_contract_module()
    contract = module.build_scene_contract()

    errors = module.validate_scene_contract(replace(contract, envelope=invalid_envelope))

    assert errors == ("envelope must be a Bounds instance",)


def test_validation_measures_clearances_from_counter_faces_not_walls() -> None:
    """Break caught: 3′-6″ clearances are measured from walls rather than counter faces."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    island_against_wall = replace(
        contract.island_footprint,
        min_x=1.0668,
        max_x=3.6830,
        min_y=1.0668,
        max_y=2.3622,
    )

    errors = module.validate_scene_contract(
        replace(contract, island_footprint=island_against_wall)
    )

    assert any("west clearance" in error for error in errors)
    assert any("north clearance" in error for error in errors)


@pytest.mark.parametrize(
    ("counter_name", "face_field", "clearance_name"),
    [
        ("west_counter", "max_x", "west clearance"),
        ("north_counter", "max_y", "north clearance"),
    ],
)
def test_validation_uses_the_actual_named_counter_face(
    counter_name: str, face_field: str, clearance_name: str
) -> None:
    """Break caught: an authored counter face moves without invalidating its clearance."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    colliders = tuple(
        replace(collider, **{face_field: 0.7004})
        if collider.name == counter_name
        else collider
        for collider in contract.collision_rectangles
    )

    errors = module.validate_scene_contract(
        replace(contract, collision_rectangles=colliders)
    )

    assert any(clearance_name in error for error in errors)


@pytest.mark.parametrize(
    ("order_name", "wrong_items"),
    [
        ("north_sink_wall", ("tower", "sink", "dishwasher", "trash", "tower")),
        ("west_wall", ("range", "upper_cabinets", "upper_cabinets", "refrigerator")),
        ("north_glazing", ("deck_door_group", "kitchen_window_group")),
        ("east_south_transitions", ("tv_wall", "mudroom_opening", "south_living_opening")),
    ],
)
def test_validation_rejects_wrong_a1_cabinet_opening_and_transition_order(
    order_name: str, wrong_items: tuple[str, ...]
) -> None:
    """Break caught: a named A-1 wall sequence is reordered before scene construction."""
    module = scene_contract_module()
    contract = module.build_scene_contract()
    orders = tuple(
        replace(order, items=wrong_items) if order.name == order_name else order
        for order in contract.cabinet_appliance_order
    )

    errors = module.validate_scene_contract(replace(contract, cabinet_appliance_order=orders))

    assert any(order_name in error and "order" in error for error in errors)


def test_validation_rejects_an_unapproved_provisional_category() -> None:
    """Break caught: the staging boundary changes without an explicit contract update."""
    module = scene_contract_module()
    contract = module.build_scene_contract()

    errors = module.validate_scene_contract(
        replace(contract, provisional_categories=("finishes",))
    )

    assert any("provisional categories" in error for error in errors)
