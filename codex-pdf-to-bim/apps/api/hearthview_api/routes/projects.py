from pathlib import Path

from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from hearthview.a1_trace import build_a1_trace, trace_summary
from hearthview.fixture import build_a1_review_queue
from hearthview.ingest import PdfIngestError, inspect_pdf, render_page, render_rect, render_region
from hearthview.storage import ArtifactTooLarge

from hearthview_api.api_models import (
    ProjectCreate,
    ProjectResponse,
    A1TraceResponse,
    PdfRectResponse,
    ReviewItemResponse,
    SourceResponse,
    TraceGeometryResponse,
    TraceRecordResponse,
    TraceSummaryResponse,
)
from hearthview_api.errors import DomainError


router = APIRouter(prefix="/api", tags=["projects"])


def _not_found(kind: str) -> DomainError:
    return DomainError(
        status_code=404,
        code=f"{kind.upper()}_NOT_FOUND",
        message=f"HearthView could not find this {kind}.",
        action="Return to the project home and choose an available item.",
    )


def _a1_trace_for_source(source: object, request: Request):
    if getattr(source, "sha256", None) != request.app.state.config.supported_source_sha256:
        raise DomainError(
            status_code=422,
            code="UNSUPPORTED_A1_TRACE_SOURCE",
            message="This trace only supports the approved Garrigan A-1 source.",
            action="Return to Plans and select the Garrigan PDF used for this review.",
        )
    return build_a1_trace()


def _trace_response(trace: object) -> A1TraceResponse:
    summary = trace_summary(trace)
    return A1TraceResponse(
        page_number=trace.page_number,
        page_width_points=trace.page_width_points,
        page_height_points=trace.page_height_points,
        proposed_crop=PdfRectResponse(**trace.proposed_crop.__dict__),
        records=tuple(
            TraceRecordResponse(
                id=record.id,
                kind=record.kind,
                room=record.room,
                provenance=record.provenance,
                geometry=TraceGeometryResponse(
                    points=record.geometry.points,
                    closed=record.geometry.closed,
                ),
                source_page=record.source_page,
                dimension_labels=record.dimension_labels,
            )
            for record in trace.records
        ),
        summary=TraceSummaryResponse(**summary.__dict__),
        approval_blocked=summary.ambiguous > 0,
    )


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, request: Request) -> ProjectResponse:
    project = request.app.state.repository.create(payload.name)
    return ProjectResponse(id=project.id, name=project.name, revision=project.revision)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, request: Request) -> ProjectResponse:
    try:
        project = request.app.state.repository.get(project_id)
    except KeyError as error:
        raise _not_found("project") from error
    return ProjectResponse(id=project.id, name=project.name, revision=project.revision)


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_source(project_id: str, request: Request, file: UploadFile = File()) -> SourceResponse:
    try:
        request.app.state.repository.get(project_id)
    except KeyError as error:
        raise _not_found("project") from error
    try:
        artifact = request.app.state.artifact_store.install(
            file.file,
            max_bytes=request.app.state.config.max_upload_bytes,
            validator=inspect_pdf,
        )
    except ArtifactTooLarge as error:
        raise DomainError(
            status_code=413,
            code="PDF_TOO_LARGE",
            message="This PDF is too large for the current project limit.",
            action="Export a smaller PDF or split the drawing set, then try again.",
        ) from error
    except PdfIngestError as error:
        raise DomainError(
            status_code=422,
            code="INVALID_PDF",
            message="HearthView could not read this PDF.",
            action="Choose an unencrypted architectural PDF and try again.",
        ) from error
    try:
        inspection = inspect_pdf(artifact.path)
    except PdfIngestError as error:
        raise DomainError(
            status_code=422,
            code="INVALID_PDF",
            message="HearthView could not read this PDF.",
            action="Choose an unencrypted architectural PDF and try again.",
        ) from error
    source = request.app.state.repository.add_source(
        project_id=project_id,
        display_name=Path(file.filename or "plans.pdf").name,
        sha256=artifact.sha256,
        byte_count=artifact.byte_count,
        page_count=inspection.page_count,
        profile=(
            "GARRIGAN_A1"
            if artifact.sha256 == request.app.state.config.supported_source_sha256
            else "UNSUPPORTED"
        ),
    )
    return SourceResponse(
        id=source.id,
        display_name=source.display_name,
        sha256=source.sha256,
        byte_count=source.byte_count,
        page_count=source.page_count,
    )


@router.get("/projects/{project_id}/sources/{source_id}/file")
def source_file(project_id: str, source_id: str, request: Request) -> FileResponse:
    try:
        source = request.app.state.repository.get_source(project_id, source_id)
    except KeyError as error:
        raise _not_found("source") from error
    path = request.app.state.artifact_store.resolve(source.sha256)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=source.display_name,
        content_disposition_type="inline",
    )


@router.get(
    "/projects/{project_id}/sources/{source_id}",
    response_model=SourceResponse,
)
def source_metadata(project_id: str, source_id: str, request: Request) -> SourceResponse:
    try:
        source = request.app.state.repository.get_source(project_id, source_id)
    except KeyError as error:
        raise _not_found("source") from error
    return SourceResponse(
        id=source.id,
        display_name=source.display_name,
        sha256=source.sha256,
        byte_count=source.byte_count,
        page_count=source.page_count,
    )


@router.get("/projects/{project_id}/sources/{source_id}/pages/{page_number}/preview")
def source_preview(
    project_id: str,
    source_id: str,
    page_number: int,
    request: Request,
    max_width: int = Query(default=1200, ge=320, le=2048),
) -> Response:
    try:
        source = request.app.state.repository.get_source(project_id, source_id)
    except KeyError as error:
        raise _not_found("source") from error
    try:
        content = render_page(
            request.app.state.artifact_store.resolve(source.sha256),
            page_number=page_number,
            max_width=max_width,
        )
    except PdfIngestError as error:
        raise DomainError(
            status_code=422,
            code="PAGE_PREVIEW_FAILED",
            message="HearthView could not preview this page.",
            action="Choose another page or re-import the PDF.",
        ) from error
    return Response(content=content, media_type="image/png")


@router.get(
    "/projects/{project_id}/sources/{source_id}/a1-trace",
    response_model=A1TraceResponse,
)
def a1_trace(project_id: str, source_id: str, request: Request) -> A1TraceResponse:
    try:
        source = request.app.state.repository.get_source(project_id, source_id)
    except KeyError as error:
        raise _not_found("source") from error
    return _trace_response(_a1_trace_for_source(source, request))


@router.get("/projects/{project_id}/sources/{source_id}/a1-trace/preview")
def a1_trace_preview(
    project_id: str,
    source_id: str,
    request: Request,
    max_width: int = Query(default=1600, ge=320, le=2048),
) -> Response:
    try:
        source = request.app.state.repository.get_source(project_id, source_id)
    except KeyError as error:
        raise _not_found("source") from error
    trace = _a1_trace_for_source(source, request)
    try:
        content = render_rect(
            request.app.state.artifact_store.resolve(source.sha256),
            page_number=trace.page_number,
            rect=trace.proposed_crop,
            max_width=max_width,
        )
    except PdfIngestError as error:
        raise DomainError(
            status_code=422,
            code="A1_TRACE_PREVIEW_FAILED",
            message="HearthView could not preview the proposed A-1 plan.",
            action="Return to Plans and re-import the approved Garrigan PDF.",
        ) from error
    return Response(content=content, media_type="image/png")


@router.get("/projects/{project_id}/evidence/{reference_id}/preview")
def evidence_preview(
    project_id: str,
    reference_id: str,
    request: Request,
    max_width: int = Query(default=900, ge=320, le=2048),
) -> Response:
    try:
        model = request.app.state.repository.replay(project_id)
        reference = next(
            item for item in model.source_references if item.id == reference_id
        )
        source = request.app.state.repository.get_source(project_id, reference.source_id)
        path = request.app.state.artifact_store.resolve(source.sha256)
    except (KeyError, StopIteration) as error:
        raise DomainError(
            404,
            "EVIDENCE_NOT_FOUND",
            "HearthView could not find this source highlight.",
            "Return to Review and choose a documented plan detail.",
        ) from error
    try:
        content = render_region(
            path,
            page_number=reference.page_number,
            pdf_polygon=reference.pdf_polygon,
            max_width=max_width,
        )
    except PdfIngestError as error:
        raise DomainError(
            422,
            "EVIDENCE_PREVIEW_FAILED",
            "HearthView could not preview this source highlight.",
            "Open the full plan page and review the detail there.",
        ) from error
    return Response(content=content, media_type="image/png")


@router.get(
    "/projects/{project_id}/review-queue",
    response_model=list[ReviewItemResponse],
)
def review_queue(project_id: str, request: Request) -> list[ReviewItemResponse]:
    try:
        model = request.app.state.repository.replay(project_id)
    except KeyError as error:
        raise _not_found("project") from error
    return [
        ReviewItemResponse(
            **item.model_dump(),
            state=model.review_state(item.id),
        )
        for item in build_a1_review_queue()
    ]
