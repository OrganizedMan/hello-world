"""The frames stage of the orchestrator, run against a real decoded video.

Skips honestly when FFmpeg is absent rather than faking a decode.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from amber.config import get_profile
from amber.events import MemoryEventSink
from amber.models import EVAL, REGENERABLE, TRAIN
from amber.pipeline.run import FRAME_REPORT, Pipeline, RunOptions
from amber.services.projects import SceneStore

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is not installed")


def make_video(path: Path, duration: int = 12) -> Path:
    subprocess.run(
        [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"testsrc=duration={duration}:size=640x480:rate=30",
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture()
def prepared(tmp_path: Path):
    """A scene whose import stage is already satisfied.

    Import needs ffprobe, which is not bundled with the ffmpeg binary available
    here; stubbing it lets the frames stage be tested for real.
    """
    video = make_video(tmp_path / "clip.mp4")
    store = SceneStore.create(tmp_path / "library", "Frames test")
    manifest = store.read_manifest()

    destination, digest = store.ingest_source(video)
    manifest.source = {"filename": destination.name, "sha256": digest}
    store.write_manifest(manifest)

    options = RunOptions(profile=get_profile("draft"), title="Frames test")
    pipeline = Pipeline(store, options, events=MemoryEventSink())
    pipeline.state.complete("import", sha256=digest)
    return store, pipeline


def test_the_frames_stage_produces_both_image_tiers(prepared):
    store, pipeline = prepared
    pipeline.stage_frames(store.read_manifest())

    pose_frames = list((store.working_dir / "pose-frames").glob("*.png"))
    training_frames = list((store.working_dir / "training-frames").glob("*.png"))

    assert pose_frames and training_frames
    assert len(pose_frames) >= len(training_frames)


def test_the_pose_tier_is_not_limited_by_the_training_budget(prepared):
    """Pose images must not inherit the trainer's memory ceiling."""
    from PIL import Image

    store, pipeline = prepared
    profile = pipeline.options.profile
    pipeline.stage_frames(store.read_manifest())

    pose = sorted((store.working_dir / "pose-frames").glob("*.png"))[0]
    training = sorted((store.working_dir / "training-frames").glob("*.png"))[0]

    with Image.open(pose) as img:
        pose_edge = max(img.size)
    with Image.open(training) as img:
        training_edge = max(img.size)

    assert training_edge <= profile.training_long_edge
    assert pose_edge >= training_edge


def test_the_frame_report_records_scores_and_the_split(prepared):
    store, pipeline = prepared
    pipeline.stage_frames(store.read_manifest())

    with store.abs(FRAME_REPORT).open() as fh:
        report = json.load(fh)

    assert report["candidate_count"] > 0
    assert report["eligible_count"] > 0
    assert report["config"]["decode_fps"] == 4.0
    assert all(f["sharpness"] is not None for f in report["frames"])


def test_a_production_run_defers_the_holdout_until_after_registration(prepared):
    """With `registered_interval`, nothing is held out before poses run."""
    store, pipeline = prepared
    manifest = pipeline.stage_frames(store.read_manifest())

    config = manifest.frame_config
    assert config.split_policy == "registered_interval"
    assert config.training_frame_ids
    assert config.evaluation_frame_ids == []
    assert config.split_locked is False


def test_a_comparison_run_reserves_and_locks_the_split_first(tmp_path: Path):
    video = make_video(tmp_path / "clip.mp4", duration=20)
    store = SceneStore.create(tmp_path / "library", "Comparison")
    manifest = store.read_manifest()
    destination, digest = store.ingest_source(video)
    manifest.source = {"filename": destination.name, "sha256": digest}
    store.write_manifest(manifest)

    options = RunOptions(
        profile=get_profile("draft"),
        title="Comparison",
        comparison_group_id="group-a",
    )
    pipeline = Pipeline(store, options, events=MemoryEventSink())
    pipeline.state.complete("import", sha256=digest)
    manifest = pipeline.stage_frames(store.read_manifest())

    config = manifest.frame_config
    assert config.split_policy == "fixed_candidate_stratified"
    assert config.split_locked is True
    assert config.comparison_group_id == "group-a"
    assert len(config.evaluation_frame_ids) == 32
    assert set(config.evaluation_frame_ids).isdisjoint(config.training_frame_ids)
    assert config.candidate_pool_sha256


def test_evaluation_images_are_written_to_their_own_tier(tmp_path: Path):
    video = make_video(tmp_path / "clip.mp4", duration=20)
    store = SceneStore.create(tmp_path / "library", "Comparison")
    manifest = store.read_manifest()
    destination, digest = store.ingest_source(video)
    manifest.source = {"filename": destination.name, "sha256": digest}
    store.write_manifest(manifest)

    options = RunOptions(
        profile=get_profile("draft"), comparison_group_id="group-a"
    )
    pipeline = Pipeline(store, options, events=MemoryEventSink())
    pipeline.state.complete("import", sha256=digest)
    manifest = pipeline.stage_frames(store.read_manifest())

    evaluation = {p.stem for p in (store.working_dir / "evaluation-frames").glob("*.png")}
    training = {p.stem for p in (store.working_dir / "training-frames").glob("*.png")}

    assert evaluation == set(manifest.frame_config.evaluation_frame_ids)
    assert evaluation.isdisjoint(training), "evaluation images must never train"


def test_the_stage_is_idempotent_when_already_complete(prepared):
    store, pipeline = prepared
    pipeline.stage_frames(store.read_manifest())
    first = sorted(p.name for p in (store.working_dir / "pose-frames").glob("*.png"))

    pipeline.stage_frames(store.read_manifest())
    second = sorted(p.name for p in (store.working_dir / "pose-frames").glob("*.png"))

    assert first == second
    assert pipeline.state.stages["frames"].attempts == 1, "a complete stage re-runs nothing"


def test_image_tiers_are_registered_as_regenerable(prepared):
    store, pipeline = prepared
    manifest = pipeline.stage_frames(store.read_manifest())

    for path in (
        "working/candidate-frames",
        "working/pose-frames",
        "working/training-frames",
    ):
        artifact = manifest.artifact(path)
        assert artifact is not None, f"{path} was not recorded"
        assert artifact.retention_class == REGENERABLE
        assert artifact.bytes > 0


def test_roles_are_stamped_onto_every_candidate(tmp_path: Path):
    video = make_video(tmp_path / "clip.mp4", duration=20)
    store = SceneStore.create(tmp_path / "library", "Roles")
    manifest = store.read_manifest()
    destination, digest = store.ingest_source(video)
    manifest.source = {"filename": destination.name, "sha256": digest}
    store.write_manifest(manifest)

    pipeline = Pipeline(
        store,
        RunOptions(profile=get_profile("draft"), comparison_group_id="g"),
        events=MemoryEventSink(),
    )
    pipeline.state.complete("import", sha256=digest)
    pipeline.stage_frames(store.read_manifest())

    with store.abs(FRAME_REPORT).open() as fh:
        roles = {f["role"] for f in json.load(fh)["frames"]}

    assert TRAIN in roles and EVAL in roles
