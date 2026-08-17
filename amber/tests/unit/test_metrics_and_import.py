from __future__ import annotations

from pathlib import Path

import pytest

from amber.models import AmberError
from amber.pipeline.import_video import assess_footage, parse_probe
from amber.pipeline.quality import (
    FAIL,
    MotionArtifactReview,
    NOT_APPLICABLE,
    PASS,
    evaluate_holdout,
    psnr,
    ssim,
)

from tests.conftest import make_image, make_noisy_image


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------


def test_identical_images_have_infinite_psnr_and_unit_ssim():
    import numpy as np

    image = np.full((32, 32), 0.5)
    assert psnr(image, image) == float("inf")
    assert ssim(image, image) == pytest.approx(1.0)


def test_psnr_falls_as_error_grows():
    import numpy as np

    base = np.full((32, 32), 0.5)
    near = base + 0.01
    far = base + 0.2

    assert psnr(base, near) > psnr(base, far)


def test_ssim_is_lower_for_structurally_different_images():
    import numpy as np

    rng = np.random.default_rng(0)
    base = rng.random((64, 64))
    noise = rng.random((64, 64))

    assert ssim(base, base * 0.99) > ssim(base, noise)


def test_comparing_mismatched_shapes_is_refused():
    import numpy as np

    with pytest.raises(AmberError, match="different shapes"):
        psnr(np.zeros((4, 4)), np.zeros((5, 5)))


def test_ssim_needs_enough_pixels_for_its_window():
    import numpy as np

    with pytest.raises(AmberError, match="at least 11px"):
        ssim(np.zeros((8, 8)), np.zeros((8, 8)))


def test_holdout_evaluation_matches_renders_to_sources(tmp_path: Path):
    renders, sources = tmp_path / "renders", tmp_path / "sources"
    for frame_id in ("e0", "e1"):
        make_noisy_image(sources / f"{frame_id}.png", seed=1)
        make_noisy_image(renders / f"{frame_id}.png", seed=1)

    metrics = evaluate_holdout(renders, sources, ["e0", "e1"])

    assert len(metrics.views) == 2
    assert metrics.missing_renders == []
    assert metrics.aggregate()["count"] == 2


def test_a_missing_render_is_recorded_not_skipped_silently(tmp_path: Path):
    renders, sources = tmp_path / "renders", tmp_path / "sources"
    make_image(sources / "e0.png")
    make_image(sources / "e1.png")
    make_image(renders / "e0.png")

    metrics = evaluate_holdout(renders, sources, ["e0", "e1"])

    assert metrics.missing_renders == ["e1"]
    assert len(metrics.views) == 1


# --------------------------------------------------------------------------
# motion-artifact review
# --------------------------------------------------------------------------


def test_a_failed_motion_review_blocks_success():
    review = MotionArtifactReview(verdict=FAIL, subjects=["person"], required=True)
    assert review.blocks_success


def test_a_required_but_unreviewed_capture_blocks_success():
    """Silence is not a pass when the capture could contain movement."""
    assert MotionArtifactReview(verdict=NOT_APPLICABLE, required=True).blocks_success


def test_a_passed_review_does_not_block():
    assert not MotionArtifactReview(verdict=PASS, required=True).blocks_success


def test_a_capture_that_needs_no_review_does_not_block():
    assert not MotionArtifactReview(verdict=NOT_APPLICABLE, required=False).blocks_success


def test_an_invalid_verdict_is_refused():
    with pytest.raises(AmberError, match="verdict must be one of"):
        MotionArtifactReview(verdict="probably fine")


# --------------------------------------------------------------------------
# import metadata
# --------------------------------------------------------------------------


def probe_payload(**stream_overrides):
    stream = {
        "codec_type": "video",
        "codec_name": "hevc",
        "width": 3840,
        "height": 2160,
        "r_frame_rate": "30/1",
        "avg_frame_rate": "30/1",
        "color_transfer": "bt709",
        "color_primaries": "bt709",
    }
    stream.update(stream_overrides)
    return {
        "streams": [stream],
        "format": {
            "duration": "62.5",
            "bit_rate": "45000000",
            "tags": {
                "creation_time": "2026-08-16T10:30:00.000000Z",
                "com.apple.quicktime.model": "iPhone 16 Pro",
            },
        },
    }


def test_core_metadata_is_read():
    meta = parse_probe(probe_payload(), "IMG_1234.MOV")

    assert meta.device == "iPhone 16 Pro"
    assert meta.duration_seconds == 62.5
    assert meta.long_edge == 3840
    assert meta.nominal_frame_rate == 30.0
    assert meta.creation_time.startswith("2026-08-16")


def test_hlg_footage_is_detected_as_hdr():
    meta = parse_probe(probe_payload(color_transfer="arib-std-b67"), "a.mov")
    assert meta.is_hdr and meta.hdr_kind == "hlg"


def test_pq_footage_is_detected_as_hdr():
    meta = parse_probe(probe_payload(color_transfer="smpte2084"), "a.mov")
    assert meta.is_hdr and meta.hdr_kind == "pq"


def test_variable_frame_rate_is_detected():
    meta = parse_probe(
        probe_payload(r_frame_rate="30/1", avg_frame_rate="2997/125"), "a.mov"
    )
    assert meta.variable_frame_rate


def test_rotation_metadata_is_normalised():
    meta = parse_probe(
        probe_payload(side_data_list=[{"rotation": -90}]), "a.mov"
    )
    assert meta.rotation == 270


def test_a_file_without_a_video_stream_is_refused():
    with pytest.raises(AmberError, match="no video stream"):
        parse_probe({"streams": [{"codec_type": "audio"}], "format": {}}, "a.mov")


def test_a_short_clip_produces_a_warning_not_a_refusal():
    health = assess_footage(parse_probe(probe_payload(), "a.mov"))
    assert health.warnings == []

    payload = probe_payload()
    payload["format"]["duration"] = "8.0"
    health = assess_footage(parse_probe(payload, "a.mov"))
    assert any("under about 30s" in w for w in health.warnings)


def test_hdr_footage_notes_that_the_original_is_preserved():
    health = assess_footage(parse_probe(probe_payload(color_transfer="arib-std-b67"), "a.mov"))
    assert any("preserved untouched" in note for note in health.notes)


def test_gps_metadata_is_flagged_as_local_only():
    payload = probe_payload()
    payload["format"]["tags"]["com.apple.quicktime.location.ISO6709"] = "+51.5-0.1/"
    health = assess_footage(parse_probe(payload, "a.mov"))
    assert any("stays local" in note for note in health.notes)
