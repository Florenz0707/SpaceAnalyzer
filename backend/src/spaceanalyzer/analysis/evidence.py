"""Trusted query allowlist and bounded evidence projection for model context."""

import json
from typing import Any, cast

from pydantic import Field

from spaceanalyzer.analysis.models.contracts import (
    ModelCapacity,
    Record,
    ToolDefinition,
)
from spaceanalyzer.services.snapshots import SnapshotService
from spaceanalyzer.storage.analysis import AnalysisQueries


class QueryArguments(Record):
    node_id: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=20)


class Evidence(Record):
    id: str
    query: str
    snapshot_id: str
    data: dict[str, object]


class SkillDefinition(Record):
    id: str
    version: int
    goal: str
    tools: tuple[str, ...]
    capacity: ModelCapacity = ModelCapacity()


DISK_OVERVIEW = SkillDefinition(
    id="disk-overview",
    version=1,
    goal="Explain disk usage with evidence and manual review candidates.",
    tools=("overview", "children", "largest_files", "extensions", "errors"),
)


class EvidenceBuilder:
    def __init__(self, snapshots: SnapshotService) -> None:
        self.snapshots = snapshots
        self.queries = AnalysisQueries(snapshots.store)
        self.allowed = (*DISK_OVERVIEW.tools, "node")

    def tool_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name=name,
                description=f"Read snapshot {name}",
                parameters=QueryArguments.model_json_schema(),
            )
            for name in self.allowed
        ]

    def query(
        self, snapshot_id: str, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        if name not in self.allowed:
            raise ValueError("Unknown read-only query")
        args = QueryArguments.model_validate(arguments)
        return self.queries.query(snapshot_id, name, args.node_id, args.limit)

    def build(self, snapshot_id: str) -> list[Evidence]:
        snapshot = self.snapshots.get_snapshot(snapshot_id)
        if snapshot.status in {"queued", "running"}:
            raise ValueError("Wait for scanning to finish before analysis")
        return [
            Evidence(
                id=f"E{index}",
                query=name,
                snapshot_id=snapshot_id,
                data=self.query(snapshot_id, name, {}),
            )
            for index, name in enumerate(DISK_OVERVIEW.tools, 1)
        ]

    @staticmethod
    def context(evidence: list[Evidence], *, cloud: bool) -> str:
        def project(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    str(key): project(item)
                    for key, item in cast(dict[str, Any], value).items()
                    if not (cloud and key in {"path", "root_path", "name", "message"})
                }
            if isinstance(value, list):
                return [project(item) for item in cast(list[Any], value)[:20]]
            if isinstance(value, str):
                return value[:240]
            return value

        result = json.dumps(
            [project(item.model_dump(mode="json")) for item in evidence],
            ensure_ascii=False,
        )
        if len(result) > 32000:
            raise ValueError("Evidence exceeds context budget")
        return result
