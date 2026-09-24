"""Tests for the shared terminal style tokens (S3)."""

import io

from rich.console import Console

from frame_compare.utils.terminal_theme import (
    GLYPHS_ASCII,
    GLYPHS_UNICODE,
    glyphs_for_console,
    glyphs_for_encoding,
    human_console,
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
    utf_stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    ascii_stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    try:
        utf_console = Console(file=utf_stream, force_terminal=True)
        ascii_console = Console(file=ascii_stream, force_terminal=True)
        assert glyphs_for_console(utf_console) == GLYPHS_UNICODE
        assert glyphs_for_console(ascii_console) == GLYPHS_ASCII
    finally:
        utf_stream.close()
        ascii_stream.close()


def test_human_console_disables_highlight() -> None:
    stream = io.StringIO()
    human_console(file=stream, force_terminal=True, width=100).print("seed 20202020")
    assert stream.getvalue() == "seed 20202020\n"
