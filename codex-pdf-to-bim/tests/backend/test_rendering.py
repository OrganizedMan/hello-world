import json
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

import hearthview.rendering as rendering
from hearthview.rendering import (
    RenderFailed,
    RenderRequest,
    build_blender_command,
    create_render_job,
    detect_blender,
    load_latest_render_job,
    load_render_job,
    mark_render_interrupted,
    run_render,
)


def png_bytes(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def render_request(tmp_path: Path) -> RenderRequest:
    geometry_path = tmp_path / "approved model.glb"
    geometry_path.write_bytes(b"geometry")
    return RenderRequest(
        project_id="project-1",
        geometry_path=geometry_path,
        model_hash="b" * 64,
        geometry_hash="a" * 64,
        glb_file_hash="c" * 64,
        source_sha256="d" * 64,
        camera="KITCHEN",
        quality="DRAFT",
        width=1280,
        height=720,
    )


def test_missing_blender_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendering.shutil, "which", lambda _name: None)

    capability = detect_blender()

    assert capability.available is False
    assert capability.action == "Install Blender LTS, then restart HearthView."


def test_failed_blender_version_probe_is_not_reported_as_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "blender"
    executable.write_text("placeholder")
    monkeypatch.setattr(rendering.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(
        rendering.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[str(executable)], returncode=1, stdout="", stderr="failed"
        ),
    )

    capability = detect_blender()

    assert capability.available is False
    assert capability.action == "Install Blender LTS, then restart HearthView."


def test_render_command_uses_locked_glb_and_explicit_arguments(tmp_path: Path) -> None:
    job = create_render_job(render_request(tmp_path), tmp_path / "render jobs")

    command = build_blender_command(job, Path("/Applications/Blender.app/Contents/MacOS/Blender"))

    assert "render_scene.py" in " ".join(command)
    assert str(job.geometry_path) in command
    assert "--factory-startup" in command
    assert "--python-expr" not in command
    manifest = json.loads(job.manifest_path.read_text())
    assert manifest["geometry_hash"] == "a" * 64
    assert manifest["model_hash"] == "b" * 64
    assert manifest["glb_file_hash"] == "c" * 64
    assert manifest["source_sha256"] == "d" * 64
    assert manifest["project_id"] == "project-1"
    assert manifest["canonical_collection"] == "HV_CANONICAL"


def test_draft_render_command_uses_a_version_neutral_engine_name(tmp_path: Path) -> None:
    job = create_render_job(render_request(tmp_path), tmp_path / "render jobs")

    command = build_blender_command(job, Path("/Applications/Blender.app/Contents/MacOS/Blender"))

    engine_index = command.index("--engine") + 1
    assert command[engine_index] == "DRAFT"


def test_render_job_can_be_loaded_from_its_persisted_manifest(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    job = create_render_job(render_request(tmp_path), root)

    restored = load_render_job(root, job.id)

    assert restored == job


def test_latest_render_job_is_discovered_for_project_and_model(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    first = create_render_job(render_request(tmp_path), root)
    second = create_render_job(render_request(tmp_path), root)

    restored = load_latest_render_job(root, "project-1", "b" * 64)

    assert restored.id == second.id
    assert restored.id != first.id


def test_interrupted_persisted_render_becomes_failed(tmp_path: Path) -> None:
    job = create_render_job(render_request(tmp_path), tmp_path / "jobs")

    mark_render_interrupted(job)

    manifest = json.loads(job.manifest_path.read_text())
    assert manifest["status"] == "FAILED"
    assert manifest["error"] == "INTERRUPTED_RENDER"


def test_render_job_loader_rejects_path_like_ids(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        load_render_job(tmp_path / "jobs", "../manifest")


def test_render_timeout_is_reported_without_shell_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_render_job(render_request(tmp_path), tmp_path / "jobs")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["blender"], timeout=2)

    monkeypatch.setattr(rendering.subprocess, "run", timeout)

    with pytest.raises(RenderFailed, match="timed out"):
        run_render(job, Path("/opt/blender"), timeout_seconds=2)

    assert "timed out" in job.log_path.read_text().lower()


def test_completed_render_preserves_blender_geometry_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_render_job(render_request(tmp_path), tmp_path / "jobs")

    def successful_blender(*_args, **_kwargs):
        manifest = json.loads(job.manifest_path.read_text())
        manifest["canonical_signature"] = [{"name": "verified-wall"}]
        manifest["quality_checks"] = {
            "canonical_geometry_unchanged": True,
            "external_textures_missing": False,
        }
        job.manifest_path.write_text(json.dumps(manifest))
        job.output_path.write_bytes(png_bytes(job.width, job.height))
        return subprocess.CompletedProcess(args=["blender"], returncode=0, stdout="done", stderr="")

    monkeypatch.setattr(rendering.subprocess, "run", successful_blender)

    run_render(job, Path("/opt/blender"))

    manifest = json.loads(job.manifest_path.read_text())
    assert manifest["canonical_signature"] == [{"name": "verified-wall"}]


def test_invalid_or_wrong_size_png_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_render_job(render_request(tmp_path), tmp_path / "jobs")

    def invalid_output(*_args, **_kwargs):
        job.output_path.write_bytes(b"not a png")
        return subprocess.CompletedProcess(args=["blender"], returncode=0, stdout="done", stderr="")

    monkeypatch.setattr(rendering.subprocess, "run", invalid_output)

    with pytest.raises(RenderFailed, match="verified PNG"):
        run_render(job, Path("/opt/blender"))

    assert json.loads(job.manifest_path.read_text())["status"] == "FAILED"
