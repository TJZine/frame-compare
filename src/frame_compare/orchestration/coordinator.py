"""Run coordination composition root for Frame Compare."""

from __future__ import annotations

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
from frame_compare.orchestration.selection_report import emit_final_selection_report
from frame_compare.orchestration.types import (
    RunDependencies,
    RunRequest,
    RunResult,
)
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
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
    if deps is None:
        local_deps = RunDependencies()
    else:
        local_deps = RunDependencies(
            vs_loader=deps.vs_loader,
            ffmpeg_runner=deps.ffmpeg_runner,
            http_client=deps.http_client,
            progress=deps.progress,
            confirm_slowpics_upload=deps.confirm_slowpics_upload,
            clock=deps.clock,
        )

    if local_deps.vs_loader is None:
        local_deps.vs_loader = DefaultVSLoader()

    if local_deps.progress is None:
        local_deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
            no_color=request.no_color,
        )

    async def _execute_with_deps() -> RunResult:
        run_start = local_deps.clock()
        reporter = local_deps.progress
        if reporter is None:
            raise RuntimeError("Progress reporter must be initialized before execution.")

        prep = await execute_prep(request, local_deps)
        if local_deps.ffmpeg_runner is None:
            local_deps.ffmpeg_runner = DefaultFFmpegRunner(
                extraction_timeout_seconds=prep.config.screenshots.ffmpeg_timeout_seconds
            )
        state = ExecutionState(artifacts=prep.artifacts)

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
        load_sources_end = local_deps.clock()
        state.phase_timings["load_sources"] = (
            load_sources_end - prep.load_sources_start
        ).total_seconds()

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
        run_end = local_deps.clock()
        duration_seconds = (run_end - run_start).total_seconds()

        return _assemble_run_result(
            artifacts=prep.artifacts,
            selected_frames=state.selected_frames,
            context=context,
            preflight_warnings=prep.preflight_warnings,
            phase_timings=state.phase_timings,
            duration_seconds=duration_seconds,
        )

    if local_deps.http_client is not None:
        return await _execute_with_deps()

    async with httpx.AsyncClient() as http_client:
        local_deps.http_client = http_client
        try:
            return await _execute_with_deps()
        finally:
            local_deps.http_client = None
