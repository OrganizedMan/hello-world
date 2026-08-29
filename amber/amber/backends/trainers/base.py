"""The trainer backend interface (ADR 0002)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Protocol

from ...config import TrainConfig
from ...events import EventSink


@dataclass
class ColmapDataset:
    """Everything a Gaussian trainer needs, with the split made explicit.

    `training_frame_ids` and `evaluation_frame_ids` are passed to the backend
    rather than inferred, so a backend can never guess wrong about which images
    may supervise optimisation.

    The two image directories are separate tiers on disk, but both are rendered
    at the same resolution so a held-out render is comparable with its source.
    """

    image_dir: Path
    sparse_model_dir: Path
    training_frame_ids: list[str]
    evaluation_frame_ids: list[str]
    evaluation_image_dir: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_dir": str(self.image_dir),
            "evaluation_image_dir": str(self.evaluation_image_dir)
            if self.evaluation_image_dir
            else None,
            "sparse_model_dir": str(self.sparse_model_dir),
            "training_frame_count": len(self.training_frame_ids),
            "evaluation_frame_count": len(self.evaluation_frame_ids),
        }


@dataclass
class BackendHealth:
    name: str
    available: bool
    version: str | None = None
    executable: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrainResult:
    success: bool
    ply_path: Path | None
    checkpoint_dir: Path | None = None
    steps: int | None = None
    duration_seconds: float = 0.0
    peak_rss_bytes: int | None = None
    command: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    dataset_view_dir: Path | None = None
    evaluation_render_dir: Path | None = None
    evaluation_rendered_ids: list[str] = field(default_factory=list)
    diagnostic: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "ply_path": str(self.ply_path) if self.ply_path else None,
            "checkpoint_dir": str(self.checkpoint_dir)
            if self.checkpoint_dir
            else None,
            "steps": self.steps,
            "duration_seconds": self.duration_seconds,
            "peak_rss_bytes": self.peak_rss_bytes,
            "command": self.command,
            "config": self.config,
            "dataset_view_dir": str(self.dataset_view_dir)
            if self.dataset_view_dir
            else None,
            "evaluation_render_dir": str(self.evaluation_render_dir)
            if self.evaluation_render_dir
            else None,
            "evaluation_rendered_ids": self.evaluation_rendered_ids,
            "diagnostic": self.diagnostic,
            "message": self.message,
        }


class TrainerBackend(Protocol):
    def doctor(self) -> BackendHealth: ...

    def train(
        self, dataset: ColmapDataset, config: TrainConfig, events: EventSink
    ) -> TrainResult: ...

    def cancel(self) -> None: ...
