from pathlib import Path

from fastapi.testclient import TestClient

from hearthview.rendering import RenderRequest, create_render_job
from hearthview.validation import validate
from tests.backend.test_compile_api import approved_project


def test_render_capability_explains_optional_blender(client: TestClient) -> None:
    response = client.get("/api/render-capability")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["available"], bool)
    if not payload["available"]:
        assert payload["action"] == "Install Blender LTS, then restart HearthView."
        assert "interactive 3D" in payload["message"]


def test_render_job_rejects_unknown_geometry_before_starting_blender(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Garrigan"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/render-jobs",
        json={
            "geometry_artifact_id": "a" * 64,
            "camera": "KITCHEN",
            "quality": "DRAFT",
            "width": 1280,
            "height": 720,
            "style": "WARM_BLANK_SLATE",
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "GEOMETRY_NOT_FOUND"


def test_render_job_rejects_geometry_owned_by_another_project(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    owner_id, token = approved_project(client, four_page_pdf)
    artifact = client.post(
        f"/api/projects/{owner_id}/compile",
        json={"token": token},
    ).json()
    other_id = client.post("/api/projects", json={"name": "Other"}).json()["id"]

    response = client.post(
        f"/api/projects/{other_id}/render-jobs",
        json={
            "geometry_artifact_id": artifact["artifact_id"],
            "camera": "KITCHEN",
            "quality": "DRAFT",
            "width": 1280,
            "height": 720,
            "style": "WARM_BLANK_SLATE",
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "GEOMETRY_NOT_FOUND"


def test_render_job_rejects_geometry_after_model_changes(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id, token = approved_project(client, four_page_pdf)
    artifact = client.post(
        f"/api/projects/{project_id}/compile",
        json={"token": token},
    ).json()
    client.post(
        f"/api/projects/{project_id}/review-events/revert",
        json={
            "id": "undo-before-render",
            "base_revision": 5,
            "target_event_id": "approve-1",
        },
    )

    response = client.post(
        f"/api/projects/{project_id}/render-jobs",
        json={
            "geometry_artifact_id": artifact["artifact_id"],
            "camera": "KITCHEN",
            "quality": "DRAFT",
            "width": 1280,
            "height": 720,
            "style": "WARM_BLANK_SLATE",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "STALE_GEOMETRY"


def test_latest_render_is_recovered_and_interrupted_work_is_explained(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Garrigan"}).json()["id"]
    model_hash = validate(client.app.state.repository.replay(project_id)).model_hash
    geometry_path = tmp_path / "model.glb"
    geometry_path.write_bytes(b"geometry")
    job = create_render_job(
        RenderRequest(
            project_id=project_id,
            geometry_path=geometry_path,
            model_hash=model_hash,
            geometry_hash="a" * 64,
            glb_file_hash="b" * 64,
            source_sha256="c" * 64,
            camera="KITCHEN",
            quality="DRAFT",
            width=1280,
            height=720,
        ),
        client.app.state.config.data_root / "render-jobs",
    )

    response = client.get(f"/api/projects/{project_id}/render-jobs/latest")

    assert response.status_code == 200
    assert response.json()["id"] == job.id
    assert response.json()["status"] == "FAILED"


def test_latest_render_does_not_interrupt_a_live_in_memory_job(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Garrigan"}).json()["id"]
    model_hash = validate(client.app.state.repository.replay(project_id)).model_hash
    geometry_path = tmp_path / "model.glb"
    geometry_path.write_bytes(b"geometry")
    job = create_render_job(
        RenderRequest(
            project_id=project_id,
            geometry_path=geometry_path,
            model_hash=model_hash,
            geometry_hash="a" * 64,
            glb_file_hash="b" * 64,
            source_sha256="c" * 64,
            camera="KITCHEN",
            quality="DRAFT",
            width=1280,
            height=720,
        ),
        client.app.state.config.data_root / "render-jobs",
    )
    client.app.state.render_jobs[job.id] = job

    response = client.get(f"/api/projects/{project_id}/render-jobs/latest")

    assert response.status_code == 200
    assert response.json()["id"] == job.id
    assert response.json()["status"] == "QUEUED"
