"""Report generation entry point."""

from __future__ import annotations

from pathlib import Path

from frame_compare.config.schema import ReportConfig
from frame_compare.services.errors import ReportError
from frame_compare.services.report.payload import (
    ReportData,
    build_report_payload,
)
from frame_compare.services.report.renderer import build_html
from frame_compare.utils.atomic_write import write_text_atomic


def generate_report(
    data: ReportData, config: ReportConfig, output_path: Path | None = None
) -> Path:
    """Generate HTML comparison report at the caller-owned output path.

    Report placement is an orchestration/path-owner concern.  The report service
    only validates payload data, renders HTML, and atomically writes the explicit
    destination it receives.
    """
    if len(data.clips) == 0:
        raise ReportError("no clips provided")
    if len(data.clips) < 2:
        raise ReportError("at least 2 clips required for comparison")
    if len(data.frames) == 0:
        raise ReportError("no frames provided")

    has_any_screenshot = any(len(clip.screenshots) > 0 for clip in data.clips)
    if not has_any_screenshot:
        raise ReportError("no screenshots provided")

    for clip in data.clips:
        if not clip.screenshots:
            raise ReportError(f"no screenshots for clip: {clip.name}")
        if len(clip.screenshots) != len(data.frames):
            raise ReportError(
                f"screenshot count mismatch for {clip.name}: "
                f"expected {len(data.frames)}, got {len(clip.screenshots)}"
            )

    if output_path is None:
        raise ReportError("report output path is required")

    embedded_data = build_report_payload(data, config, report_dir=output_path.parent)

    html_content = build_html(embedded_data, include_filmstrip=config.include_filmstrip)

    try:
        write_text_atomic(output_path, html_content, encoding="utf-8")
    except OSError as e:
        raise ReportError(f"failed to write report: {e}") from e

    return output_path
