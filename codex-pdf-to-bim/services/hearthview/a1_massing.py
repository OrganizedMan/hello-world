"""Extrude the extracted A-1 plan into first-floor massing.

Everything horizontal comes from `a1_extract`, which copies coordinates out of
the PDF. Vertically the drawing set is much poorer, and this module is explicit
about that split:

* **From the sheet.** Ceiling height is printed per room as `CLG HT - 8' 5"`,
  and the stair area carries a `LOW CEILING` note at 6'-3" / 6'-5".
* **Assumed.** Door head height and window sill height appear nowhere in this
  set — it contains three plan sheets and no elevation or section. The values
  below are conventional residential defaults, and every primitive derived from
  them is marked `assumed_height` so a reviewer can see which solids rest on a
  measurement and which rest on a convention.

Plan coordinates are converted to inches (the sheet is 18.0 pt per foot) and
then to integer ticks, so this module hands `geometry._build_glb` the same
`Primitive` boxes the existing compiler uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from hearthview.a1_extract import (
    POINTS_PER_FOOT,
    A1Extraction,
    Opening,
    Shape,
)
from hearthview.a1_trace import PdfRect
from hearthview.geometry import Primitive, StationInterval
from hearthview.units import TICKS_PER_INCH

POINTS_PER_INCH = POINTS_PER_FOOT / 12.0

# Conventional, NOT read from this drawing set. See the module docstring.
ASSUMED_DOOR_HEAD_INCHES = 80.0  # 6'-8"
ASSUMED_WINDOW_SILL_INCHES = 30.0  # 2'-6"
ASSUMED_WINDOW_HEAD_INCHES = 80.0  # 6'-8"
ASSUMED_COUNTER_HEIGHT_INCHES = 36.0
ASSUMED_FIXTURE_HEIGHT_INCHES = 32.0
ASSUMED_STAIR_RISE_INCHES = 7.0  # matches the printed NEW STAIRS riser
FLOOR_SLAB_INCHES = 6.0
# Ceiling board. Like the floor slab this is a construction convention, not a
# printed dimension; it only has to read as a surface overhead.
CEILING_SLAB_INCHES = 5.0
DECK_SLAB_INCHES = 7.0
# A deck is built a step below the interior finished floor -- for the threshold
# and so water runs away from the house. It also has to be built that way here:
# the deck footprint overlaps the floor slab where it meets the building, and
# two coplanar faces at the same height fight for the depth buffer, which is
# the mottled brown-and-white patch that appeared on the third floor.
DECK_STEP_DOWN_INCHES = 1.0

_AXIS_TOLERANCE = 0.75  # points; a bay wall's diagonals exceed this

OpeningKind = Literal["door", "window", "cased_opening"]


class A1MassingError(ValueError):
    """Raised when the extraction cannot support a first-floor massing."""


@dataclass(frozen=True)
class HeightSource:
    """Where a vertical dimension came from."""

    inches: float
    provenance: Literal["dimension_verified", "assumed"]
    note: str


@dataclass(frozen=True)
class ClassifiedOpening:
    opening: Opening
    kind: OpeningKind
    width_feet: float
    on_exterior: bool


@dataclass(frozen=True)
class A1Massing:
    ceiling: HeightSource
    primitives: tuple[Primitive, ...]
    openings: tuple[ClassifiedOpening, ...]
    assumed_primitive_ids: frozenset[str]
    approximated_wall_ids: frozenset[str]

    @property
    def verified_fraction(self) -> float:
        if not self.primitives:
            return 0.0
        assumed = sum(1 for p in self.primitives if p.element_id in self.assumed_primitive_ids)
        return 1.0 - assumed / len(self.primitives)


def parse_ceiling_height(notes) -> HeightSource:
    """Use the tallest printed ceiling note as the room height.

    The low-ceiling zone by the stair is genuinely lower, so the *modal* room
    height is what the walls are extruded to; the low zone is reported
    separately rather than flattening the whole floor to 6'-3".
    """
    room_heights = [note.inches for note in notes if note.kind == "room"]
    if not room_heights:
        raise A1MassingError(
            "No printed room ceiling height was found; refusing to assume a wall height."
        )
    common = max(set(room_heights), key=room_heights.count)
    feet, inches = divmod(int(round(common)), 12)
    return HeightSource(
        common,
        "dimension_verified",
        f"printed ceiling note {feet}'-{inches}\" "
        f"({room_heights.count(common)} of {len(room_heights)} room notes)",
    )


def _is_axis_aligned(shape: Shape) -> bool:
    pts = shape.points
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if abs(x1 - x0) > _AXIS_TOLERANCE and abs(y1 - y0) > _AXIS_TOLERANCE:
            return False
    return True


def _classify(
    opening: Opening, doors: tuple[Shape, ...], footprint
) -> ClassifiedOpening:
    b = opening.bounds
    has_swing = any(
        not (
            d.bounds.x1 < b.x0 - 12
            or d.bounds.x0 > b.x1 + 12
            or d.bounds.y1 < b.y0 - 12
            or d.bounds.y0 > b.y1 + 12
        )
        for d in doors
    )
    edge = 2.0 * POINTS_PER_FOOT
    on_exterior = (
        b.x0 - footprint.x0 < edge
        or footprint.x1 - b.x1 < edge
        or b.y0 - footprint.y0 < edge
        or footprint.y1 - b.y1 < edge
    )
    if has_swing:
        kind: OpeningKind = "door"
    elif opening.width_feet >= 5.0:
        kind = "cased_opening"
    elif on_exterior:
        kind = "window"
    else:
        kind = "cased_opening"
    return ClassifiedOpening(opening, kind, opening.width_feet, on_exterior)


def _points_to_ticks(points: float) -> int:
    return int(round(points / POINTS_PER_INCH * TICKS_PER_INCH))


def plan_from_pdf(footprint):
    """Sheet coordinates to plan (east, north), in PDF points.

    North-positive, so (east, north, up) is right-handed and the glTF export
    lands the model the same way round as the drawing. This is a module-level
    function rather than a closure so `chirality.mapping_preserves_handedness`
    can be pointed at the conversion the build actually uses, instead of a copy
    of it that can drift.
    """
    origin_x, base_y = footprint.x0, footprint.y1

    def to_plan(pdf_x: float, pdf_y: float) -> tuple[float, float]:
        return (pdf_x - origin_x, base_y - pdf_y)

    return to_plan


def build_a1_massing(
    extraction: A1Extraction,
    *,
    datum: PdfRect | None = None,
    base_elevation_ticks: int = 0,
) -> A1Massing:
    """Turn the extracted plan into wall solids.

    `datum` sets the horizontal origin. A floor built on its own footprint
    starts at (0, 0), which is right for one floor alone and wrong for a
    building: it would stack every storey's south-west corner together no matter
    where each sits on the plan. Passing one floor's footprint for all of them
    keeps their true relative position, which the sheets support -- A-0's east
    and west walls agree with A-1's to 0.02 ft, and A-2's north edge to 0.01 ft.

    `base_elevation_ticks` lifts the storey to its height in the building.
    """
    walls = extraction.layer("wall_new") + extraction.layer("wall_existing")
    if not walls:
        raise A1MassingError("The extraction contains no walls to extrude.")

    ceiling = parse_ceiling_height(extraction.ceiling_notes)
    # Two different jobs, and conflating them is a bug: the datum fixes where
    # this storey sits relative to the others, while the storey's own footprint
    # is its actual extent -- what its floor slab spans, and which openings are
    # close enough to an outside wall to be windows rather than cased openings.
    origin = datum if datum is not None else extraction.footprint
    footprint = extraction.footprint
    origin_x, base_y = origin.x0, origin.y1

    to_plan = plan_from_pdf(origin)

    def to_ticks_x(px: float) -> int:
        return _points_to_ticks(to_plan(px, base_y)[0])

    def to_ticks_y(py: float) -> int:
        return _points_to_ticks(to_plan(origin_x, py)[1])

    def to_ticks_z(inches: float) -> int:
        return base_elevation_ticks + int(round(inches * TICKS_PER_INCH))

    primitives: list[Primitive] = []
    assumed: set[str] = set()
    approximated: set[str] = set()

    ceiling_z = to_ticks_z(ceiling.inches)
    for index, wall in enumerate(walls):
        b = wall.bounds
        element = f"{wall.layer}.{index:03d}"
        if not _is_axis_aligned(wall):
            # A diagonal bay segment cannot be an axis-aligned box; its bounding
            # box stands in for it and is reported rather than hidden.
            approximated.add(element)
        x0, x1 = sorted((to_ticks_x(b.x0), to_ticks_x(b.x1)))
        y0, y1 = sorted((to_ticks_y(b.y0), to_ticks_y(b.y1)))
        if x1 <= x0 or y1 <= y0:
            continue
        primitives.append(
            Primitive(
                element_id=element,
                part_kind="wall",
                x0_ticks=x0,
                y0_ticks=y0,
                z0_ticks=base_elevation_ticks,
                x1_ticks=x1,
                y1_ticks=y1,
                z1_ticks=ceiling_z,
                station_interval=StationInterval(0, x1 - x0),
            )
        )

    # Floor slab across the traced footprint, so the tour has ground to stand on.
    primitives.append(
        Primitive(
            "floor.slab",
            "floor",
            to_ticks_x(footprint.x0),
            to_ticks_y(footprint.y1),
            to_ticks_z(-FLOOR_SLAB_INCHES),
            to_ticks_x(footprint.x1),
            to_ticks_y(footprint.y0),
            to_ticks_z(0.0),
            StationInterval(0, to_ticks_x(footprint.x1)),
        )
    )

    # Ceiling slab at the printed ceiling height. Without one every room is lit
    # as though open to the sky, which is wrong indoors and is also why the
    # overhead view had nothing to take away: it is a separate part kind so the
    # browser can hide it and look down into the plan.
    primitives.append(
        Primitive(
            "ceiling.slab",
            "ceiling",
            to_ticks_x(footprint.x0),
            to_ticks_y(footprint.y1),
            ceiling_z,
            to_ticks_x(footprint.x1),
            to_ticks_y(footprint.y0),
            ceiling_z + _points_to_ticks(CEILING_SLAB_INCHES * POINTS_PER_INCH),
            StationInterval(0, to_ticks_x(footprint.x1)),
        )
    )

    for name, layer, height, kind in (
        ("counter", "counter", ASSUMED_COUNTER_HEIGHT_INCHES, "counter"),
        ("fixture", "fixture", ASSUMED_FIXTURE_HEIGHT_INCHES, "fixture"),
    ):
        for index, shape in enumerate(extraction.layer(layer)):
            b = shape.bounds
            element = f"{name}.{index:03d}"
            assumed.add(element)  # footprint is measured; the height is not
            x0, x1 = sorted((to_ticks_x(b.x0), to_ticks_x(b.x1)))
            y0, y1 = sorted((to_ticks_y(b.y0), to_ticks_y(b.y1)))
            if x1 <= x0 or y1 <= y0:
                continue
            primitives.append(
                Primitive(
                    element, kind, x0, y0, to_ticks_z(0.0), x1, y1, to_ticks_z(height),
                    StationInterval(0, x1 - x0),
                )
            )

    for index, shape in enumerate(extraction.layer("deck")):
        b = shape.bounds
        x0, x1 = sorted((to_ticks_x(b.x0), to_ticks_x(b.x1)))
        y0, y1 = sorted((to_ticks_y(b.y0), to_ticks_y(b.y1)))
        if x1 > x0 and y1 > y0:
            primitives.append(
                Primitive(
                    f"deck.{index:03d}", "deck", x0, y0,
                    to_ticks_z(-DECK_SLAB_INCHES - DECK_STEP_DOWN_INCHES),
                    x1, y1, to_ticks_z(-DECK_STEP_DOWN_INCHES),
                    StationInterval(0, x1 - x0),
                )
            )

    # Stair treads step up by the riser height printed in the NEW STAIRS note
    # where available; otherwise by the same conventional 7".
    rise = (
        extraction.stair_note.riser_height_inches
        if extraction.stair_note
        else ASSUMED_STAIR_RISE_INCHES
    )
    rise_is_printed = extraction.stair_note is not None
    treads = sorted(extraction.stair_treads, key=lambda t: -t[0][1])
    for index, ((ax, ay), (bx, by)) in enumerate(treads):
        element = f"stair.{index:03d}"
        if not rise_is_printed:
            assumed.add(element)
        x0, x1 = sorted((to_ticks_x(min(ax, bx)), to_ticks_x(max(ax, bx))))
        y_mid = to_ticks_y((ay + by) / 2)
        depth = int(round(6.0 * TICKS_PER_INCH))
        z1 = to_ticks_z(rise * (index + 1))
        if x1 <= x0 or z1 <= base_elevation_ticks:
            continue
        primitives.append(
            Primitive(
                element, "stair", x0, y_mid - depth, base_elevation_ticks,
                x1, y_mid + depth, z1,
                StationInterval(0, x1 - x0),
            )
        )

    doors = extraction.layer("door")
    classified = tuple(_classify(o, doors, footprint) for o in extraction.openings)

    # Openings are already voids: the wall run is split around them. What is
    # missing is the solid above (and, for a window, below) each void.
    for index, item in enumerate(classified):
        b = item.opening.bounds
        x0, x1 = sorted((to_ticks_x(b.x0), to_ticks_x(b.x1)))
        y0, y1 = sorted((to_ticks_y(b.y0), to_ticks_y(b.y1)))
        if x1 <= x0 or y1 <= y0:
            continue

        if item.kind == "window":
            sill = to_ticks_z(ASSUMED_WINDOW_SILL_INCHES)
            head = to_ticks_z(ASSUMED_WINDOW_HEAD_INCHES)
            below = f"sill.{index:03d}"
            assumed.add(below)
            primitives.append(
                Primitive(below, "wall", x0, y0, to_ticks_z(0.0), x1, y1, sill,
                          StationInterval(0, x1 - x0))
            )
        else:
            head = to_ticks_z(ASSUMED_DOOR_HEAD_INCHES)

        if head < ceiling_z:
            above = f"lintel.{index:03d}"
            assumed.add(above)
            primitives.append(
                Primitive(
                    above, "wall", x0, y0, head, x1, y1, ceiling_z, StationInterval(0, x1 - x0)
                )
            )

    return A1Massing(
        ceiling=ceiling,
        primitives=tuple(primitives),
        openings=classified,
        assumed_primitive_ids=frozenset(assumed),
        approximated_wall_ids=frozenset(approximated),
    )
