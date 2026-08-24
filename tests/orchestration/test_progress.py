"""Tests for orchestration progress reporter selection."""

import sys
from io import StringIO

import pytest
from rich.console import Console

import frame_compare.orchestration.progress as progress_module
from frame_compare.orchestration.progress import (
    emit_execution_section_end,
    emit_execution_section_start,
    select_reporter,
)
from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    PlainProgressReporter,
    RichProgressReporter,
)


def test_select_reporter_quiet_returns_null():
    """quiet=True should return NullProgressReporter."""
    reporter = select_reporter(quiet=True)
    assert isinstance(reporter, NullProgressReporter)


def test_select_reporter_json_returns_log():
    """json_output=True should return LogProgressReporter."""
    reporter = select_reporter(json_output=True)
    assert isinstance(reporter, LogProgressReporter)


def test_select_reporter_force_tty_true_returns_rich():
    """force_tty=True should return RichProgressReporter."""
    reporter = select_reporter(force_tty=True)
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_force_tty_false_returns_plain():
    """force_tty=False should return PlainProgressReporter."""
    reporter = select_reporter(force_tty=False)
    assert isinstance(reporter, PlainProgressReporter)


def test_select_reporter_tty_detection_interactive(monkeypatch: pytest.MonkeyPatch):
    """Auto-detection in TTY should return RichProgressReporter."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_tty_detection_non_interactive(monkeypatch: pytest.MonkeyPatch):
    """Auto-detection in non-TTY should return PlainProgressReporter."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    reporter = select_reporter()
    assert isinstance(reporter, PlainProgressReporter)


def test_select_reporter_uses_stderr_tty_when_stdout_is_not_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should use Rich when stderr is interactive."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_tty_detection_no_isatty_attr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-detection without isatty attributes should return PlainProgressReporter."""

    class _NoIsatty:
        pass

    monkeypatch.setattr(sys, "stdout", _NoIsatty())
    monkeypatch.setattr(sys, "stderr", _NoIsatty())
    reporter = select_reporter()
    assert isinstance(reporter, PlainProgressReporter)


def test_select_reporter_tty_detection_isatty_raises_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should treat OSError from isatty as non-interactive."""

    def _raise_oserror() -> bool:
        raise OSError("stream is unavailable")

    monkeypatch.setattr(sys.stdout, "isatty", _raise_oserror)
    monkeypatch.setattr(sys.stderr, "isatty", _raise_oserror)
    reporter = select_reporter()
    assert isinstance(reporter, PlainProgressReporter)


def test_select_reporter_tty_detection_isatty_raises_valueerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should treat ValueError from isatty as non-interactive."""

    def _raise_value_error() -> bool:
        raise ValueError("I/O operation on closed file")

    monkeypatch.setattr(sys.stdout, "isatty", _raise_value_error)
    monkeypatch.setattr(sys.stderr, "isatty", _raise_value_error)
    reporter = select_reporter()
    assert isinstance(reporter, PlainProgressReporter)


def test_select_reporter_quiet_takes_precedence_over_json():
    """quiet=True should win over json_output=True."""
    reporter = select_reporter(quiet=True, json_output=True)
    assert isinstance(reporter, NullProgressReporter)


def test_select_reporter_quiet_takes_precedence_over_force_tty():
    """quiet=True should win over force_tty=True."""
    reporter = select_reporter(quiet=True, force_tty=True)
    assert isinstance(reporter, NullProgressReporter)


def test_select_reporter_json_takes_precedence_over_force_tty():
    """json_output=True should win over force_tty=True."""
    reporter = select_reporter(json_output=True, force_tty=True)
    assert isinstance(reporter, LogProgressReporter)


def test_select_reporter_no_color_uses_rich_for_forced_tty():
    """Interactive no-color runs should keep Rich progress with color disabled."""
    reporter = select_reporter(no_color=True, force_tty=True)
    assert isinstance(reporter, RichProgressReporter)
    assert reporter.no_color is True


def test_select_reporter_no_color_uses_rich_for_detected_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detected interactive no-color runs should keep Rich progress."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter(no_color=True)
    assert isinstance(reporter, RichProgressReporter)
    assert reporter.no_color is True


def test_select_reporter_no_color_non_tty_returns_plain():
    """Non-interactive no-color output should still use plain progress."""
    reporter = select_reporter(no_color=True, force_tty=False)
    assert isinstance(reporter, PlainProgressReporter)


@pytest.mark.parametrize("width", [60, 80])
def test_execution_section_is_rich_only_and_fits_without_color(
    width: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    console = Console(file=output, width=width, no_color=True, force_terminal=False)
    monkeypatch.setattr(progress_module, "Console", lambda **_kwargs: console)

    reporter = RichProgressReporter(no_color=True)
    emit_execution_section_start(reporter, no_color=True)
    emit_execution_section_end(reporter, no_color=True)
    for non_rich in (LogProgressReporter(), PlainProgressReporter(), NullProgressReporter()):
        emit_execution_section_start(non_rich, no_color=True)
        emit_execution_section_end(non_rich, no_color=True)

    rendered = output.getvalue()
    assert rendered.count("Execution") == 1
    assert "\x1b[" not in rendered
    assert max(len(line) for line in rendered.splitlines()) <= width
