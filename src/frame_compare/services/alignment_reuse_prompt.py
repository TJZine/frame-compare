"""Human prompt for shared alignment previous-offset reuse."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table
from rich.text import Text

from frame_compare.services.alignment_reuse_cache import CACHE_FILE_NAME
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal import stream_is_tty
from frame_compare.utils.types import AlignmentRequest

PROMPT_UNAVAILABLE_MESSAGE = (
    "Previous alignment offset reuse prompt unavailable; continuing without reuse."
)
REUSE_PREVIOUS_OFFSETS_PROMPT = "Reuse previous alignment offsets? [y/N]"

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


@dataclass(frozen=True, slots=True)
class PreviousOffsetPromptInput:
    """Complete human-display input for the previous-offset reuse prompt."""

    reference_label: str
    reference_filename: str
    shared_cache_path: Path
    rows: tuple[PreviousOffsetPromptRow, ...]


def _console(*, no_color: bool) -> Console:
    return Console(stderr=True, no_color=no_color, width=300)


def _safe_text(value: object) -> Text:
    return Text(str(value), overflow="fold")


def _display_label(*, label: str, filename: str, stem: str) -> str:
    normalized = label.strip()
    if normalized:
        return normalized
    if filename:
        return filename
    return stem


def _clip_details_text(row: PreviousOffsetPromptRow) -> Text:
    text = Text()
    text.append(_display_label(label=row.label, filename=row.filename, stem=row.stem))
    text.append("\n")
    text.append(f"stem: {row.stem}")
    text.append("\n")
    text.append(f"file: {row.filename}")
    text.append("\n")
    text.append(f"path: {row.path}")
    return text


def _format_offset(value: int) -> str:
    return f"{value:+d}f"


def previous_offset_prompt_input_from_rows(
    *,
    request: AlignmentRequest,
    rows: Sequence[PreviousOffsetPromptRow],
) -> PreviousOffsetPromptInput:
    """Build prompt input from pre-resolved shared-cache display rows."""
    return PreviousOffsetPromptInput(
        reference_label=_display_label(
            label=request.reference.label,
            filename=request.reference.path.name,
            stem=request.reference.path.stem,
        ),
        reference_filename=request.reference.path.name,
        shared_cache_path=request.shared_alignment_cache_dir / CACHE_FILE_NAME,
        rows=tuple(rows),
    )


def _render_previous_offsets_table(
    *,
    console: Console,
    prompt_input: PreviousOffsetPromptInput,
) -> None:
    table = Table(title=Text("Previous Alignment Offsets"))
    table.add_column("Clip")
    table.add_column("Offset", justify="right", no_wrap=True)
    table.add_column("Seconds", justify="right", no_wrap=True)
    table.add_column("Accepted At", no_wrap=True)
    table.add_column("Source", no_wrap=True)
    for row in prompt_input.rows:
        table.add_row(
            _clip_details_text(row),
            _safe_text(_format_offset(row.frame_offset)),
            _safe_text(f"{row.time_offset_seconds:.6g}"),
            _safe_text(row.accepted_at),
            _safe_text(row.source),
        )
    console.print(
        _safe_text(f"Reference: {prompt_input.reference_label} ({prompt_input.reference_filename})")
    )
    console.print(_safe_text(f"Shared cache: {prompt_input.shared_cache_path}"))
    console.print(table)


def _stderr_is_visible() -> bool:
    return stream_is_tty(sys.stderr)


def _stdin_is_interactive() -> bool:
    return stream_is_tty(sys.stdin)


def _print_prompt_unavailable(*, no_color: bool, leading_newline: bool = False) -> None:
    console = _console(no_color=no_color)
    if leading_newline:
        console.print()
    console.print(_safe_text(PROMPT_UNAVAILABLE_MESSAGE))


def _read_reuse_response(*, no_color: bool) -> bool:
    stderr_visible = _stderr_is_visible()
    if not stderr_visible:
        return False
    if not _stdin_is_interactive():
        _print_prompt_unavailable(no_color=no_color)
        return False

    console = _console(no_color=no_color)
    console.print(_safe_text(REUSE_PREVIOUS_OFFSETS_PROMPT), end="")
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
        _render_previous_offsets_table(
            console=console,
            prompt_input=prompt_input,
        )
        return _read_reuse_response(no_color=no_color)
    finally:
        if progress_suspended and progress is not None:
            progress.resume()
