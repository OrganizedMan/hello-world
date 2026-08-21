from dataclasses import replace

from hearthview.a1_spatial import build_a1_spatial_model
from hearthview.units import TICKS_PER_INCH


def inches(value: int) -> int:
    return value * TICKS_PER_INCH


def test_a1_spatial_model_owns_printed_bounds_clearances_and_orientation() -> None:
    spatial = build_a1_spatial_model()

    assert (spatial.bounds.width_ticks, spatial.bounds.depth_ticks) == (
        inches(361),
        inches(191),
    )
    assert spatial.main_ceiling_height_ticks == inches(101)
    assert spatial.living_width_ticks == inches(177)
    assert spatial.north_vector == (0, -1)
    assert (
        spatial.island.x_ticks,
        spatial.island.y_ticks,
        spatial.island.width_ticks,
        spatial.island.depth_ticks,
    ) == (inches(68), inches(68), inches(103), inches(51))
    assert spatial.island.x_ticks - spatial.counter_depth_ticks == inches(42)
    assert spatial.island.y_ticks - spatial.counter_depth_ticks == inches(42)
    assert spatial.bounds.depth_ticks - spatial.island.max_y_ticks == inches(72)


def test_a1_spatial_model_preserves_east_and_south_wall_topology() -> None:
    spatial = build_a1_spatial_model()
    east = spatial.wall("family_east")
    south = spatial.wall("family_south")

    assert east.origin == (inches(360), 0)
    assert east.length_ticks == inches(228)
    assert [(item.kind, item.start_ticks, item.end_ticks) for item in east.segments] == [
        ("WINDOW", inches(12), inches(60)),
        ("SOLID_MOUNT_ZONE", inches(60), inches(132)),
        ("UNFRAMED_OPENING", inches(132), inches(228)),
    ]
    assert south.origin == (inches(226), inches(191))
    assert south.length_ticks == inches(134)
    assert [(item.kind, item.start_ticks, item.end_ticks) for item in south.segments] == [
        ("SOLID", 0, inches(37)),
        ("UNFRAMED_OPENING", inches(37), inches(97)),
        ("SOLID", inches(97), inches(134)),
    ]


def test_canonical_payload_and_hash_are_deterministic_and_exclude_staging() -> None:
    first = build_a1_spatial_model()
    second = build_a1_spatial_model()

    assert first.canonical_payload() == second.canonical_payload()
    assert first.canonical_hash() == second.canonical_hash()

    changed_staging = replace(
        first,
        appearance_anchors=first.appearance_anchors + (("decor_variant", "family_east"),),
    )
    assert changed_staging.canonical_hash() == first.canonical_hash()


def test_project_projection_keeps_every_architectural_source_reference() -> None:
    project = build_a1_spatial_model().to_project_model()

    assert project.source_references
    assert all(wall.source_ref_ids for wall in project.walls)
    assert all(child.source_ref_ids for wall in project.walls for child in wall.ordered_children)
    assert project.island is not None and project.island.source_ref_ids
    assert project.fixed_objects[0].source_ref_ids

