"""Tests for the shared terminal style tokens (S3)."""

import io

from frame_compare.utils.terminal_theme import (
    ACCENT,
    BORDER_FAILED,
    BORDER_NEUTRAL,
    BORDER_PENDING,
    BORDER_SUCCESS,
    FAIL,
    GLYPHS_ASCII,
    GLYPHS_UNICODE,
    KEY,
    MUTED,
    OK,
    VALUE,
    WARN,
    glyphs_for_console,
    glyphs_for_encoding,
    human_console,
)


def test_style_token_values() -> None:
    assert ACCENT == "#d2ac6b"
    assert KEY == "dim"
    assert VALUE == ""
    assert MUTED == "dim"
    assert (OK, WARN, FAIL) == ("green", "yellow", "red")
    assert (BORDER_NEUTRAL, BORDER_PENDING, BORDER_SUCCESS, BORDER_FAILED) == (
        "dim",
        "yellow",
        "green",
        "red",
    )


def test_unicode_glyphs() -> None:
    assert glyphs_for_encoding("utf-8").ok == "✓"
    assert glyphs_for_encoding("UTF-8").failed == "✗"
    assert glyphs_for_encoding("utf8").waiting == "›"
    assert glyphs_for_encoding(None) == GLYPHS_ASCII


def test_ascii_fallback_glyphs() -> None:
    fallback = glyphs_for_encoding("ascii")
    assert (fallback.ok, fallback.warning, fallback.skipped) == ("+", "!", "-")
    assert (fallback.failed, fallback.waiting, fallback.running) == ("x", ">", "~")
    assert fallback == GLYPHS_ASCII
    assert glyphs_for_encoding("cp1252").ok == "+"
    assert glyphs_for_encoding("").failed == "x"


def test_glyphs_for_console_uses_console_encoding() -> None:
    assert glyphs_for_console(human_console()).ok == GLYPHS_UNICODE.ok


def test_human_console_disables_highlight() -> None:
    stream = io.StringIO()
    human_console(file=stream, force_terminal=True, width=100).print("seed 20202020")
    assert stream.getvalue() == "seed 20202020\n"
