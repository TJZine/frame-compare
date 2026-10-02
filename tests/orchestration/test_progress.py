"""Tests for orchestration progress reporter selection."""

import sys

import pytest

from frame_compare.orchestration.progress import (
    select_reporter,
)
from frame_compare.utils.progress import (
    RichProgressReporter,
)


def test_select_reporter_tty_detection_interactive(monkeypatch: pytest.MonkeyPatch):
    """Auto-detection in TTY should return RichProgressReporter."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_uses_stderr_tty_when_stdout_is_not_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detection should use Rich when stderr is interactive."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_no_color_uses_rich_for_detected_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-detected interactive no-color runs should keep Rich progress."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter(no_color=True)
    assert isinstance(reporter, RichProgressReporter)
    assert reporter.no_color is True
