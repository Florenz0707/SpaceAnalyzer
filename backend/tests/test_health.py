"""Verify the initial API contract exposed to the frontend."""

from fastapi.testclient import TestClient

from spaceanalyzer.main import create_app


def test_health_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "spaceanalyzer",
        "read_only": True,
    }
