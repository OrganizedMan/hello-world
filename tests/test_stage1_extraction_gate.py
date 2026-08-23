"""The Stage 1 gate, scoped to the family room (plan §14):

    "extracted first floor matches the Stage-0 hand-traced model within 1 in"

`build_family_room_from_extraction()` is structurally identical to
`build_family_room()` — same wall ids, same FeatureRef names, same axis
assembly and solver — but sources its DimensionConstraint values from
real tick-to-tick matches against the pinned PDF (packages/extract)
instead of typed-in constants. This test solves both and diffs every
corresponding coordinate.
"""
from __future__ import annotations

from pdf3d_constraints import ConstraintStatus
from fixtures_garrigan import (
    build_family_room,
    build_family_room_from_extraction,
    diagnose_extracted_family_room,
)
from units import NM_PER_INCH

ONE_INCH = NM_PER_INCH


def test_extracted_family_room_solves_well_constrained():
    room = build_family_room_from_extraction()
    for d in diagnose_extracted_family_room(room):
        assert d.status in (ConstraintStatus.WELL_CONSTRAINED, ConstraintStatus.OVER_CONSTRAINED_CONSISTENT)


def test_extracted_walls_match_hand_traced_walls_within_one_inch():
    extracted = build_family_room_from_extraction()
    hand_traced = build_family_room()

    for we, wh in zip(extracted.walls, hand_traced.walls):
        assert we.id == wh.id
        (p0e, p1e), (p0h, p1h) = we.baseline, wh.baseline
        assert abs(p0e.x_nm - p0h.x_nm) < ONE_INCH
        assert abs(p0e.y_nm - p0h.y_nm) < ONE_INCH
        assert abs(p1e.x_nm - p1h.x_nm) < ONE_INCH
        assert abs(p1e.y_nm - p1h.y_nm) < ONE_INCH
        assert len(we.openings) == len(wh.openings)
        for oe, oh in zip(we.openings, wh.openings):
            assert oe.id == oh.id
            assert abs(oe.t_start_nm - oh.t_start_nm) < ONE_INCH
            assert abs(oe.t_end_nm - oh.t_end_nm) < ONE_INCH


def test_extracted_east_wall_topology_matches_the_regression_subject():
    """The exact topology the whole project exists to guarantee — window,
    then solid wall, then the mudroom opening — reproduced from real
    extraction, not typed in."""
    room = build_family_room_from_extraction()
    east = next(w for w in room.walls if w.id == "LIVING_ROOM.EAST")
    assert [o.id for o in east.openings] == ["window", "to_mudroom"]
    window, mudroom = east.openings
    assert window.t_end_nm < mudroom.t_start_nm  # a genuine solid gap between them


def test_extracted_dimension_constraints_carry_real_citations_not_invented_ones():
    from core_schema import ProvenanceState

    room = build_family_room_from_extraction()
    dimensioned = [d for d in room.dimension_constraints if d.text != "calibration datum"]
    assert dimensioned
    for d in dimensioned:
        assert d.prov.state == ProvenanceState.PROPOSED
        assert d.prov.source_refs, f"{d.id} has no source_refs — would fail the invention audit"
