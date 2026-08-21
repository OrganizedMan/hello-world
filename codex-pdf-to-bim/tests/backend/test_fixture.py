from hearthview.fixture import build_a1_fixture, build_a1_review_queue
from hearthview.units import TICKS_PER_INCH


def test_a1_fixture_contains_exact_homeowner_facts() -> None:
    model = build_a1_fixture()

    assert model.island.width_ticks == 103 * TICKS_PER_INCH
    assert model.island.depth_ticks == 51 * TICKS_PER_INCH
    assert [item.kind for item in model.wall("family_east").ordered_children] == [
        "WINDOW",
        "SOLID_MOUNT_ZONE",
        "UNFRAMED_OPENING",
    ]
    assert [item.kind for item in model.wall("family_south").ordered_children] == [
        "SOLID",
        "UNFRAMED_OPENING",
        "SOLID",
    ]


def test_all_fixture_architecture_has_source_provenance() -> None:
    model = build_a1_fixture()

    assert model.source_references
    assert all(wall.source_ref_ids for wall in model.walls)
    assert model.island.source_ref_ids
    assert model.fixed_objects[0].source_ref_ids


def test_review_queue_asks_five_plain_language_questions() -> None:
    queue = build_a1_review_queue()

    assert len(queue) == 5
    assert queue[0].title == "Use the proposed first-floor plan?"
    assert all(item.question.endswith("?") for item in queue)
    assert all(item.help_text for item in queue)
    assert all("host" not in item.question.lower() for item in queue)


def test_fixture_json_round_trip_preserves_exact_ticks() -> None:
    model = build_a1_fixture()

    rebuilt = type(model).model_validate_json(model.model_dump_json())

    assert rebuilt == model
