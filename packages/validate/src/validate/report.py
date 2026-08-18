"""The validation report (plan §12): a named, inspectable artifact that
runs before Build and blocks it outright if anything fails. Rendering a
model that failed validation is not a feature this pipeline has.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class CheckResult:
    check_id: str
    status: CheckStatus
    message: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationReport:
    checks: tuple[CheckResult, ...]

    @property
    def is_blocking(self) -> bool:
        return any(c.status == CheckStatus.BLOCK for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == CheckStatus.WARN for c in self.checks)

    def blocking_checks(self) -> tuple[CheckResult, ...]:
        return tuple(c for c in self.checks if c.status == CheckStatus.BLOCK)

    def summary(self) -> str:
        n_pass = sum(1 for c in self.checks if c.status == CheckStatus.PASS)
        n_warn = sum(1 for c in self.checks if c.status == CheckStatus.WARN)
        n_block = sum(1 for c in self.checks if c.status == CheckStatus.BLOCK)
        lines = [f"{n_pass} passed, {n_warn} warned, {n_block} blocked"]
        for c in self.checks:
            lines.append(f"  [{c.status.value.upper():5}] {c.check_id}: {c.message}")
            for d in c.details:
                lines.append(f"           - {d}")
        return "\n".join(lines)
