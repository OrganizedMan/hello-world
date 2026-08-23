import pytest

from core_schema import FixedCabinetry, Point2, ProvenanceBasis, SourceKind, SourceRef, user_authored
from geometry import build_cabinetry_solid, nm_to_m
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def make_island(width_nm=ft(8) + inch(7), depth_nm=ft(4) + inch(3), height_nm=inch(36)):
    footprint = (Point2(0, 0), Point2(width_nm, 0), Point2(width_nm, depth_nm), Point2(0, depth_nm))
    return FixedCabinetry(
        id="KITCHEN.ISLAND", level_id="first", footprint=footprint,
        height_nm=height_nm, kind="island", label="Kitchen island",
        prov=user_authored(created_by="test"),
    )


def test_island_solid_has_correct_bounding_box():
    island = make_island()
    solid = build_cabinetry_solid(island)
    mesh = solid.to_mesh()
    verts = mesh.vert_properties
    assert verts[:, 0].max() == pytest.approx(nm_to_m(ft(8) + inch(7)), abs=1e-6)
    assert verts[:, 1].max() == pytest.approx(nm_to_m(ft(4) + inch(3)), abs=1e-6)
    assert verts[:, 2].max() == pytest.approx(nm_to_m(inch(36)), abs=1e-6)
    assert verts[:, 0].min() == pytest.approx(0.0, abs=1e-6)
    assert verts[:, 2].min() == pytest.approx(0.0, abs=1e-6)


def test_zero_height_is_rejected():
    island = make_island(height_nm=0)
    with pytest.raises(ValueError):
        build_cabinetry_solid(island)


def test_degenerate_footprint_is_rejected():
    island = FixedCabinetry(
        id="x", level_id="first", footprint=(Point2(0, 0), Point2(1, 0)),
        height_nm=inch(36), kind="island", label="x", prov=user_authored(created_by="test"),
    )
    with pytest.raises(ValueError):
        build_cabinetry_solid(island)
