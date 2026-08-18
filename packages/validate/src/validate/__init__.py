from .checks import (
    check_constraint_diagnoses,
    check_invention_audit,
    check_unknowns_inventory,
    check_wall_graph_connectivity,
    check_wall_topology_invariant,
)
from .report import CheckResult, CheckStatus, ValidationReport


def run_validation(walls, diagnoses=()) -> ValidationReport:
    """Assemble the full Sprint 2 validation report for one level's walls."""
    checks = (
        check_wall_topology_invariant(walls),
        check_wall_graph_connectivity(walls),
        check_unknowns_inventory(walls),
        check_invention_audit(walls),
        *check_constraint_diagnoses(list(diagnoses)),
    )
    return ValidationReport(checks)


__all__ = [
    "CheckResult", "CheckStatus", "ValidationReport", "run_validation",
    "check_wall_topology_invariant", "check_wall_graph_connectivity",
    "check_unknowns_inventory", "check_invention_audit", "check_constraint_diagnoses",
]
