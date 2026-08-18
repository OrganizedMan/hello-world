"""Linear constraint-system assembly (plan §8).

Residential plans are almost entirely axis-aligned, so each
DimensionConstraint/AlignmentConstraint becomes one linear equation over
scalar coordinate variables — no general nonlinear geometric constraint
solver is needed for the MVP. A "variable" is a single named scalar: the
x (or y, or z) coordinate of one feature (a wall face, an opening jamb, a
grid line, a region datum). X, Y, and Z systems are independent and are
built and solved separately by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core_schema import AlignmentConstraint, DimensionConstraint, FeatureRef

#: (entity_id, feature) — the axis is implicit in which ConstraintSystem
#: this key lives in, since x/y/z systems are solved independently.
VariableKey = tuple[str, str]


def _var(ref: FeatureRef) -> VariableKey:
    return (ref.entity_id, ref.feature)


@dataclass(frozen=True, slots=True)
class Row:
    """One linear equation: sum(coeff * variable) = rhs_nm."""

    coeffs: dict[VariableKey, float]
    rhs_nm: float
    weight: float
    label: str  # the constraint id/text this row came from, for diagnostics


@dataclass(slots=True)
class ConstraintSystem:
    axis: str
    rows: list[Row] = field(default_factory=list)

    @property
    def variables(self) -> tuple[VariableKey, ...]:
        seen: dict[VariableKey, None] = {}
        for row in self.rows:
            for v in row.coeffs:
                seen.setdefault(v, None)
        # Sorted for determinism: the solver's variable ordering must be
        # fixed so the same input always produces the same rounded output
        # (plan §8: "deterministic ... on a fixed variable ordering").
        return tuple(sorted(seen))


class UnsupportedConstraintError(ValueError):
    """Raised for a constraint kind/axis the Sprint 2 solver does not yet
    reduce to a linear row (e.g. "along:<wall>" or "perpendicular"),
    rather than silently dropping or misinterpreting it."""


def anchor(feature: FeatureRef, value_nm: int, label: str | None = None) -> Row:
    """A single-variable row pinning one feature to an absolute coordinate.

    Every DimensionConstraint is inherently *relative* (plan §5.2: it
    always relates two FeatureRefs), matching how dimensions are actually
    drawn — nothing on a real sheet says "this wall is at x=0". A chain of
    purely relative constraints is therefore correctly diagnosed as
    UNDER_CONSTRAINED by `diagnose` (global translation is unconstrained),
    and that is not a bug to work around: it is the solver catching a real
    fact about the drawing. Resolving it is a deliberate modeling choice
    made by whoever assembles the system — typically anchoring one wall
    face to the region's calibrated datum (a FeatureRef with
    feature="datum") — which is what this helper is for. `build_systems`
    deliberately does not call it automatically.
    """
    return Row(coeffs={_var(feature): 1.0}, rhs_nm=float(value_nm), weight=1.0, label=label or f"anchor:{feature}")


def build_systems(
    dimension_constraints: list[DimensionConstraint],
    alignment_constraints: list[AlignmentConstraint],
) -> dict[str, ConstraintSystem]:
    """Split constraints into independent per-axis linear systems.

    Only axis="x" and axis="y" dimension constraints, and
    kind in {"collinear", "equal"} alignment constraints with an explicit
    axis, are supported. Anything else raises UnsupportedConstraintError
    naming the offending constraint — silence here would mean a real
    constraint from the drawing was quietly ignored.
    """
    systems: dict[str, ConstraintSystem] = {"x": ConstraintSystem("x"), "y": ConstraintSystem("y")}

    for dc in dimension_constraints:
        if dc.axis not in ("x", "y"):
            raise UnsupportedConstraintError(
                f"DimensionConstraint {dc.id!r} has axis={dc.axis!r}; the Sprint 2 "
                "solver only handles axis-aligned 'x'/'y' constraints directly — "
                "'along:<wall_id>' and 'z' require wall-parametric or vertical "
                "handling not yet implemented (plan §9, §18 R4)."
            )
        systems[dc.axis].rows.append(
            Row(
                coeffs={_var(dc.feature_b): 1.0, _var(dc.feature_a): -1.0},
                rhs_nm=float(dc.value_nm),
                weight=dc.weight,
                label=f"dim:{dc.id}({dc.text!r})",
            )
        )

    for ac in alignment_constraints:
        if ac.axis not in ("x", "y"):
            raise UnsupportedConstraintError(
                f"AlignmentConstraint {ac.id!r} (kind={ac.kind!r}) has axis={ac.axis!r}; "
                "only 'x'/'y' are handled by the Sprint 2 solver."
            )
        system = systems[ac.axis]
        if ac.kind == "collinear":
            base = _var(ac.members[0])
            for m in ac.members[1:]:
                system.rows.append(
                    Row(
                        coeffs={_var(m): 1.0, base: -1.0},
                        rhs_nm=0.0,
                        weight=1.0,
                        label=f"align:{ac.id}(collinear)",
                    )
                )
        elif ac.kind == "equal":
            if len(ac.members) != 3:
                raise UnsupportedConstraintError(
                    f"AlignmentConstraint {ac.id!r} (kind='equal') needs exactly 3 "
                    "members [a, b, c] meaning (b-a) == (c-b), got "
                    f"{len(ac.members)}"
                )
            a, b, c = (_var(m) for m in ac.members)
            # (b - a) == (c - b)  =>  -a + 2b - c = 0
            system.rows.append(
                Row(
                    coeffs={a: -1.0, b: 2.0, c: -1.0},
                    rhs_nm=0.0,
                    weight=1.0,
                    label=f"align:{ac.id}(equal)",
                )
            )
        else:
            raise UnsupportedConstraintError(
                f"AlignmentConstraint {ac.id!r} has kind={ac.kind!r}; only "
                "'collinear' and 'equal' are reduced to linear rows by the "
                "Sprint 2 solver — 'perpendicular' and 'vertical_align' relate "
                "two axes and are not yet implemented."
            )

    return systems
