"""Bounded analysis queries against persisted snapshots, never the filesystem."""

from pathlib import PurePath

from spaceanalyzer.storage.snapshots import SnapshotStore


def extension(name: object) -> str:
    return PurePath(str(name)).suffix.lower()[:32] or "[none]"


class AnalysisQueries:
    def __init__(self, store: SnapshotStore) -> None:
        self.store = store

    def query(
        self, snapshot_id: str, name: str, node_id: int, limit: int
    ) -> dict[str, object]:
        snapshot = self.store.snapshot(snapshot_id)
        if name == "overview":
            return snapshot.model_dump(mode="json")
        if name == "children":
            return self.store.children(snapshot_id, node_id, 0, limit).model_dump(
                mode="json"
            )
        if name == "errors":
            with self.store.connect() as db:
                rows = db.execute(
                    "SELECT code, COUNT(*) AS records FROM scan_errors "
                    "WHERE snapshot_id=? GROUP BY code ORDER BY records DESC LIMIT ?",
                    (snapshot_id, limit),
                ).fetchall()
                return {
                    "groups": [dict(row) for row in rows],
                    "record_count": snapshot.error_count,
                    "note": "Grouped records, not affected entries",
                }
        with self.store.connect() as db:
            if name == "largest_files":
                rows = db.execute(
                    "SELECT * FROM nodes WHERE snapshot_id=? AND kind='file' "
                    "ORDER BY size_bytes DESC,id LIMIT ?",
                    (snapshot_id, limit),
                ).fetchall()
                return {"items": [dict(row) for row in rows], "limit": limit}
            if name == "extensions":
                db.create_function(
                    "extension",
                    1,
                    extension,
                )
                rows = db.execute(
                    "SELECT extension(name) AS extension, COUNT(*) AS file_count, "
                    "SUM(size_bytes) AS total_bytes FROM nodes WHERE snapshot_id=? "
                    "AND kind='file' GROUP BY extension(name) "
                    "ORDER BY total_bytes DESC LIMIT ?",
                    (snapshot_id, limit),
                ).fetchall()
                return {"groups": [dict(row) for row in rows], "limit": limit}
            if name == "node":
                row = db.execute(
                    "SELECT * FROM nodes WHERE snapshot_id=? AND id=?",
                    (snapshot_id, node_id),
                ).fetchone()
                if row is None:
                    raise KeyError("Unknown node in this snapshot")
                ancestors = db.execute(
                    "WITH RECURSIVE trail AS ("
                    "SELECT id,parent_id,name,kind,0 AS depth FROM nodes "
                    "WHERE snapshot_id=? AND id=? UNION ALL "
                    "SELECT n.id,n.parent_id,n.name,n.kind,t.depth+1 FROM nodes n "
                    "JOIN trail t ON n.id=t.parent_id "
                    "WHERE n.snapshot_id=? AND t.depth<255) "
                    "SELECT id,name FROM trail WHERE kind='directory' "
                    "ORDER BY depth DESC",
                    (snapshot_id, node_id, snapshot_id),
                ).fetchall()
                return {**dict(row), "ancestors": [dict(item) for item in ancestors]}
        raise ValueError("Unknown read-only query")
