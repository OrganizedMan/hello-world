"""Canonical entity schema (plan §5.2). These dataclasses ARE the schema —
the single source of truth referenced elsewhere in the plan as
`core-schema`. JSON (de)serialization on each entity is what a generated
JSON Schema / TypeScript type would otherwise provide; that generation
step can be added later without changing these shapes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .provenance import Provenance
from .unknown import UNKNOWN, IntOrUnknown
from .wall_topology import OpeningInterval, TopologyError, validate_wall_openings


class Discipline(str, Enum):
    PLAN = "plan"
    SECTION = "section"
    ELEVATION = "elevation"
    AXONOMETRIC = "axonometric"
    DETAIL = "detail"


class Variant(str, Enum):
    EXISTING = "existing"
    PROPOSED = "proposed"
    DEMOLITION = "demolition"
    # "option:<name>" variants are represented as plain strings, not this enum,
    # since the option name is open-ended (e.g. "option:OP#B").


class WallConstruction(str, Enum):
    EXISTING = "existing"
    NEW_2X_16OC_GWB_BOTH = "new_2x_16oc_gwb_both"
    CMU = "cmu"
    DEMOLISHED = "demolished"


class OpeningKind(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    UNFRAMED = "unframed"
    CASED = "cased"
    PASS_THROUGH = "pass_through"
    NICHE = "niche"


@dataclass(frozen=True, slots=True)
class Point2:
    x_nm: int
    y_nm: int


@dataclass(frozen=True, slots=True)
class Calibration:
    in_per_pt: float
    rotation_mdeg: int
    residual_pct: float
    method: str  # "regression" | "note" | "user" | "scalebar"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    id: str
    filename: str
    sha256: str
    page_count: int
    is_vector: bool


@dataclass(frozen=True, slots=True)
class TitleBlock:
    sheet_no: str = ""
    scale_note: str = ""
    date: str = ""
    revision: str = ""


@dataclass(frozen=True, slots=True)
class Sheet:
    doc_id: str
    page_index: int
    size_pt: tuple[float, float]
    title_block: TitleBlock


@dataclass(frozen=True, slots=True)
class DrawingRegion:
    id: str
    sheet_doc_id: str
    sheet_page_index: int
    bbox_sheet: tuple[float, float, float, float]
    title: str
    scale_note: str
    discipline: Discipline
    level_id: str | None
    variant: str  # "existing" | "proposed" | "demolition" | "option:<name>"
    calibration: Calibration | None
    prov: Provenance


@dataclass(frozen=True, slots=True)
class Level:
    id: str
    name: str
    elevation_nm: IntOrUnknown
    floor_assembly_nm: IntOrUnknown
    default_ceiling_nm: IntOrUnknown
    prov: Provenance
    parent_level_id: str | None = None


@dataclass(frozen=True, slots=True)
class Opening:
    id: str
    kind: OpeningKind
    t_start_nm: int
    t_end_nm: int
    prov: Provenance
    sill_nm: IntOrUnknown = UNKNOWN
    head_nm: IntOrUnknown = UNKNOWN
    connects: tuple[str, str] | None = None  # (room_id, room_id|"EXTERIOR")
    annotation: str | None = None

    def __post_init__(self) -> None:
        if not (self.t_start_nm < self.t_end_nm):
            raise TopologyError(
                f"opening {self.id!r}: t_start_nm ({self.t_start_nm}) must be < "
                f"t_end_nm ({self.t_end_nm})"
            )


@dataclass(frozen=True, slots=True)
class WallSegment:
    """A wall with its openings as ordered parametric intervals (plan §5.3).

    This ordering is validated on construction: it is impossible to build a
    WallSegment whose openings overlap or fall outside the wall, and the
    tuple of openings is always stored sorted by t_start. This is the
    concrete fix for the reported failure — an annotation like "60\" TV"
    can only ever attach to a solid interval on a *specific* wall, and that
    wall's opening order cannot silently change.
    """

    id: str
    level_id: str
    variant: str
    baseline: tuple[Point2, Point2]
    thickness_nm: int
    construction: WallConstruction
    prov: Provenance
    offset_nm: int = 0
    base_z_nm: IntOrUnknown = UNKNOWN
    top_z_nm: IntOrUnknown = UNKNOWN
    openings: tuple[Opening, ...] = ()

    def __post_init__(self) -> None:
        if self.thickness_nm <= 0:
            raise ValueError(f"wall {self.id!r}: thickness_nm must be positive")
        length_nm = self.length_nm
        intervals = tuple(
            OpeningInterval(o.id, o.t_start_nm, o.t_end_nm) for o in self.openings
        )
        ordered = validate_wall_openings(self.id, length_nm, intervals)
        # Re-order the actual Opening objects to match, and freeze that order.
        by_id = {o.id: o for o in self.openings}
        object.__setattr__(self, "openings", tuple(by_id[iv.opening_id] for iv in ordered))

    @property
    def length_nm(self) -> int:
        p0, p1 = self.baseline
        dx = p1.x_nm - p0.x_nm
        dy = p1.y_nm - p0.y_nm
        return round((dx * dx + dy * dy) ** 0.5)

    def solid_intervals(self) -> tuple[tuple[int, int], ...]:
        """The complement of the openings: the wall intervals that are solid
        wall, i.e. the only intervals a fixed-furniture annotation (a "60\"
        TV") may ever attach to."""
        length = self.length_nm
        cuts = [0]
        for o in self.openings:
            cuts.append(o.t_start_nm)
            cuts.append(o.t_end_nm)
        cuts.append(length)
        solids = []
        for i in range(0, len(cuts), 2):
            a, b = cuts[i], cuts[i + 1]
            if b > a:
                solids.append((a, b))
        return tuple(solids)


@dataclass(frozen=True, slots=True)
class Room:
    id: str
    level_id: str
    name: str
    boundary_wall_ids: tuple[str, ...]
    prov: Provenance
    ceiling_id: str | None = None
    floor_id: str | None = None
    area_nm2: int | None = None


@dataclass(frozen=True, slots=True)
class Landing:
    polygon: tuple[Point2, ...]
    z_nm: int


@dataclass(frozen=True, slots=True)
class Stair:
    id: str
    from_level_id: str
    to_level_id: str
    riser_count: int
    riser_nm: int
    tread_nm: int
    run_path: tuple[Point2, ...]
    width_nm: int
    prov: Provenance
    landings: tuple[Landing, ...] = ()

    def __post_init__(self) -> None:
        if self.riser_count <= 0:
            raise ValueError(f"stair {self.id!r}: riser_count must be positive")
        if self.riser_nm <= 0 or self.tread_nm <= 0:
            raise ValueError(f"stair {self.id!r}: riser_nm and tread_nm must be positive")

    @property
    def total_rise_nm(self) -> int:
        return self.riser_count * self.riser_nm


@dataclass(frozen=True, slots=True)
class FloorSlab:
    id: str
    level_id: str
    boundary: tuple[Point2, ...]
    thickness_nm: int
    prov: Provenance


@dataclass(frozen=True, slots=True)
class CeilingPlane:
    id: str
    level_id: str
    boundary: tuple[Point2, ...]
    z_nm: IntOrUnknown
    prov: Provenance
    slope_mdeg: int = 0


@dataclass(frozen=True, slots=True)
class RoofPlane:
    id: str
    boundary_3d: tuple[tuple[int, int, int], ...]
    pitch_rise_per_12_nm: int
    eave_z_nm: int
    ridge_z_nm: int
    thickness_nm: int
    prov: Provenance


@dataclass(frozen=True, slots=True)
class Dormer:
    id: str
    roof_plane_id: str
    kind: str  # "shed" | "gable"
    footprint: tuple[Point2, ...]
    head_z_nm: int
    prov: Provenance


@dataclass(frozen=True, slots=True)
class FixedCabinetry:
    id: str
    level_id: str
    footprint: tuple[Point2, ...]
    height_nm: int
    kind: str  # "base" | "upper" | "tall" | "island"
    label: str
    prov: Provenance


@dataclass(frozen=True, slots=True)
class PlumbingFixture:
    id: str
    level_id: str
    kind: str
    footprint: tuple[Point2, ...]
    prov: Provenance


@dataclass(frozen=True, slots=True)
class Furniture:
    id: str
    level_id: str
    kind: str
    footprint: tuple[Point2, ...]
    prov: Provenance
    is_advisory: bool = True


@dataclass(frozen=True, slots=True)
class FeatureRef:
    """Points at a specific geometric feature a dimension or alignment controls
    (a wall face, an opening jamb, a grid line, a region datum)."""

    entity_id: str
    feature: str  # e.g. "face:start", "face:end", "jamb:a", "jamb:b", "datum"


@dataclass(frozen=True, slots=True)
class DimensionConstraint:
    id: str
    region_id: str
    text: str
    value_nm: int
    axis: str  # "x" | "y" | "along:<wall_id>" | "z"
    feature_a: FeatureRef
    feature_b: FeatureRef
    prov: Provenance
    chain_id: str | None = None
    is_overall: bool = False
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class AlignmentConstraint:
    id: str
    kind: str  # "collinear" | "equal" | "perpendicular" | "vertical_align"
    members: tuple[FeatureRef, ...]
    prov: Provenance


@dataclass(frozen=True, slots=True)
class PbrMaterial:
    base_color: tuple[float, float, float]
    roughness: float
    metallic: float
    normal_tex: str | None = None
    scale_nm: int = 0


@dataclass(frozen=True, slots=True)
class Material:
    id: str
    name: str
    pbr: PbrMaterial
    assigned_to: tuple[str, ...] = ()
    is_advisory: bool = True


@dataclass(frozen=True, slots=True)
class Camera:
    id: str
    name: str
    position: tuple[int, int, int]
    target: tuple[int, int, int]
    fov_deg: float
    clip: tuple[float, float]
    geometry_hash_at_creation: str
    level_hint: str | None = None


@dataclass(frozen=True, slots=True)
class SceneLock:
    geometry_hash: str
    built_at: str
    builder_version: str
    entity_count: int
    validation_report_id: str


@dataclass(frozen=True, slots=True)
class Project:
    id: str
    name: str
    address: str
    variant_active: str
    levels: tuple[Level, ...] = ()
    docs: tuple[SourceDocument, ...] = ()
