"""Opt-in disk benchmark. Creates and removes only its own temporary fixture."""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import shutil
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep
from typing import Literal

from pydantic import BaseModel

from spaceanalyzer.models import Status
from spaceanalyzer.scanner.traversal import io_path
from spaceanalyzer.services.snapshots import SnapshotService


class BenchmarkReport(BaseModel):
    shape: str
    requested_files: int
    environment: dict[str, str]
    generation_seconds: float
    scan_seconds: float
    query_median_ms: float
    query_p95_ms: float
    peak_process_bytes: int
    memory_scope: str = "process lifetime peak including fixture generation"
    database_bytes: int
    status: Status
    file_count: int
    directory_count: int
    total_bytes: int
    error_count: int


def peak_memory() -> int:
    if os.name != "nt":
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak * (1 if sys.platform == "darwin" else 1024))

    from ctypes import wintypes

    class MemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("faults", wintypes.DWORD),
            ("peak", ctypes.c_size_t),
            ("current", ctypes.c_size_t),
            ("paged_peak", ctypes.c_size_t),
            ("paged", ctypes.c_size_t),
            ("nonpaged_peak", ctypes.c_size_t),
            ("nonpaged", ctypes.c_size_t),
            ("pagefile", ctypes.c_size_t),
            ("pagefile_peak", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(MemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.peak)


def run_benchmark(
    shape: Literal["wide", "deep"], count: int, keep_database: Path | None = None
) -> BenchmarkReport:
    if shape not in {"wide", "deep"} or count < 1 or count > 1_000_000:
        raise ValueError("Choose wide/deep and between 1 and 1000000 files")
    if shape == "deep" and count > 256:
        raise ValueError("The deep fixture is limited to 256 levels")
    with TemporaryDirectory(prefix="spaceanalyzer-benchmark-") as temporary:
        base = Path(temporary)
        root = base / "scan"
        root.mkdir()
        current = root
        started = perf_counter()
        for index in range(count):
            if shape == "deep":
                current /= "d"
                Path(io_path(str(current))).mkdir()
            Path(io_path(str(current / f"file-{index:07d}.bin"))).write_bytes(b"x")
        generation = perf_counter() - started
        database = base / "snapshots.sqlite3"
        with SnapshotService(database) as service:
            started = perf_counter()
            job = service.start_scan(str(root))
            while True:
                result = service.get_scan(job.id)
                if result.status not in {"queued", "running"}:
                    break
                if perf_counter() - started > 600:
                    service.cancel_scan(job.id)
                    raise TimeoutError("Synthetic benchmark exceeded ten minutes")
                sleep(0.01)
            duration = perf_counter() - started
            snapshot = service.get_snapshot(result.snapshot_id)
            timings: list[float] = []
            for _ in range(20):
                started = perf_counter()
                service.list_children(snapshot.id, 1, limit=200)
                timings.append(1000 * (perf_counter() - started))
        database_size = sum(
            path.stat().st_size
            for path in (
                database,
                Path(str(database) + "-wal"),
                Path(str(database) + "-shm"),
            )
            if path.exists()
        )
        if keep_database is not None:
            keep_database.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(database, keep_database)
        return BenchmarkReport(
            shape=shape,
            requested_files=count,
            environment={
                "os": platform.platform(),
                "cpu": platform.processor(),
                "logical_cpus": str(os.cpu_count()),
                "python": platform.python_version(),
            },
            generation_seconds=generation,
            scan_seconds=duration,
            query_median_ms=statistics.median(timings),
            query_p95_ms=sorted(timings)[18],
            peak_process_bytes=peak_memory(),
            database_bytes=database_size,
            status=snapshot.status,
            file_count=snapshot.file_count,
            directory_count=snapshot.directory_count,
            total_bytes=snapshot.total_bytes,
            error_count=snapshot.error_count,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shape", choices=["wide", "deep"], default="wide")
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--keep-database", type=Path)
    options = parser.parse_args()
    shape: Literal["wide", "deep"] = "deep" if options.shape == "deep" else "wide"
    report = run_benchmark(shape, options.count, options.keep_database)
    text = report.model_dump_json(indent=2)
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if report.status != "completed" or report.file_count != options.count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
