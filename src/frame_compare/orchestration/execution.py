"""Run the fixed selection and output steps."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast, overload

import structlog

from frame_compare.analysis.errors import ExclusionRecoverySelectionError
from frame_compare.analysis.metrics import ANALYZE_PROGRESS_TOTAL
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.analysis_policy import needs_analysis
from frame_compare.orchestration.context import RunContext, SelectionSnapshot
from frame_compare.orchestration.execution_types import AlignPhaseOutput, ExecutionState, PrepState
from frame_compare.orchestration.phase_alignment import run_align_phase
from frame_compare.orchestration.phase_post_render import (
    run_confirm_slowpics_upload_phase,
    run_metadata_phase,
    run_post_report_cleanup_phase,
    run_publish_phase,
    run_report_phase,
)
from frame_compare.orchestration.phase_render import run_render_phase
from frame_compare.orchestration.phase_selection import (
    run_analyze_phase,
    select_initial_frame_plan,
    selection_label_for_frame,
)
from frame_compare.orchestration.progress import (
    phase_display_label,
    rich_phase_label,
    start_phase_progress,
    uses_rich_progress,
)
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.services.errors import AudioAlignmentCleanupError
from frame_compare.utils.cancellation import (
    cancellation_checkpoint,
    is_cancelling,
    raise_if_cancelling,
)
from frame_compare.utils.progress import LogProgressReporter, align_phase_duration_text
from frame_compare.utils.progress_protocol import (
    AlignmentSummary,
    ProgressPhaseStatus,
    ProgressReporter,
)
from frame_compare.utils.run_warnings import RunWarning, WarningSource

__all__ = [
    "RunSteps",
    "StepCompletion",
    "progress_step_names",
    "run_output_steps",
    "run_render_phase",
    "run_selection_steps",
    "selection_label_for_frame",
]

log = structlog.get_logger()


@dataclass
class StepCompletion:
    """Optional details for a successful step's progress line."""

    summary: str | None = None
    retain: bool | None = None
    alignment_summary: AlignmentSummary | None = None
    duration_text: str | None = None
    success_status: ProgressPhaseStatus | None = None


class RunSteps:
    """Progress, timing and warn-only handling for the run's fixed steps."""

    def __init__(
        self,
        *,
        reporter: ProgressReporter,
        state: ExecutionState,
        monotonic_timer: Callable[[], float],
    ) -> None:
        self._reporter = reporter
        self._state = state
        self._monotonic_timer = monotonic_timer

    async def skip(self, name: str, *, detail: str | None, total: int = 1) -> None:
        await cancellation_checkpoint()
        label = phase_display_label(name)
        start_phase_progress(
            self._reporter,
            name=name,
            display_label=label if detail is None else f"{label}  {detail}",
            total=total,
        )
        self._reporter.set_description("Skipped")
        summary = detail[:1].lower() + detail[1:] if detail else detail
        self._reporter.complete_phase(ProgressPhaseStatus.SKIPPED, summary=summary)

    @overload
    async def run[T](
        self,
        name: str,
        call: Callable[[], T | Awaitable[T]],
        *,
        warning_source: WarningSource,
        warn_only: Literal[False] = False,
        fatal: tuple[type[BaseException], ...] = (),
        total: int = 1,
        retain: bool | None = None,
        describe: Callable[[T, float], StepCompletion] | None = None,
    ) -> T: ...

    @overload
    async def run[T](
        self,
        name: str,
        call: Callable[[], T | Awaitable[T]],
        *,
        warning_source: WarningSource,
        warn_only: bool,
        fatal: tuple[type[BaseException], ...] = (),
        total: int = 1,
        retain: bool | None = None,
        describe: Callable[[T, float], StepCompletion] | None = None,
    ) -> T | None: ...

    async def run[T](
        self,
        name: str,
        call: Callable[[], T | Awaitable[T]],
        *,
        warning_source: WarningSource,
        warn_only: bool = False,
        fatal: tuple[type[BaseException], ...] = (),
        total: int = 1,
        retain: bool | None = None,
        describe: Callable[[T, float], StepCompletion] | None = None,
    ) -> T | None:
        await cancellation_checkpoint()
        reporter = self._reporter
        start_phase_progress(
            reporter, name=name, display_label=phase_display_label(name), total=total
        )
        start = self._monotonic_timer()
        completion = StepCompletion()
        status = ProgressPhaseStatus.FAILED
        try:
            # Starting progress can request cancellation before the body runs.
            raise_if_cancelling()
            pending = call()
            output = (
                await cast(Awaitable[T], pending)
                if inspect.isawaitable(pending)
                else cast(T, pending)
            )
            await cancellation_checkpoint()
        except BaseException as exc:
            self._state.phase_timings[name] = max(0.0, self._monotonic_timer() - start)
            cancelling = is_cancelling()
            if warn_only and isinstance(exc, Exception) and not cancelling:
                self._state.warnings.append(RunWarning(warning_source, "warning", f"{name}: {exc}"))
            if (
                not warn_only
                or isinstance(exc, fatal)
                or cancelling
                or not isinstance(exc, Exception)
            ):
                raise
            status = ProgressPhaseStatus.WARNED
            if isinstance(reporter, LogProgressReporter):
                log.warning(
                    "phase_warned",
                    phase=name,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=exc,
                )
            return None
        else:
            elapsed = max(0.0, self._monotonic_timer() - start)
            self._state.phase_timings[name] = elapsed
            success_completion = describe(output, elapsed) if describe is not None else completion
            # The timer and description can run after the last await.
            raise_if_cancelling()
            completion = success_completion
            status = ProgressPhaseStatus.COMPLETED
            reporter.advance(1)
            return output
        finally:
            if completion.retain is not None:
                retain = completion.retain
            if uses_rich_progress(reporter):
                if (
                    status == ProgressPhaseStatus.COMPLETED
                    and completion.success_status is not None
                ):
                    status = completion.success_status
                if name == "align":
                    retain = True
            if completion.alignment_summary is not None:
                reporter.complete_phase(
                    status,
                    retain=retain,
                    summary=completion.summary,
                    duration_text=completion.duration_text,
                    alignment_summary=completion.alignment_summary,
                )
            elif retain is None:
                reporter.complete_phase(
                    status, summary=completion.summary, duration_text=completion.duration_text
                )
            else:
                reporter.complete_phase(
                    status,
                    retain=retain,
                    summary=completion.summary,
                    duration_text=completion.duration_text,
                )


def _skip_analysis(request: RunRequest, config: ConfigSchema) -> bool:
    return request.skip_analysis or not needs_analysis(config.analysis)


def _requires_report_confirmed_slowpics(config: ConfigSchema) -> bool:
    return config.slowpics.auto_upload and config.slowpics.confirm_upload_after_report


def _describe_align(output: AlignPhaseOutput, elapsed: float) -> StepCompletion:
    return StepCompletion(
        summary=output.success_summary,
        alignment_summary=output.alignment_summary,
        success_status=(
            ProgressPhaseStatus.WARNED
            if output.review_unresolved or output.has_unapplied_offsets
            else None
        ),
        duration_text=align_phase_duration_text(
            align_seconds=elapsed, review_seconds=output.review_seconds
        ),
    )


async def run_selection_steps(
    ctx: RunContext,
    steps: RunSteps,
    *,
    request: RunRequest,
    prep: PrepState,
    state: ExecutionState,
    deps: RunDependencies,
) -> None:
    frame_plan = await steps.run(
        "frame_plan",
        lambda: select_initial_frame_plan(ctx, vs_loader=deps.vs_loader),
        warning_source="frame selection",
    )
    ctx.selection = SelectionSnapshot(
        frames=tuple(frame_plan.selected_frames),
        breakdown=frame_plan.selection_breakdown,
        details_by_source_frame=frame_plan.selection_details_by_source_frame,
    )
    state.frame_plan_warnings[:] = frame_plan.warnings
    state.warnings.extend(frame_plan.warnings)

    if _skip_analysis(request, ctx.config):
        await steps.skip(
            "analyze",
            detail="Disabled" if request.skip_analysis else "Not required",
            total=ANALYZE_PROGRESS_TOTAL,
        )
    else:
        analysis = await steps.run(
            "analyze",
            lambda: run_analyze_phase(
                ctx,
                input_videos=prep.input_videos,
                workspace=prep.workspace,
                require_cache_only=request.from_cache_only,
                force_recompute=request.no_cache,
                vs_loader=deps.vs_loader,
            ),
            warning_source="analysis",
            warn_only=not request.from_cache_only and bool(ctx.selection.frames),
            fatal=(ExclusionRecoverySelectionError,),
            total=ANALYZE_PROGRESS_TOTAL,
            describe=lambda out, _: StepCompletion(summary=out.success_summary),
        )
        if analysis is not None:
            if analysis.replaces_frame_plan_selection:
                for warning in state.frame_plan_warnings:
                    if warning in state.warnings:
                        state.warnings.remove(warning)
                state.frame_plan_warnings.clear()
            state.artifacts.metrics_cache_hit = analysis.metrics_cache_hit
            state.artifacts.metrics_cache_status = "hit" if analysis.metrics_cache_hit else "miss"
            ctx.selection = SelectionSnapshot(
                frames=tuple(analysis.selected_frames),
                breakdown=analysis.selection_breakdown,
                details_by_source_frame=analysis.selection_details_by_source_frame,
                analysis_metrics=analysis.analysis_metrics,
            )
            state.warnings.extend(analysis.warnings)

    align_total = max(1, len(prep.input_videos))
    if not ctx.config.audio_alignment.enable:
        await steps.skip("align", detail="Disabled", total=align_total)
        return

    alignment = await steps.run(
        "align",
        lambda: run_align_phase(
            ctx,
            selected_frames=list(ctx.selection.frames),
            vs_loader=deps.vs_loader,
            verbose=request.verbose,
            quiet=request.quiet,
            json_output=request.json_output,
        ),
        warning_source="alignment",
        warn_only=not prep.config.audio_alignment.force_interactive,
        fatal=(ExclusionRecoverySelectionError, AudioAlignmentCleanupError),
        total=align_total,
        describe=_describe_align,
    )
    if alignment is not None:
        ctx.reference = alignment.reference
        ctx.comparisons = alignment.comparisons
        ctx.selection = replace(
            ctx.selection,
            frames=tuple(alignment.selected_frames),
            breakdown=alignment.selection_breakdown
            if alignment.selection_breakdown is not None
            else ctx.selection.breakdown,
            details_by_source_frame=alignment.selection_details_by_source_frame
            if alignment.selection_details_by_source_frame is not None
            else ctx.selection.details_by_source_frame,
        )
        state.warnings.extend(alignment.warnings)
        state.artifacts.alignment_summary = alignment.alignment_summary
        state.artifacts.alignment_diagnostics_dir = alignment.alignment_diagnostics_dir
        state.vsview_review_seconds = max(0.0, alignment.review_seconds)


async def _report(ctx: RunContext, steps: RunSteps, state: ExecutionState) -> None:
    if not ctx.config.report.enable:
        await steps.skip("report", detail="Disabled")
        return
    artifacts = state.artifacts
    report = await steps.run(
        "report",
        lambda: run_report_phase(
            ctx,
            frames=list(ctx.selection.frames),
            render=artifacts.render,
            metadata=artifacts.resolved_metadata,
            slowpics_url=None
            if _requires_report_confirmed_slowpics(ctx.config)
            else artifacts.slowpics_url,
        ),
        warning_source="render",
        warn_only=True,
    )
    if report is not None:
        artifacts.report_path = report.report_path
        artifacts.report_succeeded = report.report_succeeded


async def _publish(
    ctx: RunContext, steps: RunSteps, state: ExecutionState, deps: RunDependencies
) -> None:
    artifacts = state.artifacts
    client = deps.http_client
    confirmation = artifacts.slowpics_upload_confirmation_status
    if not ctx.config.slowpics.auto_upload:
        await steps.skip("publish", detail="Disabled")
        return
    if client is None:
        await steps.skip("publish", detail="Unavailable")
        return
    if _requires_report_confirmed_slowpics(ctx.config) and confirmation != "confirmed":
        detail = {"declined": "Declined", "report_unavailable": "Report unavailable"}.get(
            confirmation
        )
        await steps.skip("publish", detail=detail)
        return

    def on_upload_confirmed(url: str, uploaded_file_paths: tuple[Path, ...]) -> None:
        state.artifacts.slowpics_url = url
        state.artifacts.uploaded_slowpics_file_paths = uploaded_file_paths

    publish = await steps.run(
        "publish",
        lambda: run_publish_phase(
            ctx,
            client=client,
            metadata=artifacts.resolved_metadata,
            render=artifacts.render,
            selected_frames=list(ctx.selection.frames),
            on_upload_confirmed=on_upload_confirmed,
        ),
        warning_source="slow.pics",
        warn_only=True,
        describe=lambda out, _: StepCompletion(
            summary=out.success_summary, retain=out.slowpics_url is not None
        ),
    )
    if publish is not None:
        artifacts.slowpics_url = publish.slowpics_url
        artifacts.uploaded_slowpics_file_paths = publish.uploaded_file_paths
        artifacts.post_upload_actions = publish.post_upload_actions
        state.warnings.extend(publish.warnings)
        state.warnings.extend(
            action.warning for action in publish.post_upload_actions if action.warning is not None
        )


async def run_output_steps(
    ctx: RunContext,
    steps: RunSteps,
    *,
    request: RunRequest,
    prep: PrepState,
    state: ExecutionState,
    deps: RunDependencies,
) -> None:
    report_first = _requires_report_confirmed_slowpics(prep.config)
    artifacts = state.artifacts
    render = await steps.run(
        "render",
        lambda: run_render_phase(ctx, frames=list(ctx.selection.frames), vs_loader=deps.vs_loader),
        warning_source="render",
        describe=lambda out, _: StepCompletion(summary=out.success_summary),
    )
    artifacts.render = render.render
    state.warnings.extend(render.render.warnings)

    if request.skip_metadata:
        await steps.skip("metadata", detail="Disabled")
    else:
        metadata = await steps.run(
            "metadata",
            lambda: run_metadata_phase(
                ctx, client=deps.http_client, metadata_prefetch=prep.metadata_prefetch
            ),
            warning_source="sources",
            warn_only=True,
        )
        if metadata is not None:
            artifacts.resolved_metadata = metadata.resolved_metadata

    if report_first:
        await _report(ctx, steps, state)
        confirmation = await steps.run(
            "confirm_slowpics_upload",
            lambda: run_confirm_slowpics_upload_phase(
                ctx,
                report_path=artifacts.report_path,
                report_succeeded=artifacts.report_succeeded,
                confirm_slowpics_upload=deps.confirm_slowpics_upload,
            ),
            warning_source="slow.pics",
            retain=False,
        )
        artifacts.slowpics_upload_confirmation_status = confirmation.status
        state.warnings.extend(confirmation.warnings)
        await _publish(ctx, steps, state, deps)
    else:
        await _publish(ctx, steps, state, deps)
        await _report(ctx, steps, state)

    cleanup = await steps.run(
        "post_report_cleanup",
        lambda: run_post_report_cleanup_phase(
            ctx,
            uploaded_file_paths=artifacts.uploaded_slowpics_file_paths,
            report_succeeded=artifacts.report_succeeded,
        ),
        warning_source="cleanup",
    )
    state.warnings.extend(cleanup.warnings)


def progress_step_names(request: RunRequest, config: ConfigSchema) -> list[str]:
    names: list[str] = []
    if not _skip_analysis(request, config):
        names.append("analyze")
    if config.audio_alignment.enable:
        names.append("align")
    names.append("render")
    # Confirmation or client availability can still cause Publish to be skipped.
    if config.slowpics.auto_upload and not _requires_report_confirmed_slowpics(config):
        names.append("publish")
    if config.report.enable:
        names.append("report")
    if _requires_report_confirmed_slowpics(config):
        names.append("publish")
    return [rich_phase_label(name) for name in names]
