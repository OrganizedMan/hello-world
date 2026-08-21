from pydantic import BaseModel, ConfigDict, Field, field_validator

from hearthview.models import ReviewState
from hearthview.validation import ValidationIssue, ValidationReport, ValidationToken


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter a project name.")
        return cleaned


class ProjectResponse(ApiModel):
    id: str
    name: str
    revision: int


class SourceResponse(ApiModel):
    id: str
    display_name: str
    sha256: str
    byte_count: int
    page_count: int


class ReviewItemResponse(ApiModel):
    id: str
    title: str
    question: str
    help_text: str
    source_ref_id: str
    field_name: str | None
    value: str | None
    state: ReviewState


class ReviewEventRequest(ApiModel):
    id: str
    base_revision: int = Field(ge=0)
    operation: str
    item_id: str
    payload: dict[str, str | int] = Field(default_factory=dict)
    source_ref_ids: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)


class RevisionResponse(ApiModel):
    revision: int


class RevertReviewRequest(ApiModel):
    id: str
    base_revision: int = Field(ge=0)
    target_event_id: str


class ValidationRunResponse(ApiModel):
    report: ValidationReport
    token: ValidationToken | None


class CompileRequest(ApiModel):
    token: ValidationToken


class GeometryResponse(ApiModel):
    artifact_id: str
    model_hash: str
    geometry_hash: str
    glb_file_hash: str
    island_dimensions: str
    primitive_count: int
    bounds_ticks: tuple[str, str, str, str, str, str]
    download_url: str


class ProjectReportResponse(ApiModel):
    status: str
    blocking_count: int
    evidence_coverage_percent: int
    source_name: str
    source_hash: str
    model_hash: str
    geometry_hash: str
    island_dimensions: str
    validator_version: str
    issues: tuple[ValidationIssue, ...]


class BlenderCapabilityResponse(ApiModel):
    available: bool
    executable: str | None
    version: str | None
    message: str
    action: str | None


class RenderJobRequest(ApiModel):
    geometry_artifact_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    camera: str
    quality: str
    width: int = Field(ge=640, le=7680)
    height: int = Field(ge=480, le=4320)
    style: str


class RenderJobResponse(ApiModel):
    id: str
    status: str
    geometry_hash: str
    image_url: str | None
    message: str
