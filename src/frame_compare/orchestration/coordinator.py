"""Run coordination composition root for Frame Compare."""

from __future__ import annotations

from datetime import datetime

import httpx

from frame_compare.orchestration.alignment_report import (
    build_frame_alignment_report,
    emit_frame_alignment_report,
)
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution import (
    build_execution_phase_plan,
)
from frame_compare.orchestration.execution_types import (
    ExecutionState,
    RunArtifacts,
)
from frame_compare.orchestration.fps_report import (
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)
from frame_compare.orchestration.phases import execute_phases
from frame_compare.orchestration.preparation import execute_prep
from frame_compare.orchestration.progress import select_reporter
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
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.loader import DefaultVSLoader

__all__ = ["RunDependencies", "RunRequest", "RunResult", "execute_run"]


def _assemble_run_result(
    *,
    artifacts: RunArtifacts,
    selected_frames: list[int],
    context: RunContext,
    preflight_warnings: list[str],
    phase_timings: dict[str, float],
    duration_seconds: float,
) -> RunResult:
    """Helper to assemble a RunResult from collected state."""
    return RunResult(
        success=True,
        screenshot_dir=None if artifacts.render is None else artifacts.render.screenshot_dir,
        slowpics_url=artifacts.slowpics_url,
        report_path=artifacts.report_path,
        post_upload_actions=artifacts.post_upload_actions,
        slowpics_upload_confirmation_status=artifacts.slowpics_upload_confirmation_status,
        frame_count=len(selected_frames),
        clips_processed=1 + len(context.comparisons),
        duration_seconds=duration_seconds,
        cache_hit=artifacts.metrics_cache_hit,
        metrics_cache_status=artifacts.metrics_cache_status,
        phase_timings=phase_timings,
        warnings=[*preflight_warnings, *sorted(artifacts.warnings)],
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
    preflight_warnings: tuple[str, ...] = ()
    current_preflight_warnings: list[str] | None = None

    def _capture_reserved_run(capture: ReservedRunCapture) -> None:
        nonlocal artifacts, clip_count, phase_timings, preflight_warnings, reserved_workspace
        reserved_workspace = capture.workspace
        clip_count = capture.clip_count
        phase_timings = {"preflight": capture.preflight_duration}
        preflight_warnings = capture.preflight_warnings
        artifacts = RunArtifacts(warnings=capture.run_warnings)

    if deps is None:
        local_deps = RunDependencies()
    else:
        local_deps = RunDependencies(
            vs_loader=deps.vs_loader,
            ffmpeg_runner=deps.ffmpeg_runner,
            http_client=deps.http_client,
            progress=deps.progress,
            confirm_slowpics_upload=deps.confirm_slowpics_upload,
            confirm_full_window_retry=deps.confirm_full_window_retry,
            clock=deps.clock,
            monotonic_timer=deps.monotonic_timer,
        )

    local_deps.capture_reserved_run = _capture_reserved_run

    if request.json_output or request.quiet or request.from_cache_only or request.skip_analysis:
        local_deps.confirm_full_window_retry = None

    if local_deps.vs_loader is None:
        local_deps.vs_loader = DefaultVSLoader()

    if local_deps.progress is None:
        local_deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
            no_color=request.no_color,
        )

    async def _execute_with_deps() -> RunResult:
        nonlocal artifacts, clip_count, phase_timings, preflight_warnings, run_start
        nonlocal current_preflight_warnings
        nonlocal run_timer_start
        nonlocal selected_frame_count
        run_start = local_deps.clock()
        run_timer_start = local_deps.monotonic_timer()
        reporter = local_deps.progress
        if reporter is None:
            raise RuntimeError("Progress reporter must be initialized before execution.")

        prep = await execute_prep(request, local_deps)
        if local_deps.ffmpeg_runner is None:
            local_deps.ffmpeg_runner = DefaultFFmpegRunner(
                extraction_timeout_seconds=prep.config.screenshots.ffmpeg_timeout_seconds
            )
        state = ExecutionState(artifacts=prep.artifacts)
        artifacts = prep.artifacts
        phase_timings = state.phase_timings
        clip_count = len(prep.clips)
        preflight_warnings = tuple(prep.preflight_warnings)
        current_preflight_warnings = prep.preflight_warnings

        state.phase_timings["preflight"] = prep.preflight_duration

        reference = prep.clips[0]
        comparisons = prep.clips[1:]

        context = RunContext(
            config=prep.config,
            workspace=prep.workspace,
            reference=reference,
            comparisons=comparisons,
            analysis_selection_domain=prep.analysis_selection_domain,
            analysis_clip=prep.analysis_clip,
            selection_window=prep.selection_window,
            reporter=reporter,
            confirm_full_window_retry=local_deps.confirm_full_window_retry,
            full_window_retry_override=prep.full_window_retry_override,
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
            no_color=request.no_color,
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

        phase_plan = build_execution_phase_plan(
            request=request,
            deps=local_deps,
            prep=prep,
            state=state,
        )

        await execute_phases(phase_plan.before_align, context, reporter)
        selected_frame_count = len(state.selected_frames)
        emit_final_selection_report(
            selected_frames=state.selected_frames,
            breakdown=context.selection_breakdown,
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
            no_color=request.no_color,
        )
        emit_frame_alignment_report(
            stage="after_align",
            comparisons=build_frame_alignment_report(
                reference=context.reference,
                comparisons=context.comparisons,
            ),
            selected_frames=state.selected_frames,
            alignment_warnings=[
                warning for warning in state.warnings if warning.startswith("align:")
            ],
            json_output=request.json_output,
            quiet=request.quiet,
            no_color=request.no_color,
        )
        await execute_phases(phase_plan.after_align, context, reporter)
        duration_seconds = max(0.0, local_deps.monotonic_timer() - run_timer_start)
        run_end = local_deps.clock()
        result = _assemble_run_result(
            artifacts=prep.artifacts,
            selected_frames=state.selected_frames,
            context=context,
            preflight_warnings=prep.preflight_warnings,
            phase_timings=state.phase_timings,
            duration_seconds=duration_seconds,
        )
        return record_completed_run_result(
            workspace=reserved_workspace,
            result=result,
            started_at=run_start,
            completed_at=run_end,
        )

    async def _execute_and_record_failure() -> RunResult:
        try:
            return await _execute_with_deps()
        except BaseException as original_error:
            duration_seconds = (
                0.0
                if run_timer_start is None
                else max(0.0, local_deps.monotonic_timer() - run_timer_start)
            )
            record_failed_run_best_effort(
                workspace=reserved_workspace,
                error=original_error,
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
                    else tuple(current_preflight_warnings)
                ),
            )
            raise

    if local_deps.http_client is not None:
        return await _execute_and_record_failure()

    async with httpx.AsyncClient() as http_client:
        local_deps.http_client = http_client
        try:
            return await _execute_and_record_failure()
        finally:
            local_deps.http_client = None
