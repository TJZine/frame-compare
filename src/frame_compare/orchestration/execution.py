"""Orchestration execution phases and runner mappings."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from pathlib import Path

import httpx

from frame_compare.analysis import ANALYZE_PROGRESS_TOTAL
from frame_compare.config import ConfigSchema
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
    RunArtifacts,
    RunRequest,
)
from frame_compare.render.ffmpeg import FFmpegRunner
from frame_compare.utils.types import WorkspacePaths

__all__ = [
    "build_phases_after_align",
    "build_phases_before_align",
    "run_render_phase",
    "selection_label_for_frame",
]


def _create_timed_phase(
    name: str,
    timing_key: str,
    skip_condition: Callable[[ConfigSchema], bool] | None,
    executor: Callable[[RunContext], None | Awaitable[None]],
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
                await maybe_awaitable
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


def build_phases_before_align(
    *,
    request: RunRequest,
    clock: Callable[[], datetime],
    phase_timings: dict[str, float],
    warnings: list[str],
    selected_frames: list[int],
    input_videos: list[Path],
    workspace: WorkspacePaths,
    artifacts: RunArtifacts,
) -> list[Phase]:
    return [
        _create_timed_phase(
            "frame_plan",
            "frame_plan",
            None,
            partial(select_initial_frame_plan, selected_frames=selected_frames),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
        ),
        _create_timed_phase(
            "analyze",
            "analyze",
            lambda config: request.skip_analysis,
            partial(
                run_analyze_phase,
                input_videos=input_videos,
                workspace=workspace,
                selected_frames=selected_frames,
                artifacts=artifacts,
            ),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
            warn_only=True,
            progress_total=ANALYZE_PROGRESS_TOTAL,
        ),
        _create_timed_phase(
            "align",
            "align",
            lambda config: not config.audio_alignment.enable,
            partial(run_align_phase, selected_frames=selected_frames),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
            warn_only=True,
            progress_total=max(1, len(input_videos) - 1),
        ),
    ]


def build_phases_after_align(
    *,
    request: RunRequest,
    clock: Callable[[], datetime],
    ffmpeg_runner: FFmpegRunner,
    http_client: httpx.AsyncClient | None,
    phase_timings: dict[str, float],
    warnings: list[str],
    selected_frames: list[int],
    artifacts: RunArtifacts,
    metadata_prefetched: bool,
) -> list[Phase]:
    return [
        _create_timed_phase(
            "render",
            "render",
            None,
            partial(
                run_render_phase,
                frames=selected_frames,
                runner=ffmpeg_runner,
                artifacts=artifacts,
            ),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
        ),
        _create_timed_phase(
            "metadata",
            "metadata",
            lambda config: request.skip_metadata,
            partial(
                run_metadata_phase,
                client=http_client,
                prefetched_metadata=artifacts.resolved_metadata,
                metadata_prefetched=metadata_prefetched,
                artifacts=artifacts,
            ),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
            warn_only=True,
        ),
        _create_timed_phase(
            "dovi",
            "dovi",
            lambda config: request.skip_dovi,
            partial(record_dovi_not_implemented_warning, warnings=warnings),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
            warn_only=True,
        ),
        _create_timed_phase(
            "publish",
            "publish",
            lambda config: not config.slowpics.auto_upload,
            partial(
                run_publish_phase,
                client=http_client,
                artifacts=artifacts,
            ),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
            warn_only=True,
        ),
        _create_timed_phase(
            "report",
            "report",
            lambda config: not config.report.enable,
            partial(
                run_report_phase,
                frames=selected_frames,
                artifacts=artifacts,
            ),
            clock=clock,
            phase_timings=phase_timings,
            warnings=warnings,
            warn_only=True,
        ),
    ]
