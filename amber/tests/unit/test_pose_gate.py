from __future__ import annotations

import pytest

from amber.config import PoseGateThresholds
from amber.models import AmberError, ReconstructionReport
from amber.pipeline.poses import evaluate_pose_gate, gate_message


def healthy_report(**overrides) -> ReconstructionReport:
    defaults = dict(
        selected_training_frames=120,
        reserved_evaluation_frames=32,
        total_pose_input_frames=152,
        registered_frames=150,
        sparse_point_count=40_000,
        median_observations_per_point=6,
        mean_reprojection_error_px=0.8,
        camera_path_extent=2.0,
        median_scene_depth=10.0,
        median_triangulation_angle_deg=11.0,
        connected_model_count=1,
        largest_model_frame_fraction=1.0,
        longest_temporal_gap_seconds=0.5,
        longest_consecutive_missing_selected=2,
        camera_path_review="pass",
    )
    defaults.update(overrides)
    return ReconstructionReport(**defaults)


@pytest.fixture()
def thresholds() -> PoseGateThresholds:
    return PoseGateThresholds.for_capture_class("room")


def test_thresholds_come_from_the_predeclared_plan(thresholds):
    assert thresholds.min_registration_ratio == 0.80
    assert thresholds.min_registered_frames == 120
    assert thresholds.min_dominant_model_fraction == 0.95
    assert thresholds.max_temporal_gap_seconds == 1.5


def test_object_and_room_have_different_absolute_floors():
    assert PoseGateThresholds.for_capture_class("object").min_registered_frames == 80
    assert PoseGateThresholds.for_capture_class("room").min_registered_frames == 120


def test_an_undeclared_capture_class_is_refused():
    with pytest.raises(AmberError, match="unknown capture class"):
        PoseGateThresholds.for_capture_class("underwater")


def test_a_healthy_run_passes_every_condition(thresholds):
    gate = evaluate_pose_gate(healthy_report(), thresholds)

    assert gate.passed
    assert gate.failures == []
    assert len(gate.conditions) == 9


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"registered_frames": 100}, "low_registration_ratio"),
        ({"largest_model_frame_fraction": 0.5}, "fragmented_reconstruction"),
        ({"longest_temporal_gap_seconds": 5.0}, "temporal_gap_exceeded"),
        ({"longest_consecutive_missing_selected": 12}, "consecutive_frames_missing"),
        ({"median_triangulation_angle_deg": 0.5}, "insufficient_parallax"),
        ({"camera_path_extent": 0.01}, "insufficient_translation"),
        ({"mean_reprojection_error_px": 4.0}, "high_reprojection_error"),
        ({"camera_path_review": "fail"}, "camera_path_review_failed"),
    ],
)
def test_each_condition_can_fail_on_its_own(thresholds, overrides, expected):
    gate = evaluate_pose_gate(healthy_report(**overrides), thresholds)

    assert not gate.passed
    assert expected in gate.diagnostics


def test_the_gate_is_conjunctive_not_a_score(thresholds):
    """Eight strong conditions must not outvote one failing condition."""
    gate = evaluate_pose_gate(
        healthy_report(sparse_point_count=10_000_000, camera_path_review="fail"),
        thresholds,
    )
    assert not gate.passed
    assert sum(c.passed for c in gate.conditions) == 8


def test_absolute_floor_fails_even_when_the_ratio_is_perfect(thresholds):
    """A short capture can register 100% of very few frames."""
    gate = evaluate_pose_gate(
        healthy_report(total_pose_input_frames=40, registered_frames=40), thresholds
    )
    assert not gate.passed
    assert "insufficient_registered_frames" in gate.diagnostics

    ratio = next(c for c in gate.conditions if c.name == "registration_ratio")
    assert ratio.passed, "the ratio check alone would have let this through"


def test_a_pure_pan_reports_insufficient_translation(thresholds):
    """The negative control from the test matrix."""
    gate = evaluate_pose_gate(
        healthy_report(camera_path_extent=0.0, median_triangulation_angle_deg=0.2),
        thresholds,
    )
    assert not gate.passed
    assert gate.primary_diagnostic() == "insufficient_translation"
    assert "walk while recording" in gate_message(gate)


def test_a_gate_with_no_conditions_does_not_pass():
    from amber.models import PoseGateResult

    assert PoseGateResult(conditions=[]).passed is False


def test_gate_message_is_actionable_for_a_fragmented_capture(thresholds):
    gate = evaluate_pose_gate(
        healthy_report(largest_model_frame_fraction=0.4), thresholds
    )
    message = gate_message(gate)

    assert "disconnected" in message
    assert "dominant_model_fraction" in message
