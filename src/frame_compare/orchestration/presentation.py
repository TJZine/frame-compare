"""Shared presentation primitives for orchestration output."""

from __future__ import annotations

import shutil
from typing import Final

MAX_REPORT_CONSOLE_WIDTH: Final = 180

__all__ = ["MAX_REPORT_CONSOLE_WIDTH", "clip_role", "report_console_width"]


def report_console_width(*, minimum: int = 1) -> int:
    """Return a bounded console width suitable for orchestration reports."""
    columns = shutil.get_terminal_size(fallback=(MAX_REPORT_CONSOLE_WIDTH, 24)).columns
    return min(max(columns, minimum), MAX_REPORT_CONSOLE_WIDTH)


def clip_role(index: int) -> str:
    """Return the stable presentation role for an ordered clip."""
    return "Reference" if index == 0 else f"Comparison {index}"
