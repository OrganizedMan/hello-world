from hearthview.models import (
    FixedObject,
    Island,
    ProjectModel,
    ReviewDecision,
    ReviewItem,
    SourceDocument,
    SourceReference,
    Wall,
    WallChild,
)
from hearthview.units import TICKS_PER_INCH


def _inches(value: int) -> int:
    return value * TICKS_PER_INCH


_FIXTURE_SOURCE = SourceDocument(
    id="garrigan_main",
    display_name="Garrigan A-1 fixture.pdf",
    sha256="0" * 64,
    page_count=4,
    profile="GARRIGAN_A1",
)


def build_a1_fixture(source_document: SourceDocument | None = _FIXTURE_SOURCE) -> ProjectModel:
    source_id = source_document.id if source_document is not None else "missing_source"
    source_references = (
        SourceReference(
            id="src_a1_region",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1440, 330), (2190, 330), (2190, 1490), (1440, 1490)),
            rationale="Proposed first-floor plan on sheet A-1.",
        ),
        SourceReference(
            id="src_a1_family_east",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1975, 705), (2130, 705), (2130, 990), (1975, 990)),
            rationale="East living-room wall, window, TV note, and mudroom opening.",
        ),
        SourceReference(
            id="src_a1_family_south",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1740, 975), (1990, 975), (1990, 1040), (1740, 1040)),
            rationale="South living-room wall with 3'-1\", 5'-0\", 3'-1\" chain.",
        ),
        SourceReference(
            id="src_a1_island",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1590, 690), (1830, 690), (1830, 910), (1590, 910)),
            rationale="Kitchen island dimensions 8'-7\" by 4'-3\".",
        ),
        SourceReference(
            id="src_a1_tv",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1980, 760), (2040, 760), (2040, 925), (1980, 925)),
            rationale="60-inch TV note on the solid east living-room wall.",
        ),
    )
    east_wall = Wall(
        id="family_east",
        name="East living-room wall",
        axis="Y",
        origin_x_ticks=_inches(360),
        origin_y_ticks=0,
        length_ticks=_inches(228),
        thickness_ticks=_inches(6),
        height_ticks=_inches(101),
        ordered_children=(
            WallChild(
                id="family_east_window",
                kind="WINDOW",
                start_ticks=_inches(12),
                end_ticks=_inches(60),
                source_ref_ids=("src_a1_family_east",),
            ),
            WallChild(
                id="family_east_tv_zone",
                kind="SOLID_MOUNT_ZONE",
                start_ticks=_inches(60),
                end_ticks=_inches(132),
                source_ref_ids=("src_a1_family_east", "src_a1_tv"),
            ),
            WallChild(
                id="family_east_mudroom_opening",
                kind="UNFRAMED_OPENING",
                start_ticks=_inches(132),
                end_ticks=_inches(228),
                connects_to="Mudroom",
                source_ref_ids=("src_a1_family_east",),
            ),
        ),
        source_ref_ids=("src_a1_family_east",),
    )
    south_wall = Wall(
        id="family_south",
        name="South living-room wall",
        axis="X",
        origin_x_ticks=_inches(226),
        origin_y_ticks=0,
        length_ticks=_inches(134),
        thickness_ticks=_inches(6),
        height_ticks=_inches(101),
        ordered_children=(
            WallChild(
                id="family_south_west_return",
                kind="SOLID",
                start_ticks=0,
                end_ticks=_inches(37),
                source_ref_ids=("src_a1_family_south",),
            ),
            WallChild(
                id="family_south_living_opening",
                kind="UNFRAMED_OPENING",
                start_ticks=_inches(37),
                end_ticks=_inches(97),
                connects_to="Existing living room",
                source_ref_ids=("src_a1_family_south",),
            ),
            WallChild(
                id="family_south_east_return",
                kind="SOLID",
                start_ticks=_inches(97),
                end_ticks=_inches(134),
                source_ref_ids=("src_a1_family_south",),
            ),
        ),
        source_ref_ids=("src_a1_family_south",),
    )
    return ProjectModel(
        id="garrigan-a1",
        name="Garrigan Residence - Proposed First Floor",
        source_documents=(source_document,) if source_document is not None else (),
        source_references=source_references,
        walls=(east_wall, south_wall),
        fixed_objects=(
            FixedObject(
                id="family_tv",
                kind="TV",
                host_wall_id="family_east",
                start_ticks=_inches(66),
                end_ticks=_inches(126),
                source_ref_ids=("src_a1_tv",),
            ),
        ),
        island=Island(
            id="kitchen_island",
            width_ticks=_inches(103),
            depth_ticks=_inches(51),
            x_ticks=_inches(80),
            y_ticks=_inches(72),
            source_ref_ids=("src_a1_island",),
        ),
        review_decisions=tuple(
            ReviewDecision(item_id=item.id) for item in build_a1_review_queue()
        ),
    )


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
