"""The kitchen island: a second, independent extraction technique (poché
footprint measurement, `extract.casework`) proven end to end — real PDF
geometry -> corroborated footprint -> FixedCabinetry entity -> solid mesh.
"""
from __future__ import annotations

from core_schema import ProvenanceState
from fixtures_garrigan import build_kitchen_island_from_extraction
from geometry import build_cabinetry_solid
from units import NM_PER_INCH


def test_island_footprint_matches_labelled_dimensions_within_one_inch():
    result = build_kitchen_island_from_extraction()
    assert result.footprint_match.width_error_in < 1.0
    assert result.footprint_match.depth_error_in < 1.0


def test_island_dimensions_are_8_7_by_4_3():
    result = build_kitchen_island_from_extraction()
    c = result.cabinetry
    p0, _, p2, _ = c.footprint
    width_in = round((p2.x_nm - p0.x_nm) / NM_PER_INCH)
    depth_in = round((p2.y_nm - p0.y_nm) / NM_PER_INCH)
    assert width_in == 103  # 8'-7"
    assert depth_in == 51  # 4'-3"


def test_island_is_proposed_with_a_real_citation():
    result = build_kitchen_island_from_extraction()
    prov = result.cabinetry.prov
    assert prov.state == ProvenanceState.PROPOSED
    assert prov.source_refs


def test_island_builds_a_nonempty_solid():
    result = build_kitchen_island_from_extraction()
    solid = build_cabinetry_solid(result.cabinetry)
    mesh = solid.to_mesh()
    assert len(mesh.vert_properties) > 0
    assert len(mesh.tri_verts) > 0
