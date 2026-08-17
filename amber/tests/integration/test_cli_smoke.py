"""End-to-end CLI behaviour that must hold with no external tools installed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amber.cli import collect_doctor_report, main
from amber.models import ARCHIVAL_CORE, REGENERABLE
from amber.services.projects import SceneStore


def test_doctor_reports_missing_tools_rather_than_assuming_them(capsys):
    exit_code = main(["doctor"])
    output = capsys.readouterr().out

    report = collect_doctor_report()
    if report["ready"]:  # pragma: no cover - only on a fully provisioned Mac
        assert exit_code == 0
        return

    assert exit_code == 1, "doctor must fail when the toolchain is incomplete"
    assert "Not ready" in output
    for name, info in report["tools"].items():
        if not info["available"]:
            assert name in output


def test_doctor_json_is_machine_readable(capsys):
    main(["doctor", "--json"])
    report = json.loads(capsys.readouterr().out)

    assert report["amber_version"]
    assert "missing" in report and isinstance(report["missing"], list)
    assert report["predeclared_thresholds"]["pose_gate"]["min_registration_ratio"] == 0.8


def test_doctor_never_claims_gpu_acceleration_it_has_not_verified():
    report = collect_doctor_report()
    colmap = report["backends"]["colmap"]
    if colmap.get("available"):  # pragma: no cover - depends on the machine
        assert colmap["capabilities"]["gpu_acceleration"] == "unverified"


def test_process_rejects_a_missing_video(capsys):
    assert main(["process", "/nope/missing.mov"]) == 2
    assert "no such video" in capsys.readouterr().err


def test_process_fails_cleanly_without_ffmpeg(tmp_path: Path, capsys):
    """A missing tool must produce a diagnosis, not a stack trace."""
    import shutil

    if shutil.which("ffprobe"):  # pragma: no cover - depends on the machine
        pytest.skip("ffprobe is installed; this test covers the missing-tool path")

    video = tmp_path / "clip.mov"
    video.write_bytes(b"\x00" * 1024)
    library = tmp_path / "library"

    exit_code = main(
        ["process", str(video), "--library", str(library), "--quiet", "--title", "T"]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "amber doctor" in captured.err or "ffprobe" in captured.err
    assert "Scene kept for inspection" in captured.err

    scenes = list(library.iterdir())
    assert len(scenes) == 1, "a failed run still leaves an inspectable archive"
    assert (scenes[0] / "manifest.json").is_file()


@pytest.fixture()
def scene(tmp_path: Path) -> SceneStore:
    store = SceneStore.create(tmp_path / "library", "Living room")
    manifest = store.read_manifest()

    source = store.source_dir / "original.mov"
    source.write_bytes(b"video bytes" * 100)
    store.register_artifact(manifest, source, "source_video", ARCHIVAL_CORE)

    working = store.working_dir / "candidate-frames"
    (working / "cand_000000.png").write_bytes(b"x" * 4096)
    store.register_artifact(
        manifest, working, "candidate_frames", REGENERABLE,
        regeneration_cost_seconds=90.0,
    )
    store.write_manifest(manifest)
    store.write_checksums(manifest)
    return store


def test_inspect_reports_stages_split_and_storage(scene, capsys):
    assert main(["inspect", str(scene.root)]) == 0
    output = capsys.readouterr().out

    assert "Living room" in output
    assert "never trained on" in output
    assert "retained" in output and "prunable" in output


def test_inspect_verifies_checksums(scene, capsys):
    assert main(["inspect", str(scene.root), "--verify"]) == 0
    assert "Checksums verified." in capsys.readouterr().out


def test_inspect_detects_a_tampered_source(scene, capsys):
    (scene.source_dir / "original.mov").write_bytes(b"different")
    main(["inspect", str(scene.root), "--verify"])
    assert "checksum mismatch" in capsys.readouterr().out


def test_prune_dry_run_changes_nothing(scene, capsys):
    assert main(["prune", str(scene.root), "--dry-run"]) == 0
    output = capsys.readouterr().out

    assert "Dry run" in output
    assert "regenerate: 1.5 min" in output
    assert (scene.working_dir / "candidate-frames" / "cand_000000.png").is_file()


def test_prune_requires_explicit_confirmation(scene, capsys):
    assert main(["prune", str(scene.root)]) == 2
    assert "Refusing to prune without --working" in capsys.readouterr().err
    assert (scene.working_dir / "candidate-frames" / "cand_000000.png").is_file()


def test_prune_working_removes_only_regenerable_data(scene, capsys):
    assert main(["prune", str(scene.root), "--working"]) == 0
    assert "recipe and hash was kept" in capsys.readouterr().out

    assert not (scene.working_dir / "candidate-frames" / "cand_000000.png").exists()
    assert (scene.source_dir / "original.mov").is_file()
    assert scene.verify_checksums() == []


def test_list_shows_scenes_in_the_library(scene, capsys):
    assert main(["list", "--library", str(scene.root.parent)]) == 0
    assert "Living room" in capsys.readouterr().out


def test_retry_from_an_unknown_stage_is_rejected():
    with pytest.raises(SystemExit):
        main(["retry", "/tmp/nope", "--from", "magic"])
