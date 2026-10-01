"""Tests for orchestration progress reporter selection."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

import frame_compare.orchestration.progress as progress_module
from frame_compare.orchestration.progress import (
    emit_execution_section_end,
    emit_execution_section_start,
    select_reporter,
    start_phase_progress,
)
from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    PlainProgressReporter,
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


def test_rich_phase_label_drops_skip_detail() -> None:
    """Rich live labels use the bare title-case label; detail rides the summary."""
    reporter = RichProgressReporter(no_color=True)
    with patch.object(
        reporter,
        "start_phase",
        wraps=reporter.start_phase,
    ) as start_phase:
        start_phase_progress(
            reporter,
            name="publish",
            display_label="PUBLISH  Disabled",
            total=1,
        )
    start_phase.assert_called_once_with("Publish", total=1)
    reporter.complete_phase()


@pytest.mark.parametrize("width", [60, 80])
def test_execution_section_is_rich_only_and_fits_without_color(
    width: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    console = Console(file=output, width=width, no_color=True, force_terminal=False)
    monkeypatch.setattr(progress_module, "human_console", lambda **_kwargs: console)

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
