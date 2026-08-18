"""The Garrigan family room, hand-traced (plan Stage 0 / §22 proof-of-concept).

Represents what a human produces with the calibrate-and-trace UI while
looking at sheet A-1: `DimensionConstraint`s for each witnessed dimension
string, solved by the real constraint solver, with `WallSegment`/`Opening`
geometry then *built from the solved coordinates* — not independently
hard-coded and merely cross-checked — so this is a genuine proof that
"solved constraints become deterministic geometry" (plan §5.2), not two
parallel computations that happen to agree.

LIVING_ROOM.SOUTH's chain (3'-1" | 5'-0" | 3'-1") is the exact text from
the source PDF (Appendix A). LIVING_ROOM.EAST's window/mudroom-opening
positions are representative placeholder values consistent with the
drawing's layout: Sprint 1/2 do not extract or verify them against the
PDF's actual tick-mark positions yet (dimension association is a Stage 1
concern). What this module proves is that the *pipeline* — constraints,
validation, geometry, hashing — carries this specific topology correctly
end to end: window, then solid wall (where "60\" TV" is annotated), then
the mudroom opening, on one wall; a single 5'-0" opening on a different
wall. That ordering is exactly the failure this project exists to
prevent, and it is now proven at every layer, not just at the schema.
"""
from __future__ import annotations

from dataclasses import dataclass

from constraints import ConstraintStatus, anchor_region_datums, build_systems, diagnose
from core_schema import (
    DimensionConstraint,
    FeatureRef,
    Opening,
    OpeningKind,
    Point2,
    Provenance,
    ProvenanceBasis,
    SourceKind,
    SourceRef,
    WallConstruction,
    WallSegment,
    user_confirmed,
)
from units import NM_PER_FOOT, NM_PER_INCH

FT = NM_PER_FOOT
IN = NM_PER_INCH

CEILING_HEIGHT_NM = 8 * FT + 5 * IN  # LIVING ROOM CLG HT - 8' 5" (Appendix A)
WALL_THICKNESS_NM = 6 * IN
SOURCE_DOC_ID = "garrigan-main-set"
SOURCE_PAGE = 2  # sheet A-1 (0-indexed page 1)

EAST_WALL_ID = "LIVING_ROOM.EAST"
SOUTH_WALL_ID = "LIVING_ROOM.SOUTH"

# The region's calibrated datum (plan §5.2 FeatureRef examples list
# "datum" alongside wall faces and jambs). Anchoring a wall face to it is
# a real, citable dimension constraint in its own right — grounded in the
# calibration transform, not a throwaway internal solver detail — so it
# must be a genuine DimensionConstraint returned to the caller, not a Row
# appended only inside this module's own solve. Otherwise anyone
# re-diagnosing the same constraints independently (validation, tests,
# the review UI) would see a system that looks under-constrained even
# though it was actually fully pinned when this module built it.
REGION_DATUM = FeatureRef("A-1", "datum")


def _src() -> SourceRef:
    return SourceRef(doc_id=SOURCE_DOC_ID, page=SOURCE_PAGE, kind=SourceKind.SPAN, path_uids=())


def _confirmed() -> Provenance:
    return user_confirmed(
        basis=ProvenanceBasis.EXPLICIT_DIMENSION,
        tolerance_nm=NM_PER_INCH,
        created_by="user:jhmgarrigan",
        source_refs=(_src(),),
    )


def _dim(id_: str, text: str, value_nm: int, axis: str, a: FeatureRef, b: FeatureRef) -> DimensionConstraint:
    return DimensionConstraint(
        id=id_, region_id="A-1", text=text, value_nm=value_nm, axis=axis,
        feature_a=a, feature_b=b, prov=_confirmed(),
    )


@dataclass(frozen=True, slots=True)
class HandTracedFamilyRoom:
    walls: tuple[WallSegment, WallSegment]  # (east, south)
    dimension_constraints: tuple[DimensionConstraint, ...]


def build_family_room() -> HandTracedFamilyRoom:
    # --- Y-axis system: LIVING_ROOM.EAST runs vertically at x=0. ---
    # Sequential chain, north to south: wall start -> window end -> TV
    # solid interval -> mudroom opening -> wall end. Sums to 14'-4".
    east_start = FeatureRef(EAST_WALL_ID, "face:start")
    east_end = FeatureRef(EAST_WALL_ID, "face:end")
    window_b = FeatureRef("window", "jamb:b")
    mudroom_a = FeatureRef("to_mudroom", "jamb:a")
    mudroom_b = FeatureRef("to_mudroom", "jamb:b")

    y_dims = [
        _dim("east-datum", "calibration datum", 0, "y", REGION_DATUM, east_start),
        _dim("east-d1", "3'-8\"", 3 * FT + 8 * IN, "y", east_start, window_b),
        _dim("east-d2", "7'-4\"", 7 * FT + 4 * IN, "y", window_b, mudroom_a),
        _dim("east-d3", "3'-0\"", 3 * FT, "y", mudroom_a, mudroom_b),
        _dim("east-d4", "0'-4\"", 4 * IN, "y", mudroom_b, east_end),
    ]
    y_systems = build_systems(y_dims, [])
    anchor_region_datums(y_systems["y"])
    y_diag = diagnose(y_systems["y"])
    if y_diag.is_blocking:
        raise AssertionError(f"east wall (y-axis) chain failed to solve: {y_diag.status}")

    def y(feature: FeatureRef) -> int:
        return y_diag.solution_nm[(feature.entity_id, feature.feature)]

    # --- X-axis system: LIVING_ROOM.SOUTH runs horizontally, starting at
    # the corner shared with LIVING_ROOM.EAST's south end (x=0, matching
    # EAST's constant x=0). Exact 3'-1" | 5'-0" | 3'-1" chain (Appendix A).
    south_start = FeatureRef(SOUTH_WALL_ID, "face:start")
    south_end = FeatureRef(SOUTH_WALL_ID, "face:end")
    living_room_a = FeatureRef("to_living_room", "jamb:a")
    living_room_b = FeatureRef("to_living_room", "jamb:b")

    x_dims = [
        _dim("south-datum", "calibration datum", 0, "x", REGION_DATUM, south_start),
        _dim("south-d1", "3'-1\"", 3 * FT + 1 * IN, "x", south_start, living_room_a),
        _dim("south-d2", "5'-0\"", 5 * FT, "x", living_room_a, living_room_b),
        _dim("south-d3", "3'-1\"", 3 * FT + 1 * IN, "x", living_room_b, south_end),
    ]
    x_systems = build_systems(x_dims, [])
    anchor_region_datums(x_systems["x"])
    x_diag = diagnose(x_systems["x"])
    if x_diag.is_blocking:
        raise AssertionError(f"south wall (x-axis) chain failed to solve: {x_diag.status}")

    def x(feature: FeatureRef) -> int:
        return x_diag.solution_nm[(feature.entity_id, feature.feature)]

    # --- Geometry built FROM the solved coordinates. ---
    corner_y = y(east_end)  # the L-corner: EAST's south end meets SOUTH's start, both at x=0

    window = Opening(
        id="window", kind=OpeningKind.WINDOW,
        t_start_nm=y(east_start), t_end_nm=y(window_b),
        sill_nm=2 * FT, head_nm=6 * FT + 9 * IN,
        prov=_confirmed(),
    )
    to_mudroom = Opening(
        id="to_mudroom", kind=OpeningKind.UNFRAMED,
        t_start_nm=y(mudroom_a), t_end_nm=y(mudroom_b),
        sill_nm=0, head_nm=6 * FT + 8 * IN,
        prov=_confirmed(),
        connects=("LIVING_ROOM", "MUDROOM"),
        # No `annotation` here. The "60\" TV" note belongs on the SOLID
        # interval between `window` and this opening — see
        # TV_WALL_INTERVAL below and WallSegment.solid_intervals(). Putting
        # it on an Opening would be exactly the bug this project exists to
        # prevent: it very nearly ended up here during this fixture's own
        # first draft, which is as good a demonstration as any of why the
        # schema enforces this structurally rather than by convention.
    )
    east = WallSegment(
        id=EAST_WALL_ID, level_id="first", variant="proposed",
        baseline=(Point2(0, y(east_start)), Point2(0, y(east_end))),
        thickness_nm=WALL_THICKNESS_NM,
        construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=_confirmed(), base_z_nm=0, top_z_nm=CEILING_HEIGHT_NM,
        openings=(window, to_mudroom),
    )

    to_living_room = Opening(
        id="to_living_room", kind=OpeningKind.CASED,
        t_start_nm=x(living_room_a), t_end_nm=x(living_room_b),
        sill_nm=0, head_nm=6 * FT + 8 * IN,
        prov=_confirmed(),
        connects=("FAMILY_ROOM", "(E) LIVING ROOM"),
    )
    south = WallSegment(
        id=SOUTH_WALL_ID, level_id="first", variant="proposed",
        baseline=(Point2(x(south_start), corner_y), Point2(x(south_end), corner_y)),
        thickness_nm=WALL_THICKNESS_NM,
        construction=WallConstruction.EXISTING,
        prov=_confirmed(), base_z_nm=0, top_z_nm=CEILING_HEIGHT_NM,
        openings=(to_living_room,),
    )

    return HandTracedFamilyRoom(walls=(east, south), dimension_constraints=tuple(y_dims + x_dims))


def tv_wall_interval(east_wall: WallSegment) -> tuple[int, int]:
    """The solid wall interval the "60\" TV" annotation belongs to: the
    gap between `window` and `to_mudroom` on LIVING_ROOM.EAST. Asserts it
    really is one of the wall's solid intervals (never inside an opening)
    rather than just computing it, so a future edit to this fixture that
    breaks the property fails loudly here instead of only downstream."""
    window = next(o for o in east_wall.openings if o.id == "window")
    mudroom = next(o for o in east_wall.openings if o.id == "to_mudroom")
    interval = (window.t_end_nm, mudroom.t_start_nm)
    if interval not in east_wall.solid_intervals():
        raise AssertionError(f"expected TV interval {interval} is not solid on {east_wall.id!r}")
    return interval
