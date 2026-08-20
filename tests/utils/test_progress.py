"""Unit tests for progress reporting utilities."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import frame_compare.utils.progress as progress_module
from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


def test_null_progress_reporter_noops():
    """Test that NullProgressReporter methods do not raise exceptions."""
    reporter = NullProgressReporter()
    reporter.start_phase("test", 10)
    reporter.advance(1)
    reporter.set_description("desc")
    reporter.complete_phase()
    reporter.suspend()
    reporter.resume()


def test_rich_progress_reporter_accepts_no_color() -> None:
    reporter = RichProgressReporter(no_color=True)

    assert reporter.no_color is True
    assert reporter.writes_to_stderr is True


def test_rich_progress_reporter_marks_active_work_without_color() -> None:
    reporter = RichProgressReporter(no_color=True)

    reporter.start_phase("PLAN", 1)
    assert reporter._progress.tasks[0].description == "[RUN] PLAN"  # noqa: SLF001

    reporter.set_description("Selecting frames")
    assert reporter._progress.tasks[0].description == "[RUN] Selecting frames"  # noqa: SLF001
    reporter.complete_phase()


def test_rich_progress_reporter_indents_live_work() -> None:
    reporter = RichProgressReporter(no_color=True)

    reporter.start_phase("PLAN", 1)
    task = reporter._progress.tasks[0]  # noqa: SLF001
    description = reporter._progress.columns[1].render(task)  # noqa: SLF001
    reporter.complete_phase()

    assert str(description).startswith("  [RUN] PLAN")


def test_log_progress_reporter_supports_nested_phases(capsys) -> None:
    """Nested phases should restore parent context on completion."""
    reporter = LogProgressReporter()
    reporter.start_phase("outer", 100)
    reporter.advance(10)

    reporter.start_phase("inner", 1)
    reporter.advance(1)
    reporter.complete_phase()
    reporter.advance(15)

    captured = capsys.readouterr()

    assert "phase=outer" in captured.out
    assert "percentage=10" in captured.out
    assert "phase=inner" in captured.out
    assert "percentage=100" in captured.out
    assert "percentage=25" in captured.out


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
    assert task.fields["spinner_only"] is True

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


def test_rich_progress_reporter_warned_phase_does_not_force_total(
    monkeypatch,
) -> None:
    reporter = RichProgressReporter()
    update_calls: list[dict[str, object]] = []
    original_update = reporter._progress.update  # noqa: SLF001

    def _recording_update(task_id, **kwargs):
        update_calls.append(kwargs)
        return original_update(task_id, **kwargs)

    monkeypatch.setattr(reporter._progress, "update", _recording_update)  # noqa: SLF001

    reporter.start_phase("test", 10)
    reporter.advance(3)
    reporter.complete_phase(ProgressPhaseStatus.WARNED)

    assert {"description": "Warning", "refresh": True} in update_calls
    assert {"completed": 10, "refresh": True} not in update_calls


def test_rich_progress_reporter_does_not_retain_success_below_ten_seconds(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 9.9))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("PLAN", 1)
    reporter.complete_phase()

    assert "[OK] PLAN" not in capsys.readouterr().err


def test_rich_progress_reporter_retain_success_at_ten_seconds(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 10.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("PLAN", 1)
    reporter.complete_phase()

    assert "  [OK] PLAN  Completed in 10s" in capsys.readouterr().err


def test_rich_progress_reporter_explicitly_retains_short_success(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 0.1))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("PUBLISH", 1)
    reporter.complete_phase(retain=True)

    assert "[OK] PUBLISH  Completed in 0s" in capsys.readouterr().err


def test_rich_progress_reporter_suppresses_long_nested_success(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 1.0, 12.0, 13.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("RENDER", 1)
    reporter.start_phase("ENCODE", 1)
    reporter.complete_phase()
    reporter.complete_phase()

    output = capsys.readouterr().err
    assert "[OK] ENCODE" not in output
    assert "[OK] RENDER  Completed in 13s" in output


def test_rich_progress_reporter_suppresses_generic_confirm_completion(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()
    clock = iter((0.0, 10.0))
    monkeypatch.setattr(progress_module, "monotonic", lambda: next(clock))

    reporter.start_phase("CONFIRM", 1)
    reporter.complete_phase(retain=False)

    assert "[OK] CONFIRM" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ProgressPhaseStatus.SKIPPED, "[SKIP] ANALYZE"),
        (ProgressPhaseStatus.WARNED, "[WARN] ALIGN"),
        (ProgressPhaseStatus.FAILED, "[FAIL] RENDER"),
    ],
)
def test_rich_progress_reporter_retains_non_success_statuses(
    status: ProgressPhaseStatus,
    expected: str,
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reporter = RichProgressReporter()

    reporter.start_phase(expected.split(maxsplit=1)[1], 1)
    reporter.complete_phase(status)

    assert expected in capsys.readouterr().err


def test_rich_progress_reporter_refreshes_state_changes(monkeypatch) -> None:
    reporter = RichProgressReporter()
    refresh_count = 0
    original_refresh = reporter._progress.refresh  # noqa: SLF001

    def _recording_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1
        original_refresh()

    monkeypatch.setattr(reporter._progress, "refresh", _recording_refresh)  # noqa: SLF001

    reporter.start_phase("test", 3)
    started_refresh_count = refresh_count

    reporter.set_description("Rendering")
    reporter.advance(1)

    assert refresh_count >= started_refresh_count + 2

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


def test_progress_reporter_protocol_is_single_source() -> None:
    import frame_compare.analysis.metrics as metrics_module
    import frame_compare.utils.progress as progress_module
    import frame_compare.utils.progress_protocol as progress_protocol

    assert progress_module.ProgressReporter is progress_protocol.ProgressReporter
    assert metrics_module.ProgressReporter is progress_protocol.ProgressReporter
