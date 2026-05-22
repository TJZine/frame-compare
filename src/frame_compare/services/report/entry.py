"""Report generation entry point."""

from __future__ import annotations

from pathlib import Path

from frame_compare.config.schema import ReportConfig
from frame_compare.errors import ReportError
from frame_compare.services.report.payload import (
    ReportData,
    build_report_payload,
)
from frame_compare.services.report.renderer import build_html


def generate_report(
    data: ReportData, config: ReportConfig, output_path: Path | None = None
) -> Path:
    """Generate HTML comparison report."""
    if len(data.clips) == 0:
        raise ReportError("no clips provided")
    if len(data.clips) < 2:
        raise ReportError("at least 2 clips required for comparison")
    if len(data.frames) == 0:
        raise ReportError("no frames provided")
    if len(data.screenshots) == 0:
        raise ReportError("no screenshots provided")

    for clip in data.clips:
        if clip.name not in data.screenshots:
            raise ReportError(f"no screenshots for clip: {clip.name}")
        if len(data.screenshots[clip.name]) == 0:
            raise ReportError(f"no screenshots for clip: {clip.name}")
        if len(data.screenshots[clip.name]) != len(data.frames):
            raise ReportError(
                f"screenshot count mismatch for {clip.name}: "
                f"expected {len(data.frames)}, got {len(data.screenshots[clip.name])}"
            )

    final_output_path = _resolve_output_path(data, config, output_path)
    embedded_data = build_report_payload(data, config, report_dir=final_output_path.parent)

    html_content = build_html(embedded_data, include_filmstrip=config.include_filmstrip)

    try:
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        final_output_path.write_text(html_content, encoding="utf-8")
    except OSError as e:
        raise ReportError(f"failed to write report: {e}") from e

    return final_output_path


def _resolve_output_path(data: ReportData, config: ReportConfig, output_path: Path | None) -> Path:
    """Resolve the final report path after generate_report validation."""
    if output_path is not None:
        return output_path
    if config.output_dir:
        return Path(config.output_dir) / "report.html"

    # Fallback: first clip, first frame's parent dir.
    first_clip_name = data.clips[0].name
    first_screenshot = data.screenshots[first_clip_name][0]
    return first_screenshot.parent / "report.html"
