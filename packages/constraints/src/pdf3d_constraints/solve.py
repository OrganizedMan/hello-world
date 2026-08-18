"""Solve a ConstraintSystem and diagnose it (plan §8).

    rank(A) = n_vars, residual ~ 0        -> WELL_CONSTRAINED
    rank(A) < n_vars                      -> UNDER_CONSTRAINED (report the
                                              nullspace basis: the specific
                                              variables/walls that can float)
    rank(A) = n_vars, n_eqs > rank, small
      residual                            -> OVER_CONSTRAINED_CONSISTENT
                                              (solve weighted LSQ, report
                                              per-constraint residual)
    rank(A) = n_vars, residual exceeds
      the contradiction threshold         -> CONTRADICTORY (chain does not
                                              close; blocking)

Everything here operates on plain floats internally (nanometre-scale
integers are exact in float64 well beyond any real building's size) and
rounds back to int nm at the end with a fixed, sorted variable ordering,
so the same input always produces a byte-identical result (plan §8).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.linalg import null_space

from .system import ConstraintSystem, VariableKey

#: Absolute residual below which a solved system is considered exact —
#: purely to absorb float64 solver noise, not a real-world tolerance.
EXACT_TOL_NM = 1.0

#: Above this, an over-determined system's disagreement is a real
#: dimensioning conflict rather than rounding noise. Matches the plan's
#: own chain-closure blocking threshold (plan §12 check 2).
DEFAULT_CONTRADICTION_THRESHOLD_NM = 25_400_000  # 1 in

#: Below this, a nullspace basis vector's component on a variable is
#: treated as zero (not actually free in that direction).
NULLSPACE_COMPONENT_TOL = 1e-6


class ConstraintStatus(str, Enum):
    WELL_CONSTRAINED = "well_constrained"
    UNDER_CONSTRAINED = "under_constrained"
    OVER_CONSTRAINED_CONSISTENT = "over_constrained_consistent"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class FloatingDirection:
    """One nullspace basis vector: a way the under-constrained system can
    move without violating any constraint, named by which variables move
    and by how much relative to each other."""

    components: tuple[tuple[VariableKey, float], ...]

    @property
    def variables(self) -> tuple[VariableKey, ...]:
        return tuple(v for v, _ in self.components)


@dataclass(frozen=True, slots=True)
class Diagnosis:
    axis: str
    status: ConstraintStatus
    variables: tuple[VariableKey, ...]
    solution_nm: dict[VariableKey, int]  # present (best-effort) for every status
    residuals_nm: dict[str, float]  # row label -> signed residual, nm
    floating: tuple[FloatingDirection, ...] = ()  # non-empty iff UNDER_CONSTRAINED
    worst_contradiction: tuple[str, str, float] | None = None  # (label_a, label_b, closure_error_nm)

    @property
    def max_abs_residual_nm(self) -> float:
        if not self.residuals_nm:
            return 0.0
        return max(abs(v) for v in self.residuals_nm.values())

    @property
    def is_blocking(self) -> bool:
        return self.status in (ConstraintStatus.UNDER_CONSTRAINED, ConstraintStatus.CONTRADICTORY)


def diagnose(
    system: ConstraintSystem,
    contradiction_threshold_nm: float = DEFAULT_CONTRADICTION_THRESHOLD_NM,
) -> Diagnosis:
    variables = system.variables
    n_vars = len(variables)
    var_index = {v: i for i, v in enumerate(variables)}
    n_eqs = len(system.rows)

    if n_vars == 0:
        return Diagnosis(
            axis=system.axis, status=ConstraintStatus.WELL_CONSTRAINED,
            variables=(), solution_nm={}, residuals_nm={},
        )

    A = np.zeros((n_eqs, n_vars))
    b = np.zeros(n_eqs)
    w = np.ones(n_eqs)
    for i, row in enumerate(system.rows):
        for var, coeff in row.coeffs.items():
            A[i, var_index[var]] = coeff
        b[i] = row.rhs_nm
        w[i] = row.weight

    # n_eqs == 0 here is unreachable: variables are only ever discovered
    # from row coefficients (ConstraintSystem.variables), so an empty row
    # list already returned above via the n_vars == 0 check. A wall with
    # no explicit dimension simply never becomes a variable in this
    # system at all — it keeps its as-traced coordinate with
    # basis=measured_from_geometry, handled outside the linear solver
    # (plan §5.2, §8).

    numeric_rank = int(np.linalg.matrix_rank(A))

    sqrt_w = np.sqrt(w)
    A_weighted = A * sqrt_w[:, None]
    b_weighted = b * sqrt_w
    x, *_ = np.linalg.lstsq(A_weighted, b_weighted, rcond=None)

    residual = A @ x - b
    residuals_nm = {row.label: float(residual[i]) for i, row in enumerate(system.rows)}
    max_abs_residual = max((abs(r) for r in residuals_nm.values()), default=0.0)

    solution_nm = {v: _round_half_even(x[var_index[v]]) for v in variables}

    if numeric_rank < n_vars:
        basis = null_space(A)  # columns are an orthonormal nullspace basis
        floating = tuple(
            FloatingDirection(
                components=tuple(
                    (variables[i], float(basis[i, k]))
                    for i in range(n_vars)
                    if abs(basis[i, k]) > NULLSPACE_COMPONENT_TOL
                )
            )
            for k in range(basis.shape[1])
        )
        return Diagnosis(
            axis=system.axis, status=ConstraintStatus.UNDER_CONSTRAINED,
            variables=variables, solution_nm=solution_nm,
            residuals_nm=residuals_nm, floating=floating,
        )

    if max_abs_residual <= EXACT_TOL_NM:
        status = (
            ConstraintStatus.WELL_CONSTRAINED
            if n_eqs == numeric_rank
            else ConstraintStatus.OVER_CONSTRAINED_CONSISTENT
        )
        return Diagnosis(
            axis=system.axis, status=status, variables=variables,
            solution_nm=solution_nm, residuals_nm=residuals_nm,
        )

    if max_abs_residual <= contradiction_threshold_nm:
        return Diagnosis(
            axis=system.axis, status=ConstraintStatus.OVER_CONSTRAINED_CONSISTENT,
            variables=variables, solution_nm=solution_nm, residuals_nm=residuals_nm,
        )

    worst_label = max(residuals_nm, key=lambda k: abs(residuals_nm[k]))
    worst = (worst_label, worst_label, residuals_nm[worst_label])
    return Diagnosis(
        axis=system.axis, status=ConstraintStatus.CONTRADICTORY,
        variables=variables, solution_nm=solution_nm, residuals_nm=residuals_nm,
        worst_contradiction=worst,
    )


def _round_half_even(x: float) -> int:
    # Python's round() on a float already implements round-half-to-even;
    # named here so the rounding rule is documented at the call site.
    return round(x)
