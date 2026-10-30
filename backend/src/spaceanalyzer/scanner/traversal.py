"""Stream metadata with explicit directory frames and bounded memory."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol


@dataclass(frozen=True)
class Entry:
    id: int
    parent_id: int | None
    name: str
    path: str
    kind: str
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class Total:
    id: int
    size_bytes: int
    readable: bool


@dataclass(frozen=True)
class Issue:
    path: str
    code: str
    message: str


@dataclass(frozen=True)
class Skipped:
    pass


ScanEvent = Entry | Total | Issue | Skipped


class DirectoryEntries(Protocol):
    def __next__(self) -> os.DirEntry[str]: ...

    def close(self) -> None: ...


@dataclass
class Frame:
    id: int
    path: str
    iterator: DirectoryEntries
    size: int = 0
    readable: bool = True


def io_path(path: str) -> str:
    """Use Windows extended-length paths only for filesystem calls."""
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        return "\\\\?\\" + path
    return path


def is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def validate_root(raw: str) -> str:
    if not raw or not os.path.isabs(raw) or raw.startswith(("\\\\", "//")):
        raise ValueError(
            "Choose an absolute local directory; UNC paths are unsupported"
        )
    # Check the original components before normalizing away '..' or links.
    path = Path(raw)
    current = Path(path.anchor)
    for component in path.parts[1:]:
        if component in {".", ".."}:
            raise ValueError("Relative path components are unsupported")
        current /= component
        if is_reparse(os.lstat(io_path(str(current)))):
            raise ValueError("The root or an ancestor is a link/reparse point")
    normalized = os.path.abspath(raw)
    info = os.lstat(io_path(normalized))
    if is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("The scan root must be a regular directory")
    with os.scandir(io_path(normalized)):
        pass
    return normalized


def scan_directory(
    root: str, excluded: set[str], cancelled: Event
) -> Iterator[ScanEvent]:
    info = os.lstat(io_path(root))
    yield Entry(
        1, None, Path(root).name or root, root, "directory", 0, info.st_mtime_ns
    )
    stack: list[Frame] = []
    next_id = 1
    try:
        if is_reparse(info):
            yield Issue(root, "reparse_point", "Root changed to a reparse point")
            return
        stack.append(Frame(1, root, os.scandir(io_path(root))))
        while stack and not cancelled.is_set():
            frame = stack[-1]
            try:
                item = next(frame.iterator)
            except StopIteration:
                frame.iterator.close()
                stack.pop()
                yield Total(frame.id, frame.size, frame.readable)
                if stack:
                    stack[-1].size += frame.size
                    stack[-1].readable &= frame.readable
                continue
            except OSError as error:
                frame.readable = False
                yield Issue(frame.path, type(error).__name__, str(error)[:400])
                frame.iterator.close()
                stack.pop()
                yield Total(frame.id, frame.size, False)
                if stack:
                    stack[-1].size += frame.size
                    stack[-1].readable = False
                continue
            path = os.path.join(frame.path, item.name)
            if os.path.normcase(path) in excluded:
                yield Skipped()
                continue
            try:
                metadata = os.lstat(io_path(path))
                if is_reparse(metadata):
                    frame.readable = False
                    yield Issue(
                        path, "reparse_point", "Link/reparse target was not followed"
                    )
                    continue
                next_id += 1
                if stat.S_ISREG(metadata.st_mode):
                    frame.size += metadata.st_size
                    yield Entry(
                        next_id,
                        frame.id,
                        item.name,
                        path,
                        "file",
                        metadata.st_size,
                        metadata.st_mtime_ns,
                    )
                elif stat.S_ISDIR(metadata.st_mode):
                    node_id = next_id
                    yield Entry(
                        node_id,
                        frame.id,
                        item.name,
                        path,
                        "directory",
                        0,
                        metadata.st_mtime_ns,
                    )
                    # Re-check directly before opening, including identity changes.
                    fresh = os.lstat(io_path(path))
                    if is_reparse(fresh) or (fresh.st_dev, fresh.st_ino) != (
                        metadata.st_dev,
                        metadata.st_ino,
                    ):
                        raise OSError("Directory identity changed before traversal")
                    try:
                        stack.append(Frame(node_id, path, os.scandir(io_path(path))))
                    except OSError:
                        yield Total(node_id, 0, False)
                        raise
                else:
                    frame.readable = False
                    yield Issue(
                        path, "unsupported_type", "Special filesystem entry was skipped"
                    )
            except OSError as error:
                frame.readable = False
                yield Issue(path, type(error).__name__, str(error)[:400])
    except BaseException:
        for frame in stack:
            frame.iterator.close()
        stack.clear()
        raise
    finally:
        # Cancelled scans still finalize observed subtree totals and close handles.
        while stack:
            frame = stack.pop()
            frame.iterator.close()
            yield Total(frame.id, frame.size, False)
            if stack:
                stack[-1].size += frame.size
