"""Verify the initial API contract exposed to the frontend."""

from pathlib import Path

from fastapi.testclient import TestClient

from spaceanalyzer.main import create_app


def test_health_contract(tmp_path: Path) -> None:
    with TestClient(
        create_app(database=tmp_path / "state.sqlite3"),
        base_url="http://127.0.0.1:8000",
    ) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "spaceanalyzer",
        "read_only": True,
    }
