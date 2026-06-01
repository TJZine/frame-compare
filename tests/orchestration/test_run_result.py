from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

from frame_compare.orchestration import RunResult as PublicRunResult
from frame_compare.orchestration.coordinator import RunResult
from frame_compare.orchestration.types import PostUploadActionResult


def test_run_result_defaults() -> None:
    result = RunResult(success=True)

    assert result.success is True
    assert result.screenshot_dir is None
    assert result.slowpics_url is None
    assert result.report_path is None
    assert result.post_upload_actions == ()

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
    assert second.post_upload_actions == ()


def test_run_result_accepts_typed_post_upload_action_results() -> None:
    shortcut_path = Path("Slowpics.url")
    action = PostUploadActionResult(
        kind="shortcut",
        success=True,
        detail="slow.pics shortcut",
        path=shortcut_path,
        message="Shortcut written.",
    )

    result = RunResult(success=True, post_upload_actions=(action,))

    assert result.post_upload_actions == (action,)
    assert result.post_upload_actions[0].kind == "shortcut"
    assert result.post_upload_actions[0].path == shortcut_path


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
