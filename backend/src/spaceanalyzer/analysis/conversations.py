"""Persistable conversation and execution records."""

from typing import Literal

from spaceanalyzer.analysis.evidence import Evidence
from spaceanalyzer.analysis.models.contracts import Record

RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class Conversation(Record):
    id: str
    snapshot_id: str
    model_key: str
    provider: str
    model_id: str
    allow_cloud: bool
    created_at: str
    skill_id: str = "disk-overview"
    skill_version: int = 1


class AnalysisRun(Record):
    id: str
    conversation_id: str
    request_key: str
    question: str
    status: RunStatus
    created_at: str
    text: str = ""
    evidence: list[Evidence] = []
    usage: dict[str, int | None] = {}
    warning: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class RunEvent(Record):
    run_id: str
    sequence: int
    kind: str
    data: dict[str, object]
