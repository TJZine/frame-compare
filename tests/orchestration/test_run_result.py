from __future__ import annotations

from frame_compare.orchestration.coordinator import RunResult
from frame_compare.utils.run_warnings import RunWarning


def test_run_result_default_factories_are_distinct() -> None:
    first = RunResult(success=True)
    second = RunResult(success=True)

    first.errors.append("error")
    first.warnings.append(RunWarning("sources", "warning", "warning"))
    first.phase_timings["phase"] = 1.0

    assert second.errors == []
    assert second.warnings == []
    assert second.phase_timings == {}
    assert second.post_upload_actions == ()
