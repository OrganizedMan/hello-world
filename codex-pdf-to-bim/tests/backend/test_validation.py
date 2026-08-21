import pytest

from hearthview.fixture import build_a1_fixture
from hearthview.models import FixedObject, ReviewDecision, ReviewState
from hearthview.units import TICKS_PER_INCH
from hearthview.validation import (
    TokenModelMismatch,
    ValidationBlocked,
    assert_token,
    mint_token,
    validate,
)


def approved_a1_fixture():
    model = build_a1_fixture()
    decisions = tuple(
        ReviewDecision(item_id=decision.item_id, state=ReviewState.APPROVED)
        for decision in model.review_decisions
    )
    return model.model_copy(update={"review_decisions": decisions})


def test_unreviewed_fixture_lists_five_homeowner_decisions() -> None:
    report = validate(build_a1_fixture())

    assert report.status == "NEEDS_INPUT"
    assert report.blocking_count == 5
    assert {issue.code for issue in report.issues} == {"REVIEW_REQUIRED"}


def test_approved_a1_fixture_is_ready_and_mints_bound_token() -> None:
    model = approved_a1_fixture()

    report = validate(model)
    token = mint_token(model, report)

    assert report.status == "READY_TO_VIEW"
    assert report.blocking_count == 0
    assert report.evidence_coverage_percent == 100
    assert token.model_hash == report.model_hash
    assert_token(token, model)


def test_tv_over_opening_is_plain_language_blocker() -> None:
    model = approved_a1_fixture()
    invalid_tv = FixedObject(
        id="family_tv",
        kind="TV",
        host_wall_id="family_east",
        start_ticks=140 * TICKS_PER_INCH,
        end_ticks=200 * TICKS_PER_INCH,
        source_ref_ids=("src_a1_tv",),
    )

    report = validate(model.model_copy(update={"fixed_objects": (invalid_tv,)}))

    issue = next(issue for issue in report.issues if issue.code == "TV_REQUIRES_SOLID_WALL")
    assert issue.message == "Move the TV to a solid part of the east living-room wall."
    assert issue.element_id == "family_tv"


def test_island_dimension_change_is_blocking() -> None:
    model = approved_a1_fixture()
    assert model.island is not None
    island = model.island.model_copy(update={"width_ticks": 104 * TICKS_PER_INCH})

    report = validate(model.model_copy(update={"island": island}))

    assert any(issue.code == "ISLAND_SIZE_MISMATCH" for issue in report.issues)
    with pytest.raises(ValidationBlocked, match="blocking issues"):
        mint_token(model, report)


def test_homeowner_confirmed_island_correction_is_allowed() -> None:
    model = approved_a1_fixture()
    assert model.island is not None
    island = model.island.model_copy(update={"width_ticks": 102 * TICKS_PER_INCH})
    decisions = tuple(
        decision.model_copy(update={"state": ReviewState.EDITED_APPROVED})
        if decision.item_id == "review_a1_island"
        else decision
        for decision in model.review_decisions
    )
    corrected = model.model_copy(update={"island": island, "review_decisions": decisions})

    report = validate(corrected)

    assert report.status == "READY_TO_VIEW"
    assert report.blocking_count == 0
    mint_token(corrected, report)


def test_homeowner_confirmation_cannot_allow_a_zero_size_island() -> None:
    model = approved_a1_fixture()
    assert model.island is not None
    island = model.island.model_copy(update={"width_ticks": 0})
    decisions = tuple(
        decision.model_copy(update={"state": ReviewState.EDITED_APPROVED})
        if decision.item_id == "review_a1_island"
        else decision
        for decision in model.review_decisions
    )

    report = validate(model.model_copy(update={"island": island, "review_decisions": decisions}))

    assert report.status == "NEEDS_INPUT"
    assert any(issue.code == "ISLAND_SIZE_MISMATCH" for issue in report.issues)


def test_structural_change_invalidates_existing_token() -> None:
    model = approved_a1_fixture()
    token = mint_token(model, validate(model))
    changed = model.model_copy(update={"level_height_ticks": 99 * TICKS_PER_INCH})

    with pytest.raises(TokenModelMismatch, match="model has changed"):
        assert_token(token, changed)


def test_forged_token_for_current_model_is_rejected() -> None:
    model = approved_a1_fixture()
    token = mint_token(model, validate(model))
    forged = token.model_copy(update={"token_hash": "0" * 64})

    with pytest.raises(TokenModelMismatch, match="validation token"):
        assert_token(forged, model)
