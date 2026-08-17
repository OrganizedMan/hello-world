"""Frame extraction, scoring, and the train/evaluation split.

Two rules govern this module:

1. Pose images and training images are independent tiers. Pose estimation is
   never limited by the trainer's memory budget (AGENTS.md rule 9).
2. Evaluation frames may take part in pose estimation but never in Gaussian
   supervision, and once locked they cannot move (rules 10-11).
"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from ..config import CandidateConfig, SplitConfig
from ..events import EventSink, emit
from ..models import (
    AmberError,
    EVAL,
    FIXED_CANDIDATE_STRATIFIED,
    FrameRecord,
    REGISTERED_INTERVAL,
    Split,
    TRAIN,
    UNUSED,
)
from ..services.projects import sha256_of_strings
from ..tools import ProcessRunner

# Below this many registered frames, every-Nth sampling yields too few
# evaluation views to be meaningful, so a stratified holdout is used instead.
MIN_REGISTERED_FOR_INTERVAL = 64
MIN_HOLDOUT_VIEWS = 4

# Long edge used for cheap scoring. Scoring compares frames to each other, so
# it only needs to be consistent, not full resolution.
SCORING_LONG_EDGE = 512


# --------------------------------------------------------------------------
# Deterministic selection
# --------------------------------------------------------------------------


def order_frames(frames: Sequence[FrameRecord]) -> list[FrameRecord]:
    """Canonical order: presentation time, then id. Ties break deterministically."""
    return sorted(frames, key=lambda f: (f.timestamp, f.id))


def stratified_pick(
    frames: Sequence[FrameRecord], count: int
) -> list[FrameRecord]:
    """Pick `count` frames spread evenly over time.

    The pool is divided into `count` contiguous strata of equal size and the
    frame nearest each stratum's midpoint is taken, ties resolved to the lower
    index (earlier frame). Deterministic and seed-free by construction, which
    is why the frozen split can be reproduced exactly.
    """
    ordered = order_frames(frames)
    n = len(ordered)
    if count <= 0 or n == 0:
        return []
    if count >= n:
        return ordered

    picked: list[FrameRecord] = []
    for k in range(count):
        lo = (k * n) // count
        hi = ((k + 1) * n) // count
        if hi <= lo:
            hi = lo + 1
        stratum = ordered[lo:hi]
        midpoint = (len(stratum) - 1) // 2
        picked.append(stratum[midpoint])
    return picked


def candidate_pool_hash(frames: Sequence[FrameRecord]) -> str:
    """Hash pinning the exact eligible pool a comparison group was built on."""
    return sha256_of_strings(f.id for f in order_frames(frames))


# --------------------------------------------------------------------------
# Scoring and eligibility
# --------------------------------------------------------------------------


@dataclass
class FrameScores:
    sharpness: float
    clipped_highlight_fraction: float
    clipped_shadow_fraction: float


def score_image(path: Path) -> FrameScores:
    """Measure blur and clipping for one frame.

    Sharpness is the variance of the Laplacian: low variance means little
    high-frequency detail, which for video frames means motion blur or
    defocus.
    """
    import numpy as np
    from PIL import Image

    with Image.open(path) as img:
        img = img.convert("L")
        long_edge = max(img.size)
        if long_edge > SCORING_LONG_EDGE:
            scale = SCORING_LONG_EDGE / long_edge
            new_size = (
                max(1, int(img.width * scale)),
                max(1, int(img.height * scale)),
            )
            img = img.resize(new_size, Image.BILINEAR)
        gray = np.asarray(img, dtype=np.float64) / 255.0

    if gray.size == 0 or min(gray.shape) < 3:
        return FrameScores(0.0, 0.0, 0.0)

    centre = gray[1:-1, 1:-1]
    laplacian = (
        4.0 * centre
        - gray[:-2, 1:-1]
        - gray[2:, 1:-1]
        - gray[1:-1, :-2]
        - gray[1:-1, 2:]
    )
    return FrameScores(
        sharpness=float(laplacian.var()),
        clipped_highlight_fraction=float((gray >= 250 / 255).mean()),
        clipped_shadow_fraction=float((gray <= 5 / 255).mean()),
    )


def apply_eligibility(
    frames: Sequence[FrameRecord], config: CandidateConfig
) -> list[FrameRecord]:
    """Mark frames eligible or not, using per-frame statistics only.

    Eligibility must not depend on any configuration choice, otherwise a
    comparison group's candidate pool would differ between configurations and
    the frozen split would stop being comparable.
    """
    scored = [f for f in frames if f.sharpness is not None]
    if not scored:
        return list(frames)

    sharpness_values = sorted(f.sharpness for f in scored)  # type: ignore[misc]
    median = sharpness_values[len(sharpness_values) // 2]
    floor = median * config.min_sharpness_ratio_of_median

    for frame in frames:
        reasons: list[str] = []
        if frame.sharpness is not None and frame.sharpness < floor:
            reasons.append("motion_blur")
        if (
            frame.clipped_highlight_fraction is not None
            and frame.clipped_highlight_fraction > config.max_clipped_highlight_fraction
        ):
            reasons.append("clipped_highlights")
        if (
            frame.clipped_shadow_fraction is not None
            and frame.clipped_shadow_fraction > config.max_clipped_shadow_fraction
        ):
            reasons.append("clipped_shadows")
        frame.eligible = not reasons
        frame.ineligible_reason = ",".join(reasons) if reasons else None
    return list(frames)


def eligible_frames(frames: Sequence[FrameRecord]) -> list[FrameRecord]:
    return [f for f in frames if f.eligible]


# --------------------------------------------------------------------------
# Splits
# --------------------------------------------------------------------------


def reserve_fixed_evaluation(
    candidates: Sequence[FrameRecord],
    config: SplitConfig,
) -> Split:
    """Reserve the comparison group's evaluation set (plan §8.2).

    Called after scoring and eligibility but *before* any training selection or
    pose configuration, so no configuration can influence which frames test it.
    """
    if config.policy != FIXED_CANDIDATE_STRATIFIED:
        raise AmberError(
            "reserve_fixed_evaluation requires the "
            f"{FIXED_CANDIDATE_STRATIFIED!r} policy"
        )
    if not config.comparison_group_id:
        raise AmberError(
            "a comparative split requires a comparison_group_id so its frozen "
            "identity can be recorded"
        )
    pool = eligible_frames(candidates)
    n_eval = config.n_eval or 0
    if n_eval <= 0:
        raise AmberError("comparative split requires n_eval > 0")
    if len(pool) <= n_eval:
        raise AmberError(
            f"only {len(pool)} eligible candidates for {n_eval} evaluation "
            "frames; nothing would remain to train on"
        )

    reserved = stratified_pick(pool, n_eval)
    return Split(
        policy=FIXED_CANDIDATE_STRATIFIED,
        algorithm_version=config.algorithm_version,
        seed=config.seed,
        evaluation_interval=None,
        n_eval=n_eval,
        training_frame_ids=[],
        evaluation_frame_ids=[f.id for f in reserved],
        candidate_pool_sha256=candidate_pool_hash(pool),
        comparison_group_id=config.comparison_group_id,
    )


def select_training_frames(
    candidates: Sequence[FrameRecord],
    split: Split,
    count: int,
) -> list[FrameRecord]:
    """Choose training views, excluding the reserved evaluation frames."""
    reserved = set(split.evaluation_frame_ids)
    pool = [f for f in eligible_frames(candidates) if f.id not in reserved]
    if not pool:
        raise AmberError("no eligible candidate frames remain for training")
    return stratified_pick(pool, count)


def registered_interval_split(
    registered: Sequence[FrameRecord],
    config: SplitConfig,
) -> Split:
    """Production split: hold out views *after* registration succeeds.

    Every registered frame contributed to the camera solve; a temporal subset
    is then withheld from Gaussian supervision so the metrics test novel views
    rather than memorised ones.
    """
    ordered = order_frames(registered)
    if not ordered:
        raise AmberError("cannot split an empty set of registered frames")

    interval = config.evaluation_interval or 8
    if len(ordered) >= MIN_REGISTERED_FOR_INTERVAL:
        evaluation = ordered[interval - 1 :: interval]
    else:
        holdout = max(
            MIN_HOLDOUT_VIEWS,
            int(math.ceil(len(ordered) * config.small_capture_holdout_fraction)),
        )
        holdout = min(holdout, max(1, len(ordered) - 1))
        evaluation = stratified_pick(ordered, holdout)

    evaluation_ids = {f.id for f in evaluation}
    training = [f for f in ordered if f.id not in evaluation_ids]
    if not training:
        raise AmberError(
            "the holdout consumed every registered frame; the capture is too "
            "small to evaluate honestly"
        )

    return Split(
        policy=REGISTERED_INTERVAL,
        algorithm_version=config.algorithm_version,
        seed=None,
        evaluation_interval=interval,
        training_frame_ids=[f.id for f in training],
        evaluation_frame_ids=[f.id for f in order_frames(evaluation)],
        candidate_pool_sha256=candidate_pool_hash(ordered),
        comparison_group_id=None,
    )


def apply_roles(frames: Sequence[FrameRecord], split: Split) -> None:
    """Stamp each frame with its role so `frame-report.json` is self-describing."""
    training = set(split.training_frame_ids)
    evaluation = set(split.evaluation_frame_ids)
    for frame in frames:
        if frame.id in evaluation:
            frame.role = EVAL
        elif frame.id in training:
            frame.role = TRAIN
        else:
            frame.role = UNUSED


def pose_input_ids(split: Split) -> list[str]:
    """Frames fed to the pose solver: training *and* evaluation.

    Evaluation frames must be registered so their cameras exist to render from;
    that is exactly why they take part here and nowhere in training.
    """
    seen: dict[str, None] = {}
    for frame_id in list(split.training_frame_ids) + list(
        split.evaluation_frame_ids
    ):
        seen.setdefault(frame_id, None)
    return list(seen)


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------


def extract_candidates(
    video: Path,
    out_dir: Path,
    config: CandidateConfig,
    runner: ProcessRunner,
    events: EventSink,
    ffmpeg: str = "ffmpeg",
) -> list[FrameRecord]:
    """Decode candidate frames at the predeclared rate.

    Writes PNG (lossless) so that frame selection is not judging JPEG artifacts,
    and so the pose tier is not degraded before COLMAP sees it.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    emit(
        events,
        "frames",
        "info",
        f"decoding candidates at {config.decode_fps} fps",
        fps=config.decode_fps,
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vf",
        f"fps={config.decode_fps}",
        "-vsync",
        "0",
        "-pix_fmt",
        "rgb24",
        str(out_dir / "cand_%06d.png"),
    ]
    runner.run(command)

    frames: list[FrameRecord] = []
    for index, path in enumerate(sorted(out_dir.glob("cand_*.png"))):
        frames.append(
            FrameRecord(
                id=path.stem,
                index=index,
                timestamp=index / config.decode_fps,
                path=str(path.name),
            )
        )
    if not frames:
        raise AmberError(
            "no frames were decoded from the video; it may be truncated or use "
            "an unsupported codec"
        )
    emit(events, "frames", "info", f"decoded {len(frames)} candidate frames")
    return frames


def score_frames(
    frames: Sequence[FrameRecord],
    directory: Path,
    events: EventSink,
) -> list[FrameRecord]:
    for frame in frames:
        if not frame.path:
            continue
        scores = score_image(Path(directory) / frame.path)
        frame.sharpness = scores.sharpness
        frame.clipped_highlight_fraction = scores.clipped_highlight_fraction
        frame.clipped_shadow_fraction = scores.clipped_shadow_fraction
    emit(events, "frames", "info", f"scored {len(frames)} candidate frames")
    return list(frames)


def write_tier(
    frames: Sequence[FrameRecord],
    source_dir: Path,
    dest_dir: Path,
    long_edge: int | None,
) -> list[Path]:
    """Materialise one image tier.

    `long_edge=None` keeps source resolution, which is what the pose tier
    wants: pose estimation must not inherit the trainer's memory budget
    (AGENTS.md rule 9).
    """
    from PIL import Image

    source_dir, dest_dir = Path(source_dir), Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for frame in frames:
        if not frame.path:
            continue
        src = source_dir / frame.path
        dst = dest_dir / f"{frame.id}.png"
        if long_edge is None:
            shutil.copy2(src, dst)
        else:
            with Image.open(src) as img:
                current = max(img.size)
                if current > long_edge:
                    scale = long_edge / current
                    img = img.resize(
                        (
                            max(1, round(img.width * scale)),
                            max(1, round(img.height * scale)),
                        ),
                        Image.LANCZOS,
                    )
                img.save(dst)
        written.append(dst)
    return written


def frame_report(
    frames: Sequence[FrameRecord], split: Split, config: dict[str, Any]
) -> dict[str, Any]:
    ordered = order_frames(frames)
    eligible = [f for f in ordered if f.eligible]
    return {
        "candidate_count": len(ordered),
        "eligible_count": len(eligible),
        "ineligible_reasons": _reason_counts(ordered),
        "split": split.to_dict(),
        "config": config,
        "frames": [f.to_dict() for f in ordered],
    }


def _reason_counts(frames: Sequence[FrameRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for frame in frames:
        if frame.eligible or not frame.ineligible_reason:
            continue
        for reason in frame.ineligible_reason.split(","):
            counts[reason] = counts.get(reason, 0) + 1
    return counts
