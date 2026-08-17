"""The conjunctive pose gate.

Training is expensive and a bad camera solution cannot be rescued by it, so
this gate stands between the two. Every condition must pass; there is no
weighted score, no partial pass, and no threshold derived from the run being
judged (AGENTS.md rule 8).
"""

from __future__ import annotations

from typing import Any

from ..config import PoseGateThresholds
from ..events import EventSink, emit
from ..models import GateCondition, PoseGateResult, ReconstructionReport

# Plain-language explanations attached to each diagnostic, shown to the user
# instead of a raw failure (plan §4, item 10).
DIAGNOSTIC_ADVICE: dict[str, str] = {
    "low_registration_ratio": (
        "Too few views could be linked together. This usually means motion "
        "blur, poor light, or gaps where the camera moved too fast."
    ),
    "insufficient_registered_frames": (
        "The camera solution covers too few views for a scene of this size. "
        "Record for longer, or move more slowly so more views overlap."
    ),
    "fragmented_reconstruction": (
        "The capture broke into several disconnected pieces, so they cannot be "
        "assembled into one scene. Revisit an earlier angle mid-capture to tie "
        "the loop together."
    ),
    "temporal_gap_exceeded": (
        "There is a long stretch of the video the camera track could not "
        "follow. The result would have a hole in it."
    ),
    "consecutive_frames_missing": (
        "A run of consecutive views failed to register, which breaks the "
        "camera path."
    ),
    "insufficient_parallax": (
        "Views were taken from nearly the same direction, so depth cannot be "
        "resolved reliably. Walk around the subject rather than pivoting."
    ),
    "insufficient_translation": (
        "The camera rotated but barely moved through space. A pan from one "
        "spot cannot produce a 3D scene — walk while recording."
    ),
    "high_reprojection_error": (
        "The camera solution does not fit the observed features well enough to "
        "trust. Blur or a moving subject are the usual causes."
    ),
    "camera_path_review_failed": (
        "The rendered camera path was reviewed and rejected."
    ),
}


def _ge(
    name: str,
    value: float | None,
    threshold: float,
    diagnostic: str,
) -> GateCondition:
    passed = value is not None and value >= threshold
    return GateCondition(
        name=name,
        passed=bool(passed),
        value=value,
        threshold=threshold,
        comparison=">=",
        diagnostic=None if passed else diagnostic,
    )


def _le(
    name: str,
    value: float | None,
    threshold: float,
    diagnostic: str,
) -> GateCondition:
    passed = value is not None and value <= threshold
    return GateCondition(
        name=name,
        passed=bool(passed),
        value=value,
        threshold=threshold,
        comparison="<=",
        diagnostic=None if passed else diagnostic,
    )


def evaluate_pose_gate(
    report: ReconstructionReport,
    thresholds: PoseGateThresholds,
) -> PoseGateResult:
    """Apply every predeclared condition and return them all.

    All conditions are evaluated even after one fails, because a capture that
    fails several is a different diagnosis from one that fails a single check.
    """
    conditions = [
        _ge(
            "registration_ratio",
            report.registration_ratio,
            thresholds.min_registration_ratio,
            "low_registration_ratio",
        ),
        _ge(
            "registered_frames",
            report.registered_frames,
            thresholds.min_registered_frames,
            "insufficient_registered_frames",
        ),
        _ge(
            "dominant_model_fraction",
            report.largest_model_frame_fraction,
            thresholds.min_dominant_model_fraction,
            "fragmented_reconstruction",
        ),
        _le(
            "longest_temporal_gap_seconds",
            report.longest_temporal_gap_seconds,
            thresholds.max_temporal_gap_seconds,
            "temporal_gap_exceeded",
        ),
        _le(
            "longest_consecutive_missing_selected",
            report.longest_consecutive_missing_selected,
            thresholds.max_consecutive_missing_selected_frames,
            "consecutive_frames_missing",
        ),
        _ge(
            "median_triangulation_angle_deg",
            report.median_triangulation_angle_deg,
            thresholds.min_median_triangulation_angle_deg,
            "insufficient_parallax",
        ),
        _ge(
            "translation_to_depth_ratio",
            report.translation_to_depth_ratio,
            thresholds.min_translation_to_depth_ratio,
            "insufficient_translation",
        ),
        _le(
            "mean_reprojection_error_px",
            report.mean_reprojection_error_px,
            thresholds.max_mean_reprojection_error_px,
            "high_reprojection_error",
        ),
    ]

    if thresholds.requires_camera_path_review:
        passed = report.camera_path_review == "pass"
        conditions.append(
            GateCondition(
                name="camera_path_review",
                passed=passed,
                value=None,
                threshold=None,
                comparison="==",
                diagnostic=None if passed else "camera_path_review_failed",
            )
        )

    return PoseGateResult(conditions=conditions)


def gate_message(result: PoseGateResult) -> str:
    """One actionable sentence describing why the gate failed."""
    if result.passed:
        return "The camera solution passed every check."
    diagnostic = result.primary_diagnostic()
    advice = DIAGNOSTIC_ADVICE.get(diagnostic or "", "")
    failed = ", ".join(c.name for c in result.failures)
    return f"{advice} (failed checks: {failed})".strip()


def reconstruction_report_document(
    report: ReconstructionReport,
    gate: PoseGateResult,
    thresholds: PoseGateThresholds,
    pose_config: dict[str, Any],
) -> dict[str, Any]:
    """The contents of `qa/reconstruction-report.json`."""
    return {
        "gate": gate.to_dict(),
        "gate_message": gate_message(gate),
        "thresholds": thresholds.to_dict(),
        "thresholds_source": "docs/m0-thresholds.json (predeclared)",
        "pose_config": pose_config,
        "report": report.to_dict(),
        "evaluation_coverage": {
            "reserved": report.reserved_evaluation_frames,
            "registered": len(report.registered_evaluation_frame_ids),
            "registered_ids": report.registered_evaluation_frame_ids,
        },
    }


def emit_gate(events: EventSink, gate: PoseGateResult) -> None:
    for condition in gate.conditions:
        if not condition.passed:
            emit(
                events,
                "poses",
                "warning",
                f"gate check failed: {condition.name} "
                f"({condition.value} {condition.comparison} "
                f"{condition.threshold} required)",
                condition=condition.name,
                diagnostic=condition.diagnostic,
            )
    if gate.passed:
        emit(events, "poses", "info", "pose gate passed")
