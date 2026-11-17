"""Shared terminal style tokens for the design-refresh terminal surfaces.

Specification S3: one module importable by every layer. It holds the color
vocabulary, the status glyphs with their ASCII fallback, human-console
construction with Rich's automatic number highlighting disabled, and the
ASCII fallback for text a non-UTF terminal stream cannot encode.
"""

from __future__ import annotations

import codecs
import io
import os
import re
import sys
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from typing import IO, Literal

from rich.cells import cell_len, chop_cells
from rich.console import Console
from rich.text import Text

ACCENT = "#d2ac6b"
KEY = "dim"
VALUE = ""
MUTED = "dim"
OK = "green"
WARN = "yellow"
FAIL = "red"

BORDER_NEUTRAL = "dim"
BORDER_PENDING = "yellow"
BORDER_SUCCESS = "green"
BORDER_FAILED = "red"

_ColorSystem = Literal["auto", "standard", "256", "truecolor", "windows"]


@dataclass(frozen=True, slots=True)
class GlyphSet:
    """Status glyphs for one console encoding."""

    ok: str
    warning: str
    skipped: str
    failed: str
    waiting: str
    running: str


GLYPHS_UNICODE = GlyphSet(ok="✓", warning="!", skipped="–", failed="✗", waiting="›", running="…")
GLYPHS_ASCII = GlyphSet(ok="+", warning="!", skipped="-", failed="x", waiting=">", running="~")


def glyphs_for_encoding(encoding: str | None) -> GlyphSet:
    """Return Unicode glyphs for UTF encodings, ASCII fallback otherwise."""
    if (encoding or "").lower().startswith("utf"):
        return GLYPHS_UNICODE
    return GLYPHS_ASCII


def glyphs_for_console(console: Console) -> GlyphSet:
    """Return the glyph set matching a Rich console's encoding."""
    return glyphs_for_encoding(console.encoding)


def glyphs_for_stream(stream: object) -> GlyphSet:
    """Return the S3 glyph set for a text stream's encoding."""
    return glyphs_for_encoding(getattr(stream, "encoding", None))


def human_console(
    *,
    file: IO[str] | None = None,
    stderr: bool = False,
    no_color: bool | None = None,
    color_system: _ColorSystem | None = "auto",
    width: int | None = None,
    height: int | None = None,
) -> Console:
    """Build a Rich console for human output with highlighting disabled."""
    console = Console(
        file=file,
        stderr=stderr,
        no_color=no_color,
        color_system=color_system,
        width=width,
        height=height,
        highlight=False,
    )

    # Rich assigns dumb terminals a fixed size even when the stream is a PTY.
    if width is None and console.is_dumb_terminal:
        with suppress(OSError, ValueError):
            size = os.get_terminal_size(console.file.fileno())
            if size.columns > 0:
                console.size = (size.columns, height or size.lines or console.height)
    return console


def print_with_paths(console: Console, markup: str, paths: Iterable[str]) -> None:
    """Wrap human output at the console width, keeping each path on one line."""
    text = Text.from_markup(markup)
    present_paths = sorted(
        {path for path in paths if path and path in text.plain and "\n" not in path},
        key=len,
        reverse=True,
    )
    if not present_paths:
        console.print(text)
        return

    # Rich expands each tab to between one and eight spaces depending on its column.
    # Match those spaces within the path so wrapping cannot split the expanded name.
    alternatives = "|".join(
        r" {1,8}".join(map(re.escape, path.split("\t"))) for path in present_paths
    )
    tokens = re.compile(rf"""(?P<path>[\['"(]*(?:{alternatives})(?=$|[\s:'"),\]]))|\S+""")
    width = max(1, console.width)
    lines: list[Text] = []
    for line in text.split(allow_blank=True):
        lines.extend(_wrap_path_line(line, width, tokens))
    # If a path exceeds the terminal width on its own, let the terminal handle
    # its display. Cropping or inserting a newline would change the copied path.
    console.print(Text("\n").join(lines), soft_wrap=True)


def _wrap_path_line(line: Text, width: int, tokens: re.Pattern[str]) -> list[Text]:
    line.expand_tabs()
    plain = line.plain
    breaks: list[int] = []
    used_width = 0
    previous_end = 0
    for match in tokens.finditer(plain):
        token = match[0]
        start = match.start()
        token_width = cell_len(token)
        used_width += cell_len(plain[previous_end:start])
        if previous_end and used_width + token_width > width:
            breaks.append(start)
            used_width = 0
        if match["path"] is None and token_width > width:
            pieces = chop_cells(token, width)
            for piece in pieces[:-1]:
                start += len(piece)
                breaks.append(start)
            used_width = cell_len(pieces[-1])
        else:
            used_width += token_width
        previous_end = match.end()

    wrapped = list(line.divide(breaks))
    for fragment in wrapped:
        fragment.rstrip()
    return wrapped


_ASCII_PUNCTUATION = str.maketrans(
    {
        "·": "|",
        "×": "x",
        "–": "-",
        "—": "-",
        "…": "...",
        "›": ">",
        "╭": "+",
        "─": "-",
        "│": "|",
        "╰": "+",
        "●": "*",
        "○": "o",
    }
)
_ASCII_FALLBACK_ERRORS = "frame_compare.ascii_fallback"


def _ascii_fallback(error: UnicodeError) -> tuple[str, int]:
    if not isinstance(error, UnicodeEncodeError):
        raise error
    text = error.object[error.start : error.end].translate(_ASCII_PUNCTUATION)
    return text.encode("ascii", "replace").decode("ascii"), error.end


def use_ascii_fallback_on_non_utf_streams() -> None:
    """Degrade unencodable terminal text instead of crashing on non-UTF streams.

    Only characters the stream cannot encode are replaced: generated punctuation
    gets an ASCII equivalent and anything else becomes ``?``. JSON output is
    ASCII-escaped and never reaches the handler.
    """
    codecs.register_error(_ASCII_FALLBACK_ERRORS, _ascii_fallback)
    for stream in (sys.stdout, sys.stderr):
        if glyphs_for_stream(stream) is GLYPHS_ASCII and isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors=_ASCII_FALLBACK_ERRORS)


def format_duration(seconds: float) -> str:
    """Format elapsed time or a source duration for human output."""
    total_seconds = max(0.0, seconds)
    if total_seconds < 60.0:
        return f"{total_seconds:.1f} s"

    whole_seconds = int(total_seconds)
    minutes, remaining_seconds = divmod(whole_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:02d}s"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes:02d}m"


def format_exclusion_duration(seconds: float) -> str:
    """Display authored sub-minute exclusion settings at their configured precision."""
    if seconds < 60.0:
        return f"{float(seconds)} s"
    return format_duration(seconds)


__all__ = [
    "ACCENT",
    "BORDER_FAILED",
    "BORDER_NEUTRAL",
    "BORDER_PENDING",
    "BORDER_SUCCESS",
    "FAIL",
    "GLYPHS_ASCII",
    "GLYPHS_UNICODE",
    "KEY",
    "MUTED",
    "OK",
    "VALUE",
    "WARN",
    "GlyphSet",
    "format_duration",
    "format_exclusion_duration",
    "glyphs_for_console",
    "glyphs_for_encoding",
    "glyphs_for_stream",
    "human_console",
    "print_with_paths",
    "use_ascii_fallback_on_non_utf_streams",
]
