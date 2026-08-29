from __future__ import annotations

import json
from pathlib import Path

import pytest

from amber.models import (
    ARCHIVAL_CORE,
    Artifact,
    PRESENT,
    PRUNED,
    REGENERABLE,
    RetentionError,
)
from amber.services.projects import SceneStore, sha256_file
from amber.services.storage import (
    apply_prune,
    estimate_required_space,
    plan_prune,
    repair_interrupted_prune,
)


@pytest.fixture()
def scene(tmp_path: Path):
    store = SceneStore.create(tmp_path, "Living room")
    manifest = store.read_manifest()

    source = store.source_dir / "original.mov"
    source.write_bytes(b"pretend video" * 100)
    store.register_artifact(manifest, source, "source_video", ARCHIVAL_CORE)

    master = store.master_dir / "scene.ply"
    master.write_bytes(b"ply" * 500)
    store.register_artifact(manifest, master, "master_ply", ARCHIVAL_CORE)

    working = store.working_dir / "candidate-frames"
    for i in range(3):
        (working / f"cand_{i}.png").write_bytes(b"x" * 1000)
    store.register_artifact(
        manifest,
        working,
        "candidate_frames",
        REGENERABLE,
        regeneration_cost_seconds=120.0,
    )
    store.write_manifest(manifest)
    return store, manifest


def test_prune_plan_targets_only_regenerable_data(scene):
    _store, manifest = scene
    plan = plan_prune(manifest)

    assert [t.path for t in plan.targets] == ["working/candidate-frames"]
    assert "source/original.mov" in plan.protected
    assert "master/scene.ply" in plan.protected


def test_prune_plan_does_not_mutate_anything(scene):
    _store, manifest = scene
    before = json.dumps(manifest.to_dict(), sort_keys=True)
    plan_prune(manifest)
    assert json.dumps(manifest.to_dict(), sort_keys=True) == before


def test_a_plan_can_never_include_the_archival_core(scene):
    _store, manifest = scene
    with pytest.raises(RetentionError, match="archival core"):
        plan_prune(manifest, frozenset({ARCHIVAL_CORE}))


def test_pruning_frees_bytes_and_keeps_the_source_and_master(scene):
    store, manifest = scene
    plan = plan_prune(manifest)

    freed = apply_prune(store, manifest, plan)

    assert freed == 3000
    assert (store.source_dir / "original.mov").is_file()
    assert (store.master_dir / "scene.ply").is_file()
    assert list((store.working_dir / "candidate-frames").iterdir()) == []


def test_pruning_records_status_and_regeneration_cost(scene):
    store, manifest = scene
    apply_prune(store, manifest, plan_prune(manifest))

    art = manifest.artifact("working/candidate-frames")
    assert art.status == PRUNED
    assert art.prior_bytes == 3000
    assert art.regeneration_cost_seconds == 120.0
    assert store.read_manifest().artifact("working/candidate-frames").status == PRUNED


def test_the_manifest_is_written_before_files_are_deleted(scene, monkeypatch):
    """An interrupted prune must not claim a deleted file is still present."""
    store, manifest = scene
    plan = plan_prune(manifest)

    def explode(_path):
        raise OSError("interrupted")

    monkeypatch.setattr("amber.services.storage._remove", explode)
    with pytest.raises(OSError):
        apply_prune(store, manifest, plan)

    on_disk = store.read_manifest().artifact("working/candidate-frames")
    assert on_disk.status == PRUNED, "the safe direction is 'pruned but present'"
    assert (store.working_dir / "candidate-frames" / "cand_0.png").is_file()


def test_an_interrupted_prune_can_be_finished(scene):
    store, manifest = scene
    manifest.mark_pruned("working/candidate-frames")
    store.write_manifest(manifest)

    freed = repair_interrupted_prune(store, manifest)

    assert freed == 3000
    assert list((store.working_dir / "candidate-frames").iterdir()) == []


def test_pruning_an_unknown_artifact_is_refused(scene):
    _store, manifest = scene
    with pytest.raises(RetentionError, match="unknown artifact"):
        manifest.mark_pruned("working/not-a-thing")


def test_a_second_prune_finds_nothing_left(scene):
    store, manifest = scene
    apply_prune(store, manifest, plan_prune(manifest))
    assert plan_prune(manifest).targets == []


# --------------------------------------------------------------------------
# checksums
# --------------------------------------------------------------------------


def test_checksums_cover_the_archival_core_only(scene):
    store, manifest = scene
    store.write_checksums(manifest)

    lines = store.checksums_path.read_text().strip().splitlines()
    paths = {line.split("  ", 1)[1] for line in lines}

    assert paths == {"source/original.mov", "master/scene.ply"}


def test_checksums_match_the_files_on_disk(scene):
    store, manifest = scene
    store.write_checksums(manifest)

    assert store.verify_checksums() == []


def test_verification_detects_a_modified_file(scene):
    store, manifest = scene
    store.write_checksums(manifest)
    (store.master_dir / "scene.ply").write_bytes(b"tampered")

    problems = store.verify_checksums()

    assert problems == [("master/scene.ply", "checksum mismatch")]


def test_verification_detects_a_missing_file(scene):
    store, manifest = scene
    store.write_checksums(manifest)
    (store.master_dir / "scene.ply").unlink()

    assert store.verify_checksums() == [("master/scene.ply", "missing")]


def test_pruning_does_not_invalidate_the_checksum_file(scene):
    """Working data is not checksummed, so pruning it changes nothing."""
    store, manifest = scene
    store.write_checksums(manifest)
    apply_prune(store, manifest, plan_prune(manifest))

    assert store.verify_checksums() == []


def test_source_hash_survives_a_full_round_trip(scene):
    store, manifest = scene
    expected = sha256_file(store.source_dir / "original.mov")
    apply_prune(store, manifest, plan_prune(manifest))

    assert manifest.artifact("source/original.mov").sha256 == expected


# --------------------------------------------------------------------------
# space
# --------------------------------------------------------------------------


def test_an_unmeasured_estimate_is_labelled_as_such(tmp_path: Path):
    estimate = estimate_required_space(1_000_000, tmp_path)
    assert estimate.basis == "unmeasured"
    assert "provisional" in estimate.message()


def test_a_measured_estimate_is_labelled_with_its_profile(tmp_path: Path):
    estimate = estimate_required_space(
        1_000_000, tmp_path, measured_multiplier=12.0, profile_name="compact"
    )
    assert estimate.basis == "measured:compact"
    assert estimate.estimated_required_bytes == 12_000_000
    assert "measured" in estimate.message()
