"""Orchestration execution phases and runner mappings."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader

import httpx

from frame_compare.analysis.metrics import ANALYZE_PROGRESS_TOTAL
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.phase_tasks import (
    record_dovi_not_implemented_warning,
    run_align_phase,
    run_analyze_phase,
    run_metadata_phase,
    run_publish_phase,
    run_render_phase,
    run_report_phase,
    select_initial_frame_plan,
    selection_label_for_frame,
)
from frame_compare.orchestration.phases import Phase
from frame_compare.orchestration.types import (
    AlignPhaseOutput,
    AnalyzePhaseOutput,
    DoviPhaseOutput,
    ExecutionPhasePlan,
    ExecutionState,
    FramePlanPhaseOutput,
    MetadataPhaseOutput,
    MetadataPrefetch,
    PhaseOutput,
    PrepState,
    PublishPhaseOutput,
    RenderPhaseOutput,
    ReportPhaseOutput,
    RunDependencies,
    RunRequest,
)
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.utils.types import WorkspacePaths

__all__ = [
    "build_execution_phase_plan",
    "build_phases_after_align",
    "build_phases_before_align",
    "run_render_phase",
    "selection_label_for_frame",
]


def _create_timed_phase(
    name: str,
    timing_key: str,
    skip_condition: Callable[[ConfigSchema], bool] | None,
    executor: Callable[[RunContext], PhaseOutput | Awaitable[PhaseOutput]],
    state: ExecutionState,
    clock: Callable[[], datetime],
    phase_timings: dict[str, float],
    warnings: list[str],
    *,
    warn_only: bool = False,
    progress_total: int = 1,
) -> Phase:
    async def _execute(ctx: RunContext) -> None:
        start = clock()
        try:
            maybe_awaitable = executor(ctx)
            if inspect.isawaitable(maybe_awaitable):
                output = await maybe_awaitable
            else:
                output = maybe_awaitable
            _apply_phase_output(ctx=ctx, state=state, output=output)
        except Exception as exc:
            if warn_only:
                warnings.append(f"{name}: {exc}")
                raise
            raise
        finally:
            end = clock()
            phase_timings[timing_key] = (end - start).total_seconds()

    return Phase(
        name=name,
        execute=_execute,
        skip_condition=skip_condition,
        progress_total=progress_total,
        warn_only=warn_only,
    )


def _apply_phase_output(*, ctx: RunContext, state: ExecutionState, output: PhaseOutput) -> None:
    if isinstance(output, FramePlanPhaseOutput):
        state.selected_frames[:] = output.selected_frames
    elif isinstance(output, AnalyzePhaseOutput):
        state.selected_frames[:] = output.selected_frames
        state.artifacts.metrics_cache_hit = output.metrics_cache_hit
        ctx.selection_breakdown = output.selection_breakdown
    elif isinstance(output, AlignPhaseOutput):
        ctx.reference = output.reference
        ctx.comparisons = output.comparisons
        state.selected_frames[:] = output.selected_frames
    elif isinstance(output, RenderPhaseOutput):
        state.artifacts.render = output.render
    elif isinstance(output, MetadataPhaseOutput):
        state.artifacts.resolved_metadata = output.resolved_metadata
    elif isinstance(output, DoviPhaseOutput):
        state.warnings.append(output.warning)
    elif isinstance(output, PublishPhaseOutput):
        state.artifacts.slowpics_url = output.slowpics_url
    else:
        state.artifacts.report_path = output.report_path


def build_phases_before_align(
    *,
    request: RunRequest,
    clock: Callable[[], datetime],
    state: ExecutionState,
    input_videos: list[Path],
    workspace: WorkspacePaths,
    vs_loader: VSLoader | None = None,
) -> list[Phase]:
    return [
        _create_timed_phase(
            "frame_plan",
            "frame_plan",
            None,
            select_initial_frame_plan,
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
        ),
        _create_timed_phase(
            "analyze",
            "analyze",
            lambda config: request.skip_analysis,
            partial(
                run_analyze_phase,
                input_videos=input_videos,
                workspace=workspace,
                vs_loader=vs_loader,
            ),
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
            progress_total=ANALYZE_PROGRESS_TOTAL,
        ),
        _create_timed_phase(
            "align",
            "align",
            lambda config: not config.audio_alignment.enable,
            partial(run_align_phase, selected_frames=state.selected_frames),
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
        ),
    ]


def build_phases_after_align(
    *,
    request: RunRequest,
    clock: Callable[[], datetime],
    ffmpeg_runner: FFmpegRunner,
    http_client: httpx.AsyncClient | None,
    state: ExecutionState,
    metadata_prefetch: MetadataPrefetch,
) -> list[Phase]:
    async def _run_publish_with_current_artifacts(ctx: RunContext) -> PublishPhaseOutput:
        return await run_publish_phase(
            ctx,
            client=http_client,
            metadata=state.artifacts.resolved_metadata,
        )

    def _run_report_with_current_artifacts(ctx: RunContext) -> ReportPhaseOutput:
        return run_report_phase(
            ctx,
            frames=state.selected_frames,
            render=state.artifacts.render,
            metadata=state.artifacts.resolved_metadata,
            slowpics_url=state.artifacts.slowpics_url,
        )

    return [
        _create_timed_phase(
            "render",
            "render",
            None,
            partial(
                run_render_phase,
                frames=state.selected_frames,
                runner=ffmpeg_runner,
            ),
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
        ),
        _create_timed_phase(
            "metadata",
            "metadata",
            lambda config: request.skip_metadata,
            partial(
                run_metadata_phase,
                client=http_client,
                metadata_prefetch=metadata_prefetch,
            ),
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
        ),
        _create_timed_phase(
            "dovi",
            "dovi",
            lambda config: request.skip_dovi,
            record_dovi_not_implemented_warning,
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
        ),
        _create_timed_phase(
            "publish",
            "publish",
            lambda config: not config.slowpics.auto_upload,
            _run_publish_with_current_artifacts,
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
        ),
        _create_timed_phase(
            "report",
            "report",
            lambda config: not config.report.enable,
            _run_report_with_current_artifacts,
            state=state,
            clock=clock,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
        ),
    ]


def build_execution_phase_plan(
    *,
    request: RunRequest,
    deps: RunDependencies,
    prep: PrepState,
    state: ExecutionState,
) -> ExecutionPhasePlan:
    """Build the split execution plan around the post-align reporting boundary.

    The before/after align split is intentional: coordinator emits the
    consolidated FPS report after align completes and before render starts.
    """
    before_align = build_phases_before_align(
        request=request,
        clock=deps.clock,
        state=state,
        input_videos=prep.input_videos,
        workspace=prep.workspace,
        vs_loader=deps.vs_loader,
    )

    ffmpeg_runner = deps.ffmpeg_runner
    if ffmpeg_runner is None:
        raise RuntimeError("FFmpeg runner must be initialized before execution.")

    after_align = build_phases_after_align(
        request=request,
        clock=deps.clock,
        ffmpeg_runner=ffmpeg_runner,
        http_client=deps.http_client,
        state=state,
        metadata_prefetch=prep.metadata_prefetch,
    )
    return ExecutionPhasePlan(
        before_align=before_align,
        after_align=after_align,
    )
