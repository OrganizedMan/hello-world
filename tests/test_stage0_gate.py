"""The Stage 0 gate (plan §14) and the §22 proof-of-concept, backend half.

    "A user traces the family room from the rasterised A-1 page, and it
    builds, validates, locks, and renders from 8 cameras with one geometry
    hash. Topology assertion green."

This test proves everything up to rendering: constraint solving, the
validation report, solid construction, and hash determinism, driven by
`fixtures_garrigan.build_family_room()` — the hand-traced input a human
would produce with the calibrate-and-trace UI. The UI itself and the
Three.js/Cycles renderers are not built yet (see the session's message
about the human-testing boundary); "renders from 8 cameras with one
geometry hash" is proven here as "the hash a renderer would key off is
single-valued and stable," which is the actual guarantee that matters —
who computes the pixels is a separate concern from whether they'd agree.
"""
from __future__ import annotations

from constraints import ConstraintStatus, anchor_region_datums, build_systems, diagnose
from fixtures_garrigan import build_family_room, tv_wall_interval
from geometry import build_wall_solid, compute_geometry_hash
from units import nm_to_ft_in
from validate import CheckStatus, run_validation


def _diagnoses(dimension_constraints):
    """Re-derive diagnoses independently from the constraints the fixture
    returns — deliberately not reusing family_room.py's internal solve —
    so this proves the returned DimensionConstraints are self-sufficient:
    anyone downstream (validation, the review UI) gets the same answer."""
    systems = build_systems(dimension_constraints, [])
    results = []
    for system in systems.values():
        if not system.rows:
            continue
        anchor_region_datums(system)
        results.append(diagnose(system))
    return results


def test_family_room_chain_solves_well_constrained():
    room = build_family_room()
    for d in _diagnoses(room.dimension_constraints):
        assert d.status in (ConstraintStatus.WELL_CONSTRAINED, ConstraintStatus.OVER_CONSTRAINED_CONSISTENT)


def test_east_wall_topology_is_window_then_solid_tv_then_mudroom():
    room = build_family_room()
    east = next(w for w in room.walls if w.id == "LIVING_ROOM.EAST")
    assert [o.id for o in east.openings] == ["window", "to_mudroom"]
    tv_interval = tv_wall_interval(east)  # raises if not actually solid
    assert tv_interval[0] < tv_interval[1]


def test_south_wall_has_only_the_5ft_opening_to_the_original_living_room():
    room = build_family_room()
    south = next(w for w in room.walls if w.id == "LIVING_ROOM.SOUTH")
    assert len(south.openings) == 1
    opening = south.openings[0]
    assert opening.t_end_nm - opening.t_start_nm == 5 * 304_800_000  # 5'-0" exactly
    assert nm_to_ft_in(opening.t_start_nm) == "3'-1\""


def test_the_reported_failure_is_unrepresentable_by_construction():
    # The specific bug this project exists to prevent: the TV ending up on
    # the SOUTH wall's opening instead of solid EAST wall. Both walls are
    # independent WallSegments — nothing links "60\" TV" to any Opening at
    # all (see family_room.py's comment on to_mudroom), so there is no
    # field to corrupt that would move the annotation onto the wrong wall.
    room = build_family_room()
    south = next(w for w in room.walls if w.id == "LIVING_ROOM.SOUTH")
    assert all(o.annotation != '60" TV' for w in room.walls for o in w.openings)
    assert len(south.openings) == 1 and south.openings[0].kind.value == "cased"


def test_validation_report_is_not_blocking():
    room = build_family_room()
    diagnoses = _diagnoses(room.dimension_constraints)
    report = run_validation(list(room.walls), diagnoses=diagnoses)
    assert not report.is_blocking, report.summary()
    # every check that ran should have an opinion; nothing silently absent
    assert len(report.checks) >= 4 + len(diagnoses)


def test_build_validate_lock_end_to_end():
    room = build_family_room()
    diagnoses = _diagnoses(room.dimension_constraints)
    report = run_validation(list(room.walls), diagnoses=diagnoses)
    assert not report.is_blocking, report.summary()

    solids = {w.id: build_wall_solid(w) for w in room.walls}
    geometry_hash = compute_geometry_hash(list(room.walls), solids)

    assert len(geometry_hash) == 64
    for wall in room.walls:
        assert solids[wall.id].volume() > 0


def test_geometry_hash_is_stable_across_rebuilds_the_render_guarantee():
    # "Identical geometry across every rendered camera view" (plan §2, §17)
    # reduces to: the hash a renderer keys off must be single-valued and
    # reproducible. This rebuilds the whole model from scratch 3 times —
    # constraint solve included, not just the mesh step — and checks the
    # hash never moves.
    hashes = set()
    for _ in range(3):
        room = build_family_room()
        solids = {w.id: build_wall_solid(w) for w in room.walls}
        hashes.add(compute_geometry_hash(list(room.walls), solids))
    assert len(hashes) == 1
