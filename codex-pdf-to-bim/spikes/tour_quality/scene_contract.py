"""Deterministic tour projection of HearthView's canonical A-1 spatial model."""

from __future__ import annotations

from dataclasses import dataclass

from hearthview.a1_spatial import A1SpatialModel, build_a1_spatial_model
from hearthview.canonical import canonical_hash
from hearthview.units import TICKS_PER_INCH


def ticks_to_meters(ticks: int) -> float:
    return round((ticks / TICKS_PER_INCH) * 0.0254, 4)


_CANONICAL = build_a1_spatial_model()
SPAN_METERS = ticks_to_meters(_CANONICAL.bounds.width_ticks)
ROOM_DEPTH_METERS = ticks_to_meters(_CANONICAL.bounds.depth_ticks)
COUNTER_ZONE_DEPTH_METERS = ticks_to_meters(_CANONICAL.counter_depth_ticks)
CEILING_HEIGHT_METERS = ticks_to_meters(_CANONICAL.main_ceiling_height_ticks)
ISLAND_WIDTH_METERS = ticks_to_meters(_CANONICAL.island.width_ticks)
ISLAND_DEPTH_METERS = ticks_to_meters(_CANONICAL.island.depth_ticks)
WEST_CLEARANCE_METERS = ticks_to_meters(
    _CANONICAL.island.x_ticks - _CANONICAL.counter_depth_ticks
)
NORTH_CLEARANCE_METERS = ticks_to_meters(
    _CANONICAL.island.y_ticks - _CANONICAL.counter_depth_ticks
)
SOUTH_TRANSITION_METERS = ticks_to_meters(
    _CANONICAL.bounds.depth_ticks - _CANONICAL.island.max_y_ticks
)
LIVING_CLEAR_WIDTH_METERS = ticks_to_meters(_CANONICAL.living_width_ticks)
EYE_HEIGHT_METERS = 1.65

DIMENSION_TOLERANCE_METERS = 0.003
SCHEMA = "hearthview-tour-spike/v1"
SCENE_LABEL = "Quality spike · visual staging"

_PRINTED_DIMENSIONS = (
    ("span", SPAN_METERS, "A-1 printed dimension"),
    ("room_depth", ROOM_DEPTH_METERS, "A-1 printed dimension"),
    ("counter_zone_depth", COUNTER_ZONE_DEPTH_METERS, "A-1 derived dimension"),
    ("ceiling", CEILING_HEIGHT_METERS, "A-1 printed dimension"),
    ("island_width", ISLAND_WIDTH_METERS, "A-1 printed dimension"),
    ("island_depth", ISLAND_DEPTH_METERS, "A-1 printed dimension"),
    ("west_clearance", WEST_CLEARANCE_METERS, "A-1 printed dimension"),
    ("north_clearance", NORTH_CLEARANCE_METERS, "A-1 printed dimension"),
    ("south_transition", SOUTH_TRANSITION_METERS, "A-1 printed dimension"),
    ("living_clear_width", LIVING_CLEAR_WIDTH_METERS, "A-1 printed dimension"),
    ("eye_height", EYE_HEIGHT_METERS, "tour navigation requirement"),
)
_PROVISIONAL_CATEGORIES = (
    "cabinetry_detail",
    "hardware",
    "finishes",
    "furniture",
    "decor",
    "undimensioned_offsets",
)
_REQUIRED_ORDERS = (
    ("north_sink_wall", ("tower", "dishwasher", "sink", "trash", "tower")),
    ("west_wall", ("upper_cabinets", "range", "upper_cabinets", "refrigerator")),
    ("north_glazing", ("kitchen_window_group", "deck_door_group")),
    (
        "east_south_transitions",
        ("family_east_window", "tv_wall", "mudroom_opening", "south_living_opening"),
    ),
)
_REQUIRED_OPENINGS = (
    "kitchen_window_group",
    "deck_door_group",
    "family_east_window",
    "mudroom_opening",
    "south_living_opening",
)
_REQUIRED_COLLIDERS = ("west_counter", "north_counter", "island", "tv_wall")
_REQUIRED_CAMERAS = ("kitchen_overview", "walk_start", "overhead")


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def to_manifest(self) -> dict[str, float]:
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "min_z": self.min_z,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "max_z": self.max_z,
        }


@dataclass(frozen=True)
class Rectangle:
    name: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    def to_manifest(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
        }


@dataclass(frozen=True)
class WallOpening:
    name: str
    wall: str
    footprint: Rectangle

    def to_manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "wall": self.wall,
            "footprint": self.footprint.to_manifest(),
        }


@dataclass(frozen=True)
class OrderedWallItems:
    name: str
    items: tuple[str, ...]

    def to_manifest(self) -> dict[str, object]:
        return {"name": self.name, "items": list(self.items)}


@dataclass(frozen=True)
class CameraPreset:
    name: str
    position: tuple[float, float, float]
    target: tuple[float, float, float]
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)

    def to_manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "position": list(self.position),
            "target": list(self.target),
            "up": list(self.up),
        }


@dataclass(frozen=True)
class OrientationSpec:
    bounds: Rectangle
    north_vector: tuple[int, int]
    regions: tuple[Rectangle, ...]
    openings: tuple[WallOpening, ...]

    def to_manifest(self) -> dict[str, object]:
        return {
            "bounds": self.bounds.to_manifest(),
            "north_vector": list(self.north_vector),
            "north_up": self.north_vector == (0, -1),
            "regions": [region.to_manifest() for region in self.regions],
            "openings": [opening.to_manifest() for opening in self.openings],
        }


@dataclass(frozen=True)
class PrintedDimension:
    name: str
    meters: float
    source: str

    def to_manifest(self) -> dict[str, float | str]:
        return {"name": self.name, "meters": self.meters, "source": self.source}


@dataclass(frozen=True)
class SceneContract:
    schema: str
    label: str
    canonical_geometry: bool
    canonical_model_hash: str
    canonical_geometry_hash: str
    envelope: Bounds | None
    counter_zone_depth: float
    printed_dimensions: tuple[PrintedDimension, ...]
    wall_openings: tuple[WallOpening, ...]
    island_footprint: Rectangle
    living_clear_area: Rectangle
    cabinet_appliance_order: tuple[OrderedWallItems, ...]
    walkable_polygon: tuple[tuple[float, float], ...]
    collision_rectangles: tuple[Rectangle, ...]
    camera_presets: tuple[CameraPreset, ...]
    orientation: OrientationSpec
    provisional_categories: tuple[str, ...]

    def to_manifest(self) -> dict[str, object]:
        """Return a stable, primitive-only representation for Blender and the browser."""
        return {
            "schema": self.schema,
            "label": self.label,
            "canonical_geometry": self.canonical_geometry,
            "canonical_model_hash": self.canonical_model_hash,
            "canonical_geometry_hash": self.canonical_geometry_hash,
            "envelope": self.envelope.to_manifest() if self.envelope else None,
            "counter_zone_depth_meters": self.counter_zone_depth,
            "printed_dimensions": [item.to_manifest() for item in self.printed_dimensions],
            "wall_openings": [item.to_manifest() for item in self.wall_openings],
            "island_footprint": self.island_footprint.to_manifest(),
            "living_clear_area": self.living_clear_area.to_manifest(),
            "cabinet_appliance_order": [
                item.to_manifest() for item in self.cabinet_appliance_order
            ],
            "walkable_polygon": [list(point) for point in self.walkable_polygon],
            "collision_rectangles": [
                item.to_manifest() for item in self.collision_rectangles
            ],
            "camera_presets": [item.to_manifest() for item in self.camera_presets],
            "orientation": self.orientation.to_manifest(),
            "provisional_categories": list(self.provisional_categories),
        }


def build_scene_contract(spatial: A1SpatialModel | None = None) -> SceneContract:
    """Project canonical ticks to the Blender/browser meter coordinate system."""
    spatial = spatial or build_a1_spatial_model()
    span = ticks_to_meters(spatial.bounds.width_ticks)
    envelope_depth = ticks_to_meters(spatial.bounds.depth_ticks)
    ceiling = ticks_to_meters(spatial.main_ceiling_height_ticks)
    counter_depth = ticks_to_meters(spatial.counter_depth_ticks)
    island_min_x = ticks_to_meters(spatial.island.x_ticks)
    island_min_y = ticks_to_meters(spatial.island.y_ticks)
    island = Rectangle(
        "island",
        island_min_x,
        island_min_y,
        ticks_to_meters(spatial.island.max_x_ticks),
        ticks_to_meters(spatial.island.max_y_ticks),
    )
    living_start = span - ticks_to_meters(spatial.living_width_ticks)
    north = spatial.wall("kitchen_north")
    east = spatial.wall("family_east")
    south = spatial.wall("family_south")
    north_window, deck_glazing = north.segments
    east_window, _tv_zone, mudroom = east.segments
    south_opening = south.segments[1]
    wall_openings = (
        WallOpening(
            "kitchen_window_group",
            "north",
            Rectangle(
                "kitchen_window_group",
                ticks_to_meters(north_window.start_ticks),
                0.0,
                ticks_to_meters(north_window.end_ticks),
                ticks_to_meters(north.thickness_ticks),
            ),
        ),
        WallOpening(
            "deck_door_group",
            "north",
            Rectangle(
                "deck_door_group",
                ticks_to_meters(deck_glazing.start_ticks),
                0.0,
                ticks_to_meters(deck_glazing.end_ticks),
                ticks_to_meters(north.thickness_ticks),
            ),
        ),
        WallOpening(
            "family_east_window",
            "east",
            Rectangle(
                "family_east_window",
                ticks_to_meters(east.origin_x_ticks),
                ticks_to_meters(east_window.start_ticks),
                span,
                ticks_to_meters(east_window.end_ticks),
            ),
        ),
        WallOpening(
            "mudroom_opening",
            "east",
            Rectangle(
                "mudroom_opening",
                ticks_to_meters(east.origin_x_ticks),
                ticks_to_meters(mudroom.start_ticks),
                span,
                ticks_to_meters(mudroom.end_ticks),
            ),
        ),
        WallOpening(
            "south_living_opening",
            "south",
            Rectangle(
                "south_living_opening",
                ticks_to_meters(south.origin_x_ticks + south_opening.start_ticks),
                envelope_depth - ticks_to_meters(south.thickness_ticks),
                ticks_to_meters(south.origin_x_ticks + south_opening.end_ticks),
                envelope_depth,
            ),
        ),
    )
    regions = tuple(
        Rectangle(
            region.id,
            ticks_to_meters(region.bounds.x_ticks),
            ticks_to_meters(region.bounds.y_ticks),
            ticks_to_meters(region.bounds.max_x_ticks),
            ticks_to_meters(region.bounds.max_y_ticks),
        )
        for region in spatial.regions
    )
    orientation = OrientationSpec(
        bounds=Rectangle("focused_a1", 0.0, 0.0, span, envelope_depth),
        north_vector=spatial.north_vector,
        regions=regions,
        openings=wall_openings,
    )
    geometry_payload = {
        "adapter": "hearthview-tour-adapter/v2",
        "canonical": spatial.canonical_payload(),
    }
    return SceneContract(
        schema=SCHEMA,
        label=SCENE_LABEL,
        canonical_geometry=False,
        canonical_model_hash=spatial.canonical_hash(),
        canonical_geometry_hash=canonical_hash(geometry_payload),
        envelope=Bounds(0.0, 0.0, 0.0, span, envelope_depth, ceiling),
        counter_zone_depth=counter_depth,
        printed_dimensions=tuple(PrintedDimension(*value) for value in _PRINTED_DIMENSIONS),
        wall_openings=wall_openings,
        island_footprint=island,
        living_clear_area=Rectangle("living_clear_area", living_start, 0.0, SPAN_METERS, envelope_depth),
        cabinet_appliance_order=tuple(
            OrderedWallItems(name, items) for name, items in _REQUIRED_ORDERS
        ),
        walkable_polygon=(
            (0.18, 0.18),
            (span - 0.18, 0.18),
            (span - 0.18, envelope_depth - 0.18),
            (0.18, envelope_depth - 0.18),
        ),
        collision_rectangles=(
            Rectangle("west_counter", 0.0, 0.0, counter_depth, 2.75),
            Rectangle("north_counter", 0.0, 0.0, 3.70, counter_depth),
            island,
            Rectangle(
                "tv_wall",
                span - 0.18,
                ticks_to_meters(east.segments[1].start_ticks),
                span,
                ticks_to_meters(east.segments[1].end_ticks),
            ),
        ),
        camera_presets=(
            CameraPreset("kitchen_overview", (0.70, envelope_depth - 0.55, 1.65), (island.max_x, island.max_y, 0.90)),
            CameraPreset("walk_start", (4.15, envelope_depth - 0.65, EYE_HEIGHT_METERS), (5.20, 2.10, EYE_HEIGHT_METERS)),
            CameraPreset(
                "overhead",
                (span / 2, envelope_depth / 2, 8.0),
                (span / 2, envelope_depth / 2, 0.0),
                (0.0, -1.0, 0.0),
            ),
        ),
        orientation=orientation,
        provisional_categories=_PROVISIONAL_CATEGORIES,
    )


def validate_scene_contract(contract: SceneContract) -> tuple[str, ...]:
    """Return independent, actionable errors without changing the supplied contract."""
    errors: list[str] = []
    if contract.schema != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    if contract.label != SCENE_LABEL:
        errors.append(f"scene label must be {SCENE_LABEL!r}")
    if contract.canonical_geometry:
        errors.append("display scene must not be marked as canonical geometry")
    expected_spatial = build_a1_spatial_model()
    if contract.canonical_model_hash != expected_spatial.canonical_hash():
        errors.append("canonical model hash must match the A-1 spatial model")
    expected_contract = build_scene_contract(expected_spatial)
    if contract.canonical_geometry_hash != expected_contract.canonical_geometry_hash:
        errors.append("canonical geometry hash must match the A-1 tour projection")
    if contract.orientation.north_vector != expected_spatial.north_vector:
        errors.append("orientation must use canonical north")
    if not isinstance(contract.envelope, Bounds):
        errors.append("envelope must be a Bounds instance")
        return tuple(errors)
    envelope = contract.envelope

    dimensions = {item.name: item for item in contract.printed_dimensions}
    for name, expected, source in _PRINTED_DIMENSIONS:
        actual = dimensions.get(name)
        if actual is None:
            errors.append(f"missing printed dimension {name}")
        elif abs(actual.meters - expected) > DIMENSION_TOLERANCE_METERS:
            errors.append(
                f"printed dimension {name} must be {expected} m within 0.003 m"
            )
        elif actual.source != source:
            errors.append(f"printed dimension {name} must cite {source!r}")
    if len(dimensions) != len(contract.printed_dimensions):
        errors.append("printed dimension names must be unique")

    _validate_dimension(
        errors, "envelope span", envelope.max_x - envelope.min_x, SPAN_METERS
    )
    _validate_dimension(
        errors, "envelope room depth", envelope.max_y - envelope.min_y, ROOM_DEPTH_METERS
    )
    _validate_dimension(
        errors, "envelope ceiling", envelope.max_z - envelope.min_z, CEILING_HEIGHT_METERS
    )
    _validate_dimension(
        errors, "counter zone depth", contract.counter_zone_depth, COUNTER_ZONE_DEPTH_METERS
    )
    _validate_dimension(errors, "island width", contract.island_footprint.width, ISLAND_WIDTH_METERS)
    _validate_dimension(errors, "island depth", contract.island_footprint.depth, ISLAND_DEPTH_METERS)
    colliders = {rectangle.name: rectangle for rectangle in contract.collision_rectangles}
    west_counter = colliders.get("west_counter")
    north_counter = colliders.get("north_counter")
    if west_counter is not None:
        _validate_dimension(
            errors,
            "west clearance",
            contract.island_footprint.min_x - west_counter.max_x,
            WEST_CLEARANCE_METERS,
        )
    if north_counter is not None:
        _validate_dimension(
            errors,
            "north clearance",
            contract.island_footprint.min_y - north_counter.max_y,
            NORTH_CLEARANCE_METERS,
        )
    _validate_dimension(
        errors, "south transition", envelope.max_y - contract.island_footprint.max_y, SOUTH_TRANSITION_METERS
    )
    _validate_dimension(errors, "living clear width", contract.living_clear_area.width, LIVING_CLEAR_WIDTH_METERS)

    opening_names = tuple(opening.name for opening in contract.wall_openings)
    for name in _REQUIRED_OPENINGS:
        if name not in opening_names:
            errors.append(f"missing wall opening {name}")
    if opening_names != _REQUIRED_OPENINGS:
        errors.append("wall opening order must match the A-1 contract")
    expected_openings = {
        opening.name: opening.footprint for opening in expected_contract.wall_openings
    }
    for opening in contract.wall_openings:
        expected = expected_openings.get(opening.name)
        if expected is None:
            continue
        if any(
            abs(actual - canonical) > DIMENSION_TOLERANCE_METERS
            for actual, canonical in (
                (opening.footprint.min_x, expected.min_x),
                (opening.footprint.min_y, expected.min_y),
                (opening.footprint.max_x, expected.max_x),
                (opening.footprint.max_y, expected.max_y),
            )
        ):
            errors.append(f"wall opening {opening.name} must match its canonical station")

    orders = {order.name: order.items for order in contract.cabinet_appliance_order}
    for name, expected in _REQUIRED_ORDERS:
        if orders.get(name) != expected:
            errors.append(f"A-1 order for {name} must be {list(expected)!r}")
    if tuple(orders) != tuple(name for name, _items in _REQUIRED_ORDERS):
        errors.append("cabinet/appliance order groups must have stable A-1 ordering")

    if len(contract.walkable_polygon) < 3:
        errors.append("walkable polygon must contain at least three points")
    elif any(
        x < envelope.min_x or x > envelope.max_x
        or y < envelope.min_y or y > envelope.max_y
        for x, y in contract.walkable_polygon
    ):
        errors.append("walkable polygon must remain inside the envelope")

    collider_names = tuple(colliders)
    for name in _REQUIRED_COLLIDERS:
        if name not in collider_names:
            errors.append(f"missing collision rectangle {name}")
    if collider_names != _REQUIRED_COLLIDERS:
        errors.append("collision rectangle order must remain stable")

    cameras = {camera.name: camera for camera in contract.camera_presets}
    for name in _REQUIRED_CAMERAS:
        if name not in cameras:
            errors.append(f"missing camera preset {name}")
    walk_start = cameras.get("walk_start")
    if walk_start is not None:
        _validate_dimension(errors, "eye height", walk_start.position[2], EYE_HEIGHT_METERS)
    if tuple(cameras) != _REQUIRED_CAMERAS:
        errors.append("camera preset order must remain stable")

    if contract.provisional_categories != _PROVISIONAL_CATEGORIES:
        errors.append("provisional categories must exactly match the visual-staging boundary")
    return tuple(errors)


def _validate_dimension(
    errors: list[str], name: str, actual: float, expected: float
) -> None:
    if abs(actual - expected) > DIMENSION_TOLERANCE_METERS:
        errors.append(f"{name} must be {expected} m within 0.003 m")
