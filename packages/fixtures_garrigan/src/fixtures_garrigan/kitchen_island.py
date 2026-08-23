"""The Garrigan kitchen island, extracted directly from its poché
footprint — a second, independent extraction technique from the family
room's dimension-line matching (`family_room_extracted.py`): here the
rectangle's own measured size is corroborated against nearby witness
text (`extract.casework.find_casework_footprints`), rather than a
dimension chain being walked tick to tick. Appendix A's original probe
found this island's poché (154.67 x 77.22 pt) measures within 0.1-0.9%
of its labelled 8'-7" x 4'-3" — this module is that finding, wired
through the real pipeline instead of measured by hand.

The island sits in its own local coordinate frame (its own bottom-left
corner as the origin) — it is not yet registered into the family room's
coordinate system, because that requires the region-to-project alignment
transform Sprint 1 does not build yet (plan §5.1's SheetCS -> RegionCS ->
ProjectCS chain). Rendering it unregistered, next to but not connected to
the family room walls, is an honest reflection of that gap rather than a
guessed-at position.
"""
from __future__ import annotations

from dataclasses import dataclass

from core_schema import (
    FixedCabinetry,
    Point2,
    ProvenanceBasis,
    SourceKind,
    SourceRef,
    proposed,
)
from extract import (
    TextClass,
    classify_text_line,
    harvest_paths,
    harvest_text_lines,
    reassemble_lines,
)
from extract.casework import CaseworkFootprint, find_casework_footprints
from ingest import PyMuPdfBackend
from units import NM_PER_INCH, ParseError, parse_feet_inches

from .family_room_extracted import HARVEST_PAGE_INDEX, NOMINAL_IN_PER_PT
from .family_room import SOURCE_DOC_ID, SOURCE_PAGE

ISLAND_HEIGHT_NM = 36 * NM_PER_INCH  # standard counter height
_MAX_CORROBORATION_ERROR_IN = 1.0  # plan §17's explicit-dimension tolerance band


@dataclass(frozen=True, slots=True)
class ExtractedKitchenIsland:
    cabinetry: FixedCabinetry
    footprint_match: CaseworkFootprint


def _harvest_footprints() -> list[CaseworkFootprint]:
    with PyMuPdfBackend().open(str(_main_set_pdf())) as h:
        paths = harvest_paths(h, HARVEST_PAGE_INDEX, suppress_text_masks=False)
        text_lines = reassemble_lines(harvest_text_lines(h, HARVEST_PAGE_INDEX))

    dim_lines = [l for l in text_lines if classify_text_line(l) == TextClass.DIMENSION_STRING]
    lines_and_values = []
    for line in dim_lines:
        try:
            lines_and_values.append((line, parse_feet_inches(line.text.strip())))
        except ParseError:
            continue

    return find_casework_footprints(paths, lines_and_values, NOMINAL_IN_PER_PT, HARVEST_PAGE_INDEX)


def _main_set_pdf():
    from ._repo_paths import MAIN_SET_PDF
    return MAIN_SET_PDF


def build_kitchen_island_from_extraction() -> ExtractedKitchenIsland:
    footprints = _harvest_footprints()
    well_corroborated = [
        f for f in footprints
        if f.width_error_in < _MAX_CORROBORATION_ERROR_IN and f.depth_error_in < _MAX_CORROBORATION_ERROR_IN
    ]
    if not well_corroborated:
        raise AssertionError(
            "extraction found no casework footprint corroborated to within "
            f"{_MAX_CORROBORATION_ERROR_IN} in on both axes — the kitchen island "
            "cannot be built without one"
        )
    # The island is the largest well-corroborated footprint on the sheet.
    match = max(well_corroborated, key=lambda f: f.width_nm * f.depth_nm)

    source_ref = SourceRef(doc_id=SOURCE_DOC_ID, page=SOURCE_PAGE, kind=SourceKind.SPAN, path_uids=())
    prov = proposed(
        basis=ProvenanceBasis.EXPLICIT_DIMENSION,
        tolerance_nm=NM_PER_INCH,
        created_by="extract@0.1.0",
        confidence=round(max(0.1, min(0.99, 1.0 - max(match.width_error_in, match.depth_error_in) / 2.0)), 2),
        source_refs=(source_ref,),
    )

    w, d = match.width_nm, match.depth_nm
    footprint = (Point2(0, 0), Point2(w, 0), Point2(w, d), Point2(0, d))
    cabinetry = FixedCabinetry(
        id="KITCHEN.ISLAND", level_id="first", footprint=footprint,
        height_nm=ISLAND_HEIGHT_NM, kind="island", label="Kitchen island", prov=prov,
    )
    return ExtractedKitchenIsland(cabinetry=cabinetry, footprint_match=match)
