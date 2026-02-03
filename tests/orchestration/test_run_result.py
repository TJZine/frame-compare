from __future__ import annotations

from dataclasses import FrozenInstanceError

from frame_compare.orchestration import RunResult as PublicRunResult
from frame_compare.orchestration.coordinator import RunResult


def test_run_result_defaults() -> None:
    result = RunResult(success=True)

    assert result.success is True
    assert result.screenshot_dir is None
    assert result.slowpics_url is None
    assert result.report_path is None

    assert result.frame_count == 0
    assert result.clips_processed == 0
    assert result.duration_seconds == 0.0
    assert result.cache_hit is False

    assert result.errors == []
    assert result.warnings == []
    assert result.phase_timings == {}


def test_run_result_default_factories_are_distinct() -> None:
    first = RunResult(success=True)
    second = RunResult(success=True)

    first.errors.append("error")
    first.warnings.append("warning")
    first.phase_timings["phase"] = 1.0

    assert second.errors == []
    assert second.warnings == []
    assert second.phase_timings == {}


def test_run_result_is_frozen() -> None:
    result = RunResult(success=True)

    try:
        result.success = False  # type: ignore[reportAttributeAccessIssue]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("RunResult should be frozen.")


def test_run_result_exported_from_orchestration() -> None:
    assert PublicRunResult is RunResult
