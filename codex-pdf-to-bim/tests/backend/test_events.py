import pytest

from hearthview.events import ModelEvent, ProjectRepository, RevisionConflict
from hearthview.models import ReviewState


def approval(event_id: str = "event-1") -> ModelEvent:
    return ModelEvent(
        id=event_id,
        operation="APPROVE_REVIEW",
        item_id="review_a1_region",
        payload={},
        source_ref_ids=("src_a1_region",),
        rationale="Homeowner confirmed the proposed plan.",
    )


def test_project_survives_repository_restart(tmp_path) -> None:
    database = tmp_path / "hearthview.sqlite3"
    created = ProjectRepository(database).create("My renovation", project_id="project-1")

    reopened = ProjectRepository(database).get(created.id)

    assert reopened.name == "My renovation"
    assert reopened.revision == 0


def test_approved_review_event_replays_into_project(repository: ProjectRepository) -> None:
    project = repository.create("Garrigan", project_id="project-1")

    revision = repository.append_event(project.id, base_revision=0, event=approval())
    replayed = repository.replay(project.id)

    assert revision == 1
    assert replayed.revision == 1
    assert replayed.review_state("review_a1_region") is ReviewState.APPROVED


def test_stale_event_revision_is_rejected(repository: ProjectRepository) -> None:
    project = repository.create("Garrigan", project_id="project-1")
    repository.append_event(project.id, base_revision=0, event=approval())

    with pytest.raises(RevisionConflict, match="current revision is 1"):
        repository.append_event(project.id, base_revision=0, event=approval("event-2"))


def test_revert_event_undoes_without_deleting_history(repository: ProjectRepository) -> None:
    project = repository.create("Garrigan", project_id="project-1")
    repository.append_event(project.id, base_revision=0, event=approval())
    repository.revert_event(project.id, base_revision=1, target_event_id="event-1")

    replayed = repository.replay(project.id)

    assert replayed.revision == 2
    assert replayed.review_state("review_a1_region") is ReviewState.UNREVIEWED
    assert [event.id for event in repository.list_events(project.id)] == ["event-1", "revert-event-1"]


def test_edit_and_approve_updates_island_dimensions(repository: ProjectRepository) -> None:
    project = repository.create("Garrigan", project_id="project-1")
    repository.append_event(
        project.id,
        base_revision=0,
        event=ModelEvent(
            id="edit-island",
            operation="EDIT_AND_APPROVE",
            item_id="review_a1_island",
            payload={"width": "8'-6\"", "depth": "4'-2\""},
            source_ref_ids=("src_a1_island",),
            rationale="Homeowner corrected the printed dimensions.",
        ),
    )

    replayed = repository.replay(project.id)

    assert replayed.review_state("review_a1_island") is ReviewState.EDITED_APPROVED
    assert replayed.island is not None
    assert replayed.island.width_ticks == 102 * 1024
    assert replayed.island.depth_ticks == 50 * 1024
