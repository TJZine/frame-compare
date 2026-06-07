"""Tests for native/runtime stderr filtering."""

from __future__ import annotations

import os
from threading import Event, Thread

from frame_compare.utils.runtime_stderr import (
    is_known_lsmash_api3_warning,
    suppress_known_lsmash_api3_stderr,
)

_KNOWN_API3_WARNING = (
    "Plugin C:\\Software\\video\\frame-compare\\.venv\\Lib\\site-packages\\vapoursynth"
    "\\plugins\\libvslsmashsource.dll is using API3 which is deprecated and will be removed shortly.\n"
)


def test_known_lsmash_api3_warning_match_is_exact_to_all_markers() -> None:
    assert is_known_lsmash_api3_warning(_KNOWN_API3_WARNING)
    assert not is_known_lsmash_api3_warning(
        "Plugin libvslsmashsource.dll failed to load because a dependency is missing.\n"
    )
    assert not is_known_lsmash_api3_warning(
        "Plugin other.dll is using API3 which is deprecated and will be removed shortly.\n"
    )


def test_suppress_known_lsmash_api3_stderr_filters_native_fd_writes(capfd) -> None:
    with suppress_known_lsmash_api3_stderr():
        os.write(2, _KNOWN_API3_WARNING.encode("utf-8"))
        os.write(2, b"real native runtime warning\n")

    captured = capfd.readouterr()
    assert "libvslsmashsource.dll is using API3" not in captured.err
    assert "real native runtime warning" in captured.err
    assert captured.out == ""


def test_suppress_known_lsmash_api3_stderr_serializes_concurrent_redirects(capfd) -> None:
    worker_attempting = Event()
    worker_entered = Event()
    worker_done = Event()
    worker_errors: list[BaseException] = []

    def worker() -> None:
        try:
            worker_attempting.set()
            with suppress_known_lsmash_api3_stderr():
                worker_entered.set()
                os.write(2, _KNOWN_API3_WARNING.encode("utf-8"))
                os.write(2, b"worker runtime warning\n")
        except BaseException as exc:
            worker_errors.append(exc)
        finally:
            worker_done.set()

    with suppress_known_lsmash_api3_stderr():
        thread = Thread(target=worker, daemon=True)
        thread.start()
        assert worker_attempting.wait(timeout=1.0)
        os.write(2, _KNOWN_API3_WARNING.encode("utf-8"))
        os.write(2, b"outer runtime warning\n")
        assert not worker_entered.wait(timeout=0.05)

    assert worker_entered.wait(timeout=1.0)
    assert worker_done.wait(timeout=1.0)
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert worker_errors == []
    captured = capfd.readouterr()
    assert "libvslsmashsource.dll is using API3" not in captured.err
    assert "outer runtime warning" in captured.err
    assert "worker runtime warning" in captured.err
    assert captured.out == ""
