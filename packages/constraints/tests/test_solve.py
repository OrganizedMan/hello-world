import pytest

from pdf3d_constraints import (
    ConstraintStatus,
    Row,
    ConstraintSystem,
    diagnose,
)
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def system(*rows: Row, axis="x") -> ConstraintSystem:
    s = ConstraintSystem(axis)
    s.rows.extend(rows)
    return s


def anchor(var, value_nm=0.0, label="anchor"):
    """A single-variable row pinning one variable to an absolute value —
    what `pdf3d_constraints.anchor()` produces for a real FeatureRef, expressed
    directly against the raw VariableKey tuples these low-level tests use.
    Every relative-only chain is genuinely UNDER_CONSTRAINED (global
    translation is free) until something anchors it; that is the solver
    working correctly, not a quirk to work around."""
    return Row({var: 1.0}, rhs_nm=value_nm, weight=1.0, label=label)


def test_well_constrained_two_points_one_dimension():
    s = system(
        anchor(("O", "x"), 0.0),
        Row({("A", "x"): 1.0, ("O", "x"): -1.0}, rhs_nm=ft(10), weight=1.0, label="d1"),
    )
    d = diagnose(s)
    assert d.status == ConstraintStatus.WELL_CONSTRAINED
    assert d.solution_nm[("O", "x")] == 0
    assert d.solution_nm[("A", "x")] - d.solution_nm[("O", "x")] == ft(10)
    assert not d.is_blocking


def test_under_constrained_reports_floating_variables():
    # Three walls (A, B, C) related by two dimensions: one degree of
    # freedom (a global offset) is left over, since nothing pins the
    # chain to an absolute position.
    s = system(
        Row({("B", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(5), weight=1.0, label="A-B"),
        Row({("C", "x"): 1.0, ("B", "x"): -1.0}, rhs_nm=ft(3), weight=1.0, label="B-C"),
    )
    # 3 variables (A,B,C), 2 equations -> 1 DOF free (a global offset)
    d = diagnose(s)
    assert d.status == ConstraintStatus.UNDER_CONSTRAINED
    assert d.is_blocking
    assert len(d.floating) >= 1
    floating_vars = {v for fd in d.floating for v in fd.variables}
    assert floating_vars <= {("A", "x"), ("B", "x"), ("C", "x")}
    # the relative distance is still pinned even though the system floats
    assert (
        d.solution_nm[("B", "x")] - d.solution_nm[("A", "x")] == ft(5)
    )
    assert (
        d.solution_nm[("C", "x")] - d.solution_nm[("B", "x")] == ft(3)
    )


def test_over_constrained_consistent_redundant_dimension_agrees():
    # A anchored at 0; A-B = 5', B-C = 3', and an overall A-C = 8' that
    # agrees exactly — a redundant but consistent dimension.
    s = system(
        anchor(("A", "x"), 0.0),
        Row({("B", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(5), weight=1.0, label="A-B"),
        Row({("C", "x"): 1.0, ("B", "x"): -1.0}, rhs_nm=ft(3), weight=1.0, label="B-C"),
        Row({("C", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(8), weight=1.0, label="A-C-overall"),
    )
    d = diagnose(s)
    assert d.status == ConstraintStatus.OVER_CONSTRAINED_CONSISTENT
    assert not d.is_blocking
    assert d.max_abs_residual_nm < 1.0


def test_contradictory_chain_does_not_close():
    # Same as above but the overall is wrong by 2 feet — a real drafting
    # contradiction, well over the 1" blocking threshold.
    s = system(
        anchor(("A", "x"), 0.0),
        Row({("B", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(5), weight=1.0, label="A-B"),
        Row({("C", "x"): 1.0, ("B", "x"): -1.0}, rhs_nm=ft(3), weight=1.0, label="B-C"),
        Row({("C", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(10), weight=1.0, label="A-C-overall-WRONG"),
    )
    d = diagnose(s)
    assert d.status == ConstraintStatus.CONTRADICTORY
    assert d.is_blocking
    assert d.worst_contradiction is not None
    assert d.max_abs_residual_nm > NM_PER_INCH


def test_small_disagreement_within_one_inch_is_not_contradictory():
    # Overall off by exactly half an inch — should warn, not block.
    s = system(
        anchor(("A", "x"), 0.0),
        Row({("B", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(5), weight=1.0, label="A-B"),
        Row({("C", "x"): 1.0, ("B", "x"): -1.0}, rhs_nm=ft(3), weight=1.0, label="B-C"),
        Row(
            {("C", "x"): 1.0, ("A", "x"): -1.0},
            rhs_nm=ft(8) + inch(0.5),
            weight=1.0,
            label="A-C-overall-slightly-off",
        ),
    )
    d = diagnose(s)
    assert d.status == ConstraintStatus.OVER_CONSTRAINED_CONSISTENT


def test_no_variables_is_trivially_well_constrained():
    d = diagnose(ConstraintSystem("x"))
    assert d.status == ConstraintStatus.WELL_CONSTRAINED
    assert d.variables == ()


# --- Determinism ---

def test_diagnosis_is_deterministic_across_runs():
    def make():
        return system(
            Row({("B", "x"): 1.0, ("A", "x"): -1.0}, rhs_nm=ft(5), weight=1.0, label="A-B"),
            Row({("C", "x"): 1.0, ("B", "x"): -1.0}, rhs_nm=ft(3), weight=1.0, label="B-C"),
        )

    results = [diagnose(make()).solution_nm for _ in range(5)]
    assert all(r == results[0] for r in results)
