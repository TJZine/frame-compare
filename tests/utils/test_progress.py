"""Unit tests for progress reporting utilities."""

import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pytest
from rich.console import Console

import frame_compare.utils.progress as progress_module
from frame_compare.utils.progress import (
    PlainProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


def _captured_rich_reporter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    no_color: bool = True,
) -> tuple[RichProgressReporter, StringIO]:
    monkeypatch.setenv("TERM", "xterm-256color")
    if not no_color:
        monkeypatch.delenv("NO_COLOR", raising=False)
    output = StringIO()
    console = Console(
        file=output,
        force_terminal=True,
        no_color=no_color,
        color_system="standard",
        width=100,
    )

    def _console(**_kwargs: object) -> Console:
        return console

    monkeypatch.setattr(progress_module, "human_console", _console)
    return RichProgressReporter(no_color=no_color), output


def test_plain_progress_reporter_emits_one_ascii_line_per_top_level_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    clock = iter((0.0, 84.9, 85.0, 86.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))
    monkeypatch.setattr(sys, "stderr", output)
    reporter = PlainProgressReporter()

    reporter.start_phase("ANALYZE", 100)
    reporter.start_indeterminate("D\N{LATIN SMALL LETTER E WITH ACUTE}CODE")
    reporter.complete_phase()
    reporter.complete_phase()
    reporter.start_phase("METADATA  Disabled", 1)
    reporter.complete_phase(ProgressPhaseStatus.SKIPPED)

    assert output.getvalue().splitlines() == [
        "[OK] ANALYZE  Completed in 1m 25s",
        "[SKIP] METADATA  Disabled",
    ]
    assert output.getvalue().isascii()
    assert "\x1b[" not in output.getvalue()
    assert "\r" not in output.getvalue()


def test_rich_progress_reporter_suspend_and_resume_preserves_active_task() -> None:
    reporter = RichProgressReporter()

    reporter.start_phase("test", 10)

    assert reporter._progress.live.is_started is True  # noqa: SLF001

    reporter.suspend()

    assert reporter._progress.live.is_started is False  # noqa: SLF001

    reporter.resume()

    assert reporter._progress.live.is_started is True  # noqa: SLF001

    reporter.complete_phase()


def test_rich_progress_reporter_hides_parent_while_nested_phase_is_active(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[tuple[object, dict[str, object]]] = []
    original_update = reporter._progress.update  # noqa: SLF001

    def _recording_update(task_id, **kwargs):
        update_calls.append((task_id, kwargs))
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)  # noqa: SLF001

    reporter.start_phase("outer", 10)
    outer_task_id = reporter._task_id  # noqa: SLF001
    reporter.start_phase("inner", 3)

    assert (outer_task_id, {"visible": False, "refresh": True}) in update_calls

    reporter.complete_phase()

    assert reporter._task_id == outer_task_id  # noqa: SLF001
    assert (outer_task_id, {"visible": True, "refresh": True}) in update_calls

    reporter.complete_phase()


def test_rich_progress_reporter_indeterminate_phase_is_spinner_only() -> None:
    reporter = RichProgressReporter()

    reporter.start_indeterminate("Loading cached data")

    task = reporter._progress.tasks[0]  # noqa: SLF001
    assert task.total is None
    assert task.fields["presentation"] == "indeterminate"

    reporter.complete_phase()


def test_rich_progress_reporter_restores_parent_when_nested_phase_fails(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[tuple[object, dict[str, object]]] = []
    original_update = reporter._progress.update  # noqa: SLF001

    def _recording_update(task_id, **kwargs):
        update_calls.append((task_id, kwargs))
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)  # noqa: SLF001

    reporter.start_phase("outer", 10)
    outer_task_id = reporter._task_id  # noqa: SLF001
    reporter.start_phase("inner", 3)

    reporter.complete_phase(ProgressPhaseStatus.FAILED)

    assert reporter._task_id == outer_task_id  # noqa: SLF001
    assert (outer_task_id, {"visible": True, "refresh": True}) in update_calls

    reporter.complete_phase()


def test_rich_progress_reporter_serializes_concurrent_updates() -> None:
    reporter = RichProgressReporter()
    reporter.start_phase("test", 40)

    def _update(index: int) -> None:
        reporter.set_description(f"Rendering {index}")
        reporter.advance(1)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(_update, range(40)))

    reporter.complete_phase()
