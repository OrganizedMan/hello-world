from __future__ import annotations

import json
from pathlib import Path

import pytest

from amber.models import (
    ARCHIVAL_CORE,
    Artifact,
    DERIVED_CACHE,
    Manifest,
    PRUNED,
    REGENERABLE,
    RetentionError,
    Split,
    SplitLockedError,
)
from amber.services.projects import SceneStore


def test_manifest_round_trips_through_json():
    manifest = Manifest(title="Backyard after the rain")
    manifest.add_artifact(
        Artifact(path="master/scene.ply", role="master_ply", retention_class=ARCHIVAL_CORE, bytes=10)
    )
    restored = Manifest.from_dict(json.loads(json.dumps(manifest.to_dict())))

    assert restored.title == manifest.title
    assert restored.scene_id == manifest.scene_id
    assert restored.schema_version == 1
    assert [a.path for a in restored.artifacts] == ["master/scene.ply"]


def test_artifact_requires_a_known_retention_class():
    with pytest.raises(RetentionError, match="unknown retention class"):
        Artifact(path="x", role="r", retention_class="whatever")


def test_adding_the_same_path_replaces_rather_than_duplicates():
    manifest = Manifest()
    manifest.add_artifact(
        Artifact(path="p", role="r", retention_class=REGENERABLE, bytes=1)
    )
    manifest.add_artifact(
        Artifact(path="p", role="r", retention_class=REGENERABLE, bytes=2)
    )
    assert len(manifest.artifacts) == 1
    assert manifest.artifacts[0].bytes == 2


def test_marking_pruned_keeps_the_recipe_and_prior_size():
    manifest = Manifest()
    manifest.add_artifact(
        Artifact(
            path="working/colmap",
            role="colmap_workspace",
            retention_class=REGENERABLE,
            bytes=5000,
            sha256="abc",
            regeneration_cost_seconds=600.0,
        )
    )
    manifest.mark_pruned("working/colmap")

    art = manifest.artifact("working/colmap")
    assert art.status == PRUNED
    assert art.bytes == 0
    assert art.prior_bytes == 5000
    assert art.sha256 == "abc", "the hash is the recipe; pruning must not erase it"
    assert art.regeneration_cost_seconds == 600.0


def test_the_archival_core_cannot_be_pruned():
    manifest = Manifest()
    manifest.add_artifact(
        Artifact(path="source/original.mov", role="source_video", retention_class=ARCHIVAL_CORE)
    )
    with pytest.raises(RetentionError, match="archival core"):
        manifest.mark_pruned("source/original.mov")


def test_byte_accounting_separates_retained_from_prunable():
    manifest = Manifest()
    manifest.add_artifact(
        Artifact(path="a", role="r", retention_class=ARCHIVAL_CORE, bytes=100)
    )
    manifest.add_artifact(
        Artifact(path="b", role="r", retention_class=REGENERABLE, bytes=250)
    )
    manifest.add_artifact(
        Artifact(path="c", role="r", retention_class=DERIVED_CACHE, bytes=50)
    )
    assert manifest.retained_bytes() == 400
    assert manifest.prunable_bytes() == 300


def test_manifest_writes_are_atomic(tmp_path: Path):
    store = SceneStore.create(tmp_path, "Test scene")
    manifest = store.read_manifest()
    manifest.title = "Renamed"
    store.write_manifest(manifest)

    leftovers = [p for p in store.root.iterdir() if p.name.startswith(".manifest")]
    assert leftovers == [], "temporary files must not survive a successful write"
    assert store.read_manifest().title == "Renamed"


def test_split_must_be_disjoint():
    split = Split(training_frame_ids=["a", "b"], evaluation_frame_ids=["b"])
    with pytest.raises(Exception, match="never supervise training"):
        split.validate_disjoint()


def test_a_locked_split_cannot_be_replaced():
    manifest = Manifest()
    manifest.set_split(
        Split(training_frame_ids=["a", "b"], evaluation_frame_ids=["c"])
    )
    manifest.lock_split()

    with pytest.raises(SplitLockedError, match="new scene version"):
        manifest.set_split(
            Split(training_frame_ids=["a", "c"], evaluation_frame_ids=["b"])
        )


def test_reapplying_an_identical_split_is_allowed():
    """Resuming a stage re-applies the same split; that is not a change."""
    manifest = Manifest()
    split = Split(training_frame_ids=["a", "b"], evaluation_frame_ids=["c"])
    manifest.set_split(split)
    manifest.lock_split()

    manifest.set_split(
        Split(training_frame_ids=["a", "b"], evaluation_frame_ids=["c"])
    )
    assert manifest.frame_config.evaluation_frame_ids == ["c"]
