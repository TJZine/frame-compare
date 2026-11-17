"""Shared presentation primitives for orchestration output."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from typing import Final

MAX_REPORT_CONSOLE_WIDTH: Final = 180

__all__ = ["MAX_REPORT_CONSOLE_WIDTH", "clip_role", "join_source_names", "report_console_width"]


def report_console_width(*, minimum: int = 1) -> int:
    """Return a bounded console width suitable for orchestration reports."""
    columns = shutil.get_terminal_size(fallback=(MAX_REPORT_CONSOLE_WIDTH, 24)).columns
    return min(max(columns, minimum), MAX_REPORT_CONSOLE_WIDTH)


def clip_role(index: int) -> str:
    """Return the stable presentation role for an ordered clip."""
    return "Reference" if index == 0 else f"Comparison {index}"


def join_source_names(names: Sequence[str]) -> str:
    """Join a non-empty sequence of source names in presentation order."""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"
