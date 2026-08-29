"""How the evaluation split is enforced against the trainer (ADR 0004).

Brush can only render an evaluation set it selected itself, by stride, and has
no render-from-given-cameras mode. So the dataset view is built so that Brush's
own stride selection lands on exactly the frames Amber locked. That alignment is
checked arithmetically before training, and the set Brush actually rendered is
checked afterwards. Neither check may be downgraded to a warning: they are the
only thing standing between "held out" and "scored on whatever the trainer felt
like holding out".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amber.backends.poses.colmap_model import read_images_text
from amber.backends.trainers.base import ColmapDataset
from amber.backends.trainers.brush import (
    BrushBackend,
    parse_flags,
    resolve_flags,
    stride_for_split,
)
from amber.backends.trainers.opensplat import OpenSplatBackend
from amber.config import TrainConfig
from amber.events import MemoryEventSink
from amber.models import AmberError

from tests.conftest import make_image, write_model

FRAME_IDS = [f"cand_{i:06d}" for i in range(8)]
EVAL_IDS = ["cand_000000", "cand_000004"]  # positions 0 and 4 → stride 4
TRAIN_IDS = [i for i in FRAME_IDS if i not in EVAL_IDS]


@pytest.fixture()
def dataset(tmp_path: Path) -> ColmapDataset:
    model = write_model(
        tmp_path / "model",
        camera_centers=[(float(i), 0.0, 0.0) for i in range(len(FRAME_IDS))],
        points=[(0.0, 0.0, 10.0), (1.0, 1.0, 10.0)],
        names=[f"{n}.png" for n in FRAME_IDS],
    )
    training_dir = tmp_path / "training-frames"
    evaluation_dir = tmp_path / "evaluation-frames"
    for frame_id in TRAIN_IDS:
        make_image(training_dir / f"{frame_id}.png")
    for frame_id in EVAL_IDS:
        make_image(evaluation_dir / f"{frame_id}.png")

    return ColmapDataset(
        image_dir=training_dir,
        evaluation_image_dir=evaluation_dir,
        sparse_model_dir=model,
        training_frame_ids=TRAIN_IDS,
        evaluation_frame_ids=EVAL_IDS,
    )


# --------------------------------------------------------------------------
# stride arithmetic
# --------------------------------------------------------------------------


def test_an_every_nth_split_resolves_to_that_stride():
    ordered = [f"f{i:03d}" for i in range(64)]
    evaluation = ordered[::8]
    assert stride_for_split(ordered, evaluation) == 8


def test_a_single_held_out_frame_uses_the_whole_length_as_stride():
    ordered = [f"f{i:03d}" for i in range(10)]
    assert stride_for_split(ordered, ["f000"]) == 10


def test_a_split_not_starting_at_the_first_frame_is_refused():
    """The trainer's stride always begins at index 0; offset 7 would misalign."""
    ordered = [f"f{i:03d}" for i in range(64)]
    with pytest.raises(AmberError, match="begins at position 0"):
        stride_for_split(ordered, ordered[7::8])


def test_an_irregularly_spaced_split_is_refused():
    """A stratified comparison split is not stride-expressible."""
    ordered = [f"f{i:03d}" for i in range(20)]
    with pytest.raises(AmberError, match="spaced irregularly"):
        stride_for_split(ordered, ["f000", "f003", "f011"])


def test_a_stride_that_would_hold_out_extra_frames_is_refused():
    ordered = [f"f{i:03d}" for i in range(20)]
    with pytest.raises(AmberError, match="refusing to train"):
        stride_for_split(ordered, ["f000", "f005"])


def test_an_empty_split_is_refused():
    with pytest.raises(AmberError, match="no evaluation frames"):
        stride_for_split(["f000", "f001"], [])


# --------------------------------------------------------------------------
# dataset view
# --------------------------------------------------------------------------


def test_the_view_contains_every_frame_and_records_the_stride(tmp_path, dataset):
    view = BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)

    images = {p.stem for p in (view.path / "images").iterdir()}
    assert images == set(FRAME_IDS)
    assert view.stride == 4
    assert view.expected_evaluation_ids == sorted(EVAL_IDS)


def test_the_stride_would_select_exactly_the_locked_evaluation_set(tmp_path, dataset):
    view = BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)
    selected = [view.ordered_frame_ids[i] for i in range(0, 8, view.stride)]

    assert sorted(selected) == sorted(EVAL_IDS)


def test_the_view_model_covers_every_split_frame(tmp_path, dataset):
    view = BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)

    names = {
        Path(img.name).stem
        for img in read_images_text(view.path / "sparse" / "0" / "images.txt").values()
    }
    assert names == set(FRAME_IDS)


def test_the_canonical_model_is_not_modified(tmp_path, dataset):
    before = (dataset.sparse_model_dir / "images.txt").read_text()
    BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)
    assert (dataset.sparse_model_dir / "images.txt").read_text() == before


def test_rebuilding_the_view_does_not_accumulate_stale_images(tmp_path, dataset):
    backend = BrushBackend(tmp_path / "brush")
    backend.prepare_dataset_view(dataset)

    dataset.training_frame_ids = ["cand_000001"]
    dataset.evaluation_frame_ids = ["cand_000000"]
    view = backend.prepare_dataset_view(dataset)

    assert {p.stem for p in (view.path / "images").iterdir()} == {
        "cand_000000",
        "cand_000001",
    }


def test_a_frame_in_both_roles_is_refused(tmp_path, dataset):
    dataset.training_frame_ids = TRAIN_IDS + ["cand_000000"]
    with pytest.raises(AmberError, match="both training and evaluation"):
        BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)


def test_a_split_naming_a_missing_image_is_refused(tmp_path, dataset):
    dataset.training_frame_ids = TRAIN_IDS + ["cand_999999"]
    with pytest.raises(AmberError, match="missing from disk"):
        BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)


def test_a_split_the_camera_model_does_not_cover_is_refused(tmp_path, dataset):
    """Every split frame needs a camera, or its render has no viewpoint.

    The model is short one camera while the split and images are unchanged, so
    the stride arithmetic passes and the coverage check is what catches it.
    """
    short = FRAME_IDS[:-1]
    dataset.sparse_model_dir = write_model(
        tmp_path / "short-model",
        camera_centers=[(float(i), 0.0, 0.0) for i in range(len(short))],
        points=[(0.0, 0.0, 10.0)],
        names=[f"{n}.png" for n in short],
    )
    with pytest.raises(AmberError, match="camera model covers 7 of 8"):
        BrushBackend(tmp_path / "brush").prepare_dataset_view(dataset)


# --------------------------------------------------------------------------
# verifying what the trainer actually rendered
# --------------------------------------------------------------------------


def write_renders(directory: Path, frame_ids: list[str]) -> Path:
    for frame_id in frame_ids:
        make_image(directory / f"{frame_id}.png")
    return directory


def test_the_latest_evaluation_pass_is_used(tmp_path):
    backend = BrushBackend(tmp_path / "brush")
    write_renders(backend.output_dir / "eval_1000", EVAL_IDS)
    write_renders(backend.output_dir / "eval_30000", EVAL_IDS)

    render_dir, rendered = backend.collect_evaluation_renders(EVAL_IDS)

    assert render_dir.name == "eval_30000", "step 30000 is later than step 1000"
    assert rendered == sorted(EVAL_IDS)


def test_a_missing_held_out_render_fails_the_run(tmp_path):
    """Not permission to score a smaller test set."""
    backend = BrushBackend(tmp_path / "brush")
    write_renders(backend.output_dir / "eval_200", ["cand_000000"])

    with pytest.raises(AmberError, match="1 missing"):
        backend.collect_evaluation_renders(EVAL_IDS)


def test_an_unexpected_held_out_render_fails_the_run(tmp_path):
    backend = BrushBackend(tmp_path / "brush")
    write_renders(backend.output_dir / "eval_200", EVAL_IDS + ["cand_000003"])

    with pytest.raises(AmberError, match="unexpected"):
        backend.collect_evaluation_renders(EVAL_IDS)


def test_no_evaluation_renders_at_all_fails_the_run(tmp_path):
    backend = BrushBackend(tmp_path / "brush")
    backend.output_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(AmberError, match="did not measure"):
        backend.collect_evaluation_renders(EVAL_IDS)


# --------------------------------------------------------------------------
# flag discovery — measured against the real v0.3.0 help output
# --------------------------------------------------------------------------

BRUSH_HELP = """
Usage: brush [OPTIONS] [PATH_OR_URL]
Options:
      --with-viewer
Training options:
      --total-steps <TOTAL_STEPS>
Refine options:
      --max-splats <MAX_SPLATS>
Model Options:
      --sh-degree <SH_DEGREE>
Dataset Options:
      --max-resolution <MAX_RESOLUTION>
      --eval-split-every <EVAL_SPLIT_EVERY>
Process options:
      --eval-save-to-disk
      --export-path <EXPORT_PATH>
      --export-name <EXPORT_NAME>
"""


def test_every_needed_flag_is_found_in_the_real_help_output():
    resolved = resolve_flags(parse_flags(BRUSH_HELP))

    assert resolved["output"] == "--export-path"
    assert resolved["total_steps"] == "--total-steps"
    assert resolved["max_resolution"] == "--max-resolution"
    assert resolved["sh_degree"] == "--sh-degree"
    assert resolved["max_splats"] == "--max-splats"
    assert resolved["eval_split"] == "--eval-split-every"
    assert resolved["eval_save_to_disk"] == "--eval-save-to-disk"


def test_a_build_without_the_eval_flags_is_unusable():
    """Without them there is no way to obtain held-out renders at all."""
    from amber.backends.trainers.brush import REQUIRED_CAPABILITIES

    resolved = resolve_flags(parse_flags("Options:\n  --export-path <P>\n"))
    missing = [c for c in REQUIRED_CAPABILITIES if resolved.get(c) is None]

    assert missing == ["eval_split", "eval_save_to_disk"]


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
