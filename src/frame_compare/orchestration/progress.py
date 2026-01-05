"""Progress reporter wiring for Frame Compare 2.0 orchestration.

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


def select_reporter(
    quiet: bool = False,
    json_output: bool = False,
    force_tty: bool | None = None,
) -> ProgressReporter:
    """Select the appropriate progress reporter based on CLI flags and environment.

    Selection Priority:
    1. quiet=True -> NullProgressReporter
    2. json_output=True -> LogProgressReporter
    3. force_tty is not None:
       - True -> RichProgressReporter
       - False -> LogProgressReporter
    4. TTY detection (sys.stdout.isatty()):
       - Interactive -> RichProgressReporter
       - Non-interactive -> LogProgressReporter

    Args:
        quiet: If True, suppress all progress output.
        json_output: If True, use structured logging instead of interactive bars.
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
            return RichProgressReporter()
        return LogProgressReporter()

    if sys.stdout.isatty():
        return RichProgressReporter()

    return LogProgressReporter()
