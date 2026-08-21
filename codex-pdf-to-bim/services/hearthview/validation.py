from __future__ import annotations

import hmac
from typing import Literal

from hearthview.canonical import canonical_hash
from hearthview.fixture import build_a1_review_queue
from hearthview.models import FrozenModel, ProjectModel, ReviewState
from hearthview.units import TICKS_PER_INCH


VALIDATOR_VERSION = "hearthview-validator-0.1.0"


class ValidationBlocked(RuntimeError):
    """Raised when release is requested for a model with blocking issues."""


class TokenModelMismatch(RuntimeError):
    """Raised when a validation token no longer matches model state."""


class ValidationIssue(FrozenModel):
    code: str
    severity: Literal["BLOCKING", "WARNING"]
    message: str
    action: str
    element_id: str | None = None
    review_item_id: str | None = None


class ValidationReport(FrozenModel):
    status: Literal["READY_TO_VIEW", "NEEDS_INPUT", "CONFLICTING_INFORMATION"]
    model_hash: str
    schema_hash: str
    validator_version: str
    blocking_count: int
    evidence_coverage_percent: int
    issues: tuple[ValidationIssue, ...]


class ValidationToken(FrozenModel):
    token_hash: str
    model_hash: str
    report_hash: str
    schema_hash: str
    validator_version: str


def _model_hash(model: ProjectModel) -> str:
    return canonical_hash(model.model_dump(mode="json"))


def _schema_hash() -> str:
    return canonical_hash(ProjectModel.model_json_schema(mode="serialization"))


def _issue(
    code: str,
    message: str,
    action: str,
    element_id: str | None = None,
    review_item_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity="BLOCKING",
        message=message,
        action=action,
        element_id=element_id,
        review_item_id=review_item_id,
    )


def _review_issues(model: ProjectModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for item in build_a1_review_queue():
        state = model.review_state(item.id)
        if state not in {ReviewState.APPROVED, ReviewState.EDITED_APPROVED}:
            issues.append(
                _issue(
                    "REVIEW_REQUIRED",
                    item.question,
                    "Review this drawing detail and confirm or correct it.",
                    review_item_id=item.id,
                )
            )
    return issues


def _wall_issues(model: ProjectModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for wall in model.walls:
        previous_end = 0
        for child in wall.ordered_children:
            if child.start_ticks < 0 or child.end_ticks <= child.start_ticks:
                issues.append(
                    _issue(
                        "INVALID_WALL_INTERVAL",
                        f"{wall.name} contains an invalid wall section.",
                        "Correct the highlighted wall section dimensions.",
                        child.id,
                    )
                )
            if child.end_ticks > wall.length_ticks:
                issues.append(
                    _issue(
                        "WALL_INTERVAL_OUTSIDE_HOST",
                        f"A section extends beyond {wall.name}.",
                        "Shorten or move the highlighted section so it remains on the wall.",
                        child.id,
                    )
                )
            if child.start_ticks < previous_end:
                issues.append(
                    _issue(
                        "WALL_INTERVAL_OVERLAP",
                        f"Two sections overlap on {wall.name}.",
                        "Adjust the highlighted wall sections so they do not overlap.",
                        child.id,
                    )
                )
            previous_end = max(previous_end, child.end_ticks)
    return issues


def _fixture_topology_issues(model: ProjectModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        east = model.wall("family_east")
        south = model.wall("family_south")
    except KeyError:
        return [
            _issue(
                "FAMILY_ROOM_WALL_MISSING",
                "A required living-room wall is missing.",
                "Restore the east and south living-room walls from the A-1 plan.",
            )
        ]
    east_kinds = [child.kind for child in east.ordered_children]
    if east_kinds != ["WINDOW", "SOLID_MOUNT_ZONE", "UNFRAMED_OPENING"]:
        issues.append(
            _issue(
                "EAST_WALL_ORDER_MISMATCH",
                "The east living-room wall must show the window, solid TV area, then mudroom opening.",
                "Restore the wall sections in the order shown on A-1.",
                east.id,
            )
        )
    else:
        solid_zone = east.ordered_children[1]
        if solid_zone.end_ticks - solid_zone.start_ticks < 60 * TICKS_PER_INCH:
            issues.append(
                _issue(
                    "TV_ZONE_TOO_NARROW",
                    "The solid TV area must be at least 60 inches wide.",
                    "Widen the solid section or review the wall dimensions.",
                    solid_zone.id,
                )
            )
    expected_south = (
        ("SOLID", 0, 37),
        ("UNFRAMED_OPENING", 37, 97),
        ("SOLID", 97, 134),
    )
    actual_south = tuple(
        (child.kind, child.start_ticks // TICKS_PER_INCH, child.end_ticks // TICKS_PER_INCH)
        for child in south.ordered_children
    )
    if actual_south != expected_south:
        issues.append(
            _issue(
                "SOUTH_WALL_DIMENSION_MISMATCH",
                "The opening wall must be 3 feet 1 inch, 5 feet, then 3 feet 1 inch.",
                "Restore the three printed A-1 dimensions.",
                south.id,
            )
        )
    return issues


def _fixed_object_issues(model: ProjectModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for fixed_object in model.fixed_objects:
        if fixed_object.kind != "TV":
            continue
        try:
            wall = model.wall(fixed_object.host_wall_id)
        except KeyError:
            wall = None
        solid_zones = (
            [child for child in wall.ordered_children if child.kind == "SOLID_MOUNT_ZONE"]
            if wall is not None
            else []
        )
        contained = any(
            fixed_object.start_ticks >= zone.start_ticks
            and fixed_object.end_ticks <= zone.end_ticks
            for zone in solid_zones
        )
        if wall is None or wall.id != "family_east" or not contained:
            issues.append(
                _issue(
                    "TV_REQUIRES_SOLID_WALL",
                    "Move the TV to a solid part of the east living-room wall.",
                    "Place the TV fully inside the highlighted solid wall section.",
                    fixed_object.id,
                )
            )
    return issues


def _island_issues(model: ProjectModel) -> list[ValidationIssue]:
    if model.island is None:
        return [
            _issue(
                "ISLAND_SIZE_MISMATCH",
                "The A-1 kitchen island dimensions are missing.",
                "Return to Review and enter the island width and depth.",
                "kitchen_island",
            )
        ]
    if model.island.width_ticks <= 0 or model.island.depth_ticks <= 0:
        return [
            _issue(
                "ISLAND_SIZE_MISMATCH",
                "The kitchen island width and depth must be greater than zero.",
                "Return to Review and enter the confirmed island dimensions.",
                "kitchen_island",
            )
        ]
    differs_from_drawing = (
        model.island.width_ticks != 103 * TICKS_PER_INCH
        or model.island.depth_ticks != 51 * TICKS_PER_INCH
    )
    if differs_from_drawing and model.review_state("review_a1_island") is not ReviewState.EDITED_APPROVED:
        return [
            _issue(
                "ISLAND_SIZE_MISMATCH",
                "The A-1 kitchen island must be 8 feet 7 inches by 4 feet 3 inches.",
                "Restore the printed island dimensions or return to Review to document a change.",
                "kitchen_island",
            )
        ]
    return []


def _provenance_issues(model: ProjectModel) -> tuple[list[ValidationIssue], int]:
    elements = [
        *model.walls,
        *(child for wall in model.walls for child in wall.ordered_children),
        *model.fixed_objects,
    ]
    if model.island is not None:
        elements.append(model.island)
    documents = {document.id: document for document in model.source_documents}
    references = {reference.id: reference for reference in model.source_references}
    valid_references = {
        reference.id
        for reference in model.source_references
        if reference.source_id in documents
        and reference.page_number <= documents[reference.source_id].page_count
        and len(reference.pdf_polygon) >= 3
        and all(x >= 0 and y >= 0 for x, y in reference.pdf_polygon)
    }
    sourced = sum(
        bool(element.source_ref_ids)
        and all(reference_id in valid_references for reference_id in element.source_ref_ids)
        for element in elements
    )
    coverage = round((sourced / len(elements)) * 100) if elements else 0
    issues: list[ValidationIssue] = []
    if not documents:
        issues.append(
            _issue(
                "PROJECT_SOURCE_REQUIRED",
                "Add the plan PDF before approving this model.",
                "Return to Plans and choose the Garrigan drawing set.",
            )
        )
    elif not any(document.profile == "GARRIGAN_A1" for document in documents.values()):
        issues.append(
            _issue(
                "UNSUPPORTED_PLAN_SET",
                "This PDF is not the supported Garrigan A-1 drawing set.",
                "Import the supplied Garrigan plan PDF. HearthView will not guess geometry for a different plan.",
            )
        )
    issues.extend([
        _issue(
            "PROVENANCE_REQUIRED",
            "A structural element is not linked to the drawing or a homeowner entry.",
            "Open the highlighted element and add its source.",
            element.id,
        )
        for element in elements
        if not element.source_ref_ids
        or any(reference_id not in valid_references for reference_id in element.source_ref_ids)
    ])
    for reference in model.source_references:
        if reference.source_id not in documents:
            issues.append(
                _issue(
                    "SOURCE_REFERENCE_MISSING",
                    "A model fact points to a plan that is not part of this project.",
                    "Re-import the source PDF and review the highlighted fact again.",
                    reference.id,
                )
            )
        elif reference.id not in valid_references:
            issues.append(
                _issue(
                    "SOURCE_REFERENCE_INVALID",
                    "A model fact points outside the available plan pages.",
                    "Choose the correct plan page and review the highlighted fact again.",
                    reference.id,
                )
            )
    return issues, coverage


def validate(model: ProjectModel) -> ValidationReport:
    issues = [
        *_review_issues(model),
        *_wall_issues(model),
        *_fixture_topology_issues(model),
        *_fixed_object_issues(model),
        *_island_issues(model),
    ]
    provenance_issues, coverage = _provenance_issues(model)
    issues.extend(provenance_issues)
    ordered = tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.code,
                issue.element_id or "",
                issue.review_item_id or "",
            ),
        )
    )
    has_conflict = any(
        model.review_state(item.id) is ReviewState.CONFLICT for item in build_a1_review_queue()
    )
    status: Literal["READY_TO_VIEW", "NEEDS_INPUT", "CONFLICTING_INFORMATION"]
    if has_conflict:
        status = "CONFLICTING_INFORMATION"
    elif ordered:
        status = "NEEDS_INPUT"
    else:
        status = "READY_TO_VIEW"
    return ValidationReport(
        status=status,
        model_hash=_model_hash(model),
        schema_hash=_schema_hash(),
        validator_version=VALIDATOR_VERSION,
        blocking_count=len(ordered),
        evidence_coverage_percent=coverage,
        issues=ordered,
    )


def mint_token(model: ProjectModel, report: ValidationReport) -> ValidationToken:
    model_hash = _model_hash(model)
    if report.blocking_count or report.status != "READY_TO_VIEW" or report.model_hash != model_hash:
        raise ValidationBlocked("The validation report contains blocking issues.")
    report_hash = canonical_hash(report.model_dump(mode="json"))
    token_payload = {
        "model_hash": model_hash,
        "report_hash": report_hash,
        "schema_hash": report.schema_hash,
        "validator_version": report.validator_version,
    }
    return ValidationToken(token_hash=canonical_hash(token_payload), **token_payload)


def assert_token(token: ValidationToken, model: ProjectModel) -> None:
    if token.model_hash != _model_hash(model):
        raise TokenModelMismatch("This model has changed since it was validated.")
    try:
        expected = mint_token(model, validate(model))
    except ValidationBlocked as error:
        raise TokenModelMismatch("This model no longer has a valid validation token.") from error
    actual_fields = token.model_dump(mode="json")
    expected_fields = expected.model_dump(mode="json")
    if set(actual_fields) != set(expected_fields) or any(
        not hmac.compare_digest(str(actual_fields[key]), str(expected_fields[key]))
        for key in expected_fields
    ):
        raise TokenModelMismatch("This validation token is invalid for the current model.")
