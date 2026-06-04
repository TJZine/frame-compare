"""Progress reporter wiring for Frame Compare orchestration.

Orchestration MUST use the canonical ProgressReporter protocol defined in
frame_compare.utils.progress_protocol. This module provides orchestration-specific
progress reporter selection.
"""

import sys

from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressReporter

_PHASE_DISPLAY_LABELS = {
    "frame_plan": "PLAN",
    "analyze": "ANALYZE",
    "align": "ALIGN",
    "render": "RENDER",
    "metadata": "METADATA",
    "dovi": "DOVI",
    "publish": "PUBLISH",
    "report": "REPORT",
    "confirm_slowpics_upload": "CONFIRM",
    "post_report_cleanup": "CLEANUP",
}


def phase_display_label(name: str) -> str:
    """Return the human progress label for an internal phase name."""
    return _PHASE_DISPLAY_LABELS.get(name, name.replace("_", " ").upper())


def start_phase_progress(
    reporter: ProgressReporter,
    *,
    name: str,
    display_label: str,
    total: int,
) -> None:
    """Start progress with human labels for Rich and internal names for log output."""
    if isinstance(reporter, LogProgressReporter):
        reporter.start_phase(name, total=total)
        return
    reporter.start_phase(display_label, total=total)


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
    3. force_tty is not None:
       - True -> RichProgressReporter(no_color=no_color)
       - False -> LogProgressReporter
    4. TTY detection (sys.stdout/sys.stderr isatty):
       - Interactive -> RichProgressReporter(no_color=no_color)
       - Non-interactive -> LogProgressReporter

    Args:
        quiet: If True, suppress all progress output.
        json_output: If True, use structured logging instead of interactive bars.
        no_color: If True, disable color in Rich progress output.
        force_tty: Override TTY detection. None = auto-detect.

    Returns:
        An instance implementing the ProgressReporter protocol.
    """
    if quiet:
        return NullProgressReporter()

    if json_output:
        return LogProgressReporter()

    if force_tty is not None:
        if force_tty:
            return RichProgressReporter(no_color=no_color)
        return LogProgressReporter()

    if _stream_is_tty(sys.stdout) or _stream_is_tty(sys.stderr):
        return RichProgressReporter(no_color=no_color)

    return LogProgressReporter()
