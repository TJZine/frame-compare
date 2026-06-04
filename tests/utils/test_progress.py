"""Unit tests for progress reporting utilities."""

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


def test_rich_progress_reporter_smoke():
    """Smoke test for RichProgressReporter."""
    reporter = RichProgressReporter()
    reporter.start_phase("test", 10)
    reporter.advance(1)
    reporter.set_description("desc")
    reporter.complete_phase()


def test_rich_progress_reporter_accepts_no_color() -> None:
    reporter = RichProgressReporter(no_color=True)

    assert reporter.no_color is True
    assert reporter.writes_to_stderr is True


def test_log_progress_reporter_smoke():
    """Smoke test for LogProgressReporter."""
    reporter = LogProgressReporter()
    reporter.start_phase("test", 100)
    # Trigger some milestones
    reporter.advance(10)  # 10%
    reporter.advance(15)  # 25%
    reporter.advance(25)  # 50%
    reporter.set_description("desc")
    reporter.complete_phase()
    reporter.suspend()
    reporter.resume()
    assert reporter._name == ""  # noqa: SLF001
    assert reporter._total == 0  # noqa: SLF001
    assert reporter._current == 0  # noqa: SLF001
    assert reporter._last_logged_milestone == 0  # noqa: SLF001


def test_log_progress_reporter_supports_nested_phases():
    """Nested phases should restore parent context on completion."""
    reporter = LogProgressReporter()
    reporter.start_phase("outer", 100)
    reporter.advance(10)

    reporter.start_phase("inner", 1)
    reporter.advance(1)
    reporter.complete_phase()

    assert reporter._name == "outer"  # noqa: SLF001
    assert reporter._total == 100  # noqa: SLF001
    assert reporter._current == 10  # noqa: SLF001


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

    assert (outer_task_id, {"visible": False}) in update_calls

    reporter.complete_phase()

    assert reporter._task_id == outer_task_id  # noqa: SLF001
    assert (outer_task_id, {"visible": True}) in update_calls

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

    assert {"description": "Warning"} in update_calls
    assert {"completed": 10} not in update_calls


def test_progress_reporter_protocol_is_single_source() -> None:
    import frame_compare.analysis.metrics as metrics_module
    import frame_compare.utils.progress as progress_module
    import frame_compare.utils.progress_protocol as progress_protocol

    assert progress_module.ProgressReporter is progress_protocol.ProgressReporter
    assert metrics_module.ProgressReporter is progress_protocol.ProgressReporter
