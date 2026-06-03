"""Tests for orchestration progress reporter selection."""

import sys

import pytest

from frame_compare.orchestration.progress import select_reporter
from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
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


def test_select_reporter_force_tty_false_returns_log():
    """force_tty=False should return LogProgressReporter."""
    reporter = select_reporter(force_tty=False)
    assert isinstance(reporter, LogProgressReporter)


def test_select_reporter_tty_detection_interactive(monkeypatch: pytest.MonkeyPatch):
    """Auto-detection in TTY should return RichProgressReporter."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_tty_detection_non_interactive(monkeypatch: pytest.MonkeyPatch):
    """Auto-detection in non-TTY should return LogProgressReporter."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    reporter = select_reporter()
    assert isinstance(reporter, LogProgressReporter)


def test_select_reporter_uses_stderr_tty_when_stdout_is_not_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should use Rich when stderr is interactive."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_tty_detection_no_isatty_attr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-detection without isatty attributes should return LogProgressReporter."""

    class _NoIsatty:
        pass

    monkeypatch.setattr(sys, "stdout", _NoIsatty())
    monkeypatch.setattr(sys, "stderr", _NoIsatty())
    reporter = select_reporter()
    assert isinstance(reporter, LogProgressReporter)


def test_select_reporter_tty_detection_isatty_raises_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should treat OSError from isatty as non-interactive."""

    def _raise_oserror() -> bool:
        raise OSError("stream is unavailable")

    monkeypatch.setattr(sys.stdout, "isatty", _raise_oserror)
    monkeypatch.setattr(sys.stderr, "isatty", _raise_oserror)
    reporter = select_reporter()
    assert isinstance(reporter, LogProgressReporter)


def test_select_reporter_tty_detection_isatty_raises_valueerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should treat ValueError from isatty as non-interactive."""

    def _raise_value_error() -> bool:
        raise ValueError("I/O operation on closed file")

    monkeypatch.setattr(sys.stdout, "isatty", _raise_value_error)
    monkeypatch.setattr(sys.stderr, "isatty", _raise_value_error)
    reporter = select_reporter()
    assert isinstance(reporter, LogProgressReporter)


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
    assert reporter._progress.console.no_color is True  # noqa: SLF001


def test_select_reporter_no_color_uses_rich_for_detected_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detected interactive no-color runs should keep Rich progress."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter(no_color=True)
    assert isinstance(reporter, RichProgressReporter)
    assert reporter._progress.console.no_color is True  # noqa: SLF001


def test_select_reporter_no_color_non_tty_returns_log():
    """Non-interactive no-color output should still use log progress."""
    reporter = select_reporter(no_color=True, force_tty=False)
    assert isinstance(reporter, LogProgressReporter)
