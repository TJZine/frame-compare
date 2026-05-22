"""Report generation service package."""

from __future__ import annotations

from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    ReportData,
    os_path_relpath,
)
from frame_compare.services.report.payload import (
    image_src_for_report as _image_src_for_report,
)

__all__ = [
    "ClipInfo",
    "ReportData",
    "generate_report",
    "_image_src_for_report",
    "os_path_relpath",
]
