from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Primitive = Literal["BOX", "CYLINDER", "SPHERE"]


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def center(self) -> tuple[float, float, float]:
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2,
        )


@dataclass(frozen=True)
class Furnishing:
    name: str
    primitive: Primitive
    location: tuple[float, float, float]
    scale: tuple[float, float, float]
    material: str
    bevel: float = 0.05


@dataclass(frozen=True)
class Camera:
    name: str
    location: tuple[float, float, float]
    target: tuple[float, float, float]
    lens: float
    orthographic_scale: float | None = None


@dataclass(frozen=True)
class ScenePlan:
    furnishings: tuple[Furnishing, ...]
    cameras: tuple[Camera, ...]


def build_warm_scene_plan(*, floor: Bounds, island: Bounds, tv: Bounds) -> ScenePlan:
    floor_top = floor.max_z
    floor_span_x = floor.max_x - floor.min_x
    floor_span_y = floor.max_y - floor.min_y
    island_x, island_y, _island_z = island.center
    tv_x, tv_y, _tv_z = tv.center

    sofa_x = max(island.max_x + 1.25, min(tv.min_x - 2.2, floor.max_x - 1.35))
    living_center_x = (sofa_x + tv.min_x) / 2
    stool_y = island.min_y - 0.36
    pendant_z = max(island.max_z + 1.05, floor_top + 2.05)
    island_positions = (
        island.min_x + (island.max_x - island.min_x) * 0.34,
        island.min_x + (island.max_x - island.min_x) * 0.66,
    )
    cabinet_panel_width = (island.max_x - island.min_x) / 3
    cabinet_panel_positions = tuple(
        island.min_x + cabinet_panel_width * (index + 0.5) for index in range(3)
    )

    furnishings = (
        Furnishing(
            "Honed stone island top",
            "BOX",
            (island_x, island_y, island.max_z + 0.045),
            (
                (island.max_x - island.min_x) / 2 + 0.045,
                (island.max_y - island.min_y) / 2 + 0.045,
                0.045,
            ),
            "stone",
            0.025,
        ),
        *(
            Furnishing(
                f"Island cabinet panel {index + 1}",
                "BOX",
                (panel_x, island.min_y - 0.018, floor_top + 0.47),
                (cabinet_panel_width / 2 - 0.018, 0.018, 0.38),
                "cabinetry",
                0.012,
            )
            for index, panel_x in enumerate(cabinet_panel_positions)
        ),
        Furnishing("Wool living-room rug", "BOX", (living_center_x, tv_y, floor_top + 0.025), (1.35, 1.55, 0.025), "wool", 0.035),
        Furnishing("Linen sofa base", "BOX", (sofa_x - 0.04, tv_y, floor_top + 0.13), (0.50, 1.23, 0.10), "oak", 0.08),
        Furnishing("Linen sofa seat", "BOX", (sofa_x, tv_y, floor_top + 0.33), (0.45, 1.15, 0.14), "linen", 0.12),
        Furnishing("Linen sofa back", "BOX", (sofa_x - 0.40, tv_y, floor_top + 0.64), (0.13, 1.18, 0.34), "linen", 0.11),
        Furnishing("Linen sofa arm 1", "BOX", (sofa_x, tv_y - 1.08, floor_top + 0.45), (0.48, 0.12, 0.25), "linen", 0.10),
        Furnishing("Linen sofa arm 2", "BOX", (sofa_x, tv_y + 1.08, floor_top + 0.45), (0.48, 0.12, 0.25), "linen", 0.10),
        Furnishing("Sofa cushion 1", "BOX", (sofa_x + 0.10, tv_y - 0.54, floor_top + 0.37), (0.34, 0.49, 0.09), "linen_light", 0.11),
        Furnishing("Sofa cushion 2", "BOX", (sofa_x + 0.10, tv_y + 0.54, floor_top + 0.37), (0.34, 0.49, 0.09), "linen_light", 0.11),
        Furnishing("Oak coffee table", "CYLINDER", (living_center_x + 0.15, tv_y, floor_top + 0.34), (0.62, 0.88, 0.06), "oak", 0.03),
        Furnishing("Coffee table base", "CYLINDER", (living_center_x + 0.15, tv_y, floor_top + 0.18), (0.14, 0.14, 0.18), "charcoal", 0.02),
        Furnishing("Oak island stool 1", "CYLINDER", (island_positions[0], stool_y, floor_top + 0.67), (0.25, 0.25, 0.07), "oak", 0.04),
        Furnishing("Oak island stool 2", "CYLINDER", (island_positions[1], stool_y, floor_top + 0.67), (0.25, 0.25, 0.07), "oak", 0.04),
        Furnishing("Stool base 1", "CYLINDER", (island_positions[0], stool_y, floor_top + 0.33), (0.075, 0.075, 0.33), "charcoal", 0.02),
        Furnishing("Stool base 2", "CYLINDER", (island_positions[1], stool_y, floor_top + 0.33), (0.075, 0.075, 0.33), "charcoal", 0.02),
        Furnishing("Island pendant 1", "SPHERE", (island_positions[0], island_y, pendant_z), (0.24, 0.24, 0.16), "linen_light", 0.04),
        Furnishing("Island pendant 2", "SPHERE", (island_positions[1], island_y, pendant_z), (0.24, 0.24, 0.16), "linen_light", 0.04),
        Furnishing("Ceramic planter", "CYLINDER", (tv_x - 0.75, floor.min_y + 0.70, floor_top + 0.24), (0.26, 0.26, 0.24), "ceramic", 0.03),
        Furnishing("Planter foliage 1", "SPHERE", (tv_x - 0.75, floor.min_y + 0.70, floor_top + 0.82), (0.34, 0.28, 0.62), "sage", 0.04),
        Furnishing("Planter foliage 2", "SPHERE", (tv_x - 0.50, floor.min_y + 0.69, floor_top + 0.92), (0.24, 0.20, 0.52), "sage", 0.04),
    )

    cameras = (
        Camera(
            "KITCHEN",
            (
                floor.min_x - min(1.0, floor_span_x * 0.12),
                floor.min_y - min(0.70, floor_span_y * 0.10),
                floor_top + 1.72,
            ),
            (island_x, island_y, island.max_z + 0.12),
            32.0,
        ),
        Camera(
            "LIVING_ROOM",
            (
                tv.min_x - 0.40,
                floor.max_y - 0.30,
                floor_top + 1.55,
            ),
            (sofa_x, tv_y, floor_top + 0.56),
            28.0,
        ),
        Camera(
            "AXONOMETRIC",
            (floor.max_x + floor_span_x * 0.42, floor.min_y - floor_span_y * 0.42, floor_top + max(floor_span_x, floor_span_y) * 0.58),
            ((floor.min_x + floor.max_x) / 2, (floor.min_y + floor.max_y) / 2, floor_top + 0.75),
            48.0,
        ),
        Camera(
            "PLAN",
            ((floor.min_x + floor.max_x) / 2, (floor.min_y + floor.max_y) / 2, floor_top + max(floor_span_x, floor_span_y) * 1.35),
            ((floor.min_x + floor.max_x) / 2, (floor.min_y + floor.max_y) / 2, floor_top),
            50.0,
            max(floor_span_x, floor_span_y) * 1.12,
        ),
    )
    return ScenePlan(furnishings=furnishings, cameras=cameras)
