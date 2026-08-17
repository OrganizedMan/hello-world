"""Prune/regenerate integration coverage (M1 exit criterion).

The archive's central promise is that `working/` is disposable: it can be
removed to reclaim space and rebuilt later from the source, the manifest
recipe, and the pinned toolchain — while the archival core and every
artifact's history survive untouched.

The recipe-driven test below proves that invariant without external tools. The
ffmpeg-backed test proves the same thing through the real decode path when the
toolchain is present, and skips honestly when it is not.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from amber.config import CandidateConfig
from amber.events import MemoryEventSink
from amber.models import (
    ARCHIVAL_CORE,
    PRESENT,
    PRUNED,
    REGENERABLE,
)
from amber.pipeline import frames as frames_mod
from amber.services.projects import SceneStore, sha256_file, tree_bytes
from amber.services.storage import apply_prune, plan_prune
from amber.tools import ProcessRunner

FFMPEG = shutil.which("ffmpeg")


# --------------------------------------------------------------------------
# A deterministic stand-in for the decode recipe
# --------------------------------------------------------------------------


def regenerate_candidates(source: Path, out_dir: Path, decode_fps: float) -> list[Path]:
    """Rebuild candidate frames from the source using only recorded parameters.

    This stands in for `ffmpeg -vf fps=<decode_fps>`: same contract, no external
    dependency. Output depends solely on the source bytes and the recipe, which
    is exactly what the regenerability invariant requires.
    """
    import numpy as np
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int.from_bytes(hashlib.sha256(source.read_bytes()).digest()[:8], "big")
    written: list[Path] = []
    for index in range(int(decode_fps * 4)):
        rng = np.random.default_rng(seed + index)
        data = rng.integers(0, 255, size=(32, 32, 3), dtype=np.uint8)
        path = out_dir / f"cand_{index:06d}.png"
        Image.fromarray(data).save(path)
        written.append(path)
    return written


@pytest.fixture()
def finalized_scene(tmp_path: Path):
    """A scene with an archival core and a populated, prunable working tier."""
    store = SceneStore.create(tmp_path / "library", "Living room")
    manifest = store.read_manifest()

    source = store.source_dir / "original.mov"
    source.write_bytes(b"not really a video, but stable bytes" * 64)
    source_hash = sha256_file(source)
    store.register_artifact(manifest, source, "source_video", ARCHIVAL_CORE)

    config = CandidateConfig.from_plan()
    candidate_dir = store.working_dir / "candidate-frames"
    regenerate_candidates(source, candidate_dir, config.decode_fps)
    store.register_artifact(
        manifest,
        candidate_dir,
        "candidate_frames",
        REGENERABLE,
        regeneration_cost_seconds=45.0,
    )

    colmap_dir = store.working_dir / "colmap"
    (colmap_dir / "database.db").write_bytes(b"sqlite" * 2000)
    store.register_artifact(manifest, colmap_dir, "colmap_workspace", REGENERABLE)

    master = store.master_dir / "scene.ply"
    master.write_bytes(b"ply header and splats" * 500)
    store.register_artifact(manifest, master, "master_ply", ARCHIVAL_CORE)

    sparse = store.master_dir / "cameras" / "colmap-sparse"
    (sparse / "images.txt").write_text("# Images\n", encoding="utf-8")
    store.register_artifact(manifest, sparse, "sparse_camera_model", ARCHIVAL_CORE)

    manifest.pipeline["frame_config"] = {"decode_fps": config.decode_fps}
    store.write_manifest(manifest)
    store.write_checksums(manifest)
    return store, manifest, source_hash


def test_working_data_regenerates_from_source_and_manifest(finalized_scene):
    store, manifest, source_hash = finalized_scene
    candidate_dir = store.working_dir / "candidate-frames"

    before = {p.name: sha256_file(p) for p in sorted(candidate_dir.glob("*.png"))}
    assert before, "the fixture must produce candidate frames"

    plan = plan_prune(manifest)
    freed = apply_prune(store, manifest, plan)
    assert freed > 0
    assert list(candidate_dir.glob("*.png")) == []

    # Regenerate using only what the archive is allowed to depend on.
    recovered = SceneStore.open(store.root)
    recovered_manifest = recovered.read_manifest()
    decode_fps = recovered_manifest.pipeline["frame_config"]["decode_fps"]
    regenerate_candidates(
        recovered.source_dir / "original.mov", candidate_dir, decode_fps
    )

    after = {p.name: sha256_file(p) for p in sorted(candidate_dir.glob("*.png"))}
    assert after == before, "regeneration must reproduce the pruned frames"
    assert sha256_file(recovered.source_dir / "original.mov") == source_hash


def test_the_archival_core_survives_a_prune(finalized_scene):
    store, manifest, _ = finalized_scene
    apply_prune(store, manifest, plan_prune(manifest))

    assert (store.source_dir / "original.mov").is_file()
    assert (store.master_dir / "scene.ply").is_file()
    assert (store.master_dir / "cameras" / "colmap-sparse" / "images.txt").is_file()
    assert store.verify_checksums() == []


def test_artifact_history_survives_a_prune(finalized_scene):
    store, manifest, _ = finalized_scene
    before = {a.path: (a.role, a.retention_class, a.bytes) for a in manifest.artifacts}

    apply_prune(store, manifest, plan_prune(manifest))
    reloaded = SceneStore.open(store.root).read_manifest()

    assert {a.path for a in reloaded.artifacts} == set(before)
    for artifact in reloaded.artifacts:
        role, retention, original_bytes = before[artifact.path]
        assert artifact.role == role
        assert artifact.retention_class == retention
        if artifact.status == PRUNED:
            assert artifact.prior_bytes == original_bytes
            assert artifact.bytes == 0
        else:
            assert artifact.status == PRESENT


def test_regeneration_cost_is_retained_for_pruned_artifacts(finalized_scene):
    store, manifest, _ = finalized_scene
    apply_prune(store, manifest, plan_prune(manifest))

    art = SceneStore.open(store.root).read_manifest().artifact(
        "working/candidate-frames"
    )
    assert art.status == PRUNED
    assert art.regeneration_cost_seconds == 45.0


def test_a_pruned_scene_reports_what_it_freed(finalized_scene):
    store, manifest, _ = finalized_scene
    prunable_before = manifest.prunable_bytes()
    retained_before = manifest.retained_bytes()

    apply_prune(store, manifest, plan_prune(manifest))

    assert manifest.prunable_bytes() == 0
    assert manifest.retained_bytes() == retained_before - prunable_before
    assert manifest.retained_bytes() > 0


# --------------------------------------------------------------------------
# The same invariant through the real decode path
# --------------------------------------------------------------------------


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is not installed")
def test_real_decode_regenerates_identical_candidate_frames(tmp_path: Path):
    """Runs only where the pinned toolchain exists; never faked when absent."""
    source = tmp_path / "clip.mp4"
    subprocess.run(
        [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=30",
            "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
    )

    config = CandidateConfig.from_plan()
    runner, events = ProcessRunner(), MemoryEventSink()

    first_dir = tmp_path / "first"
    first = frames_mod.extract_candidates(source, first_dir, config, runner, events)
    assert first, "decoding must produce candidate frames"
    first_hashes = {p.name: sha256_file(p) for p in sorted(first_dir.glob("*.png"))}

    shutil.rmtree(first_dir)
    second_dir = tmp_path / "second"
    frames_mod.extract_candidates(source, second_dir, config, runner, events)
    second_hashes = {p.name: sha256_file(p) for p in sorted(second_dir.glob("*.png"))}

    assert second_hashes == first_hashes


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is not installed")
def test_scoring_separates_a_blurred_frame_from_a_sharp_one(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    subprocess.run(
        [
            FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
            "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
    )
    config = CandidateConfig.from_plan()
    directory = tmp_path / "frames"
    candidates = frames_mod.extract_candidates(
        source, directory, config, ProcessRunner(), MemoryEventSink()
    )
    frames_mod.score_frames(candidates, directory, MemoryEventSink())

    from PIL import Image, ImageFilter

    sharp = candidates[0]
    blurred_path = directory / "blurred.png"
    with Image.open(directory / sharp.path) as img:
        img.filter(ImageFilter.GaussianBlur(6)).save(blurred_path)

    sharp_score = frames_mod.score_image(directory / sharp.path).sharpness
    blur_score = frames_mod.score_image(blurred_path).sharpness
    assert blur_score < sharp_score
