"""Run coordination composition root for Frame Compare."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from datetime import datetime

import httpx

from frame_compare.orchestration.alignment_report import (
    build_frame_alignment_report,
    emit_frame_alignment_report,
)
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution import (
    RunSteps,
    progress_step_names,
    run_output_steps,
    run_selection_steps,
)
from frame_compare.orchestration.execution_types import (
    ExecutionState,
    RunArtifacts,
)
from frame_compare.orchestration.fps_report import (
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)
from frame_compare.orchestration.preparation import execute_prep
from frame_compare.orchestration.progress import (
    select_reporter,
    uses_rich_progress,
)
from frame_compare.orchestration.run_result_lifecycle import (
    record_completed_run_result,
    record_failed_run_best_effort,
)
from frame_compare.orchestration.selection_report import emit_final_selection_report
from frame_compare.orchestration.types import (
    ReservedRunCapture,
    RunDependencies,
    RunRequest,
    RunResult,
)
from frame_compare.services.errors import AudioAlignmentCleanupError
from frame_compare.utils.cancellation import (
    _RunInterrupt,  # pyright: ignore[reportPrivateUsage] - private coroutine-boundary marker
    cancellation_checkpoint,
    is_cancelling,
)
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.types import WorkspacePaths

__all__ = ["RunDependencies", "RunRequest", "RunResult", "execute_run"]


@asynccontextmanager
async def _run_http_client(deps: RunDependencies) -> AsyncGenerator[httpx.AsyncClient]:
    if deps.http_client is not None:
        yield deps.http_client
        return

    client = httpx.AsyncClient()
    deps.http_client = client
    try:
        yield client
    except BaseException:
        deps.http_client = None
        # Preserve the run error. A cancel delivered during close still leaves
        # the task cancelling for _interrupt_outcome.
        with suppress(Exception, asyncio.CancelledError):
            await client.aclose()
        raise
    deps.http_client = None
    with suppress(Exception):
        await client.aclose()


def _interrupt_outcome(error: BaseException) -> BaseException:
    if isinstance(error, _RunInterrupt) or (
        isinstance(error, Exception)
        and is_cancelling()
        and not isinstance(error, AudioAlignmentCleanupError)
    ):
        return asyncio.CancelledError()
    return error


def _assemble_run_result(
    *,
    artifacts: RunArtifacts,
    selected_frames: list[int],
    context: RunContext,
    preflight_warnings: list[RunWarning],
    phase_timings: dict[str, float],
    duration_seconds: float,
    vsview_review_seconds: float = 0.0,
) -> RunResult:
    """Helper to assemble a RunResult from collected state."""
    return RunResult(
        success=True,
        screenshot_dir=None if artifacts.render is None else artifacts.render.screenshot_dir,
        slowpics_url=artifacts.slowpics_url,
        report_path=artifacts.report_path,
        alignment_summary=artifacts.alignment_summary,
        alignment_diagnostics_dir=artifacts.alignment_diagnostics_dir,
        post_upload_actions=artifacts.post_upload_actions,
        slowpics_upload_confirmation_status=artifacts.slowpics_upload_confirmation_status,
        frame_count=len(selected_frames),
        clips_processed=1 + len(context.comparisons),
        duration_seconds=duration_seconds,
        cache_hit=artifacts.metrics_cache_hit,
        metrics_cache_status=artifacts.metrics_cache_status,
        phase_timings=phase_timings,
        vsview_review_seconds=max(0.0, vsview_review_seconds),
        warnings=[
            *preflight_warnings,
            *sorted(
                artifacts.warnings,
                key=lambda warning: (
                    warning.message + (" " + warning.detail if warning.detail is not None else "")
                ),
            ),
        ],
    )


async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult:
    """Execute a run request asynchronously.

    Raises:
        FrameCompareError: Any preflight validation errors are propagated.
    """
    reserved_workspace: WorkspacePaths | None = None
    run_start: datetime | None = None
    run_timer_start: float | None = None
    phase_timings: dict[str, float] = {}
    clip_count = 0
    selected_frame_count = 0
    artifacts: RunArtifacts | None = None
    preflight_warnings: list[RunWarning] = []
    current_preflight_warnings: list[RunWarning] | None = None

    def _capture_reserved_run(capture: ReservedRunCapture) -> None:
        nonlocal artifacts, clip_count, phase_timings, preflight_warnings, reserved_workspace
        reserved_workspace = capture.workspace
        clip_count = capture.clip_count
        phase_timings = {"preflight": capture.preflight_duration}
        preflight_warnings = capture.preflight_warnings
        artifacts = RunArtifacts(warnings=capture.run_warnings)

    local_deps = RunDependencies() if deps is None else replace(deps)

    local_deps.capture_reserved_run = _capture_reserved_run

    if request.json_output or request.quiet or request.from_cache_only or request.skip_analysis:
        local_deps.confirm_full_window_retry = None

    if local_deps.progress is None:
        local_deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
            no_color=request.no_color,
        )

    async def _execute_with_deps() -> tuple[RunResult, datetime, datetime]:
        nonlocal artifacts, clip_count, phase_timings, preflight_warnings, run_start
        nonlocal current_preflight_warnings
        nonlocal run_timer_start
        nonlocal selected_frame_count
        run_start = local_deps.clock()
        run_timer_start = local_deps.monotonic_timer()
        reporter = local_deps.progress
        if reporter is None:
            raise RuntimeError("Progress reporter must be initialized before execution.")

        await cancellation_checkpoint()
        prep = await execute_prep(request, local_deps)
        await cancellation_checkpoint()
        state = ExecutionState(artifacts=prep.artifacts)
        artifacts = prep.artifacts
        phase_timings = state.phase_timings
        clip_count = len(prep.clips)
        preflight_warnings = list(prep.preflight_warnings)
        current_preflight_warnings = prep.preflight_warnings

        state.phase_timings["preflight"] = prep.preflight_duration

        reference = prep.clips[0]
        comparisons = prep.clips[1:]

        context = RunContext(
            config=prep.config,
            workspace=prep.workspace,
            reference=reference,
            comparisons=comparisons,
            selection_domain=prep.selection_domain,
            reporter=reporter,
            confirm_full_window_retry=local_deps.confirm_full_window_retry,
            run_warnings=state.warnings,
            preflight_warnings=prep.preflight_warnings,
            no_color=request.no_color,
        )
        emit_consolidated_fps_report(
            stage="after_load_sources",
            clips=build_consolidated_fps_report(reference, comparisons),
            diagnostics=prep.load_source_diagnostics,
            json_output=request.json_output,
            quiet=request.quiet,
            rich_output=uses_rich_progress(reporter),
            no_color=request.no_color,
            verbose=request.verbose,
        )
        state.phase_timings["load_sources"] = max(
            0.0, local_deps.monotonic_timer() - prep.load_sources_start
        )

        state.phase_timings.update(
            {
                "frame_plan": 0.0,
                "analyze": 0.0,
                "align": 0.0,
                "render": 0.0,
                "metadata": 0.0,
                "publish": 0.0,
                "report": 0.0,
                "post_report_cleanup": 0.0,
            }
        )
        if prep.config.slowpics.auto_upload and prep.config.slowpics.confirm_upload_after_report:
            state.phase_timings["confirm_slowpics_upload"] = 0.0

        steps = RunSteps(reporter=reporter, state=state, monotonic_timer=local_deps.monotonic_timer)
        reporter.set_phase_steps(progress_step_names(request, prep.config))
        await run_selection_steps(
            context, steps, request=request, prep=prep, state=state, deps=local_deps
        )
        selected_frame_count = len(list(context.selection.frames))
        emit_final_selection_report(
            selected_frames=list(context.selection.frames),
            breakdown=context.selection.breakdown,
            verbose=request.verbose,
            json_output=request.json_output,
            quiet=request.quiet,
            no_color=request.no_color,
        )
        emit_consolidated_fps_report(
            stage="after_align",
            clips=build_consolidated_fps_report(context.reference, context.comparisons),
            json_output=request.json_output,
            quiet=request.quiet,
            rich_output=uses_rich_progress(reporter),
            no_color=request.no_color,
            verbose=request.verbose,
        )
        emit_frame_alignment_report(
            stage="after_align",
            comparisons=build_frame_alignment_report(
                reference=context.reference,
                comparisons=context.comparisons,
            ),
            selected_frames=list(context.selection.frames),
            alignment_warnings=[
                warning for warning in state.warnings if warning.source == "alignment"
            ],
            json_output=request.json_output,
            quiet=request.quiet,
            no_color=request.no_color,
            verbose=request.verbose,
        )
        await run_output_steps(
            context, steps, request=request, prep=prep, state=state, deps=local_deps
        )
        duration_seconds = max(0.0, local_deps.monotonic_timer() - run_timer_start)
        run_end = local_deps.clock()
        result = _assemble_run_result(
            artifacts=prep.artifacts,
            selected_frames=list(context.selection.frames),
            context=context,
            preflight_warnings=prep.preflight_warnings,
            phase_timings=state.phase_timings,
            duration_seconds=duration_seconds,
            vsview_review_seconds=state.vsview_review_seconds,
        )
        return result, run_start, run_end

    try:
        async with _run_http_client(local_deps):
            result, started_at, completed_at = await _execute_with_deps()
        recorded = record_completed_run_result(
            workspace=reserved_workspace,
            result=result,
            started_at=started_at,
            completed_at=completed_at,
        )
        # An interrupt after the completed record is written still fails the run.
        await cancellation_checkpoint()
        return recorded
    except BaseException as error:
        outcome = _interrupt_outcome(error)
        duration_seconds = (
            0.0
            if run_timer_start is None
            else max(0.0, local_deps.monotonic_timer() - run_timer_start)
        )
        record_failed_run_best_effort(
            workspace=reserved_workspace,
            error=outcome,
            started_at=run_start,
            completed_at=local_deps.clock,
            duration_seconds=duration_seconds,
            artifacts=artifacts,
            clip_count=clip_count,
            selected_frame_count=selected_frame_count,
            phase_timings=phase_timings,
            warnings=(
                preflight_warnings
                if current_preflight_warnings is None
                else list(current_preflight_warnings)
            ),
        )
        if outcome is error:
            raise
        raise outcome from None
