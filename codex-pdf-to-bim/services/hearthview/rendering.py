from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


CameraName = Literal["PLAN", "AXONOMETRIC", "KITCHEN", "LIVING_ROOM"]
RenderQuality = Literal["DRAFT", "FINAL"]
VisualStyle = Literal["WARM_BLANK_SLATE"]


class RenderFailed(RuntimeError):
    """Raised when Blender cannot produce a verified still image."""


@dataclass(frozen=True)
class BlenderCapability:
    available: bool
    executable: str | None
    version: str | None
    message: str
    action: str | None


@dataclass(frozen=True)
class RenderRequest:
    project_id: str
    geometry_path: Path
    model_hash: str
    geometry_hash: str
    glb_file_hash: str
    source_sha256: str
    camera: CameraName
    quality: RenderQuality
    width: int
    height: int
    style: VisualStyle = "WARM_BLANK_SLATE"


@dataclass(frozen=True)
class RenderJob:
    id: str
    project_id: str
    created_at_ns: int
    geometry_path: Path
    model_hash: str
    geometry_hash: str
    glb_file_hash: str
    source_sha256: str
    camera: CameraName
    quality: RenderQuality
    width: int
    height: int
    style: VisualStyle
    job_dir: Path
    output_path: Path
    manifest_path: Path
    log_path: Path


@dataclass(frozen=True)
class RenderArtifact:
    job_id: str
    output_path: Path
    sha256: str
    byte_count: int


def detect_blender() -> BlenderCapability:
    configured = os.environ.get("HEARTHVIEW_BLENDER")
    candidate = configured or shutil.which("blender")
    if not candidate or not Path(candidate).is_file():
        return BlenderCapability(
            available=False,
            executable=None,
            version=None,
            message="Photoreal rendering needs Blender LTS. You can still use interactive 3D without it.",
            action="Install Blender LTS, then restart HearthView.",
        )
    try:
        completed = subprocess.run(
            [candidate, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        first_line = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
        if completed.returncode != 0 or not first_line.startswith("Blender"):
            raise OSError("Blender version probe failed.")
    except (OSError, subprocess.SubprocessError):
        return BlenderCapability(
            available=False,
            executable=None,
            version=None,
            message="HearthView found Blender but could not start it.",
            action="Install Blender LTS, then restart HearthView.",
        )
    return BlenderCapability(
        available=True,
        executable=str(Path(candidate).resolve()),
        version=first_line,
        message="Blender is ready for local photoreal rendering.",
        action=None,
    )


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _manifest_for(job: RenderJob, status: str) -> dict[str, object]:
    payload = asdict(job)
    payload = {key: str(value) if isinstance(value, Path) else value for key, value in payload.items()}
    payload.update({
        "status": status,
        "canonical_collection": "HV_CANONICAL",
        "styling_collection": "HV_STYLING",
    })
    return payload


def _png_dimensions(content: bytes) -> tuple[int, int]:
    if (
        len(content) < 24
        or content[:8] != b"\x89PNG\r\n\x1a\n"
        or content[12:16] != b"IHDR"
    ):
        raise ValueError("Output is not a PNG with an IHDR header.")
    width, height = struct.unpack_from(">II", content, 16)
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive.")
    return width, height


def _record_failure(job: RenderJob, error_code: str) -> None:
    try:
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    manifest.update(_manifest_for(job, "FAILED"))
    manifest["error"] = error_code
    _write_manifest(job.manifest_path, manifest)


def create_render_job(request: RenderRequest, jobs_root: Path) -> RenderJob:
    geometry_path = request.geometry_path.resolve(strict=True)
    root = jobs_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    job_dir = root / job_id
    job_dir.mkdir(mode=0o700)
    job = RenderJob(
        id=job_id,
        project_id=request.project_id,
        created_at_ns=time.time_ns(),
        geometry_path=geometry_path,
        model_hash=request.model_hash,
        geometry_hash=request.geometry_hash,
        glb_file_hash=request.glb_file_hash,
        source_sha256=request.source_sha256,
        camera=request.camera,
        quality=request.quality,
        width=request.width,
        height=request.height,
        style=request.style,
        job_dir=job_dir,
        output_path=job_dir / "warm-blank-slate.png",
        manifest_path=job_dir / "manifest.json",
        log_path=job_dir / "blender.log",
    )
    _write_manifest(job.manifest_path, _manifest_for(job, "QUEUED"))
    return job


def load_render_job(jobs_root: Path, job_id: str) -> RenderJob:
    try:
        parsed_id = str(uuid.UUID(job_id))
    except ValueError as error:
        raise KeyError(job_id) from error
    if parsed_id != job_id:
        raise KeyError(job_id)
    root = jobs_root.resolve()
    job_dir = root / job_id
    manifest_path = job_dir / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        job = RenderJob(
            id=str(payload["id"]),
            project_id=str(payload.get("project_id", "")),
            created_at_ns=int(payload.get("created_at_ns", manifest_path.stat().st_mtime_ns)),
            geometry_path=Path(str(payload["geometry_path"])).resolve(strict=True),
            model_hash=str(payload.get("model_hash", "")),
            geometry_hash=str(payload["geometry_hash"]),
            glb_file_hash=str(payload.get("glb_file_hash", "")),
            source_sha256=str(payload.get("source_sha256", "")),
            camera=str(payload["camera"]),  # type: ignore[arg-type]
            quality=str(payload["quality"]),  # type: ignore[arg-type]
            width=int(payload["width"]),
            height=int(payload["height"]),
            style=str(payload["style"]),  # type: ignore[arg-type]
            job_dir=job_dir,
            output_path=job_dir / "warm-blank-slate.png",
            manifest_path=manifest_path,
            log_path=job_dir / "blender.log",
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        raise KeyError(job_id) from error
    if job.id != job_id:
        raise KeyError(job_id)
    return job


def load_latest_render_job(
    jobs_root: Path,
    project_id: str,
    model_hash: str,
) -> RenderJob:
    root = jobs_root.resolve()
    if not root.is_dir():
        raise KeyError(project_id)
    candidates: list[RenderJob] = []
    for job_dir in root.iterdir():
        if not job_dir.is_dir():
            continue
        try:
            job = load_render_job(root, job_dir.name)
        except KeyError:
            continue
        if job.project_id == project_id and job.model_hash == model_hash:
            candidates.append(job)
    if not candidates:
        raise KeyError(project_id)
    return max(candidates, key=lambda job: job.created_at_ns)


def mark_render_interrupted(job: RenderJob) -> None:
    try:
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    if manifest.get("status") not in {"QUEUED", "RUNNING"}:
        return
    manifest.update(_manifest_for(job, "FAILED"))
    manifest["error"] = "INTERRUPTED_RENDER"
    _write_manifest(job.manifest_path, manifest)


def _scene_script() -> Path:
    return Path(__file__).resolve().parents[1] / "blender" / "render_scene.py"


def build_blender_command(job: RenderJob, blender_executable: Path) -> list[str]:
    return [
        str(blender_executable),
        "--background",
        "--factory-startup",
        "--python",
        str(_scene_script()),
        "--",
        "--geometry",
        str(job.geometry_path),
        "--output",
        str(job.output_path),
        "--manifest",
        str(job.manifest_path),
        "--camera",
        job.camera,
        "--engine",
        job.quality,
        "--width",
        str(job.width),
        "--height",
        str(job.height),
        "--style",
        job.style,
    ]


def run_render(job: RenderJob, blender_executable: Path, timeout_seconds: int = 900) -> RenderArtifact:
    _write_manifest(job.manifest_path, _manifest_for(job, "RUNNING"))
    command = build_blender_command(job, blender_executable)
    environment = {
        "PATH": str(blender_executable.parent),
        "TMPDIR": tempfile.gettempdir(),
        "LC_ALL": "C.UTF-8",
    }
    try:
        completed = subprocess.run(
            command,
            cwd=job.job_dir,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        job.log_path.write_text(
            f"Blender render timed out after {timeout_seconds} seconds.\n",
            encoding="utf-8",
        )
        _record_failure(job, "RENDER_TIMEOUT")
        raise RenderFailed(f"Blender render timed out after {timeout_seconds} seconds.") from error
    except (OSError, subprocess.SubprocessError) as error:
        job.log_path.write_text(f"Blender could not be started: {error}\n", encoding="utf-8")
        _record_failure(job, "BLENDER_START_FAILED")
        raise RenderFailed("Blender could not be started for this render.") from error
    log = f"{completed.stdout}\n{completed.stderr}".strip() + "\n"
    job.log_path.write_text(log, encoding="utf-8")
    if completed.returncode != 0 or not job.output_path.is_file():
        _record_failure(job, "BLENDER_RENDER_FAILED")
        raise RenderFailed("Blender did not produce the requested still image.")
    content = job.output_path.read_bytes()
    try:
        width, height = _png_dimensions(content)
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
        quality_checks = manifest.get("quality_checks", {})
        if (width, height) != (job.width, job.height):
            raise ValueError("PNG dimensions do not match the request.")
        if not isinstance(manifest.get("canonical_signature"), list) or not manifest["canonical_signature"]:
            raise ValueError("Canonical geometry evidence is missing.")
        if not isinstance(quality_checks, dict) or quality_checks.get("canonical_geometry_unchanged") is not True:
            raise ValueError("Canonical geometry check did not pass.")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        _record_failure(job, "RENDER_OUTPUT_INVALID")
        raise RenderFailed("Blender did not produce a verified PNG render.") from error
    artifact = RenderArtifact(
        job_id=job.id,
        output_path=job.output_path,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_count=len(content),
    )
    manifest.update(_manifest_for(job, "COMPLETE"))
    manifest["image_sha256"] = artifact.sha256
    manifest["byte_count"] = artifact.byte_count
    _write_manifest(job.manifest_path, manifest)
    return artifact


def read_glb_identity(path: Path) -> tuple[str, str]:
    content = path.read_bytes()
    if len(content) < 20:
        raise ValueError("GLB is too short.")
    magic, version, total_length = struct.unpack_from("<4sII", content, 0)
    json_length, chunk_type = struct.unpack_from("<I4s", content, 12)
    if magic != b"glTF" or version != 2 or total_length != len(content) or chunk_type != b"JSON":
        raise ValueError("Artifact is not a supported GLB.")
    document = json.loads(content[20 : 20 + json_length].decode("utf-8"))
    extras = document.get("asset", {}).get("extras", {})
    model_hash = extras.get("modelHash")
    geometry_hash = extras.get("geometryHash")
    if not isinstance(model_hash, str) or not isinstance(geometry_hash, str):
        raise ValueError("GLB does not contain HearthView identity metadata.")
    return model_hash, geometry_hash


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local Blender render support.")
    parser.add_argument("--doctor", action="store_true")
    args = parser.parse_args()
    if args.doctor:
        capability = detect_blender()
        print(json.dumps(asdict(capability), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
