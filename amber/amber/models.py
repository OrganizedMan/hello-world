"""Core data model: manifest, artifacts, frames, splits, and reports.

The manifest is the source of truth for a scene. There is no database; a scene
archive must survive without the application (ADR 0003).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from . import SCHEMA_VERSION

# --------------------------------------------------------------------------
# Retention (ADR 0003)
# --------------------------------------------------------------------------

ARCHIVAL_CORE = "archival_core"
REGENERABLE = "regenerable"
DERIVED_CACHE = "derived_cache"

RETENTION_CLASSES = frozenset({ARCHIVAL_CORE, REGENERABLE, DERIVED_CACHE})
PRUNABLE_CLASSES = frozenset({REGENERABLE, DERIVED_CACHE})

PRESENT = "present"
PRUNED = "pruned"

# --------------------------------------------------------------------------
# Split policies (plan §8.2)
# --------------------------------------------------------------------------

REGISTERED_INTERVAL = "registered_interval"
FIXED_CANDIDATE_STRATIFIED = "fixed_candidate_stratified"
SPLIT_POLICIES = frozenset({REGISTERED_INTERVAL, FIXED_CANDIDATE_STRATIFIED})

TRAIN = "train"
EVAL = "eval"
UNUSED = "unused"


class AmberError(Exception):
    """Base class for errors that carry user-actionable meaning."""


class SplitLockedError(AmberError):
    """Raised when code attempts to change a locked evaluation split.

    Rule 11 in AGENTS.md: a deliberate new split creates a new run/version and
    invalidates rather than overwrites prior metrics.
    """


class RetentionError(AmberError):
    """Raised when an operation would damage the archival core."""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------


@dataclass
class Artifact:
    """One file (or directory) recorded in the manifest.

    A pruned artifact keeps its entry: the entry *is* the recipe for
    regenerating it, so erasing it would destroy provenance.
    """

    path: str
    role: str
    retention_class: str
    bytes: int = 0
    sha256: str | None = None
    status: str = PRESENT
    prior_bytes: int | None = None
    regeneration_cost_seconds: float | None = None
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.retention_class not in RETENTION_CLASSES:
            raise RetentionError(
                f"artifact {self.path!r} has unknown retention class "
                f"{self.retention_class!r}; expected one of "
                f"{sorted(RETENTION_CLASSES)}"
            )
        if self.status not in (PRESENT, PRUNED):
            raise RetentionError(
                f"artifact {self.path!r} has unknown status {self.status!r}"
            )

    @property
    def prunable(self) -> bool:
        return self.retention_class in PRUNABLE_CLASSES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        return cls(**data)


# --------------------------------------------------------------------------
# Frames and splits
# --------------------------------------------------------------------------


@dataclass
class FrameRecord:
    """A candidate frame and everything measured about it."""

    id: str
    index: int
    timestamp: float  # presentation timestamp, seconds
    path: str | None = None
    sha256: str | None = None
    sharpness: float | None = None
    clipped_highlight_fraction: float | None = None
    clipped_shadow_fraction: float | None = None
    eligible: bool = True
    ineligible_reason: str | None = None
    role: str = UNUSED
    registered: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FrameRecord":
        return cls(**data)


@dataclass
class Split:
    """The train/evaluation assignment for a scene.

    Once `locked` is true the assignment is immutable for this scene version.
    """

    policy: str = REGISTERED_INTERVAL
    algorithm_version: int = 1
    seed: int | None = None
    evaluation_interval: int | None = 8
    n_eval: int | None = None
    training_frame_ids: list[str] = field(default_factory=list)
    evaluation_frame_ids: list[str] = field(default_factory=list)
    candidate_pool_sha256: str | None = None
    comparison_group_id: str | None = None
    locked: bool = False
    locked_at: str | None = None

    def __post_init__(self) -> None:
        if self.policy not in SPLIT_POLICIES:
            raise AmberError(
                f"unknown split policy {self.policy!r}; expected one of "
                f"{sorted(SPLIT_POLICIES)}"
            )

    def validate_disjoint(self) -> None:
        overlap = set(self.training_frame_ids) & set(self.evaluation_frame_ids)
        if overlap:
            raise AmberError(
                "evaluation frames must never supervise training; "
                f"{len(overlap)} frame(s) appear in both roles: "
                f"{sorted(overlap)[:5]}"
            )

    def lock(self) -> None:
        self.validate_disjoint()
        self.locked = True
        self.locked_at = utcnow_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Split":
        return cls(**data)


# --------------------------------------------------------------------------
# Pose gate
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GateCondition:
    name: str
    passed: bool
    value: float | None
    threshold: float | None
    comparison: str  # ">=" or "<="
    diagnostic: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PoseGateResult:
    """Result of the conjunctive pose gate (plan §8.3).

    Conjunctive means every condition must pass. There is no weighted score
    and no partial pass.
    """

    conditions: list[GateCondition] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.conditions) and all(c.passed for c in self.conditions)

    @property
    def failures(self) -> list[GateCondition]:
        return [c for c in self.conditions if not c.passed]

    @property
    def diagnostics(self) -> list[str]:
        return [c.diagnostic for c in self.failures if c.diagnostic]

    def primary_diagnostic(self) -> str | None:
        """The single most explanatory failure for a user-facing message.

        A capture that fails only the parallax/translation checks is a pure-pan
        capture, which is the most actionable thing we can tell someone.
        """
        diags = self.diagnostics
        if not diags:
            return None
        for preferred in ("insufficient_translation", "insufficient_parallax"):
            if preferred in diags:
                return preferred
        return diags[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "diagnostics": self.diagnostics,
            "primary_diagnostic": self.primary_diagnostic(),
            "conditions": [c.to_dict() for c in self.conditions],
        }


@dataclass
class ReconstructionReport:
    """Everything §8.3 requires a pose run to report."""

    selected_training_frames: int = 0
    reserved_evaluation_frames: int = 0
    total_pose_input_frames: int = 0
    registered_frames: int = 0
    registered_frame_ids: list[str] = field(default_factory=list)
    registered_evaluation_frame_ids: list[str] = field(default_factory=list)
    sparse_point_count: int = 0
    median_observations_per_point: float = 0.0
    mean_reprojection_error_px: float = 0.0
    camera_path_extent: float = 0.0
    median_scene_depth: float = 0.0
    median_triangulation_angle_deg: float = 0.0
    connected_model_count: int = 0
    largest_model_frame_fraction: float = 0.0
    longest_temporal_gap_seconds: float = 0.0
    longest_consecutive_missing_selected: int = 0
    camera_path_review: str = "not_reviewed"  # pass | fail | not_reviewed
    timings_seconds: dict[str, float] = field(default_factory=dict)
    effective_image_size: dict[str, Any] = field(default_factory=dict)

    @property
    def registration_ratio(self) -> float:
        if self.total_pose_input_frames == 0:
            return 0.0
        return self.registered_frames / self.total_pose_input_frames

    @property
    def translation_to_depth_ratio(self) -> float:
        if self.median_scene_depth <= 0:
            return 0.0
        return self.camera_path_extent / self.median_scene_depth

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["registration_ratio"] = self.registration_ratio
        data["translation_to_depth_ratio"] = self.translation_to_depth_ratio
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReconstructionReport":
        known = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{k: v for k, v in data.items() if k in known})


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


@dataclass
class FrameConfig:
    pose_long_edge: int | None = None
    training_long_edge: int = 1600
    decode_fps: float = 4.0
    split_policy: str = REGISTERED_INTERVAL
    split_algorithm_version: int = 1
    split_locked: bool = False
    comparison_group_id: str | None = None
    candidate_pool_sha256: str | None = None
    split_seed: int | None = None
    evaluation_interval: int | None = 8
    training_frame_ids: list[str] = field(default_factory=list)
    evaluation_frame_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FrameConfig":
        known = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{k: v for k, v in data.items() if k in known})

    def apply_split(self, split: Split) -> None:
        self.split_policy = split.policy
        self.split_algorithm_version = split.algorithm_version
        self.split_locked = split.locked
        self.comparison_group_id = split.comparison_group_id
        self.candidate_pool_sha256 = split.candidate_pool_sha256
        self.split_seed = split.seed
        self.evaluation_interval = split.evaluation_interval
        self.training_frame_ids = list(split.training_frame_ids)
        self.evaluation_frame_ids = list(split.evaluation_frame_ids)

    def as_split(self) -> Split:
        return Split(
            policy=self.split_policy,
            algorithm_version=self.split_algorithm_version,
            seed=self.split_seed,
            evaluation_interval=self.evaluation_interval,
            training_frame_ids=list(self.training_frame_ids),
            evaluation_frame_ids=list(self.evaluation_frame_ids),
            candidate_pool_sha256=self.candidate_pool_sha256,
            comparison_group_id=self.comparison_group_id,
            locked=self.split_locked,
        )


@dataclass
class Manifest:
    scene_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    captured_at: str | None = None
    created_at: str = field(default_factory=utcnow_iso)
    location: Any = None
    notes: str = ""
    schema_version: int = SCHEMA_VERSION
    source: dict[str, Any] = field(default_factory=dict)
    pipeline: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    scale: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "unknown",
            "meters_per_unit": None,
            "method": None,
        }
    )
    cover_camera: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)

    # -- frame config -----------------------------------------------------

    @property
    def frame_config(self) -> FrameConfig:
        return FrameConfig.from_dict(self.pipeline.get("frame_config", {}))

    def set_frame_config(self, cfg: FrameConfig) -> None:
        self.pipeline.setdefault("frame_config", {})
        self.pipeline["frame_config"] = cfg.to_dict()

    # -- split ------------------------------------------------------------

    def set_split(self, split: Split) -> None:
        """Install a split, refusing to modify a locked one.

        The lock is what makes an evaluation metric trustworthy: if the split
        could move after training, a metric would describe an unknown
        experiment.
        """
        current = self.frame_config
        if current.split_locked:
            same = (
                list(current.training_frame_ids) == list(split.training_frame_ids)
                and list(current.evaluation_frame_ids)
                == list(split.evaluation_frame_ids)
                and current.split_policy == split.policy
            )
            if not same:
                raise SplitLockedError(
                    "this scene's evaluation split is locked; a different split "
                    "requires a new scene version, which invalidates rather "
                    "than overwrites the existing metrics"
                )
        split.validate_disjoint()
        cfg = current
        cfg.apply_split(split)
        self.set_frame_config(cfg)

    def lock_split(self) -> None:
        cfg = self.frame_config
        split = cfg.as_split()
        split.lock()
        cfg.apply_split(split)
        self.set_frame_config(cfg)

    @property
    def split_locked(self) -> bool:
        return bool(self.frame_config.split_locked)

    # -- artifacts --------------------------------------------------------

    def artifact(self, path: str) -> Artifact | None:
        for art in self.artifacts:
            if art.path == path:
                return art
        return None

    def add_artifact(self, artifact: Artifact) -> Artifact:
        existing = self.artifact(artifact.path)
        if existing is not None:
            self.artifacts[self.artifacts.index(existing)] = artifact
        else:
            self.artifacts.append(artifact)
        return artifact

    def mark_pruned(
        self, path: str, regeneration_cost_seconds: float | None = None
    ) -> Artifact:
        art = self.artifact(path)
        if art is None:
            raise RetentionError(f"cannot prune unknown artifact {path!r}")
        if not art.prunable:
            raise RetentionError(
                f"refusing to prune {path!r}: retention class "
                f"{art.retention_class!r} is part of the archival core"
            )
        art.prior_bytes = art.bytes if art.bytes else art.prior_bytes
        art.bytes = 0
        art.status = PRUNED
        if regeneration_cost_seconds is not None:
            art.regeneration_cost_seconds = regeneration_cost_seconds
        return art

    def retained_bytes(self) -> int:
        return sum(a.bytes for a in self.artifacts if a.status == PRESENT)

    def prunable_bytes(self) -> int:
        return sum(
            a.bytes for a in self.artifacts if a.status == PRESENT and a.prunable
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "title": self.title,
            "captured_at": self.captured_at,
            "created_at": self.created_at,
            "location": self.location,
            "notes": self.notes,
            "source": self.source,
            "pipeline": self.pipeline,
            "quality": self.quality,
            "scale": self.scale,
            "cover_camera": self.cover_camera,
            "artifacts": [a.to_dict() for a in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        data = dict(data)
        artifacts = [Artifact.from_dict(a) for a in data.pop("artifacts", [])]
        known = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        kwargs = {k: v for k, v in data.items() if k in known and k != "artifacts"}
        manifest = cls(**kwargs)
        manifest.artifacts = artifacts
        return manifest
