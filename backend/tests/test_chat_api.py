import json
from pathlib import Path
from time import sleep

from fastapi.testclient import TestClient
from test_analysis_workflow import ScriptedAdapter
from test_snapshots import wait_for_scan

from spaceanalyzer.analysis.models.contracts import ModelSpec
from spaceanalyzer.analysis.models.registry import ModelRegistry
from spaceanalyzer.main import create_app
from spaceanalyzer.services.snapshots import SnapshotService


def test_chat_http_history_replay_and_idempotency(tmp_path: Path) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    (root / "a.txt").write_bytes(b"abc")
    database = tmp_path / "state.sqlite3"
    with SnapshotService(database) as snapshots:
        snapshot_id = wait_for_scan(snapshots, snapshots.start_scan(str(root)).id)
    registry = ModelRegistry()
    adapter = ScriptedAdapter()
    registry.register(
        ModelSpec(key="fixture", provider="ollama", model_id="fixture"), adapter
    )
    with TestClient(
        create_app(database=database, model_registry=registry),
        base_url="http://127.0.0.1:8000",
    ) as client:
        assert client.get("/api/models").json()["items"][0]["key"] == "fixture"
        response = client.post(
            "/api/conversations",
            json={"snapshot_id": snapshot_id, "model_key": "fixture"},
        )
        assert response.status_code == 201
        conversation = response.json()["id"]
        path = f"/api/conversations/{conversation}/runs"
        request = {"question": "分析", "request_key": "fixture-request"}
        response = client.post(path, json=request)
        assert response.status_code == 202
        run_id = response.json()["id"]
        run: dict[str, object] = {}
        for _ in range(100):
            run = client.get(f"/api/runs/{run_id}").json()
            if run["status"] not in {"queued", "running"}:
                break
            sleep(0.01)
        assert run["status"] == "completed"
        events = client.get(f"/api/runs/{run_id}/events").text
        payloads = [
            json.loads(line[6:])
            for line in events.splitlines()
            if line.startswith("data: ")
        ]
        assert payloads[-1]["kind"] == "terminal"
        last_id = payloads[-1]["sequence"]
        assert not client.get(
            f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(last_id)}
        ).text
        assert (
            client.get(
                f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "invalid"}
            ).status_code
            == 400
        )
        assert client.post(path, json=request).json()["id"] == run_id
        assert len(adapter.requests) == 1
        assert len(client.get(path).json()) == 1
        assert (
            client.get(f"/api/snapshots/{snapshot_id}/nodes/2").json()["name"]
            == "a.txt"
        )
        assert client.get("/api/health").status_code == 200
