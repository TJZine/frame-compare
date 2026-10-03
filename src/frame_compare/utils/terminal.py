"""Terminal capability and ANSI policy helpers."""

from __future__ import annotations

import os


def no_color_requested(
    *,
    explicit_no_color: bool = False,
) -> bool:
    """Return whether ANSI color should be disabled for human output."""
    return explicit_no_color or "NO_COLOR" in os.environ


def stream_is_tty(stream: object) -> bool:
    """Return True when a stream behaves like an interactive TTY."""
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (OSError, TypeError, ValueError):
        return False
