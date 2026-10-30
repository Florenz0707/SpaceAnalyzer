"""Public snapshot service: queries never implicitly revisit the filesystem."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from types import TracebackType

from spaceanalyzer.models import ChildrenPage, Job, Page, ScanError, Snapshot, Status
from spaceanalyzer.scanner.traversal import scan_directory, validate_root
from spaceanalyzer.storage.snapshots import SnapshotStore


class ScanBusyError(RuntimeError):
    """A single scan is already active in this application instance."""


class SnapshotService:
    def __init__(self, database: Path) -> None:
        self.database = database.absolute()
        self.store = SnapshotStore(self.database)
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="snapshot"
        )
        self._lock = Lock()
        self._active: tuple[str, Event] | None = None
        self._closed = False
        self._failures: dict[str, str] = {}

    def __enter__(self) -> SnapshotService:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def start_scan(self, root: str) -> Job:
        with self._lock:
            if self._closed:
                raise RuntimeError("The snapshot service is closed")
            if self._active is not None and self.store.job(self._active[0]).status in {
                "queued",
                "running",
            }:
                raise ScanBusyError("Another scan is already active")
            normalized = validate_root(root)
            job = self.store.create(normalized)
            cancelled = Event()
            self._active = (job.id, cancelled)
            self._executor.submit(self._run, job, cancelled)
            return job

    def _run(self, job: Job, cancelled: Event) -> None:
        excluded = {
            os.path.normcase(str(self.database) + suffix)
            for suffix in ("", "-wal", "-shm", "-journal")
        }
        try:
            self.store.begin(job)
            counts = self.store.ingest(
                job, scan_directory(job.root_path, excluded, cancelled)
            )
            status: Status = "completed"
            if cancelled.is_set():
                status = "cancelled"
            elif counts.error_count:
                status = "completed_with_errors"
            self.store.finish(job, status)
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"[:400]
            with self._lock:
                self._failures[job.id] = failure
            try:
                self.store.finish(job, "failed", failure)
            except Exception:
                # A read-only/full database may prevent persisting the failure.
                # Keep failure observable in memory until restart recovery.
                pass
        finally:
            with self._lock:
                if self._active is not None and self._active[0] == job.id:
                    self._active = None

    def get_scan(self, job_id: str) -> Job:
        job = self.store.job(job_id)
        with self._lock:
            failure = self._failures.get(job_id)
        if failure:
            return job.model_copy(
                update={"status": "failed", "failure_message": failure}
            )
        return job

    def cancel_scan(self, job_id: str) -> Job:
        self.get_scan(job_id)
        with self._lock:
            if self._active is not None and self._active[0] == job_id:
                self._active[1].set()
        return self.get_scan(job_id)

    def list_snapshots(self, offset: int = 0, limit: int = 100) -> Page[Snapshot]:
        return self.store.snapshots(offset, limit)

    def get_snapshot(self, snapshot_id: str) -> Snapshot:
        return self.store.snapshot(snapshot_id)

    def list_children(
        self, snapshot_id: str, node_id: int, offset: int = 0, limit: int = 200
    ) -> ChildrenPage:
        return self.store.children(snapshot_id, node_id, offset, limit)

    def list_errors(
        self, snapshot_id: str, offset: int = 0, limit: int = 100
    ) -> Page[ScanError]:
        return self.store.errors(snapshot_id, offset, limit)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._active is not None:
                self._active[1].set()
        self._executor.shutdown(wait=True)
