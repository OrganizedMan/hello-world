import pytest

from constraints import ConstraintStatus, Diagnosis, FloatingDirection
from core_schema import (
    UNKNOWN,
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
from units import NM_PER_FOOT, NM_PER_INCH
from validate import CheckStatus, run_validation
from validate.checks import (
    check_invention_audit,
    check_unknowns_inventory,
    check_wall_graph_connectivity,
    check_wall_topology_invariant,
)


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


def make_opening(id_, t0, t1, sill=0, head=ft(8), kind=OpeningKind.WINDOW, **kw):
    return Opening(id=id_, kind=kind, t_start_nm=t0, t_end_nm=t1, sill_nm=sill, head_nm=head, prov=confirmed(), **kw)


def make_wall(id_, p0, p1, height_nm=ft(8), thickness_nm=inch(6), openings=(), prov=None):
    return WallSegment(
        id=id_, level_id="L1", variant="proposed", baseline=(p0, p1),
        thickness_nm=thickness_nm, construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=prov or user_authored(created_by="user:jhmgarrigan"),
        base_z_nm=0, top_z_nm=height_nm, openings=openings,
    )


# --- individual checks ---

def test_wall_topology_check_passes_for_valid_walls():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0))
    result = check_wall_topology_invariant([wall])
    assert result.status == CheckStatus.PASS


def test_wall_graph_connectivity_warns_on_dangling_endpoints():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0))
    result = check_wall_graph_connectivity([wall])
    assert result.status == CheckStatus.WARN
    assert len(result.details) == 2  # both endpoints of an isolated wall


def test_wall_graph_connectivity_passes_for_closed_loop():
    walls = [
        make_wall("N", Point2(0, 0), Point2(ft(10), 0)),
        make_wall("E", Point2(ft(10), 0), Point2(ft(10), ft(10))),
        make_wall("S", Point2(ft(10), ft(10)), Point2(0, ft(10))),
        make_wall("W", Point2(0, ft(10)), Point2(0, 0)),
    ]
    result = check_wall_graph_connectivity(walls)
    assert result.status == CheckStatus.PASS


def test_unknowns_inventory_blocks_on_unresolved_height():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0), height_nm=UNKNOWN)
    result = check_unknowns_inventory([wall])
    assert result.status == CheckStatus.BLOCK
    assert "top_z_nm" in result.details[0]


def test_unknowns_inventory_blocks_on_unresolved_opening_head():
    opening = make_opening("o1", 0, ft(3), sill=ft(2), head=UNKNOWN)
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0), openings=(opening,))
    result = check_unknowns_inventory([wall])
    assert result.status == CheckStatus.BLOCK
    assert any("sill_nm" not in d and "head_nm" in d for d in result.details)


def test_unknowns_inventory_passes_when_fully_resolved():
    opening = make_opening("o1", 0, ft(3))
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0), openings=(opening,))
    result = check_unknowns_inventory([wall])
    assert result.status == CheckStatus.PASS


def test_invention_audit_passes_for_user_authored():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0))
    result = check_invention_audit([wall])
    assert result.status == CheckStatus.PASS


def test_invention_audit_passes_for_cited_proposal():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0), prov=confirmed())
    result = check_invention_audit([wall])
    assert result.status == CheckStatus.PASS


# --- full report ---

def test_run_validation_clean_family_room_is_not_blocking():
    window = make_opening("window", 0, ft(3) + inch(8), sill=ft(2), head=ft(5) + inch(6))
    to_mudroom = make_opening("to_mudroom", ft(11), ft(14), sill=0, head=ft(6) + inch(8), kind=OpeningKind.UNFRAMED)
    east_wall = make_wall(
        "LIVING_ROOM.EAST", Point2(0, 0), Point2(0, ft(14) + inch(4)),
        openings=(to_mudroom, window),
    )
    report = run_validation([east_wall])
    assert not report.is_blocking, report.summary()


def test_run_validation_blocks_on_unresolved_height():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0), height_nm=UNKNOWN)
    report = run_validation([wall])
    assert report.is_blocking
    blocking_ids = {c.check_id for c in report.blocking_checks()}
    assert "unknowns_inventory" in blocking_ids


def test_run_validation_includes_constraint_diagnoses():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0))
    contradictory = Diagnosis(
        axis="x", status=ConstraintStatus.CONTRADICTORY,
        variables=(("A", "face"), ("B", "face")),
        solution_nm={("A", "face"): 0, ("B", "face"): ft(10)},
        residuals_nm={"overall": float(NM_PER_INCH * 2)},
        worst_contradiction=("overall", "overall", float(NM_PER_INCH * 2)),
    )
    report = run_validation([wall], diagnoses=[contradictory])
    assert report.is_blocking
    assert any(c.check_id == "constraints_x" and c.status == CheckStatus.BLOCK for c in report.checks)


def test_summary_is_human_readable_text():
    wall = make_wall("W1", Point2(0, 0), Point2(ft(10), 0))
    report = run_validation([wall])
    text = report.summary()
    assert "passed" in text
    assert "wall_topology" in text
