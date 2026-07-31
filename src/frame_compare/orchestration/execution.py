"""Orchestration execution phases and runner mappings."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader

import httpx

from frame_compare.analysis.metrics import ANALYZE_PROGRESS_TOTAL
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.analysis_policy import needs_analysis
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution_types import (
    ConfirmSlowpicsUploadPhaseOutput,
    ExecutionPhasePlan,
    ExecutionState,
    MetadataPrefetch,
    PhaseOutput,
    PostReportCleanupPhaseOutput,
    PrepState,
    PublishPhaseOutput,
    ReportPhaseOutput,
)
from frame_compare.orchestration.phase_output_application import apply_phase_output
from frame_compare.orchestration.phase_post_render import (
    run_confirm_slowpics_upload_phase,
    run_metadata_phase,
    run_post_report_cleanup_phase,
    run_publish_phase,
    run_report_phase,
)
from frame_compare.orchestration.phase_selection import (
    run_analyze_phase,
    select_initial_frame_plan,
    selection_label_for_frame,
)
from frame_compare.orchestration.phase_tasks import (
    run_align_phase,
    run_render_phase,
)
from frame_compare.orchestration.phases import Phase
from frame_compare.orchestration.types import (
    RunDependencies,
    RunRequest,
    SlowpicsUploadConfirmationFn,
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
    monotonic_timer: Callable[[], float],
    phase_timings: dict[str, float],
    warnings: list[str],
    *,
    warn_only: bool = False,
    progress_total: int = 1,
) -> Phase:
    async def _execute(ctx: RunContext) -> None:
        start = monotonic_timer()
        try:
            maybe_awaitable = executor(ctx)
            if inspect.isawaitable(maybe_awaitable):
                output = await maybe_awaitable
            else:
                output = maybe_awaitable
            apply_phase_output(ctx=ctx, state=state, output=output)
        except Exception as exc:
            if warn_only:
                warnings.append(f"{name}: {exc}")
                raise
            raise
        finally:
            phase_timings[timing_key] = max(0.0, monotonic_timer() - start)

    return Phase(
        name=name,
        execute=_execute,
        skip_condition=skip_condition,
        progress_total=progress_total,
        warn_only=warn_only,
    )


def build_phases_before_align(
    *,
    request: RunRequest,
    monotonic_timer: Callable[[], float],
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
            monotonic_timer=monotonic_timer,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
        ),
        _create_timed_phase(
            "analyze",
            "analyze",
            lambda config: request.skip_analysis or not needs_analysis(config.analysis),
            partial(
                run_analyze_phase,
                input_videos=input_videos,
                workspace=workspace,
                require_cache_only=request.from_cache_only,
                vs_loader=vs_loader,
            ),
            state=state,
            monotonic_timer=monotonic_timer,
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
            monotonic_timer=monotonic_timer,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
            progress_total=max(1, len(input_videos)),
        ),
    ]


def build_phases_after_align(
    *,
    request: RunRequest,
    monotonic_timer: Callable[[], float],
    ffmpeg_runner: FFmpegRunner,
    http_client: httpx.AsyncClient | None,
    state: ExecutionState,
    metadata_prefetch: MetadataPrefetch,
    config: ConfigSchema,
    confirm_slowpics_upload: SlowpicsUploadConfirmationFn | None = None,
) -> list[Phase]:
    async def _run_publish_with_current_artifacts(ctx: RunContext) -> PublishPhaseOutput:
        if (
            _requires_report_confirmed_slowpics(ctx.config)
            and state.artifacts.slowpics_upload_confirmation_status != "confirmed"
        ):
            return PublishPhaseOutput(slowpics_url=None)
        return await run_publish_phase(
            ctx,
            client=http_client,
            metadata=state.artifacts.resolved_metadata,
            render=state.artifacts.render,
            selected_frames=state.selected_frames,
        )

    def _run_report_with_current_artifacts(ctx: RunContext) -> ReportPhaseOutput:
        return run_report_phase(
            ctx,
            frames=state.selected_frames,
            render=state.artifacts.render,
            metadata=state.artifacts.resolved_metadata,
            slowpics_url=None
            if _requires_report_confirmed_slowpics(ctx.config)
            else state.artifacts.slowpics_url,
        )

    def _run_confirm_slowpics_upload_with_current_artifacts(
        ctx: RunContext,
    ) -> ConfirmSlowpicsUploadPhaseOutput:
        return run_confirm_slowpics_upload_phase(
            ctx,
            report_path=state.artifacts.report_path,
            report_succeeded=state.artifacts.report_succeeded,
            confirm_slowpics_upload=confirm_slowpics_upload,
        )

    def _run_post_report_cleanup_with_current_artifacts(
        ctx: RunContext,
    ) -> PostReportCleanupPhaseOutput:
        return run_post_report_cleanup_phase(
            ctx,
            uploaded_file_paths=state.artifacts.uploaded_slowpics_file_paths,
            report_succeeded=state.artifacts.report_succeeded,
        )

    render_metadata_phases = [
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
            monotonic_timer=monotonic_timer,
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
            monotonic_timer=monotonic_timer,
            phase_timings=state.phase_timings,
            warnings=state.warnings,
            warn_only=True,
        ),
    ]
    publish_phase = _create_timed_phase(
        "publish",
        "publish",
        lambda config: not config.slowpics.auto_upload,
        _run_publish_with_current_artifacts,
        state=state,
        monotonic_timer=monotonic_timer,
        phase_timings=state.phase_timings,
        warnings=state.warnings,
        warn_only=True,
    )
    report_phase = _create_timed_phase(
        "report",
        "report",
        lambda config: not config.report.enable,
        _run_report_with_current_artifacts,
        state=state,
        monotonic_timer=monotonic_timer,
        phase_timings=state.phase_timings,
        warnings=state.warnings,
        warn_only=True,
    )
    confirm_slowpics_upload_phase = _create_timed_phase(
        "confirm_slowpics_upload",
        "confirm_slowpics_upload",
        None,
        _run_confirm_slowpics_upload_with_current_artifacts,
        state=state,
        monotonic_timer=monotonic_timer,
        phase_timings=state.phase_timings,
        warnings=state.warnings,
    )
    post_report_cleanup_phase = _create_timed_phase(
        "post_report_cleanup",
        "post_report_cleanup",
        None,
        _run_post_report_cleanup_with_current_artifacts,
        state=state,
        monotonic_timer=monotonic_timer,
        phase_timings=state.phase_timings,
        warnings=state.warnings,
    )
    if not _requires_report_confirmed_slowpics(config):
        return [
            *render_metadata_phases,
            publish_phase,
            report_phase,
            post_report_cleanup_phase,
        ]

    return [
        *render_metadata_phases,
        report_phase,
        confirm_slowpics_upload_phase,
        publish_phase,
        post_report_cleanup_phase,
    ]


def _requires_report_confirmed_slowpics(config: ConfigSchema) -> bool:
    return config.slowpics.auto_upload and config.slowpics.confirm_upload_after_report


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
        monotonic_timer=deps.monotonic_timer,
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
        monotonic_timer=deps.monotonic_timer,
        ffmpeg_runner=ffmpeg_runner,
        http_client=deps.http_client,
        state=state,
        metadata_prefetch=prep.metadata_prefetch,
        config=prep.config,
        confirm_slowpics_upload=deps.confirm_slowpics_upload,
    )
    return ExecutionPhasePlan(
        before_align=before_align,
        after_align=after_align,
    )
