"""Run coordination composition root for Frame Compare."""

from __future__ import annotations

import httpx

from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution import (
    build_phases_after_align,
    build_phases_before_align,
)
from frame_compare.orchestration.fps_report import (
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)
from frame_compare.orchestration.phases import execute_phases
from frame_compare.orchestration.preparation import execute_prep
from frame_compare.orchestration.progress import select_reporter
from frame_compare.orchestration.types import (
    RunArtifacts,
    RunDependencies,
    RunRequest,
    RunResult,
)
from frame_compare.render.ffmpeg import DefaultFFmpegRunner
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
        screenshot_dir=artifacts.screenshot_dir,
        slowpics_url=artifacts.slowpics_url,
        report_path=artifacts.report_path,
        frame_count=len(selected_frames),
        clips_processed=1 + len(context.comparisons),
        duration_seconds=duration_seconds,
        cache_hit=artifacts.metrics_cache_hit,
        phase_timings=phase_timings,
        warnings=[*preflight_warnings, *sorted(artifacts.warnings)],
    )


async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult:
    """Execute a run request asynchronously.

    Raises:
        FrameCompareError: Any preflight validation errors are propagated.
    """
    if deps is None:
        deps = RunDependencies()

    if deps.vs_loader is None:
        deps.vs_loader = DefaultVSLoader()

    if deps.ffmpeg_runner is None:
        deps.ffmpeg_runner = DefaultFFmpegRunner()

    if deps.progress is None:
        deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
            no_color=request.no_color,
        )

    async def _execute_with_deps() -> RunResult:
        run_start = deps.clock()
        phase_timings: dict[str, float] = {}
        reporter = deps.progress
        if reporter is None:
            raise RuntimeError("Progress reporter must be initialized before execution.")

        prep = await execute_prep(request, deps)

        phase_timings["preflight"] = prep.preflight_duration

        reference = prep.clips[0]
        comparisons = prep.clips[1:]

        context = RunContext(
            config=prep.config,
            workspace=prep.workspace,
            reference=reference,
            comparisons=comparisons,
            reporter=reporter,
        )
        emit_consolidated_fps_report(
            stage="after_load_sources",
            clips=build_consolidated_fps_report(reference, comparisons),
            json_output=request.json_output,
            quiet=request.quiet,
        )
        load_sources_end = deps.clock()
        phase_timings["load_sources"] = (load_sources_end - prep.load_sources_start).total_seconds()

        phase_timings.update(
            {
                "frame_plan": 0.0,
                "analyze": 0.0,
                "align": 0.0,
                "render": 0.0,
                "metadata": 0.0,
                "dovi": 0.0,
                "publish": 0.0,
                "report": 0.0,
            }
        )
        selected_frames: list[int] = []

        phases_before_align = build_phases_before_align(
            request=request,
            clock=deps.clock,
            phase_timings=phase_timings,
            warnings=prep.artifacts.warnings,
            selected_frames=selected_frames,
            input_videos=prep.input_videos,
            workspace=prep.workspace,
            artifacts=prep.artifacts,
        )

        if deps.ffmpeg_runner is None:
            raise RuntimeError("FFmpeg runner must be initialized before execution.")
        phases_after_align = build_phases_after_align(
            request=request,
            clock=deps.clock,
            ffmpeg_runner=deps.ffmpeg_runner,
            http_client=deps.http_client,
            phase_timings=phase_timings,
            warnings=prep.artifacts.warnings,
            selected_frames=selected_frames,
            artifacts=prep.artifacts,
            metadata_prefetched=prep.metadata_prefetched,
        )

        await execute_phases(phases_before_align, context, reporter)
        emit_consolidated_fps_report(
            stage="after_align",
            clips=build_consolidated_fps_report(context.reference, context.comparisons),
            json_output=request.json_output,
            quiet=request.quiet,
        )
        await execute_phases(phases_after_align, context, reporter)
        run_end = deps.clock()
        duration_seconds = (run_end - run_start).total_seconds()

        return _assemble_run_result(
            artifacts=prep.artifacts,
            selected_frames=selected_frames,
            context=context,
            preflight_warnings=prep.preflight_warnings,
            phase_timings=phase_timings,
            duration_seconds=duration_seconds,
        )

    if deps.http_client is not None:
        return await _execute_with_deps()

    async with httpx.AsyncClient() as http_client:
        deps.http_client = http_client
        try:
            return await _execute_with_deps()
        finally:
            deps.http_client = None
