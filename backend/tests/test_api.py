"""HTTP contracts over synthetic scan roots, never user directories."""

import os
from pathlib import Path
from threading import Event, current_thread
from time import monotonic, sleep
from typing import Any

import pytest
from fastapi.testclient import TestClient

from spaceanalyzer.main import create_app
from spaceanalyzer.models import Job


def test_api_scan_query_and_static_fallback(tmp_path: Path) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    (root / "one.bin").write_bytes(b"12345")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>Snapshot app</h1>")
    app = create_app(database=tmp_path / "state.sqlite3", static_dir=static)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/scans", json={"root_path": str(root)})
        assert response.status_code == 202
        job = Job.model_validate(response.json())
        job_id = job.id
        deadline = monotonic() + 5
        while monotonic() < deadline:
            job = Job.model_validate(client.get(f"/api/scans/{job_id}").json())
            if job.status not in {"queued", "running"}:
                break
            sleep(0.01)
        assert job.status == "completed"
        snapshot_id = job.snapshot_id
        assert client.get(f"/api/snapshots/{snapshot_id}").json()["total_bytes"] == 5
        children = client.get(f"/api/snapshots/{snapshot_id}/nodes/1/children").json()
        assert children["items"][0]["name"] == "one.bin"
        assert children["total_bytes"] == 5
        assert client.get("/api/snapshots").json()["total"] == 1
        assert client.get(f"/api/snapshots/{snapshot_id}/errors").json()["total"] == 0
        assert client.get("/api/missing").status_code == 404
        assert "Snapshot app" in client.get("/snapshots/example").text
        assert client.get("/missing.js").status_code == 404
        assert client.get("/api/snapshots/missing").status_code == 404
        assert (
            client.post("/api/scans", json={"root_path": "relative"}).status_code == 400
        )
        assert client.get("/api/snapshots?limit=1001").status_code == 422
        assert (
            client.get(
                "/api/health", headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert (
            client.get("/api/health", headers={"host": "evil.example"}).status_code
            == 403
        )
        assert (
            client.get(
                "/api/health", headers={"origin": "http://127.0.0.1:5173"}
            ).status_code
            == 200
        )


def test_api_remains_responsive_and_rejects_parallel_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = Event(), Event()
    original = os.scandir

    def blocked(path: str) -> Any:
        if current_thread().name.startswith("snapshot"):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("HTTP test gate timed out")
        return original(path)

    monkeypatch.setattr(os, "scandir", blocked)
    app = create_app(database=tmp_path / "state.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        try:
            job = client.post("/api/scans", json={"root_path": str(tmp_path)}).json()
            assert entered.wait(5)
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/snapshots").status_code == 200
            assert (
                client.post("/api/scans", json={"root_path": str(tmp_path)}).status_code
                == 409
            )
            assert client.post(f"/api/scans/{job['id']}/cancel").status_code == 200
        finally:
            release.set()
