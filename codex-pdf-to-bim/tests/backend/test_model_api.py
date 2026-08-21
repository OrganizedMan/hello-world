from fastapi.testclient import TestClient


def create_project(client: TestClient) -> str:
    return client.post("/api/projects", json={"name": "Garrigan"}).json()["id"]


def test_validate_is_blocked_until_review_is_complete(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/validate")

    assert response.status_code == 200
    assert response.json()["report"]["status"] == "NEEDS_INPUT"
    assert response.json()["report"]["blocking_count"] >= 6
    assert any(
        issue["code"] == "PROJECT_SOURCE_REQUIRED"
        for issue in response.json()["report"]["issues"]
    )
    assert response.json()["token"] is None


def test_review_events_without_an_imported_pdf_remain_blocked(client: TestClient) -> None:
    project_id = create_project(client)
    queue = client.get(f"/api/projects/{project_id}/review-queue").json()
    revision = 0
    for index, item in enumerate(queue, start=1):
        response = client.post(
            f"/api/projects/{project_id}/review-events",
            json={
                "id": f"approve-without-source-{index}",
                "base_revision": revision,
                "operation": "APPROVE_REVIEW",
                "item_id": item["id"],
                "payload": {},
                "source_ref_ids": [item["source_ref_id"]],
                "rationale": "Homeowner confirmed this drawing fact.",
            },
        )
        revision = response.json()["revision"]

    result = client.post(f"/api/projects/{project_id}/validate").json()

    assert result["report"]["status"] == "NEEDS_INPUT"
    assert any(issue["code"] == "PROJECT_SOURCE_REQUIRED" for issue in result["report"]["issues"])
    assert result["token"] is None


def test_non_garrigan_pdf_is_never_labeled_as_verified_model(
    client: TestClient,
    one_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("different.pdf", one_page_pdf, "application/pdf")},
    )
    queue = client.get(f"/api/projects/{project_id}/review-queue").json()
    revision = 0
    for index, item in enumerate(queue, start=1):
        response = client.post(
            f"/api/projects/{project_id}/review-events",
            json={
                "id": f"approve-other-{index}",
                "base_revision": revision,
                "operation": "APPROVE_REVIEW",
                "item_id": item["id"],
                "payload": {},
                "source_ref_ids": [item["source_ref_id"]],
                "rationale": "Confirmed.",
            },
        )
        revision = response.json()["revision"]

    result = client.post(f"/api/projects/{project_id}/validate").json()

    assert any(issue["code"] == "UNSUPPORTED_PLAN_SET" for issue in result["report"]["issues"])
    assert result["token"] is None


def test_review_events_make_source_bound_project_ready_and_return_token(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    imported = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("plans.pdf", four_page_pdf, "application/pdf")},
    ).json()
    queue = client.get(f"/api/projects/{project_id}/review-queue").json()
    revision = 0
    for index, item in enumerate(queue, start=1):
        response = client.post(
            f"/api/projects/{project_id}/review-events",
            json={
                "id": f"approve-{index}",
                "base_revision": revision,
                "operation": "APPROVE_REVIEW",
                "item_id": item["id"],
                "payload": {},
                "source_ref_ids": [item["source_ref_id"]],
                "rationale": "Homeowner confirmed this drawing fact.",
            },
        )
        assert response.status_code == 201
        revision = response.json()["revision"]

    result = client.post(f"/api/projects/{project_id}/validate").json()

    assert result["report"]["status"] == "READY_TO_VIEW"
    assert result["report"]["blocking_count"] == 0
    assert result["token"]["model_hash"] == result["report"]["model_hash"]
    model = client.get(f"/api/projects/{project_id}/model").json()
    assert model["source_documents"] == [{
        "id": imported["id"],
        "display_name": "plans.pdf",
        "sha256": imported["sha256"],
        "page_count": 4,
        "profile": "GARRIGAN_A1",
    }]
    assert {reference["source_id"] for reference in model["source_references"]} == {imported["id"]}


def test_stale_review_event_returns_revision_guidance(client: TestClient) -> None:
    project_id = create_project(client)
    event = {
        "id": "approval-1",
        "base_revision": 0,
        "operation": "APPROVE_REVIEW",
        "item_id": "review_a1_region",
        "payload": {},
        "source_ref_ids": ["src_a1_region"],
        "rationale": "Confirmed.",
    }
    assert client.post(f"/api/projects/{project_id}/review-events", json=event).status_code == 201
    event["id"] = "approval-2"

    stale = client.post(f"/api/projects/{project_id}/review-events", json=event)

    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"
    assert "Reload" in stale.json()["action"]


def test_review_decision_can_be_undone_through_api(client: TestClient) -> None:
    project_id = create_project(client)
    approved = client.post(
        f"/api/projects/{project_id}/review-events",
        json={
            "id": "approval-1",
            "base_revision": 0,
            "operation": "APPROVE_REVIEW",
            "item_id": "review_a1_region",
            "payload": {},
            "source_ref_ids": ["src_a1_region"],
            "rationale": "Confirmed.",
        },
    )
    assert approved.status_code == 201

    undone = client.post(
        f"/api/projects/{project_id}/review-events/revert",
        json={
            "id": "undo-1",
            "base_revision": 1,
            "target_event_id": "approval-1",
        },
    )

    assert undone.status_code == 201
    assert undone.json()["revision"] == 2
    queue = client.get(f"/api/projects/{project_id}/review-queue").json()
    assert queue[0]["state"] == "UNREVIEWED"


def test_invalid_dimension_edit_is_rejected_before_event_is_saved(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/review-events",
        json={
            "id": "bad-edit",
            "base_revision": 0,
            "operation": "EDIT_AND_APPROVE",
            "item_id": "review_a1_island",
            "payload": {"width": "banana", "depth": "4'-3\""},
            "source_ref_ids": ["src_a1_island"],
            "rationale": "Corrected.",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_LENGTH"
    assert client.get(f"/api/projects/{project_id}").json()["revision"] == 0


def test_zero_dimension_edit_is_rejected_before_event_is_saved(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/review-events",
        json={
            "id": "zero-edit",
            "base_revision": 0,
            "operation": "EDIT_AND_APPROVE",
            "item_id": "review_a1_island",
            "payload": {"width": "0 in", "depth": "4'-3\""},
            "source_ref_ids": ["src_a1_island"],
            "rationale": "Corrected.",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_LENGTH"
    assert client.get(f"/api/projects/{project_id}").json()["revision"] == 0
