"""Tests for orchestration progress reporter selection."""

import sys
from io import StringIO

import pytest
from rich.console import Console

import frame_compare.utils.progress as progress_module
from frame_compare.orchestration.progress import (
    select_reporter,
)
from frame_compare.utils.progress import (
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


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
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    output = StringIO()

    def console(*, stderr: bool, no_color: bool) -> Console:
        return Console(file=output, force_terminal=True, no_color=no_color)

    monkeypatch.setattr(progress_module, "human_console", console)
    reporter = select_reporter(no_color=True)
    assert isinstance(reporter, RichProgressReporter)
    reporter._print_durable_line(  # noqa: SLF001
        ProgressPhaseStatus.FAILED, "TEST", summary=None, duration=0, duration_text=None
    )
    assert "TEST" in output.getvalue()
    assert "\x1b[" not in output.getvalue()
