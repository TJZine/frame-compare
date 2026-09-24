"""Shared terminal style tokens for the design-refresh terminal surfaces.

Specification S3: one module importable by every layer. It holds the color
vocabulary, the status glyphs with their ASCII fallback, and human-console
construction with Rich's automatic number highlighting disabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def human_console(**kwargs: Any) -> Console:
    """Build a Rich console for human output with highlighting disabled."""
    kwargs.setdefault("highlight", False)
    return Console(**kwargs)


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
    "glyphs_for_console",
    "glyphs_for_encoding",
    "human_console",
]
