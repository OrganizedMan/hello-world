from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from hearthview.canonical import canonical_hash
from hearthview.models import (
    ChildKind,
    FixedObject,
    Island,
    ProjectModel,
    ReviewDecision,
    SourceDocument,
    SourceReference,
    Wall,
    WallChild,
)
from hearthview.units import TICKS_PER_INCH


Axis = Literal["X", "Y"]


def _inches(value: int) -> int:
    return value * TICKS_PER_INCH


@dataclass(frozen=True)
class PlanBounds:
    width_ticks: int
    depth_ticks: int


@dataclass(frozen=True)
class SpatialRect:
    id: str
    x_ticks: int
    y_ticks: int
    width_ticks: int
    depth_ticks: int
    source_ref_ids: tuple[str, ...]

    @property
    def max_x_ticks(self) -> int:
        return self.x_ticks + self.width_ticks

    @property
    def max_y_ticks(self) -> int:
        return self.y_ticks + self.depth_ticks


@dataclass(frozen=True)
class SpatialSegment:
    id: str
    kind: ChildKind
    start_ticks: int
    end_ticks: int
    source_ref_ids: tuple[str, ...]
    connects_to: str | None = None


@dataclass(frozen=True)
class SpatialWall:
    id: str
    name: str
    axis: Axis
    origin_x_ticks: int
    origin_y_ticks: int
    length_ticks: int
    thickness_ticks: int
    height_ticks: int
    segments: tuple[SpatialSegment, ...]
    source_ref_ids: tuple[str, ...]

    @property
    def origin(self) -> tuple[int, int]:
        return (self.origin_x_ticks, self.origin_y_ticks)


@dataclass(frozen=True)
class SpatialRegion:
    id: str
    label: str
    bounds: SpatialRect
    evidence: Literal["PRINTED", "REVIEWED"]


@dataclass(frozen=True)
class CeilingZone:
    id: str
    bounds: SpatialRect
    height_ticks: int
    evidence: Literal["PRINTED", "REVIEWED"]


@dataclass(frozen=True)
class A1SpatialModel:
    bounds: PlanBounds
    main_ceiling_height_ticks: int
    living_width_ticks: int
    counter_depth_ticks: int
    walls: tuple[SpatialWall, ...]
    regions: tuple[SpatialRegion, ...]
    ceiling_zones: tuple[CeilingZone, ...]
    island: SpatialRect
    north_vector: tuple[int, int]
    tv_interval_ticks: tuple[int, int]
    appearance_anchors: tuple[tuple[str, str], ...]

    def wall(self, wall_id: str) -> SpatialWall:
        try:
            return next(wall for wall in self.walls if wall.id == wall_id)
        except StopIteration as error:
            raise KeyError(wall_id) from error

    def canonical_payload(self) -> dict[str, object]:
        return {
            "coordinate_frame": {
                "origin": "NW_INNER_FACE",
                "positive_x": "EAST",
                "positive_y": "SOUTH",
                "positive_z": "UP",
                "ticks_per_inch": TICKS_PER_INCH,
            },
            "bounds": asdict(self.bounds),
            "main_ceiling_height_ticks": self.main_ceiling_height_ticks,
            "living_width_ticks": self.living_width_ticks,
            "counter_depth_ticks": self.counter_depth_ticks,
            "north_vector": self.north_vector,
            "walls": [asdict(wall) for wall in self.walls],
            "regions": [asdict(region) for region in self.regions],
            "ceiling_zones": [asdict(zone) for zone in self.ceiling_zones],
            "island": asdict(self.island),
            "tv_interval_ticks": self.tv_interval_ticks,
        }

    def canonical_hash(self) -> str:
        return canonical_hash(self.canonical_payload())

    def to_project_model(
        self,
        *,
        source_document: SourceDocument | None = None,
    ) -> ProjectModel:
        document = source_document if source_document is not None else default_a1_source_document()
        source_id = document.id
        return ProjectModel(
            id="garrigan-a1",
            name="Garrigan Residence - Proposed First Floor",
            level_height_ticks=self.main_ceiling_height_ticks,
            source_documents=(document,),
            source_references=build_a1_source_references(source_id),
            walls=tuple(
                Wall(
                    id=wall.id,
                    name=wall.name,
                    axis=wall.axis,
                    origin_x_ticks=wall.origin_x_ticks,
                    origin_y_ticks=wall.origin_y_ticks,
                    length_ticks=wall.length_ticks,
                    thickness_ticks=wall.thickness_ticks,
                    height_ticks=wall.height_ticks,
                    ordered_children=tuple(
                        WallChild(
                            id=segment.id,
                            kind=segment.kind,
                            start_ticks=segment.start_ticks,
                            end_ticks=segment.end_ticks,
                            connects_to=segment.connects_to,
                            source_ref_ids=segment.source_ref_ids,
                        )
                        for segment in wall.segments
                    ),
                    source_ref_ids=wall.source_ref_ids,
                )
                for wall in self.walls
            ),
            fixed_objects=(
                FixedObject(
                    id="family_tv",
                    kind="TV",
                    host_wall_id="family_east",
                    start_ticks=self.tv_interval_ticks[0],
                    end_ticks=self.tv_interval_ticks[1],
                    source_ref_ids=("src_a1_tv",),
                ),
            ),
            island=Island(
                id=self.island.id,
                width_ticks=self.island.width_ticks,
                depth_ticks=self.island.depth_ticks,
                x_ticks=self.island.x_ticks,
                y_ticks=self.island.y_ticks,
                source_ref_ids=self.island.source_ref_ids,
            ),
            review_decisions=tuple(
                ReviewDecision(item_id=item_id)
                for item_id in (
                    "review_a1_region",
                    "review_a1_island",
                    "review_a1_east_wall",
                    "review_a1_south_wall",
                    "review_a1_tv",
                )
            ),
        )


def default_a1_source_document() -> SourceDocument:
    return SourceDocument(
        id="garrigan_main",
        display_name="Garrigan A-1 fixture.pdf",
        sha256="0" * 64,
        page_count=4,
        profile="GARRIGAN_A1",
    )


def build_a1_source_references(source_id: str) -> tuple[SourceReference, ...]:
    return (
        SourceReference(
            id="src_a1_region",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1440, 330), (2190, 330), (2190, 1490), (1440, 1490)),
            rationale="Proposed first-floor plan on sheet A-1.",
        ),
        SourceReference(
            id="src_a1_north_wall",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1450, 650), (1980, 650), (1980, 735), (1450, 735)),
            rationale="Reviewed north kitchen window and deck-glazing topology on A-1.",
        ),
        SourceReference(
            id="src_a1_west_wall",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1435, 650), (1510, 650), (1510, 970), (1435, 970)),
            rationale="Reviewed west kitchen appliance-wall topology on A-1.",
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
            rationale="Kitchen island dimensions and printed clearances.",
        ),
        SourceReference(
            id="src_a1_tv",
            source_id=source_id,
            page_number=2,
            pdf_polygon=((1980, 760), (2040, 760), (2040, 925), (1980, 925)),
            rationale="60-inch TV note on the solid east living-room wall.",
        ),
    )


def build_a1_spatial_model() -> A1SpatialModel:
    height = _inches(101)
    thickness = _inches(6)
    island = SpatialRect(
        id="kitchen_island",
        x_ticks=_inches(68),
        y_ticks=_inches(68),
        width_ticks=_inches(103),
        depth_ticks=_inches(51),
        source_ref_ids=("src_a1_island",),
    )
    walls = (
        SpatialWall(
            id="kitchen_north",
            name="North kitchen and deck wall",
            axis="X",
            origin_x_ticks=0,
            origin_y_ticks=0,
            length_ticks=_inches(361),
            thickness_ticks=thickness,
            height_ticks=height,
            segments=(
                SpatialSegment(
                    id="kitchen_north_window",
                    kind="WINDOW",
                    start_ticks=_inches(155),
                    end_ticks=_inches(209),
                    source_ref_ids=("src_a1_north_wall",),
                ),
                SpatialSegment(
                    id="kitchen_north_deck_glazing",
                    kind="WINDOW",
                    start_ticks=_inches(238),
                    end_ticks=_inches(346),
                    source_ref_ids=("src_a1_north_wall",),
                    connects_to="Deck",
                ),
            ),
            source_ref_ids=("src_a1_north_wall",),
        ),
        SpatialWall(
            id="kitchen_west",
            name="West kitchen appliance wall",
            axis="Y",
            origin_x_ticks=0,
            origin_y_ticks=0,
            length_ticks=_inches(191),
            thickness_ticks=thickness,
            height_ticks=height,
            segments=(),
            source_ref_ids=("src_a1_west_wall",),
        ),
        SpatialWall(
            id="family_east",
            name="East living-room wall",
            axis="Y",
            origin_x_ticks=_inches(360),
            origin_y_ticks=0,
            length_ticks=_inches(228),
            thickness_ticks=thickness,
            height_ticks=height,
            segments=(
                SpatialSegment(
                    id="family_east_window",
                    kind="WINDOW",
                    start_ticks=_inches(12),
                    end_ticks=_inches(60),
                    source_ref_ids=("src_a1_family_east",),
                ),
                SpatialSegment(
                    id="family_east_tv_zone",
                    kind="SOLID_MOUNT_ZONE",
                    start_ticks=_inches(60),
                    end_ticks=_inches(132),
                    source_ref_ids=("src_a1_family_east", "src_a1_tv"),
                ),
                SpatialSegment(
                    id="family_east_mudroom_opening",
                    kind="UNFRAMED_OPENING",
                    start_ticks=_inches(132),
                    end_ticks=_inches(228),
                    source_ref_ids=("src_a1_family_east",),
                    connects_to="Mudroom",
                ),
            ),
            source_ref_ids=("src_a1_family_east",),
        ),
        SpatialWall(
            id="family_south",
            name="South living-room wall",
            axis="X",
            origin_x_ticks=_inches(226),
            origin_y_ticks=_inches(191),
            length_ticks=_inches(134),
            thickness_ticks=thickness,
            height_ticks=height,
            segments=(
                SpatialSegment(
                    id="family_south_west_return",
                    kind="SOLID",
                    start_ticks=0,
                    end_ticks=_inches(37),
                    source_ref_ids=("src_a1_family_south",),
                ),
                SpatialSegment(
                    id="family_south_living_opening",
                    kind="UNFRAMED_OPENING",
                    start_ticks=_inches(37),
                    end_ticks=_inches(97),
                    source_ref_ids=("src_a1_family_south",),
                    connects_to="Existing living room",
                ),
                SpatialSegment(
                    id="family_south_east_return",
                    kind="SOLID",
                    start_ticks=_inches(97),
                    end_ticks=_inches(134),
                    source_ref_ids=("src_a1_family_south",),
                ),
            ),
            source_ref_ids=("src_a1_family_south",),
        ),
    )
    for wall in walls:
        previous_end = 0
        for segment in wall.segments:
            if segment.start_ticks < previous_end or segment.end_ticks > wall.length_ticks:
                raise ValueError(f"Invalid canonical interval {segment.id} on {wall.id}")
            previous_end = segment.end_ticks

    return A1SpatialModel(
        bounds=PlanBounds(width_ticks=_inches(361), depth_ticks=_inches(191)),
        main_ceiling_height_ticks=height,
        living_width_ticks=_inches(177),
        counter_depth_ticks=_inches(26),
        walls=walls,
        regions=(
            SpatialRegion(
                id="kitchen",
                label="Kitchen",
                bounds=SpatialRect("kitchen", 0, 0, _inches(184), _inches(191), ("src_a1_region",)),
                evidence="REVIEWED",
            ),
            SpatialRegion(
                id="family_room",
                label="Family room",
                bounds=SpatialRect(
                    "family_room", _inches(184), 0, _inches(177), _inches(191), ("src_a1_region",)
                ),
                evidence="PRINTED",
            ),
            SpatialRegion(
                id="mudroom_context",
                label="Mudroom",
                bounds=SpatialRect(
                    "mudroom_context", _inches(361), _inches(132), _inches(72), _inches(96), ("src_a1_region",)
                ),
                evidence="REVIEWED",
            ),
            SpatialRegion(
                id="existing_living_context",
                label="Existing living room",
                bounds=SpatialRect(
                    "existing_living_context", _inches(226), _inches(191), _inches(134), _inches(72), ("src_a1_region",)
                ),
                evidence="REVIEWED",
            ),
        ),
        ceiling_zones=(
            CeilingZone(
                id="main_ceiling",
                bounds=SpatialRect("main_ceiling", 0, 0, _inches(361), _inches(191), ("src_a1_region",)),
                height_ticks=height,
                evidence="PRINTED",
            ),
            CeilingZone(
                id="pantry_stair_low_ceiling",
                bounds=SpatialRect(
                    "pantry_stair_low_ceiling", _inches(361), _inches(60), _inches(72), _inches(72), ("src_a1_region",)
                ),
                height_ticks=_inches(84),
                evidence="REVIEWED",
            ),
        ),
        island=island,
        north_vector=(0, -1),
        tv_interval_ticks=(_inches(66), _inches(126)),
        appearance_anchors=(
            ("north_cabinetry", "kitchen_north"),
            ("west_appliances", "kitchen_west"),
            ("family_tv", "family_east_tv_zone"),
            ("island_stools", "kitchen_island"),
        ),
    )

