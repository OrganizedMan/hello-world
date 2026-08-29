from __future__ import annotations

from amber.pipeline.quality import (
    CONCLUSIVE,
    INCONCLUSIVE,
    EvaluationMetrics,
    ViewMetrics,
    common_evaluation_intersection,
    compare_configurations,
)


def metrics_for(ids, psnr_base=30.0):
    return EvaluationMetrics(
        views=[
            ViewMetrics(frame_id=i, psnr=psnr_base + n, ssim=0.9)
            for n, i in enumerate(ids)
        ]
    )


def test_intersection_is_the_frames_every_configuration_registered():
    coverage = {
        "P1": ["a", "b", "c", "d"],
        "P2": ["b", "c", "d", "e"],
        "P3": ["c", "d"],
    }
    assert common_evaluation_intersection(coverage) == ["c", "d"]


def test_intersection_of_no_configurations_is_empty():
    assert common_evaluation_intersection({}) == []


def test_comparison_reports_coverage_loss_per_configuration():
    reserved = [f"e{i}" for i in range(16)]
    coverage = {"P1": reserved, "P2": reserved[:-3]}
    result = compare_configurations(
        coverage,
        {"P1": metrics_for(reserved), "P2": metrics_for(reserved[:-3])},
        reserved,
        min_common_evaluation_views=12,
    )

    p2 = result["configurations"]["P2"]["coverage"]
    assert p2["reserved"] == 16
    assert p2["registered"] == 13
    assert p2["missing_ids"] == ["e13", "e14", "e15"]


def test_a_thin_intersection_makes_the_comparison_inconclusive():
    """Ranking on whichever few views survived would flatter a weak solve."""
    reserved = [f"e{i}" for i in range(16)]
    coverage = {"P1": reserved, "P2": reserved[:4]}
    result = compare_configurations(
        coverage,
        {"P1": metrics_for(reserved), "P2": metrics_for(reserved[:4], psnr_base=50)},
        reserved,
        min_common_evaluation_views=12,
    )

    assert result["status"] == INCONCLUSIVE
    assert "ranking" not in result
    assert "below the predeclared minimum" in result["reason"]


def test_a_full_intersection_is_conclusive_and_ranked():
    reserved = [f"e{i}" for i in range(16)]
    coverage = {"P1": reserved, "P2": reserved}
    result = compare_configurations(
        coverage,
        {
            "P1": metrics_for(reserved, psnr_base=30),
            "P2": metrics_for(reserved, psnr_base=25),
        },
        reserved,
        min_common_evaluation_views=12,
    )

    assert result["status"] == CONCLUSIVE
    assert [entry["config"] for entry in result["ranking"]] == ["P1", "P2"]


def test_both_intersection_and_full_coverage_metrics_are_published():
    """The intersection alone could hide a configuration's weak pose solution."""
    reserved = [f"e{i}" for i in range(16)]
    coverage = {"P1": reserved, "P2": reserved[:14]}
    result = compare_configurations(
        coverage,
        {"P1": metrics_for(reserved), "P2": metrics_for(reserved[:14])},
        reserved,
        min_common_evaluation_views=12,
    )

    p2 = result["configurations"]["P2"]
    assert p2["intersection_aggregate"]["count"] == 14
    assert p2["full_registered_aggregate"]["count"] == 14
    p1 = result["configurations"]["P1"]
    assert p1["full_registered_aggregate"]["count"] == 16
    assert p1["intersection_aggregate"]["count"] == 14


def test_aggregate_ignores_infinite_psnr_from_identical_images():
    metrics = EvaluationMetrics(
        views=[
            ViewMetrics("a", float("inf"), 1.0),
            ViewMetrics("b", 20.0, 0.8),
        ]
    )
    assert metrics.aggregate()["psnr"] == 20.0
    assert metrics.aggregate()["count"] == 2
