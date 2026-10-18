import asyncio
import sys
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from rich.text import Text

import frame_compare.utils.progress as progress_module
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.phases import Phase, execute_phases
from frame_compare.orchestration.progress import (
    select_reporter,
)
from frame_compare.utils.progress import (
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


def test_select_reporter_tty_detection_interactive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_uses_stderr_tty_when_stdout_is_not_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    reporter = select_reporter()
    assert isinstance(reporter, RichProgressReporter)


def test_select_reporter_no_color_uses_rich_for_detected_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    output = StringIO()

    def console(*, stderr: bool, no_color: bool) -> Console:
        return Console(file=output, force_terminal=True, no_color=no_color)

    monkeypatch.setattr(progress_module, "human_console", console)
    reporter = select_reporter(no_color=True)
    assert isinstance(reporter, RichProgressReporter)
    reporter._print_durable_line(
        ProgressPhaseStatus.FAILED, "TEST", summary=None, duration=0, duration_text=None
    )
    assert "TEST" in output.getvalue()
    assert "\x1b[" not in output.getvalue()


def test_fast_successful_align_keeps_its_phase_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from .phase_task_helpers import _context

    output = StringIO()
    monkeypatch.setattr(
        progress_module,
        "human_console",
        lambda **_kwargs: Console(file=output, force_terminal=False, width=100),
    )
    monkeypatch.setattr(progress_module, "monotonic", lambda: 0.0)
    reporter = RichProgressReporter()

    async def align(_context: RunContext) -> None:
        return

    phase = Phase("align", align, success_summary="source +0f · reused from last run")
    asyncio.run(execute_phases([phase], _context(tmp_path), reporter))
    assert Text.from_ansi(output.getvalue()).plain.strip() == (
        "✓ Align           source +0f · reused from last run · 0s"
    )
