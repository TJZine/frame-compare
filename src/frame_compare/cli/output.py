from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from frame_compare.config.overrides import TonemapCliOverrides
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.coordinator import RunRequest, RunResult
    from frame_compare.vs.types import TonemapSettings

# ── Theme constants ────────────────────────────────────────────────────────────
# Role-based color vocabulary inspired by the legacy CLI layout engine.

STYLE_KEY = "blue"
STYLE_VALUE = "bright_white"
STYLE_UNIT = "dim"
STYLE_PATH = "dim"
STYLE_BOOL_TRUE = "green"
STYLE_BOOL_FALSE = "red"
STYLE_SUCCESS = "bold green"
STYLE_WARN = "yellow"
STYLE_HEADER = "bold cyan"
STYLE_SUBHEADER = "bold bright_cyan"
STYLE_CHECK = "green"
STYLE_METRIC_KEY = "dim"


# ── Formatting helpers ─────────────────────────────────────────────────────────


def _styled_bool(value: bool) -> str:
    """Return a color-coded boolean string."""
    if value:
        return f"[{STYLE_BOOL_TRUE}]true[/]"
    return f"[{STYLE_BOOL_FALSE}]false[/]"


def _styled_value(value: str) -> str:
    return f"[{STYLE_VALUE}]{value}[/]"


def _styled_unit(value: str) -> str:
    return f"[{STYLE_UNIT}]{value}[/]"


def _styled_path(value: str) -> str:
    return f"[{STYLE_PATH}]{value}[/]"



def _group_table() -> Table:
    """Create a borderless two-column table for key-value rows."""
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1, 0, 0))
    table.add_column("key", style=STYLE_KEY, no_wrap=True, min_width=22)
    table.add_column("value")
    return table


def _add_subheader(table: Table, title: str) -> None:
    """Add a styled sub-header row to a group table."""
    table.add_row(f"[{STYLE_SUBHEADER}]{title}[/]", "")


def _add_kv(table: Table, key: str, value: str) -> None:
    """Add an indented key-value row."""
    table.add_row(f"  {key}", value)


def _add_separator(table: Table) -> None:
    """Add a blank separator row."""
    table.add_row("", "")


# ── Tonemap settings resolution ───────────────────────────────────────────────


def _resolve_preview_tonemap_settings(config: ConfigSchema, request: RunRequest) -> TonemapSettings:
    from frame_compare.render.prepare import resolve_tonemap_settings

    overrides: TonemapCliOverrides = {
        "tm_preset": request.tm_preset,
        "tm_target": request.tm_target_nits,
        "tm_curve": request.tm_curve,
    }
    return resolve_tonemap_settings(config, overrides)


# ── At-a-Glance panel ─────────────────────────────────────────────────────────


def print_at_a_glance(
    console: Console,
    *,
    request: RunRequest,
    config: ConfigSchema,
    root: Path,
    config_path: Path,
) -> None:
    vspreview_status: str | None = None
    if config.audio_alignment.use_vspreview or config.audio_alignment.force_interactive:
        from frame_compare.vspreview.adapter import (
            VSPreviewAvailabilityStatus,
            check_vspreview_availability,
        )

        availability = check_vspreview_availability()
        if availability.is_available:
            vspreview_status = "true"
        elif availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            vspreview_status = availability.public_probe_failure_status()
        else:
            vspreview_status = "false"

    ffmpeg_available = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    tonemap_settings = _resolve_preview_tonemap_settings(config, request)

    table = _group_table()

    # ── Workspace ──
    _add_subheader(table, "Workspace")
    _add_kv(table, "root", _styled_path(str(root)))
    _add_kv(table, "config", _styled_path(str(config_path)))
    _add_kv(table, "input", _styled_path(str(config.paths.input_dir)))
    _add_kv(table, "screenshots", _styled_path(str(config.paths.screenshots_dir)))
    _add_kv(table, "generated", _styled_path(str(config.paths.generated_dir)))

    # ── Analysis ──
    _add_separator(table)
    _add_subheader(table, "Analysis")
    selection_text = (
        f"{_styled_value(config.analysis.selection_mode.value)}, "
        f"n={_styled_value(str(config.analysis.frame_count))}, "
        f"seed={_styled_value(str(config.analysis.random_seed))}"
    )
    _add_kv(table, "selection", selection_text)
    renderer = "ffmpeg" if config.screenshots.use_ffmpeg else "vapoursynth"
    _add_kv(table, "renderer", _styled_value(renderer))
    _add_kv(table, "overlay", _styled_value(str(config.screenshots.overlay_mode.value)))

    # ── Audio Alignment ──
    _add_separator(table)
    _add_subheader(table, "Audio Alignment")
    _add_kv(table, "audio_alignment.enabled", _styled_bool(config.audio_alignment.enable))
    _add_kv(table, "audio_alignment.ffmpeg_available", _styled_bool(ffmpeg_available))
    _add_kv(table, "audio_alignment.use_vspreview", _styled_bool(config.audio_alignment.use_vspreview))
    _add_kv(table, "audio_alignment.force_interactive", _styled_bool(config.audio_alignment.force_interactive))
    if vspreview_status is not None:
        _add_kv(table, "vspreview.available", _styled_value(vspreview_status))

    # ── Tonemap ──
    _add_separator(table)
    _add_subheader(table, "Tonemap")
    _add_kv(table, "tonemap.enabled", _styled_bool(config.color.enable_tonemap))
    _add_kv(table, "tonemap.preset", _styled_value(tonemap_settings.preset.value))
    _add_kv(
        table,
        "tonemap.target_nits",
        f"{_styled_value(str(tonemap_settings.target_nits))} {_styled_unit('nits')}",
    )
    _add_kv(table, "tonemap.curve", _styled_value(tonemap_settings.tone_curve.value))

    # ── Output ──
    _add_separator(table)
    _add_subheader(table, "Output")
    upload_status = "disabled" if request.no_upload else "enabled"
    _add_kv(table, "upload", _styled_value(upload_status))
    slowpics_detail = (
        f"visibility={_styled_value(config.slowpics.visibility.value)}  "
        f"auto_upload={_styled_bool(config.slowpics.auto_upload)}  "
        f"delete_after={_styled_bool(config.slowpics.delete_after_upload)}"
    )
    _add_kv(table, "slow.pics", slowpics_detail)
    report_detail = (
        f"enabled={_styled_bool(config.report.enable)}  "
        f"auto_open={_styled_bool(config.report.auto_open)}"
    )
    _add_kv(table, "report", report_detail)

    console.print(Panel(table, title=f"[{STYLE_HEADER}]At-a-Glance[/]", border_style="cyan"))


# ── Result summary ────────────────────────────────────────────────────────────


def print_result_summary(console: Console, *, result: RunResult, quiet: bool) -> None:
    screenshot_dir = str(result.screenshot_dir) if result.screenshot_dir is not None else None

    if quiet:
        if screenshot_dir is not None:
            console.print(f"Screenshots: {screenshot_dir}", soft_wrap=True)
        return

    table = _group_table()

    # Artifact rows with checkmarks
    has_artifacts = False
    if screenshot_dir is not None:
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] screenshots",
            _styled_path(screenshot_dir),
        )
    if result.slowpics_url is not None:
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] slow.pics",
            _styled_value(result.slowpics_url),
        )
    if result.report_path is not None:
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] report",
            _styled_path(str(result.report_path)),
        )

    if not has_artifacts:
        table.add_row(f"  [{STYLE_CHECK}]\u2713[/] status", _styled_value("success"))

    # Metrics section
    has_metrics = (
        result.frame_count > 0
        or result.clips_processed > 0
        or result.duration_seconds > 0.0
    )
    if has_metrics:
        _add_separator(table)
        if result.frame_count > 0:
            _add_kv(table, "frames", _styled_value(str(result.frame_count)))
        if result.clips_processed > 0:
            _add_kv(table, "clips", _styled_value(str(result.clips_processed)))
        if result.duration_seconds > 0.0:
            _add_kv(
                table,
                "duration",
                f"{_styled_value(f'{result.duration_seconds:.1f}')}{_styled_unit('s')}",
            )
        _add_kv(
            table,
            "cache",
            _styled_value("hit" if result.cache_hit else "miss"),
        )

    console.print(Panel(table, title=f"[{STYLE_HEADER}]Result[/]", border_style="cyan"))

    if result.warnings:
        max_lines = 8
        visible = result.warnings[:max_lines]
        remaining = len(result.warnings) - len(visible)
        warning_text = "\n".join(f"[{STYLE_WARN}]\u2022[/] {w}" for w in visible)
        if remaining > 0:
            warning_text += f"\n[{STYLE_WARN}]\u2022[/] ... ({remaining} more)"
        console.print(
            Panel(
                warning_text,
                title=f"[{STYLE_WARN}]Warnings[/]",
                border_style="yellow",
                expand=False,
            )
        )
