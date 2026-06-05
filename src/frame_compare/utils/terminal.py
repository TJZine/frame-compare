"""Terminal capability and ANSI policy helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping


def no_color_requested(
    *,
    explicit_no_color: bool = False,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return whether ANSI color should be disabled for human output."""
    resolved_environ = os.environ if environ is None else environ
    return explicit_no_color or "NO_COLOR" in resolved_environ


def stream_is_tty(stream: object) -> bool:
    """Return True when a stream behaves like an interactive TTY."""
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (OSError, TypeError, ValueError):
        return False
