"""Small cross-process file locking helper for persistence owners."""

from __future__ import annotations

import errno
import importlib
import os
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast


class FileLockTimeoutError(TimeoutError):
    """Raised when a lock file cannot be acquired within the configured timeout."""


class _FcntlModule(Protocol):
    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, fd: int, operation: int) -> None: ...


class _MsvcrtModule(Protocol):
    LK_NBLCK: int
    LK_UNLCK: int

    def locking(self, fd: int, mode: int, nbytes: int) -> None: ...


def _load_module(name: str) -> ModuleType:
    return importlib.import_module(name)


def _lock_blocked(exc: OSError) -> bool:
    return exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}


def _acquire_posix_lock(fd: int) -> None:
    fcntl = cast(_FcntlModule, _load_module("fcntl"))
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_posix_lock(fd: int) -> None:
    fcntl = cast(_FcntlModule, _load_module("fcntl"))
    fcntl.flock(fd, fcntl.LOCK_UN)


def _acquire_windows_lock(fd: int) -> None:
    msvcrt = cast(_MsvcrtModule, _load_module("msvcrt"))
    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)


def _release_windows_lock(fd: int) -> None:
    msvcrt = cast(_MsvcrtModule, _load_module("msvcrt"))
    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


def _acquire_platform_lock(fd: int) -> None:
    if sys.platform == "win32":
        _acquire_windows_lock(fd)
        return
    _acquire_posix_lock(fd)


def _release_platform_lock(fd: int) -> None:
    if sys.platform == "win32":
        _release_windows_lock(fd)
        return
    _release_posix_lock(fd)


@contextmanager
def exclusive_file_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.05,
) -> Generator[None]:
    """Hold an exclusive cross-process lock for the lifetime of the context."""
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must be non-negative")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(lock_path, flags, 0o666)
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    try:
        while True:
            try:
                _acquire_platform_lock(fd)
                acquired = True
                break
            except BlockingIOError:
                pass
            except OSError as exc:
                if not _lock_blocked(exc):
                    raise

            if time.monotonic() >= deadline:
                raise FileLockTimeoutError(f"timed out acquiring lock file {lock_path}")
            time.sleep(min(poll_interval_seconds, max(0.0, deadline - time.monotonic())))

        yield
    finally:
        try:
            if acquired:
                _release_platform_lock(fd)
        finally:
            os.close(fd)
