"""Runtime stderr filtering for known native dependency noise."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress
from threading import RLock
from typing import BinaryIO

# MUST KEEP until the bundled/installed L-SMASH-Works plugin is updated to a
# non-API3 build. Native VapourSynth emits this known deprecation line directly
# to stderr, which corrupts otherwise clean CLI progress and human diagnostics.
_LSMAS_API3_WARNING_MARKERS = (
    "libvslsmashsource",
    "API3",
    "deprecated",
)
_STDERR_REDIRECT_LOCK = RLock()


def is_known_lsmash_api3_warning(line: str) -> bool:
    """Return whether stderr line is the known Windows L-SMASH API3 warning."""
    return all(marker in line for marker in _LSMAS_API3_WARNING_MARKERS)


@contextmanager
def suppress_known_lsmash_api3_stderr() -> Generator[None]:
    """Suppress only the known native L-SMASH API3 warning emitted on stderr."""
    with _STDERR_REDIRECT_LOCK:
        stderr_fd = _stderr_fileno()
        if stderr_fd is None:
            yield
            return

        try:
            saved_fd = os.dup(stderr_fd)
        except OSError:
            yield
            return

        with tempfile.TemporaryFile(mode="w+b") as captured:
            try:
                sys.stderr.flush()
                os.dup2(captured.fileno(), stderr_fd)
            except OSError:
                os.close(saved_fd)
                yield
                return

            try:
                yield
            finally:
                with suppress(OSError):
                    sys.stderr.flush()
                try:
                    os.dup2(saved_fd, stderr_fd)
                finally:
                    os.close(saved_fd)
                _replay_filtered_stderr(captured)


def write_stderr_unless_known_lsmash_api3_warning(line: str) -> None:
    """Write a child-process stderr line unless it is the known L-SMASH warning."""
    if is_known_lsmash_api3_warning(line):
        return
    try:
        sys.stderr.write(line)
    except (OSError, ValueError):
        return


def _stderr_fileno() -> int | None:
    try:
        os.fstat(2)
    except OSError:
        return None
    return 2


def _replay_filtered_stderr(captured: BinaryIO) -> None:
    captured.seek(0)
    data = captured.read()
    if not data:
        return

    text = data.decode(_stderr_encoding(), errors="replace")
    for line in text.splitlines(keepends=True):
        write_stderr_unless_known_lsmash_api3_warning(line)
    sys.stderr.flush()


def _stderr_encoding() -> str:
    return sys.stderr.encoding or "utf-8"
