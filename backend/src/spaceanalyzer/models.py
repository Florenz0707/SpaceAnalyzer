"""Public records shared by snapshot services and HTTP contracts."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

Status = Literal[
    "queued", "running", "completed", "completed_with_errors", "cancelled", "failed"
]
T = TypeVar("T")


class Counts(BaseModel):
    total_bytes: int = 0
    file_count: int = 0
    directory_count: int = 0
    error_count: int = 0
    skipped_count: int = 0


class Job(Counts):
    id: str
    snapshot_id: str
    root_path: str
    status: Status
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    failure_message: str | None = None


class Snapshot(Counts):
    id: str
    job_id: str
    root_path: str
    root_node_id: int = 1
    status: Status
    created_at: str
    ended_at: str | None = None
    metric: Literal["logical"] = "logical"
    policy_version: int = 1


class Node(BaseModel):
    id: int
    parent_id: int | None
    snapshot_id: str
    name: str
    path: str
    kind: Literal["directory", "file"]
    size_bytes: int
    modified_ns: int
    readable: bool = True


class ScanError(BaseModel):
    id: int
    snapshot_id: str
    path: str
    code: str
    message: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class ChildrenPage(Page[Node]):
    total_bytes: int
    returned_bytes: int
    omitted_bytes: int
