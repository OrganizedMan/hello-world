from io import BytesIO

from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse

from hearthview.events import ModelEvent, RevisionConflict
from hearthview.geometry import compile_glb
from hearthview.models import ProjectModel
from hearthview.units import LengthParseError, format_length, parse_length
from hearthview.validation import (
    TokenModelMismatch,
    ValidationBlocked,
    mint_token,
    validate,
)

from hearthview_api.api_models import (
    CompileRequest,
    GeometryResponse,
    ProjectReportResponse,
    ReviewEventRequest,
    RevertReviewRequest,
    RevisionResponse,
    ValidationRunResponse,
)
from hearthview_api.errors import DomainError


router = APIRouter(prefix="/api", tags=["model"])


def _missing_project() -> DomainError:
    return DomainError(
        status_code=404,
        code="PROJECT_NOT_FOUND",
        message="HearthView could not find this project.",
        action="Return to the project home and choose an available project.",
    )


@router.post(
    "/projects/{project_id}/review-events",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_review_event(
    project_id: str,
    payload: ReviewEventRequest,
    request: Request,
) -> RevisionResponse:
    if payload.operation not in {"APPROVE_REVIEW", "EDIT_AND_APPROVE", "REJECT_REVIEW"}:
        raise DomainError(
            status_code=422,
            code="INVALID_REVIEW_ACTION",
            message="HearthView does not recognize this review action.",
            action="Choose Confirm, Edit and confirm, or Reject.",
        )
    if payload.operation == "EDIT_AND_APPROVE":
        if payload.item_id != "review_a1_island":
            raise DomainError(
                422,
                "INVALID_REVIEW_EDIT",
                "This plan detail does not have an editable dimension yet.",
                "Confirm it as shown or return to the plan.",
            )
        try:
            width = payload.payload.get("width")
            depth = payload.payload.get("depth")
            if not isinstance(width, str) or not isinstance(depth, str):
                raise LengthParseError("Missing width or depth.")
            if parse_length(width) <= 0 or parse_length(depth) <= 0:
                raise LengthParseError("Island dimensions must be greater than zero.")
        except LengthParseError as error:
            raise DomainError(
                422,
                "INVALID_LENGTH",
                str(error),
                'Enter a length such as 8\'-7" or 103 in.',
            ) from error
    try:
        revision = request.app.state.repository.append_event(
            project_id,
            payload.base_revision,
            ModelEvent(
                id=payload.id,
                operation=payload.operation,
                item_id=payload.item_id,
                payload=payload.payload,
                source_ref_ids=payload.source_ref_ids,
                rationale=payload.rationale,
            ),
        )
    except KeyError as error:
        raise _missing_project() from error
    except RevisionConflict as error:
        raise DomainError(
            status_code=409,
            code="REVISION_CONFLICT",
            message=str(error),
            action="Reload the latest project, then confirm the detail again.",
        ) from error
    return RevisionResponse(revision=revision)


@router.post(
    "/projects/{project_id}/review-events/revert",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def revert_review_event(
    project_id: str,
    payload: RevertReviewRequest,
    request: Request,
) -> RevisionResponse:
    try:
        known_events = request.app.state.repository.list_events(project_id)
        if not any(
            event.id == payload.target_event_id and event.operation != "REVERT_EVENT"
            for event in known_events
        ):
            raise DomainError(
                404,
                "REVIEW_EVENT_NOT_FOUND",
                "HearthView could not find the decision to undo.",
                "Reload the review and try again.",
            )
        revision = request.app.state.repository.revert_event(
            project_id,
            payload.base_revision,
            payload.target_event_id,
            event_id=payload.id,
        )
    except KeyError as error:
        raise _missing_project() from error
    except RevisionConflict as error:
        raise DomainError(
            409,
            "REVISION_CONFLICT",
            str(error),
            "Reload the latest project, then undo the decision again.",
        ) from error
    return RevisionResponse(revision=revision)


@router.get("/projects/{project_id}/model", response_model=ProjectModel)
def get_model(project_id: str, request: Request) -> ProjectModel:
    try:
        return request.app.state.repository.replay(project_id)
    except KeyError as error:
        raise _missing_project() from error


@router.post("/projects/{project_id}/validate", response_model=ValidationRunResponse)
def validate_project(project_id: str, request: Request) -> ValidationRunResponse:
    try:
        model = request.app.state.repository.replay(project_id)
    except KeyError as error:
        raise _missing_project() from error
    report = validate(model)
    try:
        token = mint_token(model, report)
    except ValidationBlocked:
        token = None
    return ValidationRunResponse(report=report, token=token)


@router.get("/projects/{project_id}/validation-report")
def validation_report(project_id: str, request: Request):
    try:
        model = request.app.state.repository.replay(project_id)
    except KeyError as error:
        raise _missing_project() from error
    return validate(model)


@router.get("/projects/{project_id}/report", response_model=ProjectReportResponse)
def project_report(project_id: str, request: Request) -> ProjectReportResponse:
    try:
        model = request.app.state.repository.replay(project_id)
    except KeyError as error:
        raise _missing_project() from error
    validation = validate(model)
    geometry = request.app.state.repository.latest_geometry(
        project_id,
        model_hash=validation.model_hash,
    )
    source = model.source_documents[0] if model.source_documents else None
    return ProjectReportResponse(
        status=validation.status,
        blocking_count=validation.blocking_count,
        evidence_coverage_percent=validation.evidence_coverage_percent,
        source_name=source.display_name if source is not None else "No plan PDF imported",
        source_hash=source.sha256 if source is not None else "Unavailable",
        model_hash=validation.model_hash,
        geometry_hash=geometry.geometry_hash if geometry is not None else "Not created yet",
        island_dimensions=(
            f"{format_length(model.island.width_ticks)} × {format_length(model.island.depth_ticks)}"
            if model.island is not None
            else "Unavailable"
        ),
        validator_version=validation.validator_version,
        issues=validation.issues,
    )


@router.post(
    "/projects/{project_id}/compile",
    response_model=GeometryResponse,
    status_code=status.HTTP_201_CREATED,
)
def compile_project(
    project_id: str,
    payload: CompileRequest,
    request: Request,
) -> GeometryResponse:
    try:
        model = request.app.state.repository.replay(project_id)
        artifact = compile_glb(model, payload.token)
    except KeyError as error:
        raise _missing_project() from error
    except TokenModelMismatch as error:
        raise DomainError(
            status_code=409,
            code="TOKEN_MODEL_MISMATCH",
            message="The model changed after it was validated.",
            action="Validate the current model, then build the 3D view again.",
        ) from error
    stored = request.app.state.artifact_store.install(BytesIO(artifact.glb))
    request.app.state.repository.add_geometry(
        project_id=project_id,
        artifact_id=stored.sha256,
        model_hash=artifact.model_hash,
        geometry_hash=artifact.geometry_hash,
        glb_file_hash=artifact.glb_file_hash,
        primitive_count=artifact.primitive_count,
        bounds_ticks=artifact.bounds_ticks,
    )
    return GeometryResponse(
        artifact_id=stored.sha256,
        model_hash=artifact.model_hash,
        geometry_hash=artifact.geometry_hash,
        glb_file_hash=artifact.glb_file_hash,
        island_dimensions=(
            f"{format_length(model.island.width_ticks)} × {format_length(model.island.depth_ticks)}"
            if model.island is not None
            else "Unavailable"
        ),
        primitive_count=artifact.primitive_count,
        bounds_ticks=tuple(str(value) for value in artifact.bounds_ticks),
        download_url=f"/api/projects/{project_id}/geometry/{stored.sha256}.glb",
    )


@router.get("/projects/{project_id}/geometry/{artifact_id}.glb")
def download_geometry(project_id: str, artifact_id: str, request: Request) -> FileResponse:
    try:
        request.app.state.repository.get_geometry(project_id, artifact_id)
        path = request.app.state.artifact_store.resolve(artifact_id)
    except (KeyError, ValueError) as error:
        raise DomainError(
            status_code=404,
            code="GEOMETRY_NOT_FOUND",
            message="HearthView could not find this 3D model.",
            action="Build the 3D view again from the current validated model.",
        ) from error
    if not path.exists():
        raise DomainError(
            status_code=404,
            code="GEOMETRY_NOT_FOUND",
            message="HearthView could not find this 3D model.",
            action="Build the 3D view again from the current validated model.",
        )
    return FileResponse(path, media_type="model/gltf-binary", filename=f"{project_id}.glb")
