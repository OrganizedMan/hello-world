"""The predeclared plan and the machine-readable thresholds must not drift.

If they did, code could enforce one gate while the frozen plan documented
another — which would quietly defeat the point of predeclaring anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amber.config import REPO_ROOT, load_thresholds

PLAN = REPO_ROOT / "docs" / "m0-experiment-plan.md"


@pytest.fixture(scope="module")
def plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def thresholds() -> dict:
    return load_thresholds()


@pytest.mark.parametrize(
    "quoted",
    [
        "**0.80**",  # registration ratio
        "**0.95**",  # dominant model fraction
        "**1.5 s**",  # temporal gap
        "**5**",  # consecutive missing frames
        "**3.0°**",  # triangulation angle
        "**0.05**",  # translation to depth
        "**1.5 px**",  # reprojection error
        "**80**",  # object floor
        "**120**",  # room floor
        "**12.**",  # min common evaluation views
        "32 reserved evaluation frames",
    ],
)
def test_every_gate_number_is_quoted_in_the_plan(plan_text: str, quoted: str):
    assert quoted in plan_text, f"{quoted} is enforced in code but absent from the plan"


def test_gate_thresholds_match_the_plan(thresholds: dict):
    gate = thresholds["pose_gate"]
    assert gate["min_registration_ratio"] == 0.80
    assert gate["min_dominant_model_fraction"] == 0.95
    assert gate["max_temporal_gap_seconds"] == 1.5
    assert gate["max_consecutive_missing_selected_frames"] == 5
    assert gate["min_median_triangulation_angle_deg"] == 3.0
    assert gate["min_translation_to_depth_ratio"] == 0.05
    assert gate["max_mean_reprojection_error_px"] == 1.5
    assert gate["requires_camera_path_review"] is True


def test_capture_class_floors_match_the_plan(thresholds: dict):
    assert thresholds["min_registered_frames"] == {"object": 80, "room": 120}


def test_the_comparative_split_is_fully_specified(thresholds: dict):
    split = thresholds["comparative_split"]
    assert split["policy"] == "fixed_candidate_stratified"
    assert split["n_eval"] == 32
    assert split["min_common_evaluation_views"] == 12
    assert split["split_algorithm_version"] == 1
    assert split["split_seed"] == 20260817


def test_the_training_sweep_matches_the_plan(thresholds: dict, plan_text: str):
    assert thresholds["training_selections"] == [60, 120, 240]
    assert "**60 / 120 / 240**" in plan_text


def test_the_effort_bound_is_declared(thresholds: dict, plan_text: str):
    bound = thresholds["effort_bound"]
    assert bound["total_sessions"] == 6
    assert bound["gate_a_sessions"] + bound["gate_b_sessions"] == 6
    assert "six focused working sessions" in plan_text


def test_the_plan_declares_its_execution_status(plan_text: str):
    """Guards against a future edit quietly claiming unmeasured results.

    The original form asserted the plan said "not been executed", which
    stopped being true the moment Gate A part 1 passed. What must never
    disappear is an explicit, checkable status statement in §1 — bold text
    naming what has and has not run — so a reader is never left assuming.
    """
    section_1 = plan_text.split("## 1. Execution status", 1)[1].split("## 2.", 1)[0]
    assert "**" in section_1, "§1 must state execution status in bold, not prose"
    assert "not yet" in section_1 or "not been executed" in section_1, (
        "§1 must be explicit about what remains unexecuted, even after partial "
        "progress"
    )


def test_the_feasibility_report_declares_its_execution_status():
    """Guards the honesty header, not a particular stage of progress.

    The original form asserted the report said "not executed", which stopped
    being true the moment Gate A produced its first real measurement. What must
    never disappear is the explicit status and the rule-19 statement that an
    unrun stage is reported as not run.
    """
    text = (REPO_ROOT / "docs" / "feasibility-results.md").read_text(encoding="utf-8")
    recognised = (
        "**Status: not executed.**",
        "**Status: in progress.**",
        "**Status: complete.**",
    )
    assert any(marker in text for marker in recognised), (
        "the feasibility report must state its execution status explicitly"
    )
    assert "never as an estimate" in text


def test_the_thresholds_file_is_valid_json():
    with (REPO_ROOT / "docs" / "m0-thresholds.json").open(encoding="utf-8") as fh:
        assert isinstance(json.load(fh), dict)


def test_adr_index_lists_every_adr_file():
    decisions = REPO_ROOT / "docs" / "decisions"
    index = (decisions / "README.md").read_text(encoding="utf-8")
    for adr in sorted(decisions.glob("0*.md")):
        assert adr.name in index, f"{adr.name} is missing from the ADR index"


def test_every_adr_uses_the_required_format():
    for adr in sorted((REPO_ROOT / "docs" / "decisions").glob("0*.md")):
        text = adr.read_text(encoding="utf-8")
        for section in ("**Status:**", "**Date:**", "## Context", "## Decision",
                        "## Alternatives", "## Consequences", "## Evidence"):
            assert section in text, f"{adr.name} is missing {section}"
