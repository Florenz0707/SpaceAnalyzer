import json
from pathlib import Path

import pytest
from test_snapshots import wait_for_scan

from spaceanalyzer.analysis.evidence import EvidenceBuilder
from spaceanalyzer.services.snapshots import SnapshotService


def test_bounded_evidence_redaction_and_snapshot_scope(tmp_path: Path) -> None:
    root = tmp_path / "private-name"
    root.mkdir()
    (root / "personal.secret.txt").write_bytes(b"abc")
    (root / "small.bin").write_bytes(b"x")
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot = wait_for_scan(service, service.start_scan(str(root)).id)
        builder = EvidenceBuilder(service)
        evidence = builder.build(snapshot)
        assert evidence[0].data["total_bytes"] == 4
        cloud = builder.context(evidence, cloud=True)
        assert "private-name" not in cloud
        assert "personal.secret" not in cloud
        assert '"total_bytes": 4' in cloud
        assert "personal.secret.txt" in builder.context(evidence, cloud=False)
        node = builder.query(snapshot, "node", {"node_id": 2})
        assert node["snapshot_id"] == snapshot
        with pytest.raises(ValueError):
            builder.query(snapshot, "shell", {})
        with pytest.raises(ValueError):
            builder.query(snapshot, "largest_files", {"limit": 100000})
        assert len(json.loads(cloud)) == 5
