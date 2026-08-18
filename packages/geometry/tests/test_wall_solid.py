import pytest

from core_schema import (
    Opening,
    OpeningKind,
    Point2,
    ProvenanceBasis,
    SourceKind,
    SourceRef,
    WallConstruction,
    WallSegment,
    user_authored,
    user_confirmed,
)
from geometry import UnresolvedGeometryError, build_wall_solid, nm_to_m
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def src():
    return SourceRef(doc_id="doc1", page=2, kind=SourceKind.PATH, path_uids=("p1",))


def confirmed():
    return user_confirmed(
        basis=ProvenanceBasis.EXPLICIT_DIMENSION, tolerance_nm=NM_PER_INCH,
        created_by="user:jhmgarrigan", source_refs=(src(),),
    )


def make_opening(id_, t0, t1, sill, head, kind=OpeningKind.WINDOW, **kw):
    return Opening(
        id=id_, kind=kind, t_start_nm=t0, t_end_nm=t1, prov=confirmed(),
        sill_nm=sill, head_nm=head, **kw,
    )


def make_wall(id_, length_nm, height_nm=ft(8) + inch(5), thickness_nm=inch(6), openings=(), y0=0):
    return WallSegment(
        id=id_, level_id="L1", variant="proposed",
        baseline=(Point2(0, y0), Point2(length_nm, y0)),
        thickness_nm=thickness_nm,
        construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=user_authored(created_by="user:jhmgarrigan"),
        base_z_nm=0, top_z_nm=height_nm,
        openings=openings,
    )


def test_solid_wall_volume_matches_length_times_thickness_times_height():
    length, thickness, height = ft(10), inch(6), ft(8) + inch(5)
    wall = make_wall("W1", length, height_nm=height, thickness_nm=thickness)
    solid = build_wall_solid(wall)
    expected = nm_to_m(length) * nm_to_m(thickness) * nm_to_m(height)
    assert solid.volume() == pytest.approx(expected, rel=1e-6)


def test_opening_removes_expected_volume():
    length, thickness, height = ft(14) + inch(4), inch(6), ft(8) + inch(5)
    window = make_opening("window", 0, ft(3) + inch(8), sill=ft(2), head=ft(5) + inch(6))
    wall = make_wall("W1", length, height_nm=height, thickness_nm=thickness, openings=(window,))
    solid = build_wall_solid(wall)

    full = nm_to_m(length) * nm_to_m(thickness) * nm_to_m(height)
    cut = nm_to_m(window.t_end_nm - window.t_start_nm) * nm_to_m(thickness) * nm_to_m(
        window.head_nm - window.sill_nm
    )
    assert solid.volume() == pytest.approx(full - cut, rel=1e-6)


def test_two_openings_both_removed_and_no_overlap_double_counted():
    length, thickness, height = ft(14) + inch(4), inch(6), ft(8) + inch(5)
    window = make_opening("window", 0, ft(3) + inch(8), sill=ft(2), head=ft(5) + inch(6))
    to_mudroom = make_opening(
        "to_mudroom", ft(11), ft(14), sill=0, head=ft(6) + inch(8), kind=OpeningKind.UNFRAMED
    )
    wall = make_wall(
        "LIVING_ROOM.EAST", length, height_nm=height, thickness_nm=thickness,
        openings=(to_mudroom, window),
    )
    solid = build_wall_solid(wall)

    full = nm_to_m(length) * nm_to_m(thickness) * nm_to_m(height)
    cut1 = nm_to_m(window.t_end_nm) * nm_to_m(thickness) * nm_to_m(window.head_nm - window.sill_nm)
    cut2 = (
        nm_to_m(to_mudroom.t_end_nm - to_mudroom.t_start_nm)
        * nm_to_m(thickness)
        * nm_to_m(to_mudroom.head_nm - to_mudroom.sill_nm)
    )
    assert solid.volume() == pytest.approx(full - cut1 - cut2, rel=1e-6)


def test_unknown_top_z_is_a_hard_error_not_a_guess():
    from core_schema import UNKNOWN

    wall = WallSegment(
        id="W1", level_id="L1", variant="proposed",
        baseline=(Point2(0, 0), Point2(ft(10), 0)),
        thickness_nm=inch(6),
        construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=user_authored(created_by="user:jhmgarrigan"),
        base_z_nm=0, top_z_nm=UNKNOWN,
    )
    with pytest.raises(UnresolvedGeometryError):
        build_wall_solid(wall)


def test_unknown_opening_head_is_a_hard_error():
    from core_schema import UNKNOWN

    opening = Opening(
        id="o1", kind=OpeningKind.WINDOW, t_start_nm=0, t_end_nm=ft(3), prov=confirmed(),
        sill_nm=ft(2), head_nm=UNKNOWN,
    )
    wall = make_wall("W1", ft(10), openings=(opening,))
    with pytest.raises(UnresolvedGeometryError):
        build_wall_solid(wall)


def test_rotated_wall_has_same_volume_as_axis_aligned():
    # A wall running diagonally should have identical volume to the
    # equivalent axis-aligned wall — the rotation only changes orientation.
    length, thickness, height = ft(10), inch(6), ft(8)
    axis_aligned = WallSegment(
        id="W1", level_id="L1", variant="proposed",
        baseline=(Point2(0, 0), Point2(length, 0)),
        thickness_nm=thickness, construction=WallConstruction.EXISTING,
        prov=user_authored(created_by="user:jhmgarrigan"), base_z_nm=0, top_z_nm=height,
    )
    diagonal = WallSegment(
        id="W2", level_id="L1", variant="proposed",
        baseline=(Point2(0, 0), Point2(length, length)),  # 45 degrees, longer baseline
        thickness_nm=thickness, construction=WallConstruction.EXISTING,
        prov=user_authored(created_by="user:jhmgarrigan"), base_z_nm=0, top_z_nm=height,
    )
    v1 = build_wall_solid(axis_aligned).volume()
    v2 = build_wall_solid(diagonal).volume()
    # different lengths (diagonal baseline is longer), so scale by length ratio
    assert v2 / v1 == pytest.approx(diagonal.length_nm / axis_aligned.length_nm, rel=1e-6)


def test_build_is_deterministic_across_runs():
    length, thickness, height = ft(14) + inch(4), inch(6), ft(8) + inch(5)
    window = make_opening("window", 0, ft(3) + inch(8), sill=ft(2), head=ft(5) + inch(6))

    def build():
        wall = make_wall(
            "LIVING_ROOM.EAST", length, height_nm=height, thickness_nm=thickness,
            openings=(window,),
        )
        return build_wall_solid(wall)

    v1 = build().volume()
    v2 = build().volume()
    assert v1 == v2
