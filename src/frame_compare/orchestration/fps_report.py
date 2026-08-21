"""Consolidated FPS diagnostics reporting helpers."""

from __future__ import annotations

import shutil
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
from frame_compare.services.release_identity import (
    ReleaseIdentity,
    common_content_identity,
    format_compact_identity,
    format_content_identity,
    format_release_descriptor,
)

log = structlog.get_logger()

_REPORT_CONSOLE_WIDTH = 180


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
    size_bytes: int = 0
    release_identity: ReleaseIdentity | None = None
    label_is_explicit: bool = False


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
                size_bytes=clip.probe.fingerprint.size_bytes,
                release_identity=clip.release_identity,
                label_is_explicit=clip.label_is_explicit,
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
        return "Reference"
    return f"Comparison {index}"


def _format_fps_transition(clip: FpsReportClip) -> str:
    source_fps = _format_fraction(clip.source_fps)
    effective_fps = _format_fraction(clip.effective_fps)
    if clip.fps_divergent:
        return f"{escape(source_fps)} -> {escape(effective_fps)}"
    return escape(effective_fps)


def _format_frame_count(num_frames: int) -> str:
    unit = "frame" if num_frames == 1 else "frames"
    return f"{num_frames:,} {unit}"


def _format_dynamic_range(is_hdr: bool) -> str:
    if is_hdr:
        return "[bright_white]HDR[/]"
    return "[dim]SDR[/]"


def _format_file_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024.0
    raise AssertionError("unreachable")


def _report_console_width() -> int:
    columns = shutil.get_terminal_size(fallback=(_REPORT_CONSOLE_WIDTH, 24)).columns
    return min(max(columns, 1), _REPORT_CONSOLE_WIDTH)


def _display_path(path: Path, *, input_dir: Path | None, verbose: bool) -> str:
    absolute = path.resolve()
    if verbose:
        return str(absolute)
    if input_dir is None:
        return str(path)

    try:
        relative = absolute.relative_to(input_dir.resolve())
    except ValueError:
        return str(absolute)
    return str(relative) if relative != Path(".") else "."


def _render_clip_overview(
    clips: Sequence[FpsReportClip],
    *,
    input_dir: Path | None,
    verbose: bool,
) -> Table:
    table = Table(
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("key", style="grey70", no_wrap=True, min_width=14, overflow="fold")
    table.add_column("value", overflow="fold")

    identities = [clip.release_identity for clip in clips]
    common_content = (
        common_content_identity([identity for identity in identities if identity is not None])
        if all(identity is not None for identity in identities)
        else None
    )
    if common_content is not None:
        table.add_row(
            "Content", f"[bright_white]{escape(format_content_identity(common_content))}[/]"
        )

    for index, clip in enumerate(clips):
        if index > 0:
            table.add_row("", "")

        filename = clip.path.name
        label = clip.label.strip()
        table.add_row(_clip_role(index), "")
        if clip.label_is_explicit and label:
            table.add_row("  Label", f"[bright_white]{escape(label)}[/]")
        if clip.release_identity is not None:
            release = (
                format_release_descriptor(clip.release_identity)
                if common_content is not None
                else format_compact_identity(clip.release_identity)
            )
            table.add_row("  Release", f"[bright_white]{escape(release or filename)}[/]")
        elif label and label not in {clip.path.stem, filename}:
            table.add_row("  Label", f"[bright_white]{escape(label)}[/]")
        table.add_row("  File", f"[bright_white]{escape(filename)}[/]")
        table.add_row(
            "  Video",
            f"[bright_white]{escape(f'{clip.width}x{clip.height}')}[/] | {_format_dynamic_range(clip.is_hdr)}",
        )
        table.add_row(
            "  Timing",
            f"[bright_white]{_format_fps_transition(clip)}[/] | [dim]{escape(_format_frame_count(clip.num_frames))}[/]",
        )
        table.add_row(
            "  Size",
            f"[bright_white]{escape(_format_file_size(clip.size_bytes))}[/]",
        )
        display_path = _display_path(clip.path, input_dir=input_dir, verbose=verbose)
        if verbose or Path(display_path).parent != Path("."):
            table.add_row("  Path", f"[dim]{escape(display_path)}[/]")

    return table


def _render_load_sources_overview(
    *,
    clips: Sequence[FpsReportClip],
    diagnostics: Sequence[str],
    input_dir: Path | None,
    verbose: bool,
) -> Table:
    table = _render_clip_overview(clips, input_dir=input_dir, verbose=verbose)
    if diagnostics:
        table.add_row("", "")
        for index, diagnostic in enumerate(diagnostics):
            key = "diagnostic" if index == 0 else ""
            table.add_row(key, f"[bright_white]{escape(diagnostic)}[/]")
    return table


def _fps_status(clip: FpsReportClip, *, reference_fps: Fraction) -> str:
    if clip.effective_fps != reference_fps:
        return "[red]divergent[/]"
    if clip.fps_divergent:
        return "[yellow]adjusted[/]"
    return "[green]matched[/]"


def _render_fps_table(
    clips: Sequence[FpsReportClip],
    *,
    input_dir: Path | None,
    verbose: bool,
) -> Table:
    table = Table(
        show_header=True,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("role", style="blue", no_wrap=True, overflow="fold")
    table.add_column("clip", style="bright_white", overflow="fold")
    table.add_column("fps", style="bright_white", no_wrap=True, overflow="fold")
    table.add_column("status", no_wrap=True, overflow="fold")
    if verbose:
        table.add_column("path", style="dim", overflow="fold")

    if not clips:
        return table
    reference_fps = clips[0].effective_fps
    for index, clip in enumerate(clips):
        status_text = _fps_status(clip, reference_fps=reference_fps)
        if clip.note is not None:
            status_text = f"{status_text} [dim]({escape(clip.note)})[/]"

        descriptor = (
            clip.label
            if clip.label_is_explicit
            else (
                format_release_descriptor(clip.release_identity)
                if clip.release_identity is not None
                else clip.label
            )
        )
        cells = [
            _clip_role(index),
            escape(descriptor or clip.path.name),
            _format_fps_transition(clip),
            status_text,
        ]
        if verbose:
            cells.append(escape(_display_path(clip.path, input_dir=input_dir, verbose=True)))
        table.add_row(*cells)

    return table


def _can_summarize_matching_fps(clips: Sequence[FpsReportClip]) -> bool:
    if not clips or any(clip.fps_divergent for clip in clips):
        return False
    effective_fps = clips[0].effective_fps
    return all(clip.effective_fps == effective_fps for clip in clips)


def _render_human_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    diagnostics: Sequence[str],
    no_color: bool,
    input_dir: Path | None,
    verbose: bool,
) -> None:
    console = Console(stderr=True, no_color=no_color, width=_report_console_width(), height=1000)
    if stage == "after_load_sources":
        title = f"[bold green][OK][/] Sources — {len(clips)} loaded"
        table = _render_load_sources_overview(
            clips=clips,
            diagnostics=diagnostics,
            input_dir=input_dir,
            verbose=verbose,
        )
    else:
        if not verbose and _can_summarize_matching_fps(clips):
            effective_fps = _format_fraction(clips[0].effective_fps)
            console.print(f"  [bold green][OK][/] Frame rates match: {escape(effective_fps)}")
            return
        title = "Frame rates"
        table = _render_fps_table(
            clips,
            input_dir=input_dir,
            verbose=verbose,
        )

    console.print(
        Panel(
            table,
            title=(
                f"[bold cyan]{title}[/]"
                if stage == "after_load_sources"
                else f"[bold cyan]{escape(title)}[/] [dim]{escape(_stage_label(stage))}[/]"
            ),
            border_style="cyan",
        )
    )


def emit_consolidated_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    json_output: bool,
    quiet: bool,
    rich_output: bool,
    no_color: bool = False,
    diagnostics: Sequence[str] = (),
    input_dir: Path | None = None,
    verbose: bool = False,
) -> None:
    """Emit the consolidated FPS report in JSON or human-readable form."""
    if quiet:
        return

    if json_output or not rich_output:
        payload = [_serialize_clip(clip) for clip in clips]
        log.info("fps_report", stage=stage, clips=payload, diagnostics=list(diagnostics))
        return

    _render_human_fps_report(
        stage=stage,
        clips=clips,
        diagnostics=diagnostics,
        no_color=no_color,
        input_dir=input_dir,
        verbose=verbose,
    )
