from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.coordinator import RunRequest, RunResult


def _fmt_bool(value: bool) -> str:
    return "true" if value else "false"


def _kv_table(*, rows: list[tuple[str, str]]) -> Table:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("key", style="bold", no_wrap=True)
    table.add_column("value")
    for key, value in rows:
        table.add_row(key, value)
    return table


def print_at_a_glance(
    console: Console,
    *,
    request: RunRequest,
    config: ConfigSchema,
    root: Path,
    config_path: Path,
) -> None:
    rows: list[tuple[str, str]] = [
        ("root", str(root)),
        ("config", str(config_path)),
        ("input", str(config.paths.input_dir)),
        ("screenshots", str(config.paths.screenshots_dir)),
        ("generated", str(config.paths.generated_dir)),
        (
            "selection",
            f"{config.analysis.selection_mode.value}, n={config.analysis.frame_count}, seed={config.analysis.random_seed}",
        ),
        ("tonemap.enabled", _fmt_bool(config.color.enable_tonemap)),
        ("tonemap.preset", config.color.preset.value),
        ("tonemap.target_nits", str(config.color.target_nits)),
        ("tonemap.curve", config.color.tone_curve.value),
        ("renderer", "ffmpeg" if config.screenshots.use_ffmpeg else "vapoursynth"),
        ("overlay", str(config.screenshots.overlay_mode.value)),
        ("slow.pics.auto_upload", _fmt_bool(config.slowpics.auto_upload)),
        ("slow.pics.visibility", config.slowpics.visibility.value),
        ("slow.pics.delete_after_upload", _fmt_bool(config.slowpics.delete_after_upload)),
        ("report.enabled", _fmt_bool(config.report.enable)),
        ("report.auto_open", _fmt_bool(config.report.auto_open)),
        ("upload", "disabled" if request.no_upload else "enabled"),
    ]
    console.print(Panel(_kv_table(rows=rows), title="At-a-Glance"))


def print_result_summary(console: Console, *, result: RunResult, quiet: bool) -> None:
    screenshot_dir = str(result.screenshot_dir) if result.screenshot_dir is not None else None

    if quiet:
        if screenshot_dir is not None:
            console.print(f"Screenshots: {screenshot_dir}", soft_wrap=True)
        return

    rows: list[tuple[str, str]] = []
    if screenshot_dir is not None:
        rows.append(("screenshots", screenshot_dir))
    if result.slowpics_url is not None:
        rows.append(("slow.pics", result.slowpics_url))
    if result.report_path is not None:
        rows.append(("report", str(result.report_path)))
    if not rows:
        rows.append(("status", "success"))

    console.print(Panel(_kv_table(rows=rows), title="Result"))
