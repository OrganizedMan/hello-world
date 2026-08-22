from fastapi.testclient import TestClient


def create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "My renovation"})
    assert response.status_code == 201
    return response.json()["id"]


def test_project_name_cannot_be_only_whitespace(client: TestClient) -> None:
    response = client.post("/api/projects", json={"name": "   "})

    assert response.status_code == 422


def test_import_returns_hash_page_count_and_immutable_bytes(
    client: TestClient, one_page_pdf: bytes
) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("plans.pdf", one_page_pdf, "application/pdf")},
    )

    assert response.status_code == 201
    source = response.json()
    assert source["display_name"] == "plans.pdf"
    assert source["page_count"] == 1
    assert len(source["sha256"]) == 64
    stored = client.get(f"/api/projects/{project_id}/sources/{source['id']}/file")
    assert stored.content == one_page_pdf
    assert stored.headers["content-type"] == "application/pdf"


def test_imported_page_preview_is_png(client: TestClient, one_page_pdf: bytes) -> None:
    project_id = create_project(client)
    source = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("plans.pdf", one_page_pdf, "application/pdf")},
    ).json()

    preview = client.get(
        f"/api/projects/{project_id}/sources/{source['id']}/pages/1/preview?max_width=640"
    )

    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG")


def test_evidence_preview_is_project_bound_crop(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("plans.pdf", four_page_pdf, "application/pdf")},
    )

    preview = client.get(
        f"/api/projects/{project_id}/evidence/src_a1_island/preview?max_width=640"
    )

    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG")


def test_a1_trace_returns_source_matched_geometry(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    source = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("garrigan.pdf", four_page_pdf, "application/pdf")},
    ).json()

    response = client.get(
        f"/api/projects/{project_id}/sources/{source['id']}/a1-trace"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page_number"] == 2
    assert payload["summary"]["verified"] > 0


def test_a1_trace_preview_is_a_png_crop(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    source = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("garrigan.pdf", four_page_pdf, "application/pdf")},
    ).json()

    response = client.get(
        f"/api/projects/{project_id}/sources/{source['id']}/a1-trace/preview?max_width=1600"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_a1_trace_vector_is_source_extracted_svg(
    client: TestClient,
    four_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    source = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("garrigan.pdf", four_page_pdf, "application/pdf")},
    ).json()

    response = client.get(
        f"/api/projects/{project_id}/sources/{source['id']}/a1-trace/vector.svg"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b'<svg' in response.content
    assert b"source-drawing-count=" in response.content


def test_a1_trace_rejects_unsupported_source(
    client: TestClient,
    one_page_pdf: bytes,
) -> None:
    project_id = create_project(client)
    source = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("other-plan.pdf", one_page_pdf, "application/pdf")},
    ).json()

    response = client.get(
        f"/api/projects/{project_id}/sources/{source['id']}/a1-trace"
    )

    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_A1_TRACE_SOURCE"


def test_malformed_pdf_has_plain_language_recovery(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/sources",
        files={"file": ("not-a-plan.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "INVALID_PDF",
        "message": "HearthView could not read this PDF.",
        "action": "Choose an unencrypted architectural PDF and try again.",
    }
    assert not tuple(
        path
        for path in client.app.state.artifact_store.root.rglob("*")
        if path.is_file()
    )


def test_review_queue_exposes_five_unreviewed_questions(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.get(f"/api/projects/{project_id}/review-queue")

    assert response.status_code == 200
    queue = response.json()
    assert len(queue) == 5
    assert queue[0]["state"] == "UNREVIEWED"
    assert queue[0]["title"] == "Use the proposed first-floor plan?"
