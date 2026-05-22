"""Report generation service package."""

from __future__ import annotations

from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    ReportData,
)

__all__ = [
    "ClipInfo",
    "ReportData",
    "generate_report",
]
