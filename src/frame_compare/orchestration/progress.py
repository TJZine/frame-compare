"""Progress reporter wiring for Frame Compare orchestration.

Orchestration MUST use the canonical ProgressReporter protocol defined in
frame_compare.utils.progress. This module provides orchestration-specific
progress reporter selection.
"""

import sys

from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    ProgressReporter,
    RichProgressReporter,
)


def _stream_is_tty(stream: object) -> bool:
    """Return True when a stream behaves like an interactive TTY."""
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (ValueError, OSError):
        return False


def select_reporter(
    quiet: bool = False,
    json_output: bool = False,
    no_color: bool = False,
    force_tty: bool | None = None,
) -> ProgressReporter:
    """Select the appropriate progress reporter based on CLI flags and environment.

    Selection Priority:
    1. quiet=True -> NullProgressReporter
    2. json_output=True -> LogProgressReporter
    3. no_color=True -> LogProgressReporter
    4. force_tty is not None:
       - True -> RichProgressReporter
       - False -> LogProgressReporter
    5. TTY detection (sys.stdout/sys.stderr isatty):
       - Interactive -> RichProgressReporter
       - Non-interactive -> LogProgressReporter

    Args:
        quiet: If True, suppress all progress output.
        json_output: If True, use structured logging instead of interactive bars.
        no_color: If True, avoid Rich progress output.
        force_tty: Override TTY detection. None = auto-detect.

    Returns:
        An instance implementing the ProgressReporter protocol.
    """
    if quiet:
        return NullProgressReporter()

    if json_output:
        return LogProgressReporter()

    if no_color:
        return LogProgressReporter()

    if force_tty is not None:
        if force_tty:
            return RichProgressReporter()
        return LogProgressReporter()

    if _stream_is_tty(sys.stdout) or _stream_is_tty(sys.stderr):
        return RichProgressReporter()

    return LogProgressReporter()
