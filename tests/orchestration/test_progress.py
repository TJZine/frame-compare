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
