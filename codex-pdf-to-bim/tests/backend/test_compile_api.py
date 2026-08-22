from fastapi.testclient import TestClient


def approved_project(client: TestClient, four_page_pdf: bytes) -> tuple[str, dict]:
    project_id = client.post("/api/projects", json={"name": "Garrigan"}).json()["id"]
    imported = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("plans.pdf", four_page_pdf, "application/pdf")},
    )
    assert imported.status_code == 201
    queue = client.get(f"/api/projects/{project_id}/review-queue").json()
    for revision, item in enumerate(queue):
        response = client.post(
            f"/api/projects/{project_id}/review-events",
            json={
                "id": f"approve-{revision + 1}",
                "base_revision": revision,
                "operation": "APPROVE_REVIEW",
                "item_id": item["id"],
                "payload": {},
                "source_ref_ids": [item["source_ref_id"]],
                "rationale": "Confirmed.",
            },
        )
        assert response.status_code == 201
    validation = client.post(f"/api/projects/{project_id}/validate").json()
    return project_id, validation["token"]


def test_compile_endpoint_returns_downloadable_model_bound_glb(
    client: TestClient, four_page_pdf: bytes,
) -> None:
    project_id, token = approved_project(client, four_page_pdf)

    response = client.post(
        f"/api/projects/{project_id}/compile",
        json={"token": token},
    )

    assert response.status_code == 201
    artifact = response.json()
    assert artifact["model_hash"] == token["model_hash"]
    assert artifact["island_dimensions"] == "8'-7\" × 4'-3\""
    assert len(artifact["geometry_hash"]) == 64
    downloaded = client.get(artifact["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "model/gltf-binary"
    assert downloaded.content.startswith(b"glTF")


def test_compile_rejects_token_for_different_project(
    client: TestClient, four_page_pdf: bytes,
) -> None:
    _first_project, token = approved_project(client, four_page_pdf)
    second_project = client.post("/api/projects", json={"name": "Other"}).json()["id"]

    response = client.post(
        f"/api/projects/{second_project}/compile",
        json={"token": token},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "TOKEN_MODEL_MISMATCH"


def test_geometry_download_is_bound_to_owning_project(
    client: TestClient, four_page_pdf: bytes,
) -> None:
    project_id, token = approved_project(client, four_page_pdf)
    artifact = client.post(
        f"/api/projects/{project_id}/compile",
        json={"token": token},
    ).json()
    other_project = client.post("/api/projects", json={"name": "Other"}).json()["id"]

    response = client.get(
        f"/api/projects/{other_project}/geometry/{artifact['artifact_id']}.glb"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "GEOMETRY_NOT_FOUND"


def test_project_report_uses_persisted_source_and_geometry_identity(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id, token = approved_project(client, four_page_pdf)
    artifact = client.post(
        f"/api/projects/{project_id}/compile",
        json={"token": token},
    ).json()

    report = client.get(f"/api/projects/{project_id}/report")

    assert report.status_code == 200
    payload = report.json()
    assert len(payload["source_hash"]) == 64
    assert payload["geometry_hash"] == artifact["geometry_hash"]
    assert payload["model_hash"] == artifact["model_hash"]
    assert payload["island_dimensions"] == "8'-7\" × 4'-3\""


def test_report_never_pairs_stale_geometry_with_changed_model(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id, token = approved_project(client, four_page_pdf)
    client.post(f"/api/projects/{project_id}/compile", json={"token": token})
    undone = client.post(
        f"/api/projects/{project_id}/review-events/revert",
        json={
            "id": "undo-after-compile",
            "base_revision": 5,
            "target_event_id": "approve-1",
        },
    )
    assert undone.status_code == 201

    report = client.get(f"/api/projects/{project_id}/report").json()

    assert report["geometry_hash"] == "Not created yet"
