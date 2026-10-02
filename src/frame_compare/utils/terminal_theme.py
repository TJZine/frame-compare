"""Shared terminal style tokens for the design-refresh terminal surfaces.

Specification S3: one module importable by every layer. It holds the color
vocabulary, the status glyphs with their ASCII fallback, human-console
construction with Rich's automatic number highlighting disabled, and the
ASCII fallback for text a non-UTF terminal stream cannot encode.
"""

from __future__ import annotations

import codecs
import io
import sys
from dataclasses import dataclass
from typing import IO, Literal

from rich.console import Console

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
    force_terminal: bool | None = None,
    color_system: _ColorSystem | None = "auto",
    width: int | None = None,
    height: int | None = None,
) -> Console:
    """Build a Rich console for human output with highlighting disabled."""
    return Console(
        file=file,
        stderr=stderr,
        no_color=no_color,
        force_terminal=force_terminal,
        color_system=color_system,
        width=width,
        height=height,
        highlight=False,
    )


_ASCII_PUNCTUATION = str.maketrans({"·": "|", "×": "x", "–": "-", "—": "-", "…": "...", "›": ">"})
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
    """Format a duration for a human summary (S3 value grammar)."""
    total_seconds = max(0.0, seconds)
    if total_seconds < 1.0:
        return f"{total_seconds * 1000:.0f} ms"
    if total_seconds < 60.0:
        return f"{total_seconds:.1f} s"

    whole_seconds = int(total_seconds)
    minutes, remaining_seconds = divmod(whole_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:02d}s"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes:02d}m {remaining_seconds:02d}s"


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
    "glyphs_for_console",
    "glyphs_for_encoding",
    "glyphs_for_stream",
    "human_console",
    "use_ascii_fallback_on_non_utf_streams",
]
