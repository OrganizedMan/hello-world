from fastapi.testclient import TestClient

from hearthview_api.main import create_app


def test_health_reports_local_service() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "hearthview-api"}
