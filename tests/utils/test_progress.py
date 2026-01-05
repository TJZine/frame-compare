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
