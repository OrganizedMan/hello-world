"""Held-out evaluation metrics and comparison-group arithmetic.

Metrics support a judgement; they do not replace one. The plan is explicit that
no single metric is a proxy for beauty, so the human rubric and the
motion-artifact review are recorded alongside these numbers, never instead of
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..models import AmberError

# SSIM constants for 8-bit dynamic range (Wang et al. 2004).
SSIM_C1 = (0.01 * 1.0) ** 2
SSIM_C2 = (0.03 * 1.0) ** 2
SSIM_WINDOW = 11
SSIM_SIGMA = 1.5


def _load_gray(path: Path):
    import numpy as np
    from PIL import Image

    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.float64) / 255.0


def _load_rgb(path: Path):
    import numpy as np
    from PIL import Image

    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"), dtype=np.float64) / 255.0


def psnr(a, b) -> float:
    """Peak signal-to-noise ratio for images in [0, 1]."""
    import numpy as np

    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise AmberError(
            f"cannot compare images of different shapes: {a.shape} vs {b.shape}"
        )
    mse = float(((a - b) ** 2).mean())
    if mse <= 0:
        return float("inf")
    return float(10.0 * np.log10(1.0 / mse))


def _gaussian_kernel(size: int = SSIM_WINDOW, sigma: float = SSIM_SIGMA):
    import numpy as np

    coords = np.arange(size, dtype=np.float64) - (size - 1) / 2.0
    kernel = np.exp(-(coords**2) / (2 * sigma**2))
    return kernel / kernel.sum()


def _filter_separable(image, kernel):
    """Valid-mode separable convolution, implemented without SciPy."""
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view

    size = kernel.shape[0]
    rows = sliding_window_view(image, size, axis=0) @ kernel
    return sliding_window_view(rows, size, axis=1) @ kernel


def ssim(a, b) -> float:
    """Mean structural similarity over a Gaussian-weighted sliding window."""
    import numpy as np

    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise AmberError(
            f"cannot compare images of different shapes: {a.shape} vs {b.shape}"
        )
    if min(a.shape[:2]) < SSIM_WINDOW:
        raise AmberError(
            f"images must be at least {SSIM_WINDOW}px on each side for SSIM"
        )

    kernel = _gaussian_kernel()
    mu_a = _filter_separable(a, kernel)
    mu_b = _filter_separable(b, kernel)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b

    sigma_a2 = _filter_separable(a * a, kernel) - mu_a2
    sigma_b2 = _filter_separable(b * b, kernel) - mu_b2
    sigma_ab = _filter_separable(a * b, kernel) - mu_ab

    numerator = (2 * mu_ab + SSIM_C1) * (2 * sigma_ab + SSIM_C2)
    denominator = (mu_a2 + mu_b2 + SSIM_C1) * (sigma_a2 + sigma_b2 + SSIM_C2)
    return float((numerator / denominator).mean())


@dataclass
class ViewMetrics:
    frame_id: str
    psnr: float
    ssim: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationMetrics:
    views: list[ViewMetrics] = field(default_factory=list)
    missing_renders: list[str] = field(default_factory=list)

    def aggregate(self, only: Iterable[str] | None = None) -> dict[str, Any]:
        selected = list(self.views)
        if only is not None:
            wanted = set(only)
            selected = [v for v in selected if v.frame_id in wanted]
        if not selected:
            return {"count": 0, "psnr": None, "ssim": None}
        finite_psnr = [v.psnr for v in selected if v.psnr != float("inf")]
        return {
            "count": len(selected),
            "psnr": (sum(finite_psnr) / len(finite_psnr)) if finite_psnr else None,
            "ssim": sum(v.ssim for v in selected) / len(selected),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "views": [v.to_dict() for v in self.views],
            "missing_renders": self.missing_renders,
            "aggregate": self.aggregate(),
        }


def evaluate_holdout(
    render_dir: Path,
    source_dir: Path,
    evaluation_frame_ids: Sequence[str],
    suffix: str = ".png",
) -> EvaluationMetrics:
    """Compare each held-out render with its untouched source frame."""
    metrics = EvaluationMetrics()
    for frame_id in evaluation_frame_ids:
        render = Path(render_dir) / f"{frame_id}{suffix}"
        source = Path(source_dir) / f"{frame_id}{suffix}"
        if not render.is_file() or not source.is_file():
            metrics.missing_renders.append(frame_id)
            continue
        rendered_rgb, source_rgb = _load_rgb(render), _load_rgb(source)
        metrics.views.append(
            ViewMetrics(
                frame_id=frame_id,
                psnr=psnr(rendered_rgb, source_rgb),
                ssim=ssim(_load_gray(render), _load_gray(source)),
            )
        )
    return metrics


# --------------------------------------------------------------------------
# Comparison groups
# --------------------------------------------------------------------------

CONCLUSIVE = "conclusive"
INCONCLUSIVE = "inconclusive"


def common_evaluation_intersection(
    coverage: Mapping[str, Sequence[str]],
) -> list[str]:
    """Evaluation frames registered by *every* configuration in the group."""
    if not coverage:
        return []
    sets = [set(ids) for ids in coverage.values()]
    common = set.intersection(*sets) if sets else set()
    return sorted(common)


def compare_configurations(
    coverage: Mapping[str, Sequence[str]],
    metrics: Mapping[str, EvaluationMetrics],
    reserved_evaluation_ids: Sequence[str],
    min_common_evaluation_views: int,
) -> dict[str, Any]:
    """Rank configurations honestly, or refuse to rank them.

    Two things this deliberately does *not* do: silently shrink the evaluation
    set when a configuration fails to register a frame, and rank on a tiny
    surviving subset. A missing evaluation pose is evidence against that
    configuration, so it is reported as coverage loss, and a thin intersection
    makes the whole comparison inconclusive.
    """
    intersection = common_evaluation_intersection(coverage)
    reserved = list(reserved_evaluation_ids)

    per_config: dict[str, Any] = {}
    for config_id, registered in coverage.items():
        config_metrics = metrics.get(config_id, EvaluationMetrics())
        missing = sorted(set(reserved) - set(registered))
        per_config[config_id] = {
            "coverage": {
                "reserved": len(reserved),
                "registered": len(set(registered) & set(reserved)),
                "missing_ids": missing,
            },
            "intersection_aggregate": config_metrics.aggregate(intersection),
            "full_registered_aggregate": config_metrics.aggregate(),
        }

    status = (
        CONCLUSIVE
        if len(intersection) >= min_common_evaluation_views
        else INCONCLUSIVE
    )
    result: dict[str, Any] = {
        "status": status,
        "common_intersection": intersection,
        "common_intersection_size": len(intersection),
        "min_common_evaluation_views": min_common_evaluation_views,
        "reserved_evaluation_ids": reserved,
        "configurations": per_config,
    }
    if status == INCONCLUSIVE:
        result["reason"] = (
            f"only {len(intersection)} evaluation views were registered by every "
            f"configuration, below the predeclared minimum of "
            f"{min_common_evaluation_views}; ranking on this subset would "
            "compare configurations on whichever views happened to be easy"
        )
    else:
        ranked = sorted(
            (
                (cid, data["intersection_aggregate"]["psnr"])
                for cid, data in per_config.items()
                if data["intersection_aggregate"]["psnr"] is not None
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        result["ranking"] = [{"config": c, "psnr": p} for c, p in ranked]
    return result


# --------------------------------------------------------------------------
# Human review records
# --------------------------------------------------------------------------

PASS, FAIL, NOT_APPLICABLE = "pass", "fail", "not_applicable"
REVIEW_VALUES = frozenset({PASS, FAIL, NOT_APPLICABLE})

MOTION_RISK_SUBJECTS = ("person", "pet", "foliage", "water", "traffic")


@dataclass
class MotionArtifactReview:
    """The human review §8.5 requires for any capture that might have moved.

    Version 1 claims no automatic motion detector, so this record is the only
    thing that may declare a moving-subject capture a success or a failure.
    """

    verdict: str = NOT_APPLICABLE
    subjects: list[str] = field(default_factory=list)
    reviewer: str | None = None
    reviewed_at: str | None = None
    note: str = ""
    screenshots: list[str] = field(default_factory=list)
    required: bool = False

    def __post_init__(self) -> None:
        if self.verdict not in REVIEW_VALUES:
            raise AmberError(
                f"motion-artifact verdict must be one of {sorted(REVIEW_VALUES)}"
            )

    @property
    def blocks_success(self) -> bool:
        """A required-but-unreviewed or failed review is not a success.

        Ghosting presented as a successful preservation would be exactly the
        kind of quiet dishonesty the authenticity principle forbids.
        """
        if self.verdict == FAIL:
            return True
        return self.required and self.verdict == NOT_APPLICABLE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blocks_success"] = self.blocks_success
        return data
