"""Human-readable VSView CLI diagnostics."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from frame_compare.utils.terminal import no_color_requested

STYLE_KEY = "blue"
STYLE_PATH = "dim"
STYLE_HEADER = "bold cyan"
_STARTUP_STDERR_LIMIT = 4000


def _console(*, no_color: bool) -> Console:
    return Console(stderr=True, no_color=no_color_requested(explicit_no_color=no_color))


def _group_table() -> Table:
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column("key", style=STYLE_KEY, no_wrap=True, min_width=11)
    table.add_column("value", overflow="fold")
    return table


def _status_text(marker: str, message: str, *, style: str) -> Text:
    return Text.assemble("  ", Text(marker, style=style), " ", message)


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
    console.print(_status_text("[WARN]", "VSView alignment review unavailable", style="yellow"))
    console.print(f"       {escape(reason)}")
    console.print("       Continuing with the current alignment offsets.")
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


def print_vsview_review_result(
    *,
    accepted: bool,
    message: str,
    no_color: bool = False,
) -> None:
    """Print one bounded native-review result diagnostic to stderr."""
    marker = "[OK]" if accepted else "[WARN]"
    style = "green" if accepted else "yellow"
    console = _console(no_color=no_color)
    console.print()
    console.print(_status_text(marker, "VSView alignment review", style=style))
    console.print(f"       {escape(message)}")
