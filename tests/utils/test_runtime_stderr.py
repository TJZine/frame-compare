"""Tests for native/runtime stderr filtering."""

from __future__ import annotations

import os

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
