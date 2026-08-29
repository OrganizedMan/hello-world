"""The pose backend interface (ADR 0002).

A pose backend turns a set of images into camera poses and a sparse point
cloud. It reports its own discovered capabilities, emits progress through an
injected sink, and can be cancelled without corrupting the project.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Protocol, Sequence

from ...config import PoseConfig
from ...events import EventSink
from ...models import ReconstructionReport


@dataclass
class PoseFrame:
    """One image offered to the pose solver."""

    id: str
    path: Path
    timestamp: float
    role: str  # train | eval


@dataclass
class PoseMask:
    """A mask that suppresses a region *for camera solving only*.

    Distinct from a training mask, which decides what the splat may fit.
    Masking a person here means "do not trust this region for pose"; masking a
    person in training means "remove this person from the memory".
    """

    frame_id: str
    path: Path


@dataclass
class PoseBackendHealth:
    name: str
    available: bool
    version: str | None = None
    executable: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PoseResult:
    """Outcome of a pose run, whether or not it passed the gate."""

    success: bool
    sparse_model_dir: Path | None
    database_path: Path | None
    report: ReconstructionReport
    commands: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    effective_image_size: dict[str, Any] = field(default_factory=dict)
    diagnostic: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "sparse_model_dir": str(self.sparse_model_dir)
            if self.sparse_model_dir
            else None,
            "database_path": str(self.database_path) if self.database_path else None,
            "report": self.report.to_dict(),
            "commands": self.commands,
            "config": self.config,
            "effective_image_size": self.effective_image_size,
            "diagnostic": self.diagnostic,
            "message": self.message,
        }


class PoseBackend(Protocol):
    def doctor(self) -> PoseBackendHealth: ...

    def reconstruct(
        self,
        frames: Sequence[PoseFrame],
        masks: Sequence[PoseMask] | None,
        config: PoseConfig,
        events: EventSink,
    ) -> PoseResult: ...

    def cancel(self) -> None: ...
