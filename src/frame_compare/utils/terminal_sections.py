"""Shared open-rail sections for human terminal output.

Strings passed as row values are Rich markup; callers must escape interpolated
text. ``Text`` values can be used to supply literal text directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.segment import Segment
from rich.text import Text

from frame_compare.utils.terminal_theme import ACCENT, GLYPHS_ASCII, glyphs_for_console

_T = TypeVar("_T")


@dataclass
class Section:
    """An ordered body of list, key/value, blank and note rows."""

    title: str = ""
    rail_style: str = "dim"
    rows: list[RenderableType] = field(default_factory=lambda: list[RenderableType]())

    def add_row(self, key: str, value: RenderableType = "") -> None:
        if not key and value == "":
            self.rows.append(Text())
            return
        self.rows.append(_KeyValueRow(key, value))

    def add_line(self, value: RenderableType = "") -> None:
        self.rows.append(value)

    def add_note(self, text: str, *, skipped: bool = False) -> None:
        glyph = "–" if skipped else "!"
        style = "dim" if skipped else "yellow"
        self.rows.append(Text.assemble((glyph, style), " ", Text(text)))

    def render_body(self, console: Console, options: ConsoleOptions) -> RenderResult:
        ascii_only = glyphs_for_console(console) is GLYPHS_ASCII
        rail = "|" if ascii_only else "│"
        body_options = options.update(width=max(1, min(options.max_width, 120) - 2))
        for row in self.rows:
            for line in console.render_lines(row, body_options, pad=False):
                line = _without_padding(line)
                yield Segment(rail, console.get_style(self.rail_style))
                if Segment.get_line_length(line):
                    yield Segment(" ")
                    yield from line
                yield Segment.line()

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        ascii_only = glyphs_for_console(console) is GLYPHS_ASCII
        yield from console.render(
            Text.assemble(
                ("+- " if ascii_only else "╭─ ", self.rail_style), Text.from_markup(self.title)
            ),
            options.update(width=min(options.max_width, 120)),
        )
        yield from self.render_body(console, options)
        yield Text("+-" if ascii_only else "╰─", style=self.rail_style)

    def print(self, console: Console) -> None:
        console.print()
        console.print(self)
        console.print()

    def prompt(self, console: Console, question: str, ask: Callable[[str], _T]) -> _T:
        """Print an in-rail prompt, closing the section even on interruption.

        ``ask`` prints the final literal question fragment, appends `` [y/N]: ``,
        and reads/echoes the answer. The renderer prints earlier lines with styled
        rails, leaving room for the suffix and a short answer on the final line.
        """
        ascii_only = glyphs_for_console(console) is GLYPHS_ASCII
        console.print()
        console.print(
            Text.assemble(
                ("+- " if ascii_only else "╭─ ", self.rail_style), Text.from_markup(self.title)
            )
        )
        console.print(_SectionBody(self), end="")
        rail = "| " if ascii_only else "│ "
        body_width = max(1, min(console.width, 120) - 2)
        question_width = max(1, body_width - Text(" [y/N]: ").cell_len - 3)
        lines = Text(question).wrap(console, question_width)
        for line in lines[:-1]:
            console.print(Text.assemble((rail, self.rail_style), line))
        console.print(Text(rail, style=self.rail_style), end="")
        try:
            return ask(lines[-1].plain if lines else "")
        finally:
            console.print(Text("+-" if ascii_only else "╰─", style=self.rail_style))
            console.print()


def section_title(title: str, *, detail: str | None = None) -> str:
    """Style an already escaped neutral title and optional detail."""
    rendered = f"[bold {ACCENT}]{title}[/]"
    return rendered if detail is None else f"{rendered} [dim]· {detail}[/]"


@dataclass
class _SectionBody:
    section: Section

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield from self.section.render_body(console, options)


def _without_padding(line: list[Segment]) -> list[Segment]:
    """Remove layout padding while retaining the final content's style."""
    line = list(line)
    while line and not line[-1].control:
        segment = line.pop()
        text = segment.text.rstrip(" ")
        if text:
            line.append(Segment(text, segment.style))
            break
    return line


@dataclass
class _KeyValueRow:
    key: str
    value: RenderableType

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        # Size the value from the actual body width. Table's measurement pass can
        # re-add cell padding to a custom renderable's full-width measurement.
        key_width = min(14, max(1, options.max_width - 3))
        value_column = key_width + 2
        keys = console.render_lines(
            Text.from_markup(self.key, style="dim"), options.update(width=key_width), pad=False
        )
        values = console.render_lines(
            self.value, options.update(width=max(1, options.max_width - value_column)), pad=False
        )
        for index in range(max(len(keys), len(values))):
            key = keys[index] if index < len(keys) else []
            yield from key
            yield Segment(" " * (value_column - Segment.get_line_length(key)))
            if index < len(values):
                yield from values[index]
            yield Segment.line()
