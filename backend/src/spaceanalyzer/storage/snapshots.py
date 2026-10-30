"""Batch ingestion, recovery, and bounded indexed queries."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from spaceanalyzer.models import (
    ChildrenPage,
    Counts,
    Job,
    Node,
    Page,
    ScanError,
    Snapshot,
    Status,
)
from spaceanalyzer.scanner.traversal import Entry, Issue, ScanEvent, Total

SCHEMA = """
CREATE TABLE scan_jobs (
 id TEXT PRIMARY KEY,
 snapshot_id TEXT NOT NULL,
 root_path TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 started_at TEXT,
 ended_at TEXT,
 failure_message TEXT,
 total_bytes INTEGER NOT NULL DEFAULT 0,
 file_count INTEGER NOT NULL DEFAULT 0,
 directory_count INTEGER NOT NULL DEFAULT 0,
 error_count INTEGER NOT NULL DEFAULT 0,
 skipped_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE snapshots (
 id TEXT PRIMARY KEY,
 job_id TEXT NOT NULL REFERENCES scan_jobs(id),
 root_path TEXT NOT NULL,
 root_node_id INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 ended_at TEXT,
 metric TEXT NOT NULL DEFAULT 'logical',
 policy_version INTEGER NOT NULL DEFAULT 1,
 total_bytes INTEGER NOT NULL DEFAULT 0,
 file_count INTEGER NOT NULL DEFAULT 0,
 directory_count INTEGER NOT NULL DEFAULT 0,
 error_count INTEGER NOT NULL DEFAULT 0,
 skipped_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE nodes (
 snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 id INTEGER NOT NULL,
 parent_id INTEGER,
 name TEXT NOT NULL,
 path TEXT NOT NULL,
 kind TEXT NOT NULL,
 size_bytes INTEGER NOT NULL,
 modified_ns INTEGER NOT NULL,
 readable INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(snapshot_id,id)
);
CREATE INDEX nodes_children ON nodes(snapshot_id,parent_id,size_bytes DESC,name,id);
CREATE INDEX snapshots_created ON snapshots(created_at DESC,id);
CREATE TABLE scan_errors (
 id INTEGER PRIMARY KEY,
 snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 path TEXT NOT NULL,
 code TEXT NOT NULL,
 message TEXT NOT NULL
);
CREATE INDEX errors_snapshot ON scan_errors(snapshot_id,id);
PRAGMA user_version=1;
"""


def now() -> str:
    return datetime.now(UTC).isoformat()


def pagination(offset: int, limit: int) -> None:
    if offset < 0 or not 1 <= limit <= 1000:
        raise ValueError("offset must be nonnegative and limit between 1 and 1000")


class SnapshotStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                connection.executescript("BEGIN;" + SCHEMA + "COMMIT;")
            elif version != 1:
                raise ValueError(f"Unsupported database schema version: {version}")
            timestamp = now()
            connection.execute(
                "UPDATE scan_jobs SET status='failed', ended_at=?, "
                "failure_message='Interrupted before restart' WHERE "
                "status IN ('queued', 'running')",
                (timestamp,),
            )
            connection.execute(
                "UPDATE snapshots SET status='failed', ended_at=? "
                "WHERE status IN ('queued', 'running')",
                (timestamp,),
            )

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, root: str) -> Job:
        job_id, snapshot_id, timestamp = uuid4().hex, uuid4().hex, now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO scan_jobs(id, snapshot_id, root_path, "
                "status, created_at) VALUES(?, ?, ?, 'queued', ?)",
                (job_id, snapshot_id, root, timestamp),
            )
            connection.execute(
                "INSERT INTO snapshots(id, job_id, root_path, "
                "status, created_at) VALUES(?, ?, ?, 'queued', ?)",
                (snapshot_id, job_id, root, timestamp),
            )
        return self.job(job_id)

    def begin(self, job: Job) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE scan_jobs SET status='running',started_at=? WHERE id=?",
                (now(), job.id),
            )
            connection.execute(
                "UPDATE snapshots SET status='running' WHERE id=?", (job.snapshot_id,)
            )

    def ingest(self, job: Job, events: Iterator[ScanEvent]) -> Counts:
        counts = Counts()
        with self.connect() as connection:
            pending = 0
            for event in events:
                if isinstance(event, Entry):
                    connection.execute(
                        "INSERT INTO nodes(snapshot_id, id, parent_id, name, "
                        "path, kind, size_bytes, modified_ns) VALUES(?, ?, "
                        "?, ?, ?, ?, ?, ?)",
                        (
                            job.snapshot_id,
                            event.id,
                            event.parent_id,
                            event.name,
                            event.path,
                            event.kind,
                            event.size_bytes,
                            event.modified_ns,
                        ),
                    )
                    if event.kind == "file":
                        counts.file_count += 1
                        counts.total_bytes += event.size_bytes
                    else:
                        counts.directory_count += 1
                elif isinstance(event, Total):
                    connection.execute(
                        "UPDATE nodes SET size_bytes=?, readable=? WHERE "
                        "snapshot_id=? AND id=?",
                        (event.size_bytes, event.readable, job.snapshot_id, event.id),
                    )
                elif isinstance(event, Issue):
                    counts.error_count += 1
                    connection.execute(
                        "INSERT INTO scan_errors(snapshot_id, path, code, "
                        "message) VALUES(?, ?, ?, ?)",
                        (job.snapshot_id, event.path, event.code, event.message),
                    )
                else:
                    counts.skipped_count += 1
                pending += 1
                if pending >= 512:
                    self._counts(connection, job, counts)
                    connection.commit()
                    pending = 0
            self._counts(connection, job, counts)
        return counts

    @staticmethod
    def _counts(connection: sqlite3.Connection, job: Job, counts: Counts) -> None:
        values = (
            counts.total_bytes,
            counts.file_count,
            counts.directory_count,
            counts.error_count,
            counts.skipped_count,
        )
        for table, record_id in (("scan_jobs", job.id), ("snapshots", job.snapshot_id)):
            connection.execute(
                f"UPDATE {table} SET total_bytes=?, file_count=?, "
                "directory_count=?, error_count=?, skipped_count=? "
                "WHERE id=?",
                (*values, record_id),
            )

    def finish(self, job: Job, status: Status, failure: str | None = None) -> None:
        timestamp = now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE scan_jobs SET status=?,ended_at=?,failure_message=? WHERE id=?",
                (status, timestamp, failure, job.id),
            )
            connection.execute(
                "UPDATE snapshots SET status=?,ended_at=? WHERE id=?",
                (status, timestamp, job.snapshot_id),
            )

    def job(self, job_id: str) -> Job:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM scan_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown scan task")
            return Job.model_validate(dict(row))

    def snapshot(self, snapshot_id: str) -> Snapshot:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown snapshot")
            return Snapshot.model_validate(dict(row))

    def snapshots(self, offset: int, limit: int) -> Page[Snapshot]:
        pagination(offset, limit)
        with self.connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM snapshots ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return Page[Snapshot](
                items=[Snapshot.model_validate(dict(row)) for row in rows],
                total=total,
                offset=offset,
                limit=limit,
            )

    def children(
        self, snapshot_id: str, node_id: int, offset: int, limit: int
    ) -> ChildrenPage:
        pagination(offset, limit)
        self.snapshot(snapshot_id)
        with self.connect() as connection:
            node = connection.execute(
                "SELECT kind FROM nodes WHERE snapshot_id=? AND id=?",
                (snapshot_id, node_id),
            ).fetchone()
            if node is None:
                raise KeyError("Unknown node in this snapshot")
            if node[0] != "directory":
                raise ValueError("Only directories have children")
            total, size = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM "
                "nodes WHERE snapshot_id=? AND parent_id=?",
                (snapshot_id, node_id),
            ).fetchone()
            rows = connection.execute(
                "SELECT * FROM nodes WHERE snapshot_id=? AND "
                "parent_id=? ORDER BY size_bytes DESC, name, id "
                "LIMIT ? OFFSET ?",
                (snapshot_id, node_id, limit, offset),
            )
            items = [Node.model_validate(dict(row)) for row in rows]
            returned = sum(item.size_bytes for item in items)
            return ChildrenPage(
                items=items,
                total=total,
                offset=offset,
                limit=limit,
                total_bytes=size,
                returned_bytes=returned,
                omitted_bytes=max(0, size - returned),
            )

    def errors(self, snapshot_id: str, offset: int, limit: int) -> Page[ScanError]:
        pagination(offset, limit)
        self.snapshot(snapshot_id)
        with self.connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM scan_errors WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM scan_errors WHERE snapshot_id=? ORDER "
                "BY id LIMIT ? OFFSET ?",
                (snapshot_id, limit, offset),
            )
            return Page[ScanError](
                items=[ScanError.model_validate(dict(row)) for row in rows],
                total=total,
                offset=offset,
                limit=limit,
            )
