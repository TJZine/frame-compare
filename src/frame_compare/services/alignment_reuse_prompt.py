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
from rich.text import Text

from frame_compare.services.alignment_reuse_cache import CACHE_FILE_NAME
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal import interruptible_prompt, stream_is_tty
from frame_compare.utils.terminal_sections import Section, section_title
from frame_compare.utils.terminal_theme import ACCENT, human_console
from frame_compare.utils.types import AlignmentRequest

PROMPT_UNAVAILABLE_MESSAGE = (
    "Previous alignment offset reuse prompt unavailable; continuing without reuse."
)
REUSE_PREVIOUS_OFFSETS_PROMPT = "Reuse these offsets? [y/N]: "
_PROMPT_CONSOLE_WIDTH = 120

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
    short_name: str | None = None


@dataclass(frozen=True, slots=True)
class PreviousOffsetPromptInput:
    """Complete human-display input for the previous-offset reuse prompt."""

    shared_cache_path: Path
    rows: tuple[PreviousOffsetPromptRow, ...]


def _console(*, no_color: bool) -> Console:
    return human_console(
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
    return f"{value:+d}f"


def _format_source(value: PreviousOffsetPromptSource) -> str:
    return "confirmed in VSView" if value == "confirmed" else "audio"


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
        shared_cache_path=request.shared_alignment_cache_dir / CACHE_FILE_NAME,
        rows=tuple(rows),
    )


def _render_previous_offsets_section(
    *,
    prompt_input: PreviousOffsetPromptInput,
    verbose: bool,
) -> Section:
    section = Section(title=section_title("› Reuse previous offsets?"), rail_style=ACCENT)
    for row in prompt_input.rows:
        display_label = row.short_name or _display_label(
            label=row.label, filename=row.filename, stem=row.stem
        )
        value = (
            f"[bold]{escape(display_label)}[/]  {_format_offset(row.frame_offset)}"
            f" · {_format_source(row.source)} · {escape(_format_accepted_at(row.accepted_at))}"
        )
        if verbose:
            value += f" · {row.time_offset_seconds:.6g} s"
        section.add_line(value)
        if verbose and row.short_name is None and display_label not in {row.filename, row.stem}:
            section.add_row("file", Text(row.filename, style="dim"))
        if verbose and row.short_name is None and Path(row.path).name != row.filename:
            section.add_row("path", Text(row.path, style="dim"))
    section.add_line()
    section.add_row("cache", Text(str(prompt_input.shared_cache_path), style="dim"))
    section.add_line()
    return section


def _stderr_is_visible() -> bool:
    return stream_is_tty(sys.stderr)


def _stdin_is_interactive() -> bool:
    return stream_is_tty(sys.stdin)


def _print_prompt_unavailable(*, no_color: bool) -> None:
    console = _console(no_color=no_color)
    console.print(Text.assemble(("!", "yellow"), " ", PROMPT_UNAVAILABLE_MESSAGE))


def _read_reuse_response(question: str, *, no_color: bool) -> str | None:
    console = _console(no_color=no_color)
    console.print(Text(question), end="")
    try:
        with interruptible_prompt():
            raw_response = sys.stdin.readline()
    except OSError:
        raw_response = ""
    console.print()
    return raw_response.strip().lower() if raw_response else None


def prompt_for_previous_offset_reuse(
    *,
    prompt_input: PreviousOffsetPromptInput,
    progress: ProgressReporter | None,
    no_color: bool,
    verbose: bool = False,
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
        section = _render_previous_offsets_section(prompt_input=prompt_input, verbose=verbose)
        response = section.prompt(
            console,
            REUSE_PREVIOUS_OFFSETS_PROMPT.removesuffix(" [y/N]: "),
            lambda question: _read_reuse_response(question + " [y/N]: ", no_color=no_color),
        )
        if response is None:
            _print_prompt_unavailable(no_color=no_color)
        return response in {"y", "yes"}
    finally:
        if progress_suspended and progress is not None:
            progress.resume()
