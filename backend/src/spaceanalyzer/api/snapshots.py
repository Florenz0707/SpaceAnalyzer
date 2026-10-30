"""Thin routes over the snapshot service; no traversal or SQL here."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field

from spaceanalyzer.models import ChildrenPage, Job, Page, ScanError, Snapshot
from spaceanalyzer.services.snapshots import SnapshotService

router = APIRouter(prefix="/api")


def get_service(request: Request) -> SnapshotService:
    return cast(SnapshotService, request.app.state.snapshot_service)


Service = Annotated[SnapshotService, Depends(get_service)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=1000)]


class ScanRequest(BaseModel):
    root_path: str = Field(min_length=1, max_length=32760)


@router.post("/scans", status_code=202)
def start_scan(body: ScanRequest, service: Service) -> Job:
    return service.start_scan(body.root_path)


@router.get("/scans/{job_id}")
def get_scan(job_id: str, service: Service) -> Job:
    return service.get_scan(job_id)


@router.post("/scans/{job_id}/cancel")
def cancel_scan(job_id: str, service: Service) -> Job:
    return service.cancel_scan(job_id)


@router.get("/snapshots")
def list_snapshots(
    service: Service, offset: Offset = 0, limit: Limit = 100
) -> Page[Snapshot]:
    return service.list_snapshots(offset, limit)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str, service: Service) -> Snapshot:
    return service.get_snapshot(snapshot_id)


@router.get("/snapshots/{snapshot_id}/nodes/{node_id}/children")
def list_children(
    snapshot_id: str,
    node_id: Annotated[int, Path(ge=1)],
    service: Service,
    offset: Offset = 0,
    limit: Limit = 200,
) -> ChildrenPage:
    return service.list_children(snapshot_id, node_id, offset, limit)


@router.get("/snapshots/{snapshot_id}/errors")
def list_errors(
    snapshot_id: str, service: Service, offset: Offset = 0, limit: Limit = 100
) -> Page[ScanError]:
    return service.list_errors(snapshot_id, offset, limit)
