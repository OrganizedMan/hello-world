"""Individual validation checks (plan §12).

Sprint 2 implements the checks that apply to a single hand-traced level
with no roof, stairs, or multistory registration yet (Stage 2 concerns).
Two of these — wall topology and the invention audit — re-verify
invariants the schema and Provenance already enforce at construction time
(core_schema.wall_topology, core_schema.provenance). That is deliberate,
not redundant: the validation report is a user-facing artifact people are
meant to read and trust, and a check that can never fail is exactly the
kind of thing worth stating explicitly rather than leaving implicit in
code no one reads before rendering.

Deferred to later stages, named here so the gap is visible rather than
silent: scale-calibration residual and opening-inventory-vs-annotations
(need Stage 1 extraction to compare against), multistory registration RMS,
stair rise reconciliation, and roof-derived clear heights (Stage 2).
"""
from __future__ import annotations

import networkx as nx

from constraints import ConstraintStatus, Diagnosis
from core_schema import UNKNOWN, ProvenanceState, WallSegment
from core_schema.wall_topology import OpeningInterval, TopologyError, validate_wall_openings

from .report import CheckResult, CheckStatus


def check_wall_topology_invariant(walls: list[WallSegment]) -> CheckResult:
    problems: list[str] = []
    for w in walls:
        try:
            validate_wall_openings(
                w.id, w.length_nm,
                tuple(OpeningInterval(o.id, o.t_start_nm, o.t_end_nm) for o in w.openings),
            )
        except TopologyError as e:
            problems.append(str(e))
    if problems:
        return CheckResult(
            "wall_topology", CheckStatus.BLOCK,
            f"{len(problems)} wall(s) have invalid opening topology", tuple(problems),
        )
    return CheckResult(
        "wall_topology", CheckStatus.PASS,
        f"all {len(walls)} wall(s) have valid, non-overlapping, in-bounds opening topology",
    )


def check_wall_graph_connectivity(walls: list[WallSegment]) -> CheckResult:
    """Dangling wall endpoints are a WARN, not a BLOCK: a partial trace
    (a couple of walls confirmed, the rest of the room not yet drawn) is
    the normal mid-session state in the review UI, not an error. Room
    closure itself is checked separately, once Room entities exist."""
    graph = nx.MultiGraph()
    for w in walls:
        p0, p1 = w.baseline
        graph.add_edge((p0.x_nm, p0.y_nm), (p1.x_nm, p1.y_nm), wall_id=w.id)

    dangling = sorted(n for n in graph.nodes if graph.degree(n) == 1)
    if dangling:
        details = tuple(f"endpoint {n} is touched by only one wall" for n in dangling)
        return CheckResult(
            "wall_graph_connectivity", CheckStatus.WARN,
            f"{len(dangling)} dangling wall endpoint(s) — rooms cannot close until these connect",
            details,
        )
    return CheckResult("wall_graph_connectivity", CheckStatus.PASS, "no dangling wall endpoints")


def check_unknowns_inventory(walls: list[WallSegment]) -> CheckResult:
    """§12 check 9: an explicit, enumerated list of every Unknown field —
    never a silent default. Sprint 2 treats any Unknown vertical extent as
    blocking the whole build (the conservative default); rendering the
    resolved parts of a model "open-topped" around specific Unknowns
    (plan §11) is a Stage 1+ refinement, not implemented here."""
    unknowns: list[str] = []
    for w in walls:
        if w.base_z_nm is UNKNOWN:
            unknowns.append(f"wall {w.id}: base_z_nm is Unknown")
        if w.top_z_nm is UNKNOWN:
            unknowns.append(f"wall {w.id}: top_z_nm is Unknown")
        for o in w.openings:
            if o.sill_nm is UNKNOWN:
                unknowns.append(f"opening {o.id} (wall {w.id}): sill_nm is Unknown")
            if o.head_nm is UNKNOWN:
                unknowns.append(f"opening {o.id} (wall {w.id}): head_nm is Unknown")
    if unknowns:
        return CheckResult(
            "unknowns_inventory", CheckStatus.BLOCK,
            f"{len(unknowns)} field(s) are explicitly Unknown and must be resolved before Build",
            tuple(unknowns),
        )
    return CheckResult("unknowns_inventory", CheckStatus.PASS, "no Unknown fields remain")


def check_invention_audit(walls: list[WallSegment]) -> CheckResult:
    """§12 check 10: every wall and opening must trace to a non-user
    SourceRef or be explicitly USER_AUTHORED. Provenance.__post_init__
    already makes the alternative unconstructable — this re-states that
    guarantee as a named, reportable check."""
    problems: list[str] = []
    for w in walls:
        if w.prov.state != ProvenanceState.USER_AUTHORED and not w.prov.source_refs:
            problems.append(f"wall {w.id}: no source citation and not USER_AUTHORED")
        for o in w.openings:
            if o.prov.state != ProvenanceState.USER_AUTHORED and not o.prov.source_refs:
                problems.append(f"opening {o.id} (wall {w.id}): no source citation and not USER_AUTHORED")
    if problems:
        return CheckResult(
            "invention_audit", CheckStatus.BLOCK,
            f"{len(problems)} entities fail the invention audit", tuple(problems),
        )
    return CheckResult(
        "invention_audit", CheckStatus.PASS,
        f"all {len(walls)} wall(s) and their openings cite a source or are USER_AUTHORED",
    )


def check_constraint_diagnoses(diagnoses: list[Diagnosis]) -> tuple[CheckResult, ...]:
    """§12 checks 2+3: dimension chain closure and rank diagnosis, driven
    directly by `constraints.diagnose()` rather than re-implemented here."""
    results = []
    for d in diagnoses:
        check_id = f"constraints_{d.axis}"
        if d.status == ConstraintStatus.WELL_CONSTRAINED:
            results.append(CheckResult(
                check_id, CheckStatus.PASS,
                f"{d.axis}-axis: well-constrained ({len(d.variables)} variable(s))",
            ))
        elif d.status == ConstraintStatus.OVER_CONSTRAINED_CONSISTENT:
            results.append(CheckResult(
                check_id, CheckStatus.WARN,
                f"{d.axis}-axis: over-constrained but consistent "
                f"(max residual {d.max_abs_residual_nm:.1f} nm)",
            ))
        elif d.status == ConstraintStatus.UNDER_CONSTRAINED:
            details = tuple(
                ", ".join(f"{v}" for v in fd.variables) for fd in d.floating
            )
            results.append(CheckResult(
                check_id, CheckStatus.BLOCK,
                f"{d.axis}-axis: under-constrained — {len(d.floating)} free direction(s)",
                details,
            ))
        else:  # CONTRADICTORY
            label, _, err_nm = d.worst_contradiction
            results.append(CheckResult(
                check_id, CheckStatus.BLOCK,
                f"{d.axis}-axis: contradictory — dimension chain does not close "
                f"(worst residual {err_nm:.0f} nm on {label})",
                (label,),
            ))
    return tuple(results)
