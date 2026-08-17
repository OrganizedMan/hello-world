"""The evaluation split must be enforced structurally, not by trust."""

from __future__ import annotations

from pathlib import Path

import pytest

from amber.backends.poses.colmap_model import read_images_text
from amber.backends.trainers.base import ColmapDataset
from amber.backends.trainers.brush import BrushBackend, parse_flags, resolve_flags
from amber.backends.trainers.opensplat import OpenSplatBackend
from amber.config import TrainConfig
from amber.events import MemoryEventSink
from amber.models import AmberError

from tests.conftest import make_image, write_model


@pytest.fixture()
def dataset(tmp_path: Path) -> ColmapDataset:
    names = ["train_a", "train_b", "train_c", "eval_a", "eval_b"]
    model = write_model(
        tmp_path / "model",
        camera_centers=[(float(i), 0.0, 0.0) for i in range(len(names))],
        points=[(0.0, 0.0, 10.0), (1.0, 1.0, 10.0)],
        names=[f"{n}.png" for n in names],
    )
    image_dir = tmp_path / "training-frames"
    for name in names:
        make_image(image_dir / f"{name}.png")
    return ColmapDataset(
        image_dir=image_dir,
        sparse_model_dir=model,
        training_frame_ids=["train_a", "train_b", "train_c"],
        evaluation_frame_ids=["eval_a", "eval_b"],
    )


def test_the_dataset_view_contains_no_evaluation_imagery(tmp_path, dataset):
    backend = BrushBackend(tmp_path / "brush")
    view = backend.prepare_dataset_view(dataset)

    images = {p.stem for p in (view / "images").iterdir()}
    assert images == {"train_a", "train_b", "train_c"}
    assert "eval_a" not in images and "eval_b" not in images


def test_the_dataset_view_model_contains_no_evaluation_cameras(tmp_path, dataset):
    backend = BrushBackend(tmp_path / "brush")
    view = backend.prepare_dataset_view(dataset)

    names = {
        Path(img.name).stem
        for img in read_images_text(view / "sparse" / "0" / "images.txt").values()
    }
    assert names == {"train_a", "train_b", "train_c"}


def test_the_canonical_model_still_holds_every_camera(tmp_path, dataset):
    """Held-out views must remain renderable after training."""
    BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)

    names = {
        Path(img.name).stem
        for img in read_images_text(dataset.sparse_model_dir / "images.txt").values()
    }
    assert {"eval_a", "eval_b"} <= names


def test_rebuilding_the_view_does_not_accumulate_stale_images(tmp_path, dataset):
    backend = BrushBackend(tmp_path / "brush")
    backend.prepare_dataset_view(dataset)
    dataset.training_frame_ids = ["train_a"]
    view = backend.prepare_dataset_view(dataset)

    assert {p.stem for p in (view / "images").iterdir()} == {"train_a"}


def test_a_split_disagreeing_with_the_camera_model_is_refused(tmp_path, dataset):
    dataset.training_frame_ids = ["not_registered"]
    with pytest.raises(AmberError, match="split and the camera model disagree"):
        BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)


# --------------------------------------------------------------------------
# flag discovery
# --------------------------------------------------------------------------

BRUSH_HELP = """
Usage: brush [OPTIONS] <SOURCE>
Options:
  --export-path <PATH>
  --total-steps <N>
  --max-resolution <N>
"""


def test_flags_are_discovered_from_the_installed_build():
    resolved = resolve_flags(parse_flags(BRUSH_HELP))

    assert resolved["output"] == "--export-path"
    assert resolved["total_steps"] == "--total-steps"
    assert resolved["sh_degree"] is None, "this build exposes no SH flag"


def test_an_unsupported_setting_is_reported_rather_than_dropped():
    """A silently ignored flag would make the recorded config a fiction."""
    from amber.backends.trainers.brush import _optional

    events = MemoryEventSink()
    args = _optional({"sh_degree": None}, "sh_degree", 3, events)

    assert args == []
    warnings = events.of_kind("warning")
    assert len(warnings) == 1
    assert "NOT applied" in warnings[0].message


def test_a_supported_setting_is_passed_through():
    from amber.backends.trainers.brush import _optional

    events = MemoryEventSink()
    args = _optional({"total_steps": "--total-steps"}, "total_steps", 30000, events)

    assert args == ["--total-steps", "30000"]
    assert events.of_kind("warning") == []


def test_training_refuses_to_run_without_the_trainer_installed(tmp_path, dataset):
    backend = BrushBackend(tmp_path / "brush", executable="not-a-real-brush-binary")
    with pytest.raises(AmberError, match="amber doctor"):
        backend.train(dataset, TrainConfig(), MemoryEventSink())


def test_opensplat_is_registered_but_refuses_to_run(tmp_path, dataset):
    backend = OpenSplatBackend(tmp_path / "opensplat")

    health = backend.doctor()
    assert health.available is False
    assert "trainer ADR" in health.error

    with pytest.raises(AmberError, match="trainer ADR"):
        backend.train(dataset, TrainConfig(), MemoryEventSink())
