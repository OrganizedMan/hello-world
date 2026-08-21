from hearthview.a1_spatial import build_a1_spatial_model, default_a1_source_document
from hearthview.models import (
    ProjectModel,
    ReviewItem,
    SourceDocument,
)


_FIXTURE_SOURCE = default_a1_source_document()


def build_a1_fixture(source_document: SourceDocument | None = _FIXTURE_SOURCE) -> ProjectModel:
    if source_document is None:
        fallback = default_a1_source_document().model_copy(update={"id": "missing_source"})
        return build_a1_spatial_model().to_project_model(source_document=fallback).model_copy(
            update={"source_documents": ()}
        )
    return build_a1_spatial_model().to_project_model(source_document=source_document)


def build_a1_review_queue() -> tuple[ReviewItem, ...]:
    return (
        ReviewItem(
            id="review_a1_region",
            title="Use the proposed first-floor plan?",
            question="Is this the proposed first-floor plan you want to explore?",
            help_text="We found the proposed plan on sheet A-1. Confirming keeps it separate from the existing plan.",
            source_ref_id="src_a1_region",
        ),
        ReviewItem(
            id="review_a1_island",
            title="Confirm the kitchen island",
            question="Is the kitchen island 8 feet 7 inches by 4 feet 3 inches?",
            help_text="These printed dimensions control the island size in every 3D view.",
            source_ref_id="src_a1_island",
            field_name="island_size",
            value="8'-7\" × 4'-3\"",
        ),
        ReviewItem(
            id="review_a1_east_wall",
            title="Confirm the east living-room wall",
            question="Does this wall have a window, solid TV area, then the mudroom opening?",
            help_text="This order prevents the TV and opening from occupying the same part of the wall.",
            source_ref_id="src_a1_family_east",
        ),
        ReviewItem(
            id="review_a1_south_wall",
            title="Confirm the opening to the existing living room",
            question="Is the opening 5 feet wide with 3-foot-1-inch wall sections on both sides?",
            help_text="The three printed dimensions define this entire wall segment exactly.",
            source_ref_id="src_a1_family_south",
        ),
        ReviewItem(
            id="review_a1_tv",
            title="Confirm the TV location",
            question="Should the 60-inch TV sit on the solid east living-room wall?",
            help_text="HearthView will keep the TV on solid wall and away from windows and openings.",
            source_ref_id="src_a1_tv",
        ),
    )
