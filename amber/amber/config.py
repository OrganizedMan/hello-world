"""Configuration and predeclared thresholds.

Gate thresholds are *predeclared* in `docs/m0-experiment-plan.md` and mirrored
in `docs/m0-thresholds.json`. They are loaded from that file rather than
hard-coded here, so the plan and the code cannot drift, and so no threshold can
be quietly recomputed from the output of the run it judges (AGENTS.md rule 8).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import AmberError, REGISTERED_INTERVAL

REPO_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_FILENAME = "m0-thresholds.json"


def thresholds_path() -> Path:
    override = os.environ.get("AMBER_THRESHOLDS")
    if override:
        return Path(override)
    return REPO_ROOT / "docs" / THRESHOLDS_FILENAME


@lru_cache(maxsize=4)
def _load_thresholds(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        raise AmberError(
            f"predeclared thresholds not found at {path}. The pose gate refuses "
            "to run without them; recomputing a threshold from a run's own "
            "output would defeat the gate."
        )
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_thresholds() -> dict[str, Any]:
    return _load_thresholds(str(thresholds_path()))


@dataclass(frozen=True)
class PoseGateThresholds:
    """The conjunctive gate from plan §8.3 / experiment plan §7."""

    min_registration_ratio: float
    min_registered_frames: int
    min_dominant_model_fraction: float
    max_temporal_gap_seconds: float
    max_consecutive_missing_selected_frames: int
    min_median_triangulation_angle_deg: float
    min_translation_to_depth_ratio: float
    max_mean_reprojection_error_px: float
    requires_camera_path_review: bool = True
    capture_class: str = "room"

    @classmethod
    def for_capture_class(cls, capture_class: str) -> "PoseGateThresholds":
        data = load_thresholds()
        gate = data["pose_gate"]
        floors = data["min_registered_frames"]
        if capture_class not in floors:
            raise AmberError(
                f"unknown capture class {capture_class!r}; the experiment plan "
                f"declares floors for {sorted(floors)}. Add a class to the plan "
                "(with a rationale) before using it."
            )
        return cls(
            min_registration_ratio=float(gate["min_registration_ratio"]),
            min_registered_frames=int(floors[capture_class]),
            min_dominant_model_fraction=float(gate["min_dominant_model_fraction"]),
            max_temporal_gap_seconds=float(gate["max_temporal_gap_seconds"]),
            max_consecutive_missing_selected_frames=int(
                gate["max_consecutive_missing_selected_frames"]
            ),
            min_median_triangulation_angle_deg=float(
                gate["min_median_triangulation_angle_deg"]
            ),
            min_translation_to_depth_ratio=float(
                gate["min_translation_to_depth_ratio"]
            ),
            max_mean_reprojection_error_px=float(
                gate["max_mean_reprojection_error_px"]
            ),
            requires_camera_path_review=bool(gate["requires_camera_path_review"]),
            capture_class=capture_class,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateConfig:
    """Frame decoding and eligibility (experiment plan §4)."""

    decode_fps: float
    min_sharpness_ratio_of_median: float
    max_clipped_highlight_fraction: float
    max_clipped_shadow_fraction: float

    @classmethod
    def from_plan(cls) -> "CandidateConfig":
        c = load_thresholds()["candidate_extraction"]
        return cls(
            decode_fps=float(c["decode_fps"]),
            min_sharpness_ratio_of_median=float(c["min_sharpness_ratio_of_median"]),
            max_clipped_highlight_fraction=float(
                c["max_clipped_highlight_fraction"]
            ),
            max_clipped_shadow_fraction=float(c["max_clipped_shadow_fraction"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SplitConfig:
    policy: str = REGISTERED_INTERVAL
    algorithm_version: int = 1
    seed: int | None = None
    n_eval: int | None = None
    evaluation_interval: int | None = 8
    small_capture_holdout_fraction: float = 0.125
    min_common_evaluation_views: int = 12
    comparison_group_id: str | None = None

    @classmethod
    def production(cls) -> "SplitConfig":
        data = load_thresholds()
        prod = data["production_split"]
        comp = data["comparative_split"]
        return cls(
            policy=prod["policy"],
            evaluation_interval=int(prod["evaluation_interval"]),
            small_capture_holdout_fraction=float(
                prod["small_capture_holdout_fraction"]
            ),
            min_common_evaluation_views=int(comp["min_common_evaluation_views"]),
        )

    @classmethod
    def comparative(cls, comparison_group_id: str) -> "SplitConfig":
        c = load_thresholds()["comparative_split"]
        return cls(
            policy=c["policy"],
            algorithm_version=int(c["split_algorithm_version"]),
            seed=int(c["split_seed"]),
            n_eval=int(c["n_eval"]),
            evaluation_interval=None,
            min_common_evaluation_views=int(c["min_common_evaluation_views"]),
            comparison_group_id=comparison_group_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PoseConfig:
    """Pose backend configuration.

    Each axis is recorded separately so that a mapper comparison cannot
    masquerade as a different pipeline (ADR 0001).
    """

    feature_type: str = "sift"
    matcher_type: str = "sequential"
    mapper_type: str = "incremental"  # incremental | global
    camera_model: str = "OPENCV"
    single_camera: bool = True
    max_image_size: int = 3200
    loop_detection: bool = True
    use_pose_masks: bool = False
    vocab_tree_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrainConfig:
    """Trainer backend configuration."""

    max_resolution: int = 1600
    max_splats: int = 2_000_000
    total_steps: int = 30_000
    sh_degree: int = 3
    extra_args: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["extra_args"] = list(self.extra_args)
        return data


@dataclass(frozen=True)
class DeliveryProfile:
    """A packaging profile. SH degree and splat count are separate controls."""

    name: str
    sh_degree: int
    max_splats: int | None = None
    format: str = "sog"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DELIVERY_PROFILES: dict[str, DeliveryProfile] = {
    "mobile-sh0": DeliveryProfile(name="mobile-sh0", sh_degree=0),
    "mobile-sh2": DeliveryProfile(name="mobile-sh2", sh_degree=2),
    "desktop-sh3": DeliveryProfile(name="desktop-sh3", sh_degree=3),
}


@dataclass(frozen=True)
class Profile:
    """A named end-to-end recipe.

    `beautiful` is the only profile the product needs; `draft` exists for
    development and is never presented as a quality result.
    """

    name: str
    capture_class: str = "room"
    training_long_edge: int = 1600
    pose_long_edge: int | None = None  # None = source resolution
    target_training_frames: int = 120
    pose: PoseConfig = field(default_factory=PoseConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    delivery_profiles: tuple[str, ...] = ("mobile-sh0", "mobile-sh2")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pose"] = self.pose.to_dict()
        data["train"] = self.train.to_dict()
        data["delivery_profiles"] = list(self.delivery_profiles)
        return data


PROFILES: dict[str, Profile] = {
    "beautiful": Profile(
        name="beautiful",
        training_long_edge=1600,
        pose_long_edge=None,
        target_training_frames=120,
        pose=PoseConfig(max_image_size=3840),
        train=TrainConfig(max_resolution=1600, total_steps=30_000, sh_degree=3),
    ),
    "draft": Profile(
        name="draft",
        training_long_edge=1024,
        pose_long_edge=1600,
        target_training_frames=60,
        pose=PoseConfig(max_image_size=1600),
        train=TrainConfig(max_resolution=1024, total_steps=7_000, sh_degree=1),
    ),
}


def get_profile(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError:
        raise AmberError(
            f"unknown profile {name!r}; available: {sorted(PROFILES)}"
        ) from None


def default_library_root() -> Path:
    override = os.environ.get("AMBER_LIBRARY")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Pictures" / "Amber Memories"
