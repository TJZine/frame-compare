"""Human prompt for shared alignment previous-offset reuse."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from frame_compare.services.alignment_reuse_cache import CACHE_FILE_NAME
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal import stream_is_tty
from frame_compare.utils.types import AlignmentRequest

PROMPT_UNAVAILABLE_MESSAGE = (
    "Previous alignment offset reuse prompt unavailable; continuing without reuse."
)
REUSE_PREVIOUS_OFFSETS_PROMPT = "Reuse these offsets? [y/N]: "
_PROMPT_CONSOLE_WIDTH = 180

__all__ = [
    "PROMPT_UNAVAILABLE_MESSAGE",
    "REUSE_PREVIOUS_OFFSETS_PROMPT",
    "PreviousOffsetPromptInput",
    "PreviousOffsetPromptRow",
    "PreviousOffsetPromptSource",
    "previous_offset_prompt_input_from_rows",
    "prompt_for_previous_offset_reuse",
]

type PreviousOffsetPromptSource = Literal["computed", "confirmed"]


@dataclass(frozen=True, slots=True)
class PreviousOffsetPromptRow:
    """Display row for one reusable previous-offset comparison."""

    label: str
    stem: str
    filename: str
    path: str
    frame_offset: int
    time_offset_seconds: float
    accepted_at: str
    source: PreviousOffsetPromptSource
    presentation_name: str | None = None


@dataclass(frozen=True, slots=True)
class PreviousOffsetPromptInput:
    """Complete human-display input for the previous-offset reuse prompt."""

    reference_label: str
    reference_filename: str
    shared_cache_path: Path
    rows: tuple[PreviousOffsetPromptRow, ...]
    content: str | None = None
    reference_name_is_prebuilt: bool = False


def _console(*, no_color: bool) -> Console:
    return Console(
        stderr=True,
        no_color=no_color,
        color_system=None if no_color else "auto",
        width=_prompt_console_width(),
        height=1000,
    )


def _prompt_console_width() -> int:
    columns = shutil.get_terminal_size(fallback=(_PROMPT_CONSOLE_WIDTH, 24)).columns
    return min(max(columns, 1), _PROMPT_CONSOLE_WIDTH)


def _display_label(*, label: str, filename: str, stem: str) -> str:
    normalized = label.strip()
    if normalized in {filename, stem}:
        return filename
    if normalized:
        return normalized
    if filename:
        return filename
    return stem


def _format_offset(value: int) -> str:
    return f"{value:+d} frames" if value else "0 frames"


def _format_source(value: PreviousOffsetPromptSource) -> str:
    return "Preview-confirmed" if value == "confirmed" else "Computed"


def _format_accepted_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return value
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def previous_offset_prompt_input_from_rows(
    *,
    request: AlignmentRequest,
    rows: Sequence[PreviousOffsetPromptRow],
) -> PreviousOffsetPromptInput:
    """Build prompt input from pre-resolved shared-cache display rows."""
    return PreviousOffsetPromptInput(
        reference_label=request.reference.presentation_name
        or _display_label(
            label=request.reference.label,
            filename=request.reference.path.name,
            stem=request.reference.path.stem,
        ),
        reference_filename=request.reference.path.name,
        shared_cache_path=request.shared_alignment_cache_dir / CACHE_FILE_NAME,
        rows=tuple(rows),
        content=request.presentation_content,
        reference_name_is_prebuilt=request.reference.presentation_name is not None,
    )


def _render_previous_offsets_table(
    *,
    prompt_input: PreviousOffsetPromptInput,
) -> Table:
    table = Table(
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=True,
    )
    table.add_column("key", style="grey70", no_wrap=True, min_width=12, overflow="fold")
    table.add_column("value", overflow="fold")
    if prompt_input.content:
        table.add_row("Content", f"[bright_white]{escape(prompt_input.content)}[/]")
        table.add_row("", "")
    reference_identity = (
        prompt_input.reference_label
        if prompt_input.reference_name_is_prebuilt
        else _display_label(
            label=prompt_input.reference_label,
            filename=prompt_input.reference_filename,
            stem=Path(prompt_input.reference_filename).stem,
        )
    )
    table.add_row(
        "reference",
        f"[bright_white]{escape(reference_identity)}[/]",
    )
    if reference_identity not in {
        prompt_input.reference_filename,
        Path(prompt_input.reference_filename).stem,
    }:
        table.add_row("  File", f"[bright_white]{escape(prompt_input.reference_filename)}[/]")
    for row in prompt_input.rows:
        table.add_row("", "")
        display_label = row.presentation_name or _display_label(
            label=row.label, filename=row.filename, stem=row.stem
        )
        table.add_row("comparison", f"[bright_white]{escape(display_label)}[/]")
        if row.presentation_name is None and display_label not in {row.filename, row.stem}:
            table.add_row("  File", f"[bright_white]{escape(row.filename)}[/]")
        table.add_row(
            "  Offset",
            f"[bright_white]{escape(_format_offset(row.frame_offset))}[/] "
            f"[dim]| {escape(f'{row.time_offset_seconds:.6g}s')}[/]",
        )
        table.add_row("  Evidence", f"[bright_white]{escape(_format_source(row.source))}[/]")
        table.add_row(
            "  Accepted", f"[bright_white]{escape(_format_accepted_at(row.accepted_at))}[/]"
        )
        if row.presentation_name is None and Path(row.path).name != row.filename:
            table.add_row("  Path", f"[dim]{escape(row.path)}[/]")
    table.add_row("", "")
    table.add_row(
        "Cache",
        Text(
            str(prompt_input.shared_cache_path),
            style="dim",
            overflow="fold",
            no_wrap=False,
        ),
    )
    return table


def _stderr_is_visible() -> bool:
    return stream_is_tty(sys.stderr)


def _stdin_is_interactive() -> bool:
    return stream_is_tty(sys.stdin)


def _print_prompt_unavailable(*, no_color: bool, leading_newline: bool = False) -> None:
    console = _console(no_color=no_color)
    if leading_newline:
        console.print()
    console.print(PROMPT_UNAVAILABLE_MESSAGE)


def _read_reuse_response(*, no_color: bool) -> bool:
    stderr_visible = _stderr_is_visible()
    if not stderr_visible:
        return False
    if not _stdin_is_interactive():
        _print_prompt_unavailable(no_color=no_color)
        return False

    console = _console(no_color=no_color)
    console.print(Text(REUSE_PREVIOUS_OFFSETS_PROMPT), end="")
    try:
        raw_response = sys.stdin.readline()
    except OSError:
        _print_prompt_unavailable(no_color=no_color, leading_newline=True)
        return False
    if raw_response == "":
        _print_prompt_unavailable(no_color=no_color, leading_newline=True)
        return False

    normalized = raw_response.strip().lower()
    return normalized in {"y", "yes"}


def prompt_for_previous_offset_reuse(
    *,
    prompt_input: PreviousOffsetPromptInput,
    progress: ProgressReporter | None,
    no_color: bool,
) -> bool:
    """Return whether the user accepts complete reusable previous offsets."""
    if not prompt_input.rows:
        return False
    if not _stderr_is_visible():
        return False
    if not _stdin_is_interactive():
        _print_prompt_unavailable(no_color=no_color)
        return False

    progress_suspended = False
    if progress is not None:
        progress.suspend()
        progress_suspended = True
    try:
        console = _console(no_color=no_color)
        console.print(
            Padding(
                Panel(
                    _render_previous_offsets_table(prompt_input=prompt_input),
                    title="[bold magenta][WAIT][/] [bold cyan]Alignment reuse[/]",
                    border_style="cyan",
                ),
                (0, 0, 0, 2),
            ),
            crop=False,
        )
        return _read_reuse_response(no_color=no_color)
    finally:
        if progress_suspended and progress is not None:
            progress.resume()
