from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


Tick = Annotated[int, PlainSerializer(lambda value: str(value), return_type=str, when_used="json")]
ChildKind = Literal["WINDOW", "SOLID_MOUNT_ZONE", "UNFRAMED_OPENING", "SOLID"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReviewState(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    APPROVED = "APPROVED"
    EDITED_APPROVED = "EDITED_APPROVED"
    REJECTED = "REJECTED"
    CONFLICT = "CONFLICT"


class SourceReference(FrozenModel):
    id: str
    source_id: str
    page_number: int = Field(ge=1)
    pdf_polygon: tuple[tuple[int, int], ...]
    rationale: str


class SourceDocument(FrozenModel):
    id: str
    display_name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    profile: Literal["GARRIGAN_A1", "UNSUPPORTED"]


class WallChild(FrozenModel):
    id: str
    kind: ChildKind
    start_ticks: Tick = Field(ge=0)
    end_ticks: Tick = Field(gt=0)
    connects_to: str | None = None
    source_ref_ids: tuple[str, ...]


class Wall(FrozenModel):
    id: str
    name: str
    axis: Literal["X", "Y"]
    origin_x_ticks: Tick
    origin_y_ticks: Tick
    length_ticks: Tick = Field(gt=0)
    thickness_ticks: Tick = Field(gt=0)
    height_ticks: Tick = Field(gt=0)
    ordered_children: tuple[WallChild, ...]
    source_ref_ids: tuple[str, ...]


class FixedObject(FrozenModel):
    id: str
    kind: Literal["TV"]
    host_wall_id: str
    start_ticks: Tick = Field(ge=0)
    end_ticks: Tick = Field(gt=0)
    source_ref_ids: tuple[str, ...]


class Island(FrozenModel):
    id: str
    width_ticks: Tick = Field(gt=0)
    depth_ticks: Tick = Field(gt=0)
    x_ticks: Tick
    y_ticks: Tick
    source_ref_ids: tuple[str, ...]


class ReviewDecision(FrozenModel):
    item_id: str
    state: ReviewState = ReviewState.UNREVIEWED


class ReviewItem(FrozenModel):
    id: str
    title: str
    question: str
    help_text: str
    source_ref_id: str
    field_name: str | None = None
    value: str | None = None


class ProjectModel(FrozenModel):
    id: str
    name: str
    schema_version: str = "0.1.0"
    revision: int = Field(ge=0, default=0)
    level_height_ticks: Tick = 102400
    source_documents: tuple[SourceDocument, ...] = ()
    source_references: tuple[SourceReference, ...] = ()
    walls: tuple[Wall, ...] = ()
    fixed_objects: tuple[FixedObject, ...] = ()
    island: Island | None = None
    review_decisions: tuple[ReviewDecision, ...] = ()

    @classmethod
    def empty(cls, project_id: str, name: str) -> "ProjectModel":
        return cls(id=project_id, name=name)

    def wall(self, wall_id: str) -> Wall:
        try:
            return next(wall for wall in self.walls if wall.id == wall_id)
        except StopIteration as error:
            raise KeyError(wall_id) from error

    def review_state(self, item_id: str) -> ReviewState:
        for decision in self.review_decisions:
            if decision.item_id == item_id:
                return decision.state
        return ReviewState.UNREVIEWED
