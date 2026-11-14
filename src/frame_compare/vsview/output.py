"""Human-readable VSView CLI diagnostics."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.text import Text

from frame_compare.utils.terminal import no_color_requested
from frame_compare.utils.terminal_sections import Section, section_title
from frame_compare.utils.terminal_theme import (
    WARN,
    glyphs_for_console,
    human_console,
)

STYLE_PATH = "dim"
_STARTUP_STDERR_LIMIT = 4000


def _console(*, no_color: bool) -> Console:
    return human_console(stderr=True, no_color=no_color_requested(explicit_no_color=no_color))


def print_vsview_session(
    *,
    script_path: Path,
    command: list[str],
    no_color: bool = False,
) -> None:
    """Print app-owned VSView launch telemetry to stderr."""
    table = Section(title=section_title("VSView session"))
    table.add_row("script", f"[{STYLE_PATH}]{escape(str(script_path))}[/]")
    table.add_row("command", f"[{STYLE_PATH}]{escape(' '.join(command))}[/]")
    table.add_row("output", "Frame Compare diagnostics inherited on stderr")

    console = _console(no_color=no_color)
    table.print(console)


def print_vsview_unavailable(
    *,
    reason: str,
    no_color: bool = False,
) -> None:
    """Print the single normal human warning for optional verification failure."""
    console = _console(no_color=no_color)
    glyphs = glyphs_for_console(console)
    section = Section(
        title=f"[{WARN}]{glyphs.warning} VSView review unavailable[/]", rail_style="yellow"
    )
    section.add_line(Text(reason))
    section.add_line("Continuing with the current alignment offsets.")
    section.add_line("Check the VSView setup with frame-compare doctor.")
    section.print(console)


def print_vsview_failure_details(
    *,
    command: tuple[str, ...],
    reason: str,
    returncode: int | None,
    startup_stderr: str | None,
    no_color: bool = False,
) -> None:
    """Print bounded verbose startup evidence captured by the readiness probe."""
    table = Section(title=section_title("VSView failure details"))
    table.add_row("command", f"[{STYLE_PATH}]{escape(' '.join(command))}[/]")
    detail = reason if returncode is None else f"{reason} (exit {returncode})"
    table.add_row("reason", escape(detail))
    if startup_stderr:
        table.add_row("stderr", escape(startup_stderr[-_STARTUP_STDERR_LIMIT:]))
    console = _console(no_color=no_color)
    table.print(console)


def print_vsview_review_result(
    *,
    accepted: bool,
    message: str,
    no_color: bool = False,
) -> None:
    """Print one bounded native-review result diagnostic to stderr."""
    if accepted:
        return
    console = _console(no_color=no_color)
    glyphs = glyphs_for_console(console)
    console.print(
        Text.assemble(
            (glyphs.warning, WARN),
            f" {'VSView review':<16}",
            f"{message}; current offsets were kept.",
        )
    )
