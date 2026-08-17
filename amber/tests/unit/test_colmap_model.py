from __future__ import annotations

from pathlib import Path

from amber.backends.poses.base import PoseFrame
from amber.backends.poses.colmap import (
    parse_available_commands,
    parse_help_options,
    resolve_option,
    temporal_gaps,
)
from amber.backends.poses.colmap_model import (
    model_stats,
    read_images_text,
    write_filtered_model,
)

from tests.conftest import write_model


def test_camera_centres_are_recovered_from_pose_vectors(healthy_model: Path):
    images = read_images_text(healthy_model / "images.txt")
    centers = sorted(img.center[0] for img in images.values())
    assert centers == [-1.0, 0.0, 1.0]


def test_a_real_baseline_produces_measurable_parallax(healthy_model: Path):
    stats = model_stats(healthy_model)

    assert stats.registered_images == 3
    assert stats.sparse_point_count == 3
    assert stats.camera_path_extent == 2.0
    assert 9.0 < stats.median_scene_depth < 11.0
    assert stats.median_triangulation_angle_deg > 10.0


def test_a_pure_pan_produces_no_baseline_and_no_parallax(pure_pan_model: Path):
    stats = model_stats(pure_pan_model)

    assert stats.camera_path_extent == 0.0
    assert stats.median_triangulation_angle_deg == 0.0


def test_track_lengths_and_reprojection_error_are_read(healthy_model: Path):
    stats = model_stats(healthy_model)
    assert stats.median_observations_per_point == 3
    assert stats.mean_reprojection_error_px == 0.5


def test_filtering_a_model_removes_the_evaluation_cameras(tmp_path: Path):
    source = write_model(
        tmp_path / "full",
        camera_centers=[(float(i), 0.0, 0.0) for i in range(4)],
        points=[(0.0, 0.0, 10.0), (1.0, 0.0, 10.0)],
        names=["train_a.png", "train_b.png", "eval_a.png", "train_c.png"],
    )
    destination = tmp_path / "view"

    kept = write_filtered_model(
        source, destination, {"train_a", "train_b", "train_c"}
    )

    assert kept == 3
    names = {img.name for img in read_images_text(destination / "images.txt").values()}
    assert names == {"train_a.png", "train_b.png", "train_c.png"}
    assert "eval_a.png" not in names


def test_filtering_drops_points_that_lose_their_observers(tmp_path: Path):
    source = write_model(
        tmp_path / "full",
        camera_centers=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        points=[(0.0, 0.0, 10.0)],
        names=["a.png", "b.png"],
    )
    destination = tmp_path / "view"
    write_filtered_model(source, destination, {"a"})

    stats = model_stats(destination)
    assert stats.registered_images == 1
    assert stats.sparse_point_count == 0, "a single observation cannot triangulate"


def test_cameras_file_is_carried_over(tmp_path: Path, healthy_model: Path):
    destination = tmp_path / "view"
    write_filtered_model(healthy_model, destination, {"cand_000000"})
    assert (destination / "cameras.txt").is_file()


# --------------------------------------------------------------------------
# help parsing — flags are discovered, never assumed
# --------------------------------------------------------------------------

HELP_TEXT = """
Options:
  --database_path arg
  --image_path arg
  --FeatureExtraction.max_image_size arg (=3200)
  --FeatureExtraction.max_num_features arg (=8192)
  --ImageReader.camera_model arg (=SIMPLE_RADIAL)
"""

OLD_HELP_TEXT = """
Options:
  --SiftExtraction.max_image_size arg (=3200)
"""


def test_option_defaults_are_read_from_help_output():
    options = parse_help_options(HELP_TEXT)
    assert options["FeatureExtraction.max_image_size"] == "3200"
    assert options["ImageReader.camera_model"] == "SIMPLE_RADIAL"
    assert options["database_path"] is None


def test_the_current_option_name_is_preferred_when_present():
    from amber.backends.poses.colmap import MAX_IMAGE_SIZE_OPTIONS

    options = parse_help_options(HELP_TEXT)
    assert (
        resolve_option(options, MAX_IMAGE_SIZE_OPTIONS)
        == "FeatureExtraction.max_image_size"
    )


def test_an_older_build_falls_back_to_its_own_option_name():
    from amber.backends.poses.colmap import MAX_IMAGE_SIZE_OPTIONS

    options = parse_help_options(OLD_HELP_TEXT)
    assert (
        resolve_option(options, MAX_IMAGE_SIZE_OPTIONS)
        == "SiftExtraction.max_image_size"
    )


def test_an_unsupported_option_resolves_to_nothing():
    assert resolve_option(parse_help_options(""), ("Some.option",)) is None


def test_available_commands_are_parsed_from_the_command_list():
    commands = parse_available_commands(
        "Commands:\n  feature_extractor\n  mapper\n  global_mapper\n  -h\n"
    )
    assert {"feature_extractor", "mapper", "global_mapper"} <= commands


# --------------------------------------------------------------------------
# temporal gaps
# --------------------------------------------------------------------------


def pose_frames(count: int, fps: float = 4.0) -> list[PoseFrame]:
    return [
        PoseFrame(id=f"f{i:03d}", path=Path(f"f{i}.png"), timestamp=i / fps, role="train")
        for i in range(count)
    ]


def test_no_gap_when_everything_registers():
    frames = pose_frames(10)
    seconds, run = temporal_gaps(frames, {f.id for f in frames})
    assert (seconds, run) == (0.0, 0)


def test_a_dropped_middle_section_is_measured_both_ways():
    frames = pose_frames(12)
    registered = {f.id for f in frames} - {"f004", "f005", "f006"}

    seconds, run = temporal_gaps(frames, registered)

    assert run == 3
    assert seconds == 1.0  # f003 at 0.75s to f007 at 1.75s


def test_a_trailing_dropout_is_still_counted():
    frames = pose_frames(8)
    registered = {f.id for f in frames} - {"f006", "f007"}

    seconds, run = temporal_gaps(frames, registered)

    assert run == 2
    assert seconds > 0


def test_the_longest_gap_wins_when_there_are_several():
    frames = pose_frames(20)
    registered = {f.id for f in frames} - {"f002", "f010", "f011", "f012", "f013"}

    _seconds, run = temporal_gaps(frames, registered)

    assert run == 4
