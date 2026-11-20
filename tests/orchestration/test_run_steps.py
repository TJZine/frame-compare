"""Progress and failure behavior at the run-step boundary."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Never
from unittest.mock import Mock

import httpx
import pytest

from frame_compare.analysis.errors import ExclusionRecoverySelectionError
from frame_compare.orchestration import coordinator, execution
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution import RunSteps
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    ExecutionState,
    FramePlanPhaseOutput,
    MetadataPrefetch,
    PrepState,
    RenderPhaseOutput,
)
from frame_compare.orchestration.types import ReservedRunCapture, RunDependencies
from frame_compare.services.run_result_record import read_run_result
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.progress import NullProgressReporter, RichProgressReporter
from frame_compare.utils.progress_protocol import ProgressPhaseStatus
from frame_compare.utils.run_warnings import RunWarning
from tests.run_request_support import make_run_request

from .phase_task_helpers import _context, _render_artifacts


def prep_for_context(ctx: RunContext, state: ExecutionState) -> PrepState:
    clips = [ctx.reference, *ctx.comparisons]
    return PrepState(
        workspace=ctx.workspace,
        config=ctx.config,
        input_videos=[clip.path for clip in clips],
        clips=clips,
        artifacts=state.artifacts,
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=0.0,
        selection_domain=ctx.selection_domain,
    )


async def test_unresolved_align_review_renders_warning_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _context(tmp_path)
    state = ExecutionState()
    reporter = RichProgressReporter(no_color=True)
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(
        execution,
        "run_align_phase",
        lambda *a, **kw: AlignPhaseOutput(
            reference=ctx.reference,
            comparisons=[],
            selected_frames=[],
            success_summary="SCOPE needs visual confirmation",
            review_unresolved=True,
        ),
    )
    await execution.run_selection_steps(
        ctx,
        RunSteps(reporter=reporter, state=state, monotonic_timer=lambda: 0.0),
        request=make_run_request(root=tmp_path, config=ctx.config, skip_analysis=True),
        prep=prep_for_context(ctx, state),
        state=state,
        deps=RunDependencies(),
    )

    err = capsys.readouterr().err
    align_line = next(
        line for line in err.splitlines() if "SCOPE needs visual confirmation" in line
    )
    assert "!" in align_line
    assert "✓" not in align_line


async def test_fatal_exclusion_recovery_stops_warn_only_analyze_and_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.analysis.dark_frame_count = 1
    state = ExecutionState()
    prep = prep_for_context(ctx, state)
    error = ExclusionRecoverySelectionError(
        "configured exclusions leave too little media for frame selection",
        requested=8,
        found=4,
    )
    reporter = Mock(spec=NullProgressReporter)
    render = Mock(side_effect=AssertionError("render started after fatal analyze error"))

    async def fail_analyze(*_args: object, **_kwargs: object) -> Never:
        raise error

    async def fake_prep(*_args: object, **_kwargs: object) -> PrepState:
        return prep

    monkeypatch.setattr(coordinator, "execute_prep", fake_prep)
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(execution, "run_analyze_phase", fail_analyze)
    monkeypatch.setattr(execution, "run_render_phase", render)
    async with httpx.AsyncClient(transport=httpx.MockTransport(_reject_request)) as client:
        with pytest.raises(ExclusionRecoverySelectionError) as caught:
            await coordinator.execute_run(
                make_run_request(root=tmp_path, config=ctx.config),
                RunDependencies(progress=reporter, http_client=client),
            )
    assert caught.value is error
    reporter.complete_phase.assert_called_with(
        ProgressPhaseStatus.FAILED, summary=None, duration_text=None
    )
    assert state.warnings == [RunWarning("analysis", "warning", f"analyze: {error}")]
    render.assert_not_called()


def _reject_request(_request: httpx.Request) -> Never:
    raise AssertionError("unexpected network request")


@pytest.mark.parametrize("cancel_at_start", [False, True], ids=["report-body", "report-start"])
async def test_interrupted_warn_only_report_stops_without_applying_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_at_start: bool
) -> None:
    ctx = _context(tmp_path)
    ctx.config.audio_alignment.enable = False
    ctx.config.report.enable = True
    ctx.config.slowpics.auto_upload = False
    state = ExecutionState()
    prep = prep_for_context(ctx, state)
    run_dir = prep.workspace.run_dir
    assert run_dir is not None
    run_dir.mkdir()
    reporter = Mock(spec=NullProgressReporter)
    cleanup = Mock(side_effect=AssertionError("cleanup started after interruption"))

    def start_phase(name: str, total: int) -> None:
        if cancel_at_start and name == "REPORT":
            task = asyncio.current_task()
            assert task is not None
            task.cancel()

    reporter.start_phase.side_effect = start_phase

    async def fake_prep(_request: object, deps: RunDependencies) -> PrepState:
        assert deps.capture_reserved_run is not None
        deps.capture_reserved_run(
            ReservedRunCapture(
                workspace=prep.workspace,
                clip_count=len(prep.clips),
                preflight_duration=prep.preflight_duration,
                preflight_warnings=prep.preflight_warnings,
                run_warnings=state.warnings,
            )
        )
        return prep

    def interrupt_report(*_args: object, **_kwargs: object) -> Never:
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        raise_if_cancelling()
        raise AssertionError("interrupted report returned")

    monkeypatch.setattr(coordinator, "execute_prep", fake_prep)
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(
        execution,
        "run_render_phase",
        lambda *a, **kw: RenderPhaseOutput(
            _render_artifacts(
                screenshots_by_label={}, screenshot_dir=prep.workspace.screenshots_dir
            )
        ),
    )
    report = Mock(side_effect=interrupt_report)
    monkeypatch.setattr(execution, "run_report_phase", report)
    monkeypatch.setattr(execution, "run_post_report_cleanup_phase", cleanup)
    async with httpx.AsyncClient(transport=httpx.MockTransport(_reject_request)) as client:
        worker = asyncio.create_task(
            coordinator.execute_run(
                make_run_request(
                    root=tmp_path, config=ctx.config, skip_analysis=True, skip_metadata=True
                ),
                RunDependencies(progress=reporter, http_client=client),
            )
        )
        with pytest.raises(asyncio.CancelledError):
            await worker

    record = read_run_result(run_dir / "run_result.toml")
    assert record.status == "failed"
    assert all(not warning.startswith("report:") for warning in record.warning_summaries)
    assert all(not warning.text.startswith("report:") for warning in state.warnings)
    assert state.artifacts.report_path is None
    assert not (run_dir / "report.html").exists()
    reporter.complete_phase.assert_called_with(
        ProgressPhaseStatus.FAILED, summary=None, duration_text=None
    )
    reporter.start_phase.assert_any_call("REPORT", total=1)
    if cancel_at_start:
        report.assert_not_called()
    else:
        report.assert_called_once()
    cleanup.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("boom"), asyncio.CancelledError()])
async def test_required_step_marks_failure_and_propagates(error: BaseException) -> None:
    reporter = Mock(spec=NullProgressReporter)
    state = ExecutionState()
    clock = iter([100.0, 105.0])
    steps = RunSteps(reporter=reporter, state=state, monotonic_timer=lambda: next(clock))

    async def fail() -> Never:
        raise error

    with pytest.raises(type(error)) as caught:
        await steps.run("render", fail, warning_source="render")
    assert caught.value is error
    reporter.complete_phase.assert_called_once_with(
        ProgressPhaseStatus.FAILED, summary=None, duration_text=None
    )
    reporter.advance.assert_not_called()
    assert state.phase_timings == {"render": 5.0}
    assert state.warnings == []


async def test_cancelling_warn_only_step_keeps_its_original_error() -> None:
    reporter = Mock(spec=NullProgressReporter)
    state = ExecutionState()
    steps = RunSteps(reporter=reporter, state=state, monotonic_timer=lambda: 0.0)
    error = RuntimeError("report failed while cancelling")

    def fail() -> Never:
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        raise error

    async def run() -> None:
        with pytest.raises(RuntimeError) as caught:
            await steps.run("report", fail, warning_source="render", warn_only=True)
        assert caught.value is error
        # Consume the task's queued cancellation after observing the step's own error.
        with pytest.raises(asyncio.CancelledError):
            await asyncio.sleep(0)

    await asyncio.create_task(run())
    reporter.complete_phase.assert_called_once_with(
        ProgressPhaseStatus.FAILED, summary=None, duration_text=None
    )
    reporter.advance.assert_not_called()
    assert state.warnings == []
