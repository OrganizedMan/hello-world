"""Storage accounting, preflight free-space checks, and safe pruning.

Bytes are measured, never guessed. Where a measurement does not exist yet, the
estimate is labelled `unmeasured` so no document can quote it as a promise
(AGENTS.md rules 19-20).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ..models import (
    ARCHIVAL_CORE,
    Manifest,
    PRESENT,
    PRUNED,
    PRUNABLE_CLASSES,
    RetentionError,
)
from .projects import SceneStore, tree_bytes

# Provisional multiplier used only until M0 measures real profiles. It is
# deliberately conservative and always reported with basis="unmeasured".
PROVISIONAL_SIZE_MULTIPLIER = 25.0


@dataclass
class StageStorage:
    stage: str
    input_bytes: int = 0
    output_bytes: int = 0
    peak_temp_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorageReport:
    """`qa/storage-report.json` — input, output, and peak temp per stage."""

    stages: list[StageStorage] = field(default_factory=list)
    retained_bytes: int = 0
    prunable_bytes: int = 0
    retention_profile: str = "complete"

    def record(
        self,
        stage: str,
        input_bytes: int = 0,
        output_bytes: int = 0,
        peak_temp_bytes: int = 0,
    ) -> StageStorage:
        entry = StageStorage(
            stage=stage,
            input_bytes=input_bytes,
            output_bytes=output_bytes,
            peak_temp_bytes=peak_temp_bytes,
        )
        self.stages = [s for s in self.stages if s.stage != stage] + [entry]
        return entry

    @property
    def peak_temp_bytes(self) -> int:
        return max((s.peak_temp_bytes for s in self.stages), default=0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": [s.to_dict() for s in self.stages],
            "retained_bytes": self.retained_bytes,
            "prunable_bytes": self.prunable_bytes,
            "peak_temp_bytes": self.peak_temp_bytes,
            "retention_profile": self.retention_profile,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StorageReport":
        report = cls(
            retained_bytes=int(data.get("retained_bytes", 0)),
            prunable_bytes=int(data.get("prunable_bytes", 0)),
            retention_profile=data.get("retention_profile", "complete"),
        )
        report.stages = [StageStorage(**s) for s in data.get("stages", [])]
        return report


@dataclass
class SpaceEstimate:
    source_bytes: int
    estimated_required_bytes: int
    free_bytes: int
    basis: str  # "measured:<profile>" or "unmeasured"

    @property
    def sufficient(self) -> bool:
        return self.free_bytes >= self.estimated_required_bytes

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sufficient"] = self.sufficient
        return data

    def message(self) -> str:
        need = self.estimated_required_bytes / 1e9
        have = self.free_bytes / 1e9
        qualifier = (
            "measured" if self.basis.startswith("measured") else "provisional"
        )
        return (
            f"needs about {need:.1f} GB ({qualifier} estimate), "
            f"{have:.1f} GB free"
        )


def free_bytes(path: Path) -> int:
    target = Path(path)
    while not target.exists() and target != target.parent:
        target = target.parent
    return shutil.disk_usage(target).free


def estimate_required_space(
    source_bytes: int,
    destination: Path,
    measured_multiplier: float | None = None,
    profile_name: str | None = None,
) -> SpaceEstimate:
    """Estimate peak disk needed for a full run.

    Uses a measured multiplier from a previous profile when one exists; until
    M0 supplies one, the provisional multiplier is used and clearly labelled.
    """
    if measured_multiplier is not None:
        multiplier = measured_multiplier
        basis = f"measured:{profile_name or 'unknown'}"
    else:
        multiplier = PROVISIONAL_SIZE_MULTIPLIER
        basis = "unmeasured"
    return SpaceEstimate(
        source_bytes=source_bytes,
        estimated_required_bytes=int(source_bytes * multiplier),
        free_bytes=free_bytes(destination),
        basis=basis,
    )


# --------------------------------------------------------------------------
# Pruning
# --------------------------------------------------------------------------


@dataclass
class PruneTarget:
    path: str
    role: str
    retention_class: str
    bytes: int
    regeneration_cost_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PrunePlan:
    targets: list[PruneTarget] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(t.bytes for t in self.targets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": [t.to_dict() for t in self.targets],
            "protected": self.protected,
            "total_bytes": self.total_bytes,
        }


def plan_prune(
    manifest: Manifest,
    classes: frozenset[str] = PRUNABLE_CLASSES,
) -> PrunePlan:
    """Compute exactly what a prune would remove. Never mutates anything."""
    if ARCHIVAL_CORE in classes:
        raise RetentionError(
            "refusing to plan a prune that includes the archival core; "
            "source, sparse model, master, delivery, and QA are never prunable"
        )
    plan = PrunePlan()
    for art in manifest.artifacts:
        if art.status != PRESENT:
            continue
        if art.retention_class in classes and art.prunable:
            plan.targets.append(
                PruneTarget(
                    path=art.path,
                    role=art.role,
                    retention_class=art.retention_class,
                    bytes=art.bytes,
                    regeneration_cost_seconds=art.regeneration_cost_seconds,
                )
            )
        else:
            plan.protected.append(art.path)
    return plan


def apply_prune(store: SceneStore, manifest: Manifest, plan: PrunePlan) -> int:
    """Execute a prune plan.

    Order matters for crash safety. The manifest is updated *first*, so an
    interruption can only leave "recorded as pruned but still on disk" — wasted
    space that `repair_interrupted_prune` finishes. The opposite order could
    leave the manifest claiming a file exists after it was deleted.
    """
    for target in plan.targets:
        manifest.mark_pruned(target.path, target.regeneration_cost_seconds)
    store.write_manifest(manifest)

    freed = 0
    for target in plan.targets:
        freed += _remove(store.abs(target.path))
    return freed


def repair_interrupted_prune(store: SceneStore, manifest: Manifest) -> int:
    """Finish deleting artifacts already recorded as pruned."""
    freed = 0
    for art in manifest.artifacts:
        if art.status == PRUNED:
            freed += _remove(store.abs(art.path))
    return freed


def _remove(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    size = tree_bytes(path)
    if path.is_dir():
        shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)  # keep the layout intact
    else:
        path.unlink()
    return size


def measure_scene(store: SceneStore, manifest: Manifest) -> StorageReport:
    """Refresh byte counts from what is actually on disk."""
    report = StorageReport()
    for art in manifest.artifacts:
        if art.status != PRESENT:
            continue
        art.bytes = tree_bytes(store.abs(art.path))
    report.retained_bytes = manifest.retained_bytes()
    report.prunable_bytes = manifest.prunable_bytes()
    return report
