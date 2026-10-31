"""Conversation persistence shares SQLite without changing snapshot schema v1."""

import json
import sqlite3
from uuid import uuid4

from spaceanalyzer.analysis.conversations import AnalysisRun, Conversation, RunEvent
from spaceanalyzer.storage.snapshots import SnapshotStore, now

CHAT_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_meta(version INTEGER NOT NULL);
INSERT INTO chat_meta SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM chat_meta);
CREATE TABLE IF NOT EXISTS conversations(
 id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 model_key TEXT NOT NULL, provider TEXT NOT NULL, model_id TEXT NOT NULL,
 allow_cloud INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analysis_runs(
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 request_key TEXT NOT NULL, question TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, text TEXT NOT NULL DEFAULT '',
 evidence TEXT NOT NULL DEFAULT '[]', usage TEXT NOT NULL DEFAULT '{}',
 warning TEXT, error_code TEXT, error_message TEXT,
 UNIQUE(conversation_id,request_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_analysis_running ON analysis_runs((1))
 WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS analysis_events(
 run_id TEXT NOT NULL REFERENCES analysis_runs(id), sequence INTEGER NOT NULL,
 kind TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(run_id,sequence)
);
CREATE INDEX IF NOT EXISTS conversation_runs
 ON analysis_runs(conversation_id,created_at);
"""


class ConversationStore:
    def __init__(self, store: SnapshotStore) -> None:
        self.store = store
        with store.connect() as db:
            db.executescript(CHAT_SCHEMA)
            if db.execute("SELECT version FROM chat_meta").fetchone()[0] != 1:
                raise ValueError("Unsupported conversation schema")
            interrupted = db.execute(
                "SELECT id FROM analysis_runs WHERE status IN ('queued','running')"
            ).fetchall()
            for row in interrupted:
                db.execute(
                    "UPDATE analysis_runs SET status='failed', "
                    "error_code='interrupted', "
                    "error_message='Interrupted before restart' WHERE id=?",
                    (row[0],),
                )
                self._append(
                    db,
                    row[0],
                    "terminal",
                    {"status": "failed", "error_code": "interrupted"},
                )

    @staticmethod
    def _append(
        db: sqlite3.Connection, run_id: str, kind: str, data: dict[str, object]
    ) -> None:
        db.execute(
            "INSERT INTO analysis_events(run_id,sequence,kind,data) "
            "SELECT ?,COALESCE(MAX(sequence),0)+1,?,? "
            "FROM analysis_events WHERE run_id=?",
            (run_id, kind, json.dumps(data, ensure_ascii=False), run_id),
        )

    def create_conversation(
        self,
        snapshot_id: str,
        model_key: str,
        provider: str,
        model_id: str,
        allow_cloud: bool,
    ) -> Conversation:
        record = Conversation(
            id=uuid4().hex,
            snapshot_id=snapshot_id,
            model_key=model_key,
            provider=provider,
            model_id=model_id,
            allow_cloud=allow_cloud,
            created_at=now(),
        )
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO conversations VALUES(?,?,?,?,?,?,?)",
                (
                    record.id,
                    snapshot_id,
                    model_key,
                    provider,
                    model_id,
                    int(allow_cloud),
                    record.created_at,
                ),
            )
        return record

    def conversation(self, conversation_id: str) -> Conversation:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE id=?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown conversation")
            return Conversation.model_validate(dict(row))

    def list_conversations(self, snapshot_id: str) -> list[Conversation]:
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM conversations WHERE snapshot_id=? "
                "ORDER BY created_at DESC LIMIT 50",
                (snapshot_id,),
            ).fetchall()
            return [Conversation.model_validate(dict(row)) for row in rows]

    @staticmethod
    def _run(row: sqlite3.Row) -> AnalysisRun:
        data = dict(row)
        for field in ("evidence", "usage"):
            data[field] = json.loads(data[field])
        return AnalysisRun.model_validate(data)

    def run(self, run_id: str) -> AnalysisRun:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM analysis_runs WHERE id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown analysis run")
            return self._run(row)

    def runs(self, conversation_id: str) -> list[AnalysisRun]:
        self.conversation(conversation_id)
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM analysis_runs WHERE conversation_id=? "
                "ORDER BY created_at DESC,id DESC LIMIT 20",
                (conversation_id,),
            ).fetchall()
            return [self._run(row) for row in reversed(rows)]

    def create_run(
        self, conversation_id: str, question: str, request_key: str
    ) -> tuple[AnalysisRun, bool]:
        self.conversation(conversation_id)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT * FROM analysis_runs WHERE conversation_id=? AND request_key=?",
                (conversation_id, request_key),
            ).fetchone()
            if previous:
                run = self._run(previous)
                if run.question != question:
                    raise ValueError("Request key was used for another question")
                return run, False
            if db.execute(
                "SELECT 1 FROM analysis_runs WHERE status IN ('queued','running')"
            ).fetchone():
                raise RuntimeError("Another analysis run is active")
            run = AnalysisRun(
                id=uuid4().hex,
                conversation_id=conversation_id,
                request_key=request_key,
                question=question,
                status="queued",
                created_at=now(),
            )
            db.execute(
                "INSERT INTO analysis_runs(id,conversation_id,request_key,"
                "question,status,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (
                    run.id,
                    conversation_id,
                    request_key,
                    question,
                    run.status,
                    run.created_at,
                ),
            )
            self._append(db, run.id, "status", {"status": "queued"})
            return run, True

    def save(self, run: AnalysisRun, kind: str, data: dict[str, object]) -> None:
        with self.store.connect() as db:
            db.execute(
                "UPDATE analysis_runs SET status=?,text=?,evidence=?,usage=?,warning=?,"
                "error_code=?,error_message=? WHERE id=?",
                (
                    run.status,
                    run.text,
                    json.dumps(
                        [e.model_dump() for e in run.evidence], ensure_ascii=False
                    ),
                    json.dumps(run.usage),
                    run.warning,
                    run.error_code,
                    run.error_message,
                    run.id,
                ),
            )
            self._append(db, run.id, kind, data)

    def events(self, run_id: str, after: int) -> list[RunEvent]:
        self.run(run_id)
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM analysis_events WHERE run_id=? AND sequence>? "
                "ORDER BY sequence LIMIT 100",
                (run_id, after),
            ).fetchall()
            return [
                RunEvent(
                    run_id=row["run_id"],
                    sequence=row["sequence"],
                    kind=row["kind"],
                    data=json.loads(row["data"]),
                )
                for row in rows
            ]
