"""The Garrigan family room, built from real Stage 1 extraction instead of
hand-typed values (plan §14 Stage 1 gate: "extracted first floor matches
the Stage-0 hand-traced model within 1 in").

Structurally this mirrors `family_room.build_family_room()` exactly — same
wall ids, same `FeatureRef` names, same axis assembly, same solver and
geometry construction — so the two are a direct, apples-to-apples
comparison. The only thing that differs is where each `DimensionConstraint`
value comes from: here it's `extract.dimensions.match_dimension_text()`
run against the real, pinned `garrigan-main-set.pdf`, not a typed-in
constant.

Provenance is `PROPOSED`, not `USER_CONFIRMED`: nobody has reviewed these
matches (plan §5.2's one-way valve — only `USER_CONFIRMED`/`USER_AUTHORED`
entities are supposed to reach the constraint program in the reviewed
product). Building solved geometry straight from `PROPOSED` constraints,
as this module does, is an explicitly-labelled preview/comparison path —
see `server.app`'s `source=extracted` query param and the UI's "unreviewed
proposal" badge — not a claim that this output is approved.

Two of the east wall's four chain links (the mudroom opening's own width,
and the short run from the opening to the wall's far end) are not
independently dimensioned anywhere on sheet A-1 — only the window offset
and the mudroom-opening offset are. Those two links are carried over from
the hand-traced fixture's values, explicitly marked `ASSUMED_DEFAULT`
rather than `EXPLICIT_DIMENSION`, exactly reflecting that gap rather than
hiding it.
"""
from __future__ import annotations

from dataclasses import dataclass

from pdf3d_constraints import anchor_region_datums, build_systems, diagnose
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
    proposed,
)
from extract import (
    TextClass,
    classify_text_line,
    harvest_paths,
    harvest_text_lines,
    reassemble_lines,
)
from extract.dimensions import DimensionMatch, match_dimensions_on_page
from ingest import PyMuPdfBackend
from units import NM_PER_FOOT, NM_PER_INCH, ParseError, parse_feet_inches

from ._repo_paths import MAIN_SET_PDF
from .family_room import (
    CEILING_HEIGHT_NM,
    EAST_WALL_ID,
    REGION_DATUM,
    SOUTH_WALL_ID,
    SOURCE_DOC_ID,
    SOURCE_PAGE,
    WALL_THICKNESS_NM,
)

FT = NM_PER_FOOT
IN = NM_PER_INCH
NOMINAL_IN_PER_PT = 12 / 18  # "1/4" = 1'-0"" per the title block (plan Appendix A)
# The 0-indexed PyMuPDF page for sheet A-1 — distinct from `family_room.SOURCE_PAGE`
# (2), which the hand-traced fixture uses only as a human-facing label on
# `SourceRef.page` and never to actually open the PDF (it never reads the
# PDF at all). This module does read the PDF, so it needs the real index.
HARVEST_PAGE_INDEX = 1

_WINDOW_OFFSET_ROW_PT = 2007.2   # LIVING_ROOM.EAST: wall start -> window jamb-b
_MUDROOM_OFFSET_ROW_PT = 2022.07  # LIVING_ROOM.EAST: wall start -> mudroom jamb-a
_SOUTH_ROW_LO_PT, _SOUTH_ROW_HI_PT = 880.0, 915.0  # LIVING_ROOM.SOUTH's chain row(s)

# Not independently dimensioned on A-1 (see module docstring).
_MUDROOM_WIDTH_NM = 3 * FT
_EAST_WALL_TRAILING_NM = 4 * IN


@dataclass(frozen=True, slots=True)
class ExtractedFamilyRoom:
    walls: tuple[WallSegment, WallSegment]  # (east, south)
    dimension_constraints: tuple[DimensionConstraint, ...]
    matches: tuple[DimensionMatch, ...]  # the underlying matcher output, for diagnostics/UI


def _harvest_dimension_matches() -> list[DimensionMatch]:
    with PyMuPdfBackend().open(str(MAIN_SET_PDF)) as h:
        paths = harvest_paths(h, HARVEST_PAGE_INDEX, suppress_text_masks=False)
        text_lines = reassemble_lines(harvest_text_lines(h, HARVEST_PAGE_INDEX))

    dim_lines = [l for l in text_lines if classify_text_line(l) == TextClass.DIMENSION_STRING]
    lines_and_values = []
    for line in dim_lines:
        try:
            lines_and_values.append((line, parse_feet_inches(line.text.strip())))
        except ParseError:
            continue
    return match_dimensions_on_page(lines_and_values, paths, NOMINAL_IN_PER_PT)


def _require_one(matches: list[DimensionMatch], text: str, perp_lo: float, perp_hi: float) -> DimensionMatch:
    candidates = [m for m in matches if m.text.strip() == text and perp_lo <= m.perp_pt <= perp_hi]
    if not candidates:
        raise AssertionError(
            f"extraction did not find a {text!r} dimension match with perp in "
            f"[{perp_lo}, {perp_hi}] on page {SOURCE_PAGE} — the extracted family "
            "room cannot be built without it"
        )
    return min(candidates, key=lambda m: m.error_in)


def _confidence(error_in: float) -> float:
    return round(max(0.1, min(0.99, 1.0 - error_in / 2.0)), 2)


def _match_source_ref(m: DimensionMatch) -> SourceRef:
    return SourceRef(doc_id=SOURCE_DOC_ID, page=m.page_index, kind=SourceKind.SPAN, path_uids=())


def _extracted_prov(m: DimensionMatch) -> Provenance:
    return proposed(
        basis=ProvenanceBasis.EXPLICIT_DIMENSION,
        tolerance_nm=NM_PER_INCH,
        created_by="extract@0.1.0",
        confidence=_confidence(m.error_in),
        source_refs=(_match_source_ref(m),),
    )


def _assumed_prov() -> Provenance:
    # No witnessed dimension string exists for this link (module
    # docstring) — carried over from the hand-traced fixture, not invented
    # by the matcher, and marked accordingly rather than claimed as found.
    return proposed(
        basis=ProvenanceBasis.ASSUMED_DEFAULT,
        tolerance_nm=NM_PER_INCH,
        created_by="fixtures_garrigan@0.1.0",
        confidence=0.3,
        source_refs=(SourceRef(doc_id=SOURCE_DOC_ID, page=SOURCE_PAGE, kind=SourceKind.SPAN, path_uids=()),),
    )


def _dim(id_: str, text: str, value_nm: int, axis: str, a: FeatureRef, b: FeatureRef, prov: Provenance) -> DimensionConstraint:
    return DimensionConstraint(
        id=id_, region_id="A-1", text=text, value_nm=value_nm, axis=axis,
        feature_a=a, feature_b=b, prov=prov,
    )


def build_family_room_from_extraction() -> ExtractedFamilyRoom:
    matches = _harvest_dimension_matches()

    window_m = _require_one(matches, "3' - 8\"", _WINDOW_OFFSET_ROW_PT - 1, _WINDOW_OFFSET_ROW_PT + 1)
    mudroom_m = _require_one(matches, "7' - 4\"", _MUDROOM_OFFSET_ROW_PT - 1, _MUDROOM_OFFSET_ROW_PT + 1)
    south_matches = [
        m for m in matches
        if _SOUTH_ROW_LO_PT <= m.perp_pt <= _SOUTH_ROW_HI_PT and m.text.strip() in ("3' - 1\"", "5' - 0\"")
    ]
    south_31 = sorted((m for m in south_matches if m.text.strip() == "3' - 1\""), key=lambda m: m.a_pt)
    south_50 = [m for m in south_matches if m.text.strip() == "5' - 0\""]
    if len(south_31) != 2 or len(south_50) != 1:
        raise AssertionError(
            f"expected exactly two 3'-1\" and one 5'-0\" match on the south wall's "
            f"chain row, found {len(south_31)} and {len(south_50)}"
        )
    south_west, south_east = south_31
    south_mid = south_50[0]

    # --- Y-axis: LIVING_ROOM.EAST, wall start -> window -> TV interval -> mudroom opening -> wall end.
    east_start = FeatureRef(EAST_WALL_ID, "face:start")
    east_end = FeatureRef(EAST_WALL_ID, "face:end")
    window_b = FeatureRef("window", "jamb:b")
    mudroom_a = FeatureRef("to_mudroom", "jamb:a")
    mudroom_b = FeatureRef("to_mudroom", "jamb:b")

    y_dims = [
        _dim("east-datum", "calibration datum", 0, "y", REGION_DATUM, east_start,
             proposed(ProvenanceBasis.EXPLICIT_DIMENSION, NM_PER_INCH, "fixtures_garrigan@0.1.0",
                       0.99, (SourceRef(SOURCE_DOC_ID, SOURCE_PAGE, SourceKind.SPAN, ()),))),
        _dim("east-d1", window_m.text, window_m.value_nm, "y", east_start, window_b, _extracted_prov(window_m)),
        _dim("east-d2", mudroom_m.text, mudroom_m.value_nm, "y", window_b, mudroom_a, _extracted_prov(mudroom_m)),
        _dim("east-d3", "3'-0\" (assumed)", _MUDROOM_WIDTH_NM, "y", mudroom_a, mudroom_b, _assumed_prov()),
        _dim("east-d4", "0'-4\" (assumed)", _EAST_WALL_TRAILING_NM, "y", mudroom_b, east_end, _assumed_prov()),
    ]
    y_systems = build_systems(y_dims, [])
    anchor_region_datums(y_systems["y"])
    y_diag = diagnose(y_systems["y"])
    if y_diag.is_blocking:
        raise AssertionError(f"extracted east wall (y-axis) chain failed to solve: {y_diag.status}")

    def y(feature: FeatureRef) -> int:
        return y_diag.solution_nm[(feature.entity_id, feature.feature)]

    # --- X-axis: LIVING_ROOM.SOUTH, exact 3'-1" | 5'-0" | 3'-1" chain, extracted.
    south_start = FeatureRef(SOUTH_WALL_ID, "face:start")
    south_end = FeatureRef(SOUTH_WALL_ID, "face:end")
    living_room_a = FeatureRef("to_living_room", "jamb:a")
    living_room_b = FeatureRef("to_living_room", "jamb:b")

    x_dims = [
        _dim("south-datum", "calibration datum", 0, "x", REGION_DATUM, south_start,
             proposed(ProvenanceBasis.EXPLICIT_DIMENSION, NM_PER_INCH, "fixtures_garrigan@0.1.0",
                       0.99, (SourceRef(SOURCE_DOC_ID, SOURCE_PAGE, SourceKind.SPAN, ()),))),
        _dim("south-d1", south_west.text, south_west.value_nm, "x", south_start, living_room_a, _extracted_prov(south_west)),
        _dim("south-d2", south_mid.text, south_mid.value_nm, "x", living_room_a, living_room_b, _extracted_prov(south_mid)),
        _dim("south-d3", south_east.text, south_east.value_nm, "x", living_room_b, south_end, _extracted_prov(south_east)),
    ]
    x_systems = build_systems(x_dims, [])
    anchor_region_datums(x_systems["x"])
    x_diag = diagnose(x_systems["x"])
    if x_diag.is_blocking:
        raise AssertionError(f"extracted south wall (x-axis) chain failed to solve: {x_diag.status}")

    def x(feature: FeatureRef) -> int:
        return x_diag.solution_nm[(feature.entity_id, feature.feature)]

    corner_y = y(east_end)

    window = Opening(
        id="window", kind=OpeningKind.WINDOW,
        t_start_nm=y(east_start), t_end_nm=y(window_b),
        sill_nm=2 * FT, head_nm=6 * FT + 9 * IN,
        prov=_extracted_prov(window_m),
    )
    to_mudroom = Opening(
        id="to_mudroom", kind=OpeningKind.UNFRAMED,
        t_start_nm=y(mudroom_a), t_end_nm=y(mudroom_b),
        sill_nm=0, head_nm=6 * FT + 8 * IN,
        prov=_extracted_prov(mudroom_m),
        connects=("LIVING_ROOM", "MUDROOM"),
    )
    east = WallSegment(
        id=EAST_WALL_ID, level_id="first", variant="proposed",
        baseline=(Point2(0, y(east_start)), Point2(0, y(east_end))),
        thickness_nm=WALL_THICKNESS_NM,
        construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=_extracted_prov(window_m), base_z_nm=0, top_z_nm=CEILING_HEIGHT_NM,
        openings=(window, to_mudroom),
    )

    to_living_room = Opening(
        id="to_living_room", kind=OpeningKind.CASED,
        t_start_nm=x(living_room_a), t_end_nm=x(living_room_b),
        sill_nm=0, head_nm=6 * FT + 8 * IN,
        prov=_extracted_prov(south_mid),
        connects=("FAMILY_ROOM", "(E) LIVING ROOM"),
    )
    south = WallSegment(
        id=SOUTH_WALL_ID, level_id="first", variant="proposed",
        baseline=(Point2(x(south_start), corner_y), Point2(x(south_end), corner_y)),
        thickness_nm=WALL_THICKNESS_NM,
        construction=WallConstruction.EXISTING,
        prov=_extracted_prov(south_mid), base_z_nm=0, top_z_nm=CEILING_HEIGHT_NM,
        openings=(to_living_room,),
    )

    return ExtractedFamilyRoom(
        walls=(east, south),
        dimension_constraints=tuple(y_dims + x_dims),
        # Only the matches actually used to build this room — not every
        # match found on the page. Filtering by text alone would also
        # catch same-text dimension strings elsewhere on the sheet that
        # have nothing to do with the family room (e.g. another "3'-1\""
        # callout on a different wall).
        matches=(window_m, mudroom_m, south_west, south_mid, south_east),
    )


def diagnose_extracted_family_room(room: ExtractedFamilyRoom) -> list:
    """See `family_room.diagnose_family_room` — same correct pattern,
    duplicated deliberately rather than shared across a `HandTracedFamilyRoom`/
    `ExtractedFamilyRoom` type boundary that isn't worth introducing for
    two call sites."""
    systems = build_systems(room.dimension_constraints, [])
    results = []
    for system in systems.values():
        if not system.rows:
            continue
        anchor_region_datums(system)
        results.append(diagnose(system))
    return results
