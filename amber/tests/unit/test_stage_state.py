from __future__ import annotations

from pathlib import Path

import pytest

from amber.models import AmberError
from amber.services.jobs import COMPLETE, FAILED, PENDING, RUNNING, StageState


def test_a_new_state_starts_every_stage_pending(tmp_path: Path):
    state = StageState.load(tmp_path / "state.json")
    assert state.next_stage() == "import"
    assert all(r.status == PENDING for r in state.stages.values())


def test_completed_stages_persist_across_reloads(tmp_path: Path):
    path = tmp_path / "state.json"
    state = StageState.load(path)
    state.begin("import")
    state.complete("import", sha256="abc")

    reloaded = StageState.load(path)
    assert reloaded.is_complete("import")
    assert reloaded.stages["import"].outputs["sha256"] == "abc"
    assert reloaded.next_stage() == "frames"


def test_an_interrupted_stage_is_reset_so_it_re_runs(tmp_path: Path):
    """A crash mid-stage must not leave a stage that looks like it is running."""
    path = tmp_path / "state.json"
    state = StageState.load(path)
    state.begin("poses")
    assert state.stages["poses"].status == RUNNING

    recovered = StageState.load(path)
    assert recovered.stages["poses"].status == PENDING
    assert "interrupted" in recovered.stages["poses"].error


def test_failure_records_the_diagnostic(tmp_path: Path):
    state = StageState.load(tmp_path / "state.json")
    state.begin("poses")
    state.fail("poses", "the camera barely moved", diagnostic="insufficient_translation")

    assert state.stages["poses"].status == FAILED
    assert state.stages["poses"].diagnostic == "insufficient_translation"


def test_retrying_invalidates_the_stage_and_everything_downstream(tmp_path: Path):
    state = StageState.load(tmp_path / "state.json")
    for stage in ("import", "frames", "poses", "train"):
        state.begin(stage)
        state.complete(stage, marker=stage)

    invalidated = state.invalidate_from("poses")

    assert invalidated == ["poses", "train"]
    assert state.is_complete("import") and state.is_complete("frames")
    assert not state.is_complete("poses") and not state.is_complete("train")
    assert state.stages["train"].outputs == {}, "stale outputs must be cleared"


def test_invalidation_is_persisted(tmp_path: Path):
    path = tmp_path / "state.json"
    state = StageState.load(path)
    state.begin("import")
    state.complete("import")
    state.invalidate_from("import")

    assert StageState.load(path).is_complete("import") is False


def test_attempts_are_counted(tmp_path: Path):
    state = StageState.load(tmp_path / "state.json")
    state.begin("frames")
    state.fail("frames", "boom")
    state.begin("frames")
    assert state.stages["frames"].attempts == 2


def test_unknown_stages_are_rejected(tmp_path: Path):
    state = StageState.load(tmp_path / "state.json")
    with pytest.raises(AmberError, match="unknown stage"):
        state.begin("magic")
    with pytest.raises(AmberError, match="unknown stage"):
        state.invalidate_from("magic")


def test_completed_stages_are_reported_in_pipeline_order(tmp_path: Path):
    state = StageState.load(tmp_path / "state.json")
    state.complete("frames")
    state.complete("import")
    assert state.completed_stages() == ["import", "frames"]
