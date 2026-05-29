"""Consolidated FPS diagnostics reporting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from frame_compare.orchestration.context import ClipState

log = structlog.get_logger()


@dataclass(frozen=True)
class FpsReportClip:
    """Immutable per-clip FPS diagnostics entry."""

    path: Path
    label: str
    width: int
    height: int
    num_frames: int
    is_hdr: bool
    source_fps: Fraction
    effective_fps: Fraction
    fps_divergent: bool
    note: str | None


def build_consolidated_fps_report(
    reference: ClipState, comparisons: Sequence[ClipState]
) -> tuple[FpsReportClip, ...]:
    """Return a deterministic, ordered per-clip FPS report.

    Reference first, then comparisons in input order.
    """
    ordered = [reference, *comparisons]
    clips: list[FpsReportClip] = []
    for clip in ordered:
        clips.append(
            FpsReportClip(
                path=clip.path,
                label=clip.label,
                width=clip.probe.width,
                height=clip.probe.height,
                num_frames=clip.probe.num_frames,
                is_hdr=clip.probe.is_hdr,
                source_fps=clip.source_fps,
                effective_fps=clip.effective_fps,
                fps_divergent=clip.effective_fps != clip.source_fps,
                note=None,
            )
        )
    return tuple(clips)


def _format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _fraction_parts(value: Fraction) -> tuple[int, int]:
    return value.numerator, value.denominator


def _serialize_clip(clip: FpsReportClip) -> dict[str, Any]:
    source_num, source_den = _fraction_parts(clip.source_fps)
    effective_num, effective_den = _fraction_parts(clip.effective_fps)
    return {
        "path": str(clip.path),
        "label": clip.label,
        "width": clip.width,
        "height": clip.height,
        "num_frames": clip.num_frames,
        "is_hdr": clip.is_hdr,
        "source_fps_num": source_num,
        "source_fps_den": source_den,
        "effective_fps_num": effective_num,
        "effective_fps_den": effective_den,
        "fps_divergent": clip.fps_divergent,
        "note": clip.note,
    }


def _stage_label(stage: str) -> str:
    if stage == "after_load_sources":
        return "After Load Sources"
    if stage == "after_align":
        return "After Alignment"
    return stage.replace("_", " ").title()


def _clip_role(index: int) -> str:
    if index == 0:
        return "reference"
    return f"encode {index}"


def _format_fps_transition(clip: FpsReportClip) -> str:
    source_fps = _format_fraction(clip.source_fps)
    effective_fps = _format_fraction(clip.effective_fps)
    if clip.fps_divergent:
        return f"{escape(source_fps)} -> {escape(effective_fps)}"
    return escape(effective_fps)


def _render_clip_overview(clips: Sequence[FpsReportClip]) -> Table:
    table = Table(
        show_header=True,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("role", style="blue", no_wrap=True, overflow="fold")
    table.add_column("label", style="bright_white", overflow="fold")
    table.add_column("video", style="bright_white", no_wrap=True, overflow="fold")
    table.add_column("fps", style="bright_white", no_wrap=True, overflow="fold")
    table.add_column("frames", justify="right", no_wrap=True, overflow="fold")
    table.add_column("hdr", no_wrap=True, overflow="fold")
    table.add_column("path", style="dim", overflow="fold")

    for index, clip in enumerate(clips):
        table.add_row(
            _clip_role(index),
            escape(clip.label),
            escape(f"{clip.width}x{clip.height}"),
            _format_fps_transition(clip),
            escape(str(clip.num_frames)),
            escape("yes" if clip.is_hdr else "no"),
            escape(str(clip.path)),
        )

    return table


def _render_fps_table(clips: Sequence[FpsReportClip]) -> Table:
    table = Table(
        show_header=True,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("role", style="blue", no_wrap=True, overflow="fold")
    table.add_column("label", style="bright_white", overflow="fold")
    table.add_column("fps", style="bright_white", no_wrap=True, overflow="fold")
    table.add_column("status", no_wrap=True, overflow="fold")
    table.add_column("path", style="dim", overflow="fold")

    for index, clip in enumerate(clips):
        status_text = "[yellow]adjusted[/]" if clip.fps_divergent else "[green]matched[/]"
        if clip.note is not None:
            status_text = f"{status_text} [dim]({escape(clip.note)})[/]"

        table.add_row(
            _clip_role(index),
            escape(clip.label),
            _format_fps_transition(clip),
            status_text,
            escape(str(clip.path)),
        )

    return table


def _render_human_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    no_color: bool,
) -> None:
    if stage == "after_load_sources":
        title = "Clip Overview"
        table = _render_clip_overview(clips)
    else:
        title = "Clip FPS"
        table = _render_fps_table(clips)

    console = Console(stderr=True, no_color=no_color, width=240)
    console.print(
        Panel(
            table,
            title=f"[bold cyan]{escape(title)}[/] [dim]{escape(_stage_label(stage))}[/]",
            border_style="cyan",
        )
    )


def emit_consolidated_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    json_output: bool,
    quiet: bool,
    no_color: bool = False,
) -> None:
    """Emit the consolidated FPS report in JSON or human-readable form."""
    if quiet:
        return

    if json_output:
        payload = [_serialize_clip(clip) for clip in clips]
        log.info("fps_report", stage=stage, clips=payload)
        return

    _render_human_fps_report(stage=stage, clips=clips, no_color=no_color)
