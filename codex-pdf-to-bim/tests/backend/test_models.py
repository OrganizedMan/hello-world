import json

import pytest
from pydantic import ValidationError

from hearthview.models import Island, ProjectModel, ReviewState
from hearthview.units import TICKS_PER_INCH


def test_tick_fields_serialize_as_decimal_strings_for_json_safety() -> None:
    island = Island(
        id="island_a1",
        width_ticks=103 * TICKS_PER_INCH,
        depth_ticks=51 * TICKS_PER_INCH,
        x_ticks=0,
        y_ticks=0,
        source_ref_ids=("src_a1_island",),
    )

    payload = json.loads(island.model_dump_json())

    assert payload["width_ticks"] == "105472"
    assert payload["depth_ticks"] == "52224"
    assert Island.model_validate(payload) == island


def test_domain_models_are_frozen_after_creation() -> None:
    island = Island(
        id="island_a1",
        width_ticks=1,
        depth_ticks=1,
        x_ticks=0,
        y_ticks=0,
        source_ref_ids=("source",),
    )

    with pytest.raises(ValidationError, match="frozen"):
        island.width_ticks = 2  # type: ignore[misc]


def test_project_wall_lookup_rejects_unknown_ids() -> None:
    project = ProjectModel.empty("project", "Home")

    with pytest.raises(KeyError, match="unknown-wall"):
        project.wall("unknown-wall")


def test_review_state_uses_explicit_homeowner_decisions() -> None:
    assert {state.value for state in ReviewState} == {
        "UNREVIEWED",
        "APPROVED",
        "EDITED_APPROVED",
        "REJECTED",
        "CONFLICT",
    }
