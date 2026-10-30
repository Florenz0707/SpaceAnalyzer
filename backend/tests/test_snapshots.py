"""Public snapshot behavior using synthetic filesystem fixtures."""

import builtins
import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Event, current_thread
from time import monotonic, sleep
from typing import Any, cast

import pytest

from spaceanalyzer.services.snapshots import ScanBusyError, SnapshotService


def wait_for_scan(service: SnapshotService, job_id: str) -> str:
    deadline = monotonic() + 10
    while monotonic() < deadline:
        job = service.get_scan(job_id)
        if job.status not in {"queued", "running"}:
            return job.snapshot_id
        sleep(0.01)
    raise AssertionError("Scan did not finish within 10 seconds")


def test_scan_persists_tree_and_survives_reopen(tmp_path: Path) -> None:
    root = tmp_path / "scan 中文"
    root.mkdir()
    (root / "small.txt").write_bytes(b"abc")
    (root / "empty").mkdir()
    nested = root / "nested"
    nested.mkdir()
    (nested / "large.bin").write_bytes(b"1234567")
    database = tmp_path / "state.sqlite3"
    with SnapshotService(database) as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(root)).id)
        snapshot = service.get_snapshot(snapshot_id)
        assert snapshot.status == "completed", service.list_errors(snapshot_id)
        assert snapshot.total_bytes == 10
        assert snapshot.file_count == 2
        children = service.list_children(snapshot_id, 1)
        assert [(node.name, node.size_bytes) for node in children.items] == [
            ("nested", 7),
            ("small.txt", 3),
            ("empty", 0),
        ]
    (root / "small.txt").write_bytes(b"changed afterwards")
    with SnapshotService(database) as service:
        assert service.get_snapshot(snapshot_id).total_bytes == 10
        assert service.list_snapshots().total == 1


def test_database_exclusion_pagination_and_input_validation(tmp_path: Path) -> None:
    (tmp_path / "zero.bin").write_bytes(b"")
    (tmp_path / "one.bin").write_bytes(b"x")
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(tmp_path)).id)
        snapshot = service.get_snapshot(snapshot_id)
        assert snapshot.status == "completed"
        assert snapshot.total_bytes == 1
        assert snapshot.skipped_count >= 1
        page = service.list_children(snapshot_id, 1, limit=1)
        assert page.total == 2
        assert page.items[0].name == "one.bin"
        assert page.omitted_bytes == 0
        assert (
            service.list_children(snapshot_id, 1, offset=1).items[0].name == "zero.bin"
        )
        with pytest.raises(ValueError):
            service.list_children(snapshot_id, 1, limit=1001)
        with pytest.raises(ValueError):
            service.list_children(snapshot_id, page.items[0].id)
        with pytest.raises(KeyError):
            service.get_snapshot("missing")
        with pytest.raises(ValueError):
            service.start_scan("relative/path")
        with pytest.raises(ValueError):
            service.start_scan(r"\\server\share")


def test_unreadable_entry_is_recorded_as_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    (root / "allowed.bin").write_bytes(b"abc")
    (root / "denied.bin").write_bytes(b"hidden")
    original_lstat = os.lstat

    def unavailable(
        path: str | os.PathLike[str], *args: Any, **kwargs: Any
    ) -> os.stat_result:
        if str(path).endswith("denied.bin"):
            raise PermissionError("Synthetic access denied")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", unavailable)
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(root)).id)
        snapshot = service.get_snapshot(snapshot_id)
        assert snapshot.status == "completed_with_errors"
        assert snapshot.total_bytes == 3
        assert snapshot.error_count == 1
        assert service.list_errors(snapshot_id).items[0].code == "PermissionError"
        assert service.list_children(snapshot_id, 1).items[0].name == "allowed.bin"


def test_cancel_and_single_active_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = Event(), Event()
    original_scandir = os.scandir

    def gated(path: str) -> Any:
        if current_thread().name.startswith("snapshot"):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Test gate timed out")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", gated)
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        try:
            job = service.start_scan(str(tmp_path))
            assert entered.wait(5)
            with pytest.raises(ScanBusyError):
                service.start_scan(str(tmp_path))
            service.cancel_scan(job.id)
            service.cancel_scan(job.id)
        finally:
            release.set()
        snapshot_id = wait_for_scan(service, job.id)
        assert service.get_scan(job.id).status == "cancelled"
        assert service.get_snapshot(snapshot_id).status == "cancelled"
        assert service.list_children(snapshot_id, 1).total == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration")
def test_windows_junction_is_not_followed(tmp_path: Path) -> None:
    root, target = tmp_path / "scan", tmp_path / "outside"
    root.mkdir()
    target.mkdir()
    (target / "outside.bin").write_bytes(b"never traverse")
    junction = root / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        check=True,
        capture_output=True,
    )
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(root)).id)
        assert service.get_snapshot(snapshot_id).total_bytes == 0
        assert service.get_snapshot(snapshot_id).status == "completed_with_errors"
        assert service.list_children(snapshot_id, 1).total == 0
        assert service.list_errors(snapshot_id).items[0].code == "reparse_point"
        with pytest.raises(ValueError):
            service.start_scan(str(junction))


def test_scan_preserves_metadata_and_never_reads_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    file = root / "data.bin"
    file.write_bytes(b"metadata only")
    before = file.stat()
    original_open = builtins.open

    def guard(file: Any, *args: Any, **kwargs: Any) -> Any:
        if current_thread().name.startswith("snapshot"):
            raise AssertionError("Scanner attempted to open file contents")
        return cast(Any, original_open(file, *args, **kwargs))

    monkeypatch.setattr(builtins, "open", guard)
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(root)).id)
        assert service.get_snapshot(snapshot_id).total_bytes == 13
    after = file.stat()
    assert (after.st_size, after.st_mtime_ns, after.st_mode) == (
        before.st_size,
        before.st_mtime_ns,
        before.st_mode,
    )


def test_interrupted_worker_is_recovered_on_restart(tmp_path: Path) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    database, marker = tmp_path / "state.sqlite3", tmp_path / "ready.json"
    program = r"""
import json, os, sys
from pathlib import Path
from threading import Event, current_thread
from spaceanalyzer.services.snapshots import SnapshotService
entered = Event()
original = os.scandir
def blocked(path):
    if current_thread().name.startswith("snapshot"):
        entered.set()
        Event().wait(60)
    return original(path)
os.scandir = blocked
service = SnapshotService(Path(sys.argv[1]))
job = service.start_scan(sys.argv[2])
assert entered.wait(10)
Path(sys.argv[3]).write_text(json.dumps({"job": job.id, "snapshot": job.snapshot_id}))
Event().wait(60)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", program, str(database), str(root), str(marker)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = monotonic() + 10
        while not marker.exists() and process.poll() is None and monotonic() < deadline:
            sleep(0.01)
        assert marker.exists(), "Child did not reach the controlled interruption point"
    finally:
        process.kill()
        process.communicate(timeout=5)
    identifiers: dict[str, str] = json.loads(marker.read_text())
    with SnapshotService(database) as service:
        job = service.get_scan(identifiers["job"])
        assert job.status == "failed"
        assert job.failure_message == "Interrupted before restart"
        assert service.get_snapshot(identifiers["snapshot"]).status == "failed"


def test_disappearing_file_keeps_readable_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "scan"
    root.mkdir()
    (root / "kept.bin").write_bytes(b"abc")
    (root / "vanished.bin").write_bytes(b"gone")
    original = os.lstat

    def disappearing(
        path: str | os.PathLike[str], *args: Any, **kwargs: Any
    ) -> os.stat_result:
        if str(path).endswith("vanished.bin"):
            raise FileNotFoundError("Fixture disappeared between enumeration and stat")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", disappearing)
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(root)).id)
        snapshot = service.get_snapshot(snapshot_id)
        assert snapshot.status == "completed_with_errors"
        assert snapshot.total_bytes == 3
        assert snapshot.file_count == 1
        assert service.list_errors(snapshot_id).items[0].code == "FileNotFoundError"
        assert [item.name for item in service.list_children(snapshot_id, 1).items] == [
            "kept.bin"
        ]


def test_hardlinks_count_directory_entries_and_snapshot_ids_are_scoped(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "data.bin").write_bytes(b"abc")
    os.link(first / "data.bin", first / "alias.bin")
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        first_id = wait_for_scan(service, service.start_scan(str(first)).id)
        first_snapshot = service.get_snapshot(first_id)
        assert first_snapshot.total_bytes == 6
        assert first_snapshot.file_count == 2
        children = service.list_children(first_id, 1)
        foreign_node_id = children.items[0].id
        second_id = wait_for_scan(service, service.start_scan(str(second)).id)
        assert service.get_snapshot(second_id).total_bytes == 0
        with pytest.raises(KeyError):
            service.list_children(second_id, foreign_node_id)
        assert service.get_snapshot(first_id).total_bytes == 6


def test_prepared_windows_symbolic_link_is_not_followed(tmp_path: Path) -> None:
    raw = os.environ.get("SPACEANALYZER_TEST_SYMLINK")
    if os.name != "nt" or not raw:
        pytest.skip("Opt-in Windows integration: prepare a synthetic symbolic link")
    project = Path(__file__).resolve().parents[2]
    base = project / ".cache/symlink-fixture"
    link = Path(raw).absolute()
    assert link == base / "scan/link", "Only the prepared project fixture is accepted"
    assert link.is_symlink() and link.resolve() == (base / "target").resolve()
    before = (base / "target/outside.bin").stat()
    with SnapshotService(tmp_path / "state.sqlite3") as service:
        snapshot_id = wait_for_scan(service, service.start_scan(str(base / "scan")).id)
        snapshot = service.get_snapshot(snapshot_id)
        assert snapshot.status == "completed_with_errors"
        assert snapshot.total_bytes == 0
        assert snapshot.file_count == 0
        assert service.list_children(snapshot_id, 1).total == 0
        assert service.list_errors(snapshot_id).items[0].code == "reparse_point"
        with pytest.raises(ValueError):
            service.start_scan(str(link))
        with pytest.raises(ValueError):
            service.start_scan(str(link / "child"))
    after = (base / "target/outside.bin").stat()
    assert (before.st_size, before.st_mtime_ns, before.st_mode) == (
        after.st_size,
        after.st_mtime_ns,
        after.st_mode,
    )
