import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import FileResponse

from hearthview.rendering import (
    RenderFailed,
    RenderJob,
    RenderRequest,
    create_render_job,
    detect_blender,
    load_latest_render_job,
    load_render_job,
    mark_render_interrupted,
    read_glb_identity,
    run_render,
)
from hearthview.storage import ArtifactPathError
from hearthview.validation import validate

from hearthview_api.api_models import (
    BlenderCapabilityResponse,
    RenderJobRequest,
    RenderJobResponse,
)
from hearthview_api.errors import DomainError


router = APIRouter(prefix="/api", tags=["render"])


def _find_job(job_id: str, request: Request) -> RenderJob:
    job = request.app.state.render_jobs.get(job_id)
    if job is not None:
        return job
    try:
        job = load_render_job(
            request.app.state.config.data_root / "render-jobs",
            job_id,
        )
    except KeyError as error:
        raise DomainError(404, "RENDER_JOB_NOT_FOUND", "HearthView could not find this render job.", "Return to Render and start a new image.") from error
    mark_render_interrupted(job)
    request.app.state.render_jobs[job.id] = job
    return job


def _run_in_background(job: RenderJob, executable: str) -> None:
    try:
        run_render(job, Path(executable))
    except RenderFailed:
        return


def _job_payload(job: RenderJob) -> RenderJobResponse:
    manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
    current_status = str(manifest["status"])
    return RenderJobResponse(
        id=job.id,
        status=current_status,
        geometry_hash=job.geometry_hash,
        image_url=f"/api/render-jobs/{job.id}/image" if current_status == "COMPLETE" else None,
        message={
            "QUEUED": "Your render is waiting to start.",
            "RUNNING": "Blender is creating your warm furnished view.",
            "COMPLETE": "Your polished render is ready.",
            "FAILED": "The render did not finish. Review the guidance and try again.",
        }.get(current_status, "Render status is unavailable."),
    )


@router.get("/render-capability", response_model=BlenderCapabilityResponse)
def render_capability() -> BlenderCapabilityResponse:
    return BlenderCapabilityResponse(**detect_blender().__dict__)


@router.post(
    "/projects/{project_id}/render-jobs",
    response_model=RenderJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_render(
    project_id: str,
    payload: RenderJobRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RenderJobResponse:
    try:
        geometry_record = request.app.state.repository.get_geometry(
            project_id,
            payload.geometry_artifact_id,
        )
        geometry_path = request.app.state.artifact_store.resolve(payload.geometry_artifact_id)
    except (KeyError, ArtifactPathError) as error:
        raise DomainError(404, "GEOMETRY_NOT_FOUND", "HearthView could not find this 3D model.", "Build the 3D view again, then return to Render.") from error
    if not geometry_path.is_file():
        raise DomainError(404, "GEOMETRY_NOT_FOUND", "HearthView could not find this 3D model.", "Build the 3D view again, then return to Render.")
    try:
        model_hash, geometry_hash = read_glb_identity(geometry_path)
    except (ValueError, OSError) as error:
        raise DomainError(422, "INVALID_GEOMETRY", "This 3D artifact is not a verified HearthView model.", "Build the 3D view again from the current plan review.") from error
    if (
        model_hash != geometry_record.model_hash
        or geometry_hash != geometry_record.geometry_hash
        or payload.geometry_artifact_id != geometry_record.glb_file_hash
    ):
        raise DomainError(422, "INVALID_GEOMETRY", "This 3D artifact does not match the verified project model.", "Build the 3D view again from the current plan review.")
    current_model = request.app.state.repository.replay(project_id)
    current_validation = validate(current_model)
    if (
        current_validation.status != "READY_TO_VIEW"
        or current_validation.blocking_count
        or geometry_record.model_hash != current_validation.model_hash
    ):
        raise DomainError(
            409,
            "STALE_GEOMETRY",
            "This 3D model is older than your current plan review.",
            "Validate and build the 3D view again before rendering.",
        )
    capability = detect_blender()
    if not capability.available or capability.executable is None:
        raise DomainError(503, "BLENDER_UNAVAILABLE", capability.message, capability.action or "Restart HearthView and try again.")
    if payload.camera not in {"PLAN", "AXONOMETRIC", "KITCHEN", "LIVING_ROOM"} or payload.quality not in {"DRAFT", "FINAL"} or payload.style != "WARM_BLANK_SLATE":
        raise DomainError(422, "INVALID_RENDER_SETTING", "One or more render settings are not supported.", "Choose one of the labeled camera, quality, and style options.")
    job = create_render_job(
        RenderRequest(
            project_id=project_id,
            geometry_path=geometry_path,
            model_hash=geometry_record.model_hash,
            geometry_hash=geometry_hash,
            glb_file_hash=geometry_record.glb_file_hash,
            source_sha256=(
                request.app.state.repository.list_sources(project_id)[0].sha256
                if request.app.state.repository.list_sources(project_id)
                else ""
            ),
            camera=payload.camera,  # type: ignore[arg-type]
            quality=payload.quality,  # type: ignore[arg-type]
            width=payload.width,
            height=payload.height,
            style=payload.style,  # type: ignore[arg-type]
        ),
        request.app.state.config.data_root / "render-jobs",
    )
    request.app.state.render_jobs[job.id] = job
    background_tasks.add_task(_run_in_background, job, capability.executable)
    return _job_payload(job)


@router.get("/projects/{project_id}/render-jobs/latest", response_model=RenderJobResponse)
def latest_render_job(project_id: str, request: Request) -> RenderJobResponse:
    try:
        model = request.app.state.repository.replay(project_id)
        validation = validate(model)
        live_jobs = [
            candidate
            for candidate in request.app.state.render_jobs.values()
            if candidate.project_id == project_id
            and candidate.model_hash == validation.model_hash
        ]
        if live_jobs:
            job = max(live_jobs, key=lambda candidate: candidate.created_at_ns)
        else:
            job = load_latest_render_job(
                request.app.state.config.data_root / "render-jobs",
                project_id,
                validation.model_hash,
            )
            mark_render_interrupted(job)
    except KeyError as error:
        raise DomainError(
            404,
            "RENDER_JOB_NOT_FOUND",
            "HearthView could not find a render for this model yet.",
            "Choose your settings and create a polished render.",
        ) from error
    request.app.state.render_jobs[job.id] = job
    return _job_payload(job)


@router.get("/render-jobs/{job_id}", response_model=RenderJobResponse)
def get_render_job(job_id: str, request: Request) -> RenderJobResponse:
    job = _find_job(job_id, request)
    return _job_payload(job)


@router.get("/render-jobs/{job_id}/image")
def get_render_image(job_id: str, request: Request) -> FileResponse:
    try:
        job = _find_job(job_id, request)
    except DomainError as error:
        raise DomainError(404, "RENDER_NOT_READY", "This render is not ready yet.", "Keep the Render page open and wait for completion.") from error
    if not job.output_path.is_file():
        raise DomainError(404, "RENDER_NOT_READY", "This render is not ready yet.", "Keep the Render page open and wait for completion.")
    return FileResponse(job.output_path, media_type="image/png", filename=f"hearthview-{job.camera.lower()}.png")
