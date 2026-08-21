"""Trace contract for A-1's proposed first-floor view.

Coordinates are PDF points on page 2. They are deliberately independent of
browser preview pixels so a review overlay can retain source alignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TraceKind = Literal["wall", "opening", "room", "stair", "fixed", "dimension"]
TraceProvenance = Literal[
    "dimension_verified",
    "linework_traced",
    "ambiguous",
]


@dataclass(frozen=True)
class PdfRect:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError("PDF rectangles must have positive area.")

    def contains(self, other: "PdfRect") -> bool:
        return (
            self.x0 <= other.x0
            and self.y0 <= other.y0
            and self.x1 >= other.x1
            and self.y1 >= other.y1
        )


@dataclass(frozen=True)
class TraceGeometry:
    points: tuple[tuple[float, float], ...]
    closed: bool = True

    def __post_init__(self) -> None:
        if len(self.points) < (3 if self.closed else 2):
            raise ValueError("Trace geometry has too few points.")

    @property
    def bounds(self) -> PdfRect:
        xs, ys = zip(*self.points, strict=True)
        return PdfRect(min(xs), min(ys), max(xs), max(ys))

    def intersects(self, other: "TraceGeometry", *, tolerance: float = 4.0) -> bool:
        left = self.bounds
        right = other.bounds
        return not (
            left.x1 + tolerance < right.x0
            or right.x1 + tolerance < left.x0
            or left.y1 + tolerance < right.y0
            or right.y1 + tolerance < left.y0
        )


@dataclass(frozen=True)
class TraceRecord:
    id: str
    kind: TraceKind
    room: str
    provenance: TraceProvenance
    geometry: TraceGeometry
    source_page: int
    dimension_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.provenance == "dimension_verified" and not self.dimension_labels:
            raise ValueError("Dimension-verified records must cite A-1 labels.")


@dataclass(frozen=True)
class A1Trace:
    page_number: int
    page_width_points: float
    page_height_points: float
    proposed_crop: PdfRect
    records: tuple[TraceRecord, ...]

    def validate(self) -> None:
        ids = [record.id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("Trace record IDs must be unique.")
        for record in self.records:
            if record.source_page != self.page_number:
                raise ValueError("Trace record page must match the A-1 page.")
            if not self.proposed_crop.contains(record.geometry.bounds):
                raise ValueError(f"Trace record {record.id} falls outside the proposed crop.")

    @property
    def exterior_boundary(self) -> TraceGeometry:
        return next(record.geometry for record in self.records if record.id == "boundary.exterior")

    @property
    def openings(self) -> tuple[TraceRecord, ...]:
        return tuple(record for record in self.records if record.kind == "opening")

    @property
    def walls(self) -> tuple[TraceRecord, ...]:
        return tuple(record for record in self.records if record.kind == "wall")

    def attaches_to_wall(self, opening: TraceRecord) -> bool:
        return any(opening.geometry.intersects(wall.geometry) for wall in self.walls)


@dataclass(frozen=True)
class TraceSummary:
    verified: int
    traced: int
    ambiguous: int


_PROPOSED_CROP = PdfRect(1120.0, 300.0, 2220.0, 1630.0)


def _rect(x0: float, y0: float, x1: float, y1: float) -> TraceGeometry:
    return TraceGeometry(points=((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def _record(
    record_id: str,
    kind: TraceKind,
    room: str,
    rect: tuple[float, float, float, float],
    provenance: TraceProvenance = "linework_traced",
    *dimension_labels: str,
) -> TraceRecord:
    return TraceRecord(
        id=record_id,
        kind=kind,
        room=room,
        provenance=provenance,
        geometry=_rect(*rect),
        source_page=2,
        dimension_labels=dimension_labels,
    )


def trace_summary(trace: A1Trace) -> TraceSummary:
    return TraceSummary(
        verified=sum(record.provenance == "dimension_verified" for record in trace.records),
        traced=sum(record.provenance == "linework_traced" for record in trace.records),
        ambiguous=sum(record.provenance == "ambiguous" for record in trace.records),
    )


def build_a1_trace() -> A1Trace:
    """Return the whole proposed-first-floor trace in A-1 PDF coordinates.

    Unprinted locations remain linework-traced. The data is intentionally a
    review trace, not construction geometry or a 3D model input.
    """
    trace = A1Trace(
        page_number=2,
        page_width_points=2592.0,
        page_height_points=1728.24,
        proposed_crop=_PROPOSED_CROP,
        records=(
            TraceRecord(
                id="boundary.exterior",
                kind="wall",
                room="proposed_first_floor",
                provenance="linework_traced",
                geometry=TraceGeometry(
                    points=(
                        (1260.0, 570.0), (1715.0, 570.0), (1715.0, 455.0),
                        (1900.0, 455.0), (1900.0, 570.0), (2140.0, 570.0),
                        (2140.0, 1425.0), (2025.0, 1425.0), (2025.0, 1535.0),
                        (1745.0, 1535.0), (1745.0, 1480.0), (1640.0, 1480.0),
                        (1640.0, 1535.0), (1260.0, 1535.0),
                    ),
                ),
                source_page=2,
            ),
            _record("wall.north.kitchen", "wall", "kitchen", (1260.0, 570.0, 1720.0, 584.0)),
            _record("wall.east.living", "wall", "living_room", (1983.0, 585.0, 1997.0, 1010.0)),
            _record("wall.east.mudroom", "wall", "mudroom", (2130.0, 760.0, 2144.0, 1125.0)),
            _record("wall.south.living", "wall", "living_room", (1720.0, 1042.0, 1985.0, 1055.0)),
            _record("wall.pantry.stair", "wall", "walk_in_pantry", (1640.0, 1080.0, 1654.0, 1270.0)),
            _record("wall.study.existing_living", "wall", "study_room", (1983.0, 1120.0, 1997.0, 1410.0)),
            _record("opening.deck.north", "opening", "deck", (1720.0, 570.0, 1900.0, 586.0), "dimension_verified", "7'-8\" deck stair"),
            _record("opening.kitchen_window.north", "opening", "kitchen", (1600.0, 570.0, 1708.0, 586.0)),
            _record("opening.mudroom.living", "opening", "mudroom", (1982.0, 755.0, 1998.0, 815.0), "dimension_verified", "3'-9\" opening"),
            _record("opening.existing_living.south", "opening", "existing_living_room", (1740.0, 1041.0, 1865.0, 1056.0), "dimension_verified", "3'-1\" / 5'-0\" / 3'-1\""),
            _record("room.deck", "room", "deck", (1720.0, 470.0, 2130.0, 755.0), "dimension_verified", "23'-1\"", "14'-4\""),
            _record("room.kitchen", "room", "kitchen", (1265.0, 590.0, 1720.0, 1040.0), "dimension_verified", "15'-11\"", "12'-3\""),
            _record("room.living", "room", "living_room", (1722.0, 590.0, 1982.0, 1040.0), "dimension_verified", "14'-9\""),
            _record("room.mudroom", "room", "mudroom", (1998.0, 835.0, 2128.0, 1115.0), "dimension_verified", "7'-6\"", "10'-0\""),
            _record("room.study", "room", "study_room", (1998.0, 1125.0, 2128.0, 1405.0)),
            _record("room.existing_living", "room", "existing_living_room", (1745.0, 1120.0, 1980.0, 1405.0)),
            _record("room.staircase", "stair", "staircase", (1655.0, 1120.0, 1740.0, 1405.0)),
            _record("room.walk_in_pantry", "room", "walk_in_pantry", (1515.0, 1080.0, 1640.0, 1265.0)),
            _record("room.powder", "room", "powder_room", (1320.0, 1080.0, 1512.0, 1265.0)),
            _record("room.dining", "room", "dining_room", (1260.0, 1270.0, 1640.0, 1465.0)),
            _record("room.entry", "room", "entry", (1645.0, 1410.0, 1740.0, 1525.0)),
            _record("fixed.island", "fixed", "kitchen", (1450.0, 770.0, 1618.0, 870.0), "dimension_verified", "8'-7\"", "4'-3\""),
            _record("fixed.fireplace", "fixed", "existing_living_room", (1938.0, 1160.0, 1975.0, 1370.0)),
            _record("fixed.low_ceiling", "fixed", "staircase", (1600.0, 1057.0, 1738.0, 1115.0), "dimension_verified", "6'-3\"", "6'-5\""),
        ),
    )
    trace.validate()
    return trace
