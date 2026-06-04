"""Human-readable VSPreview CLI diagnostics."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

STYLE_KEY = "blue"
STYLE_VALUE = "bright_white"
STYLE_PATH = "dim"
STYLE_HINT = "yellow"
STYLE_HEADER = "bold cyan"


def _no_color_requested(no_color: bool) -> bool:
    return no_color or "NO_COLOR" in os.environ


def _console(*, no_color: bool) -> Console:
    return Console(stderr=True, no_color=_no_color_requested(no_color))


def _group_table() -> Table:
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column("key", style=STYLE_KEY, no_wrap=True, min_width=11)
    table.add_column("value", overflow="fold")
    return table


def print_vspreview_session(
    *,
    script_path: Path,
    command: list[str],
    no_color: bool = False,
) -> None:
    """Print app-owned VSPreview launch telemetry to stderr."""
    table = _group_table()
    table.add_row("script", f"[{STYLE_PATH}]{escape(str(script_path))}[/]")
    table.add_row("command", f"[{STYLE_PATH}]{escape(' '.join(command))}[/]")
    table.add_row("output", "Frame Compare diagnostics inherited on stderr")

    console = _console(no_color=no_color)
    console.print()
    console.print(f"[{STYLE_HEADER}]VSPreview Session[/]")
    console.print(table)


def print_vspreview_confirmation_header(
    *,
    reference: Path,
    no_color: bool = False,
) -> None:
    """Print the manual alignment confirmation instructions to stderr."""
    table = _group_table()
    table.add_row("reference", f"[{STYLE_VALUE}]{escape(reference.stem)}[/]")
    table.add_row("domain", "source-frame indices from the untrimmed clips")
    table.add_row(
        "enter",
        (
            f"[{STYLE_HINT}]reference_source_frame comparison_source_frame[/]; "
            "offset = reference_source_frame - comparison_source_frame"
        ),
    )
    table.add_row("skip", f"enter [{STYLE_HINT}]'skip'[/] or [{STYLE_HINT}]'s'[/]")

    console = _console(no_color=no_color)
    console.print()
    console.print(f"[{STYLE_HEADER}]VSPreview Confirmation[/]")
    console.print(table)
    console.print()


def write_vspreview_prompt(
    *,
    label: str,
    suggested_offset: str,
    no_color: bool = False,
) -> None:
    """Write a single interactive confirmation prompt to stderr."""
    console = _console(no_color=no_color)
    table = _group_table()
    table.add_row("comparison", f"[{STYLE_VALUE}]{escape(label)}[/]")
    console.print(table)
    prompt = Text("  frames [")
    prompt.append(suggested_offset, style=STYLE_HINT)
    prompt.append("]: ")
    console.print(prompt, end="")
    sys.stderr.flush()


def print_vspreview_input_hint(message: str, *, no_color: bool = False) -> None:
    console = _console(no_color=no_color)
    console.print(f"  [{STYLE_HINT}]Hint[/] {escape(message)}")
