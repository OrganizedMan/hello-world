"""Stage state: atomic, resumable, and cancellation-safe.

Every pipeline stage commits its state atomically. A crash or cancellation
therefore leaves a stage either committed or not started — never half-done from
the orchestrator's point of view (ADR 0002, rule 4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ..events import STAGES
from ..models import AmberError, utcnow_iso
from .projects import atomic_write_text

PENDING = "pending"
RUNNING = "running"
COMPLETE = "complete"
FAILED = "failed"


@dataclass
class StageRecord:
    name: str
    status: str = PENDING
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    diagnostic: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageRecord":
        known = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{k: v for k, v in data.items() if k in known})


class StageState:
    """Persistent per-scene stage table."""

    def __init__(self, path: Path, stages: dict[str, StageRecord] | None = None):
        self.path = Path(path)
        self.stages: dict[str, StageRecord] = stages or {
            name: StageRecord(name=name) for name in STAGES
        }

    # -- persistence ------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "StageState":
        path = Path(path)
        if not path.is_file():
            return cls(path)
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        stages = {
            name: StageRecord(name=name) for name in STAGES
        }
        for name, record in data.get("stages", {}).items():
            if name in stages:
                stages[name] = StageRecord.from_dict(record)
        state = cls(path, stages)
        state._recover_interrupted()
        return state

    def _recover_interrupted(self) -> None:
        """A stage found RUNNING at load time did not finish.

        The process died or was cancelled. Reset it to pending so it re-runs;
        its previous committed outputs, if any, were already superseded.
        """
        for record in self.stages.values():
            if record.status == RUNNING:
                record.status = PENDING
                record.error = "interrupted before completion; will re-run"
                record.finished_at = None
        self.save()

    def save(self) -> None:
        payload = {
            "stages": {n: r.to_dict() for n, r in self.stages.items()},
            "updated_at": utcnow_iso(),
        }
        atomic_write_text(self.path, json.dumps(payload, indent=2) + "\n")

    # -- queries ----------------------------------------------------------

    def record(self, stage: str) -> StageRecord:
        if stage not in self.stages:
            raise AmberError(
                f"unknown stage {stage!r}; expected one of {list(STAGES)}"
            )
        return self.stages[stage]

    def is_complete(self, stage: str) -> bool:
        return self.record(stage).status == COMPLETE

    def next_stage(self) -> str | None:
        for name in STAGES:
            if self.stages[name].status != COMPLETE:
                return name
        return None

    def completed_stages(self) -> list[str]:
        return [n for n in STAGES if self.stages[n].status == COMPLETE]

    # -- transitions ------------------------------------------------------

    def begin(self, stage: str) -> StageRecord:
        record = self.record(stage)
        record.status = RUNNING
        record.started_at = utcnow_iso()
        record.finished_at = None
        record.error = None
        record.diagnostic = None
        record.attempts += 1
        self.save()
        return record

    def complete(self, stage: str, **outputs: Any) -> StageRecord:
        record = self.record(stage)
        record.status = COMPLETE
        record.finished_at = utcnow_iso()
        record.error = None
        record.outputs.update(outputs)
        self.save()
        return record

    def fail(
        self, stage: str, error: str, diagnostic: str | None = None
    ) -> StageRecord:
        record = self.record(stage)
        record.status = FAILED
        record.finished_at = utcnow_iso()
        record.error = error
        record.diagnostic = diagnostic
        self.save()
        return record

    def invalidate_from(self, stage: str) -> list[str]:
        """Reset `stage` and every stage downstream of it.

        Used by `amber retry --from <stage>`. Downstream results are derived
        from the retried stage, so leaving them complete would produce an
        archive whose parts disagree.
        """
        if stage not in STAGES:
            raise AmberError(
                f"unknown stage {stage!r}; expected one of {list(STAGES)}"
            )
        start = STAGES.index(stage)
        invalidated: list[str] = []
        for name in STAGES[start:]:
            record = self.stages[name]
            if record.status != PENDING or record.outputs:
                invalidated.append(name)
            record.status = PENDING
            record.error = None
            record.diagnostic = None
            record.finished_at = None
            record.outputs = {}
        self.save()
        return invalidated

    def to_dict(self) -> dict[str, Any]:
        return {n: r.to_dict() for n, r in self.stages.items()}
