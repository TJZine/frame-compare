"""Unit tests for progress reporting utilities."""

from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    RichProgressReporter,
)


def test_null_progress_reporter_noops():
    """Test that NullProgressReporter methods do not raise exceptions."""
    reporter = NullProgressReporter()
    reporter.start_phase("test", 10)
    reporter.advance(1)
    reporter.set_description("desc")
    reporter.complete_phase()


def test_rich_progress_reporter_smoke():
    """Smoke test for RichProgressReporter."""
    reporter = RichProgressReporter()
    reporter.start_phase("test", 10)
    reporter.advance(1)
    reporter.set_description("desc")
    reporter.complete_phase()


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


def test_progress_reporter_protocol_is_single_source() -> None:
    from frame_compare.analysis import metrics as metrics_module
    from frame_compare.utils import progress as progress_module
    from frame_compare.utils import progress_protocol

    assert progress_module.ProgressReporter is progress_protocol.ProgressReporter
    assert metrics_module.ProgressReporter is progress_protocol.ProgressReporter
