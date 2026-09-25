"""Tests for the shared terminal style tokens (S3)."""

import io
import sys
from pathlib import Path

import pytest
from rich.console import Console

from frame_compare.cli.output import print_result_summary
from frame_compare.orchestration.types import RunResult
from frame_compare.utils.terminal_theme import (
    GLYPHS_ASCII,
    GLYPHS_UNICODE,
    glyphs_for_console,
    glyphs_for_encoding,
    human_console,
    use_ascii_fallback_on_non_utf_streams,
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


@pytest.mark.parametrize(
    ("encoding", "expected"),
    [
        ("ascii", "Comparison complete | 1 warning"),
        ("cp1252", "Comparison complete · 1 warning"),
        ("utf-8", "Comparison complete · 1 warning"),
    ],
)
def test_result_summary_degrades_generated_punctuation_on_non_utf_stderr(
    monkeypatch: pytest.MonkeyPatch, encoding: str, expected: str
) -> None:
    stderr = io.TextIOWrapper(io.BytesIO(), encoding=encoding)
    monkeypatch.setattr(sys, "stderr", stderr)
    use_ascii_fallback_on_non_utf_streams()

    print_result_summary(
        human_console(stderr=True, width=100),
        result=RunResult(success=True, duration_seconds=5.0, warnings=["Übersicht"]),
        quiet=False,
        root=Path.cwd(),
    )
    stderr.flush()
    output = stderr.buffer.getvalue().decode(encoding)

    assert expected in output
    assert ("?bersicht" if encoding == "ascii" else "Übersicht") in output
