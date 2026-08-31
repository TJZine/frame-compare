"""Human-readable VSView CLI diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from frame_compare.utils.terminal import no_color_requested

STYLE_KEY = "blue"
STYLE_VALUE = "bright_white"
STYLE_PATH = "dim"
STYLE_HINT = "yellow"
STYLE_HEADER = "bold cyan"
STYLE_WAIT = "magenta"
_STARTUP_STDERR_LIMIT = 4000
_SECTION_INDENT = 2
_CONTENT_INDENT = 4


def _console(*, no_color: bool) -> Console:
    return Console(stderr=True, no_color=no_color_requested(explicit_no_color=no_color))


def _group_table() -> Table:
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column("key", style=STYLE_KEY, no_wrap=True, min_width=11)
    table.add_column("value", overflow="fold")
    return table


def _status_text(marker: str, message: str, *, style: str) -> Text:
    return Text.assemble(Text(marker, style=style), " ", message)


def print_vsview_session(
    *,
    script_path: Path,
    command: list[str],
    no_color: bool = False,
) -> None:
    """Print app-owned VSView launch telemetry to stderr."""
    table = _group_table()
    table.add_row("script", f"[{STYLE_PATH}]{escape(str(script_path))}[/]")
    table.add_row("command", f"[{STYLE_PATH}]{escape(' '.join(command))}[/]")
    table.add_row("output", "Frame Compare diagnostics inherited on stderr")

    console = _console(no_color=no_color)
    console.print()
    console.print(f"[{STYLE_HEADER}]VSView Session[/]")
    console.print(table)


def print_vsview_unavailable(
    *,
    reason: str,
    no_color: bool = False,
) -> None:
    """Print the single normal human warning for optional verification failure."""
    console = _console(no_color=no_color)
    console.print()
    console.print(_status_text("[WARN]", "VSView verification unavailable", style="yellow"))
    console.print(f"       {escape(reason)}")
    console.print("       Continuing with computed audio alignment.")
    console.print("       Hint: Check the VSView setup with frame-compare doctor.")


def print_vsview_failure_details(
    *,
    command: tuple[str, ...],
    reason: str,
    returncode: int | None,
    startup_stderr: str | None,
    no_color: bool = False,
) -> None:
    """Print bounded verbose startup evidence captured by the readiness probe."""
    table = _group_table()
    table.add_row("command", f"[{STYLE_PATH}]{escape(' '.join(command))}[/]")
    detail = reason if returncode is None else f"{reason} (exit {returncode})"
    table.add_row("reason", escape(detail))
    if startup_stderr:
        table.add_row("stderr", escape(startup_stderr[-_STARTUP_STDERR_LIMIT:]))
    console = _console(no_color=no_color)
    console.print()
    console.print(f"[{STYLE_HEADER}]VSView Failure Details[/]")
    console.print(table)


def print_vsview_confirmation_header(
    *,
    reference_name: str,
    no_color: bool = False,
) -> None:
    """Print the manual alignment confirmation instructions to stderr."""
    table = _group_table()
    table.add_row("reference", f"[{STYLE_VALUE}]{escape(reference_name)}[/]")
    table.add_row("domain", "Untrimmed source-frame indices")
    table.add_row("task", "Find the same visible moment in both VSView outputs")
    table.add_row(
        "enter",
        f"[{STYLE_HINT}]reference_frame comparison_frame[/] (reference first; e.g. 120 108)",
    )
    table.add_row("result", "Frame Compare calculates the offset and required trim")
    table.add_row(
        "skip",
        f"[{STYLE_HINT}]'skip'[/] or [{STYLE_HINT}]'s'[/] leaves the audio result unchanged (if any)",
    )

    console = _console(no_color=no_color)
    console.print()
    console.print(
        Text.assemble(
            " " * _SECTION_INDENT,
            _status_text("[WAIT]", "VSView Confirmation", style=STYLE_WAIT),
        )
    )
    console.print(Padding(table, (0, 0, 0, _CONTENT_INDENT)))
    console.print()


def write_vsview_prompt(
    *,
    label: str,
    suggested_offset: int | None,
    no_color: bool = False,
) -> None:
    """Write a single interactive confirmation prompt to stderr."""
    console = _console(no_color=no_color)
    table = _group_table()
    table.add_row("comparison", f"[{STYLE_VALUE}]{escape(label)}[/]")
    if suggested_offset is None:
        audio_hint = "no trusted audio hint"
    elif suggested_offset > 0:
        audio_hint = (
            f"{suggested_offset:+d}f | Reference {suggested_offset} <-> Comparison 0 | "
            f"trim {suggested_offset} from reference"
        )
    elif suggested_offset < 0:
        comparison_frame = -suggested_offset
        audio_hint = (
            f"{suggested_offset:+d}f | Reference 0 <-> Comparison {comparison_frame} | "
            f"trim {comparison_frame} from comparison"
        )
    else:
        audio_hint = "+0f | Reference 0 <-> Comparison 0 | no trim"
    table.add_row("audio hint", f"[{STYLE_HINT}]{escape(audio_hint)}[/]")
    console.print(Padding(table, (0, 0, 0, _CONTENT_INDENT)))
    prompt = Text(f"{' ' * _CONTENT_INDENT}match frames ", style=STYLE_KEY)
    prompt.append("reference comparison", style=STYLE_HINT)
    prompt.append(" > ", style="bright_white")
    console.print(prompt, end="")
    sys.stderr.flush()


def print_vsview_input_hint(message: str, *, no_color: bool = False) -> None:
    console = _console(no_color=no_color)
    console.print(f"{' ' * _CONTENT_INDENT}[{STYLE_HINT}]Hint[/] {escape(message)}")


def print_vsview_confirmation_footer(*, no_color: bool = False) -> None:
    """Separate the completed blocking workflow from resumed parent progress."""
    _console(no_color=no_color).print()
