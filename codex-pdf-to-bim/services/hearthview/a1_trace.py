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


_PROPOSED_CROP = PdfRect(1460.0, 300.0, 2220.0, 1630.0)


def build_a1_trace() -> A1Trace:
    """Return the initial source-bound contract before full topology is traced."""
    trace = A1Trace(
        page_number=2,
        page_width_points=2592.0,
        page_height_points=1728.24,
        proposed_crop=_PROPOSED_CROP,
        records=(
            TraceRecord(
                id="boundary.proposed_crop",
                kind="room",
                room="proposed_first_floor",
                provenance="linework_traced",
                geometry=TraceGeometry(
                    points=((1461.0, 301.0), (2219.0, 301.0), (2219.0, 1629.0), (1461.0, 1629.0)),
                ),
                source_page=2,
            ),
        ),
    )
    trace.validate()
    return trace
