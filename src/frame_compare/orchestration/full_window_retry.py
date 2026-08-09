"""Run-only recovery from exclusion-constrained selection failures."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

from frame_compare.analysis.errors import (
    ExclusionRecoverySelectionError,
    MetricsCalculationError,
    SelectionError,
)
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.orchestration.active_rect import propagate_resolved_aspect_ratio_evidence
from frame_compare.orchestration.active_rect_content import (
    ActiveRectContentDetectionError,
    VSActiveRectFrameSampler,
    refine_auto_content_active_rects_for_clips,
)
from frame_compare.orchestration.selection_domain import (
    build_analysis_selection_domain_token,
    compute_selection_window_for_clips,
)
from frame_compare.orchestration.types import FullWindowRetryConfirmationRequest

if TYPE_CHECKING:
    from frame_compare.orchestration.context import ClipState, RunContext
    from frame_compare.orchestration.types import FullWindowRetryConfirmationFn
    from frame_compare.vs.loader import VSLoader

_FULL_WINDOW_RETRY_WARNING = (
    "analysis: configured lead/trail exclusions were disabled for this run only; "
    "the authored configuration was not changed"
)
_RECOVERY_HINT = (
    "Reduce analysis.ignore_lead_seconds/ignore_trail_seconds or use a clip-specific "
    "config with smaller exclusions"
)
_RETRY_FAILED_HINT = (
    "Reduce selector counts, use a longer clip, or use a clip-specific config with "
    "smaller analysis exclusions"
)
_ELIGIBLE_REASONS = {
    "insufficient_candidates",
    "insufficient random candidates after user frames",
    "no selectable user or random frames remain after trims/windowing",
}
_EMPTY_EXCLUSION_WINDOW_REASON = "analysis ignore windows leave no selectable frames"


@dataclass(frozen=True, slots=True)
class FullWindowRetryOverride:
    """Evidence that authored exclusions were replaced only in the effective run config."""

    ignore_lead_seconds: float
    ignore_trail_seconds: float


@dataclass(frozen=True, slots=True)
class FullWindowSelectionState:
    """Prepared selection-window state after an optional accepted recovery."""

    config: ConfigSchema
    selection_window: SelectionWindow
    override: FullWindowRetryOverride | None = None
    warnings: tuple[str, ...] = ()


def compute_selection_window_with_recovery(
    *,
    clips: list[ClipState],
    config: ConfigSchema,
    confirm: FullWindowRetryConfirmationFn | None,
    warning_sink: list[str] | None = None,
) -> FullWindowSelectionState:
    """Compute the authoritative window and recover when exclusions remove it entirely."""
    try:
        selection_window = compute_selection_window_for_clips(clips=clips, config=config)
    except SelectionError as error:
        analysis = config.analysis
        if error.reason != _EMPTY_EXCLUSION_WINDOW_REASON or (
            analysis.ignore_lead_seconds <= 0.0 and analysis.ignore_trail_seconds <= 0.0
        ):
            raise
        _require_confirmation(
            error=error,
            eligible_frame_count=0,
            config=config,
            confirm=confirm,
        )
        override_warning = _override_warning(
            analysis.ignore_lead_seconds,
            analysis.ignore_trail_seconds,
        )
        if warning_sink is not None:
            warning_sink.append(override_warning)
        effective_config = _full_window_config(config)
        try:
            selection_window = compute_selection_window_for_clips(
                clips=clips,
                config=effective_config,
            )
        except SelectionError as retry_error:
            raise _fatal_selection_error(retry_error, retry_failed=True) from retry_error
        return FullWindowSelectionState(
            config=effective_config,
            selection_window=selection_window,
            override=FullWindowRetryOverride(
                ignore_lead_seconds=analysis.ignore_lead_seconds,
                ignore_trail_seconds=analysis.ignore_trail_seconds,
            ),
            warnings=() if warning_sink is not None else (override_warning,),
        )
    return FullWindowSelectionState(config=config, selection_window=selection_window)


def recover_from_exclusion_selection_failure(
    ctx: RunContext,
    error: SelectionError,
    *,
    vs_loader: VSLoader | None,
) -> list[str]:
    """Confirm and apply one full-window retry, or raise a fatal typed selection error."""
    if ctx.full_window_retry_override is not None:
        raise _fatal_selection_error(error, retry_failed=True) from error
    if not _eligible_for_recovery(ctx.config, error):
        raise error

    analysis = ctx.config.analysis
    if ctx.reporter is None:
        _require_confirmation(
            error=error,
            eligible_frame_count=ctx.selection_window.frame_count,
            config=ctx.config,
            confirm=ctx.confirm_full_window_retry,
        )
    else:
        try:
            ctx.reporter.suspend()
        except (KeyboardInterrupt, Exception) as exc:
            raise _fatal_selection_error(error, retry_failed=False) from exc
        try:
            _require_confirmation(
                error=error,
                eligible_frame_count=ctx.selection_window.frame_count,
                config=ctx.config,
                confirm=ctx.confirm_full_window_retry,
            )
        except BaseException:
            with suppress(KeyboardInterrupt, Exception):
                ctx.reporter.resume()
            raise
        try:
            ctx.reporter.resume()
        except (KeyboardInterrupt, Exception) as exc:
            raise _fatal_selection_error(error, retry_failed=False) from exc

    override = FullWindowRetryOverride(
        ignore_lead_seconds=analysis.ignore_lead_seconds,
        ignore_trail_seconds=analysis.ignore_trail_seconds,
    )
    override_warning = _override_warning(
        override.ignore_lead_seconds,
        override.ignore_trail_seconds,
    )
    if ctx.run_warnings is not None:
        ctx.run_warnings.append(override_warning)
    try:
        active_rect_warnings = _apply_confirmed_override(
            ctx,
            override=override,
            vs_loader=vs_loader,
        )
    except ExclusionRecoverySelectionError:
        raise
    except Exception as exc:
        raise _fatal_selection_error(error, retry_failed=True) from exc
    if ctx.run_warnings is not None:
        ctx.run_warnings.extend(active_rect_warnings)
        return []
    return [override_warning, *active_rect_warnings]


def _apply_confirmed_override(
    ctx: RunContext,
    *,
    override: FullWindowRetryOverride,
    vs_loader: VSLoader | None,
) -> list[str]:
    effective_config = _full_window_config(ctx.config)
    clips, active_rect_warnings = _refine_active_rects_for_full_window(
        clips=[ctx.reference, *ctx.comparisons],
        config=effective_config,
        vs_loader=vs_loader,
    )
    analysis_source_path = None if ctx.analysis_clip is None else ctx.analysis_clip.path
    analysis_clip = next(
        (clip for clip in clips if clip.path == analysis_source_path),
        None,
    )
    selection_window = compute_selection_window_for_clips(clips=clips, config=effective_config)
    selection_domain = (
        build_analysis_selection_domain_token(
            clips=clips,
            analysis_clip=analysis_clip,
            config=effective_config,
            selection_window=selection_window,
        )
        if analysis_clip is not None
        else ""
    )

    ctx.config = effective_config
    ctx.reference = clips[0]
    ctx.comparisons = clips[1:]
    ctx.analysis_clip = analysis_clip
    ctx.selection_window = selection_window
    ctx.analysis_selection_domain = selection_domain
    ctx.full_window_retry_override = override
    if ctx.preflight_warnings is not None:
        ctx.preflight_warnings[:] = [
            warning
            for warning in ctx.preflight_warnings
            if not warning.startswith("active-rect auto detection ")
        ]
    return active_rect_warnings


def raise_if_full_window_retry_failed(ctx: RunContext, error: SelectionError) -> None:
    """Prevent an accepted recovery attempt from entering uniform fallback later."""
    if ctx.full_window_retry_override is not None:
        raise _fatal_selection_error(error, retry_failed=True) from error


def raise_if_full_window_retry_runtime_failed(
    ctx: RunContext,
    error: Exception,
) -> None:
    """Make any failure after accepted recovery fatal instead of warning-only."""
    if ctx.full_window_retry_override is None:
        return
    analysis = ctx.config.analysis
    requested = (
        len(analysis.user_frames)
        + analysis.random_frame_count
        + analysis.dark_frame_count
        + analysis.bright_frame_count
        + analysis.motion_frame_count
    )
    selection_error = SelectionError(type(error).__name__, requested=requested, found=0)
    raise _fatal_selection_error(selection_error, retry_failed=True) from error


def _eligible_for_recovery(config: ConfigSchema, error: SelectionError) -> bool:
    analysis = config.analysis
    return (
        analysis.ignore_lead_seconds > 0.0 or analysis.ignore_trail_seconds > 0.0
    ) and error.reason in _ELIGIBLE_REASONS


def _full_window_config(config: ConfigSchema) -> ConfigSchema:
    return config.model_copy(
        update={
            "analysis": config.analysis.model_copy(
                update={
                    "ignore_lead_seconds": 0.0,
                    "ignore_trail_seconds": 0.0,
                }
            )
        }
    )


def _override_warning(ignore_lead_seconds: float, ignore_trail_seconds: float) -> str:
    return (
        f"{_FULL_WINDOW_RETRY_WARNING} "
        f"(configured lead={ignore_lead_seconds:g}s, trail={ignore_trail_seconds:g}s; "
        "effective lead=0s, trail=0s)"
    )


def _require_confirmation(
    *,
    error: SelectionError,
    eligible_frame_count: int,
    config: ConfigSchema,
    confirm: FullWindowRetryConfirmationFn | None,
) -> None:
    analysis = config.analysis
    request = FullWindowRetryConfirmationRequest(
        requested_frame_count=error.requested,
        eligible_frame_count=eligible_frame_count,
        ignore_lead_seconds=analysis.ignore_lead_seconds,
        ignore_trail_seconds=analysis.ignore_trail_seconds,
    )
    if confirm is None:
        raise _fatal_selection_error(error, retry_failed=False) from error
    try:
        decision = confirm(request)
    except (KeyboardInterrupt, Exception) as exc:
        raise _fatal_selection_error(error, retry_failed=False) from exc
    if decision != "confirmed":
        raise _fatal_selection_error(error, retry_failed=False) from error


def _refine_active_rects_for_full_window(
    *,
    clips: list[ClipState],
    config: ConfigSchema,
    vs_loader: VSLoader | None,
) -> tuple[list[ClipState], list[str]]:
    selection_window = compute_selection_window_for_clips(clips=clips, config=config)
    if config.screenshots.active_rect_detection != ScreenshotActiveRectDetection.AUTO:
        return clips, []
    sampler = VSActiveRectFrameSampler(vs_loader) if vs_loader is not None else None
    try:
        refined, warnings = refine_auto_content_active_rects_for_clips(
            clips=clips,
            selection_window=selection_window,
            detection=config.screenshots.active_rect_detection,
            sampler=sampler,
            fail_closed=True,
            recompute_content_derived=True,
        )
    except ActiveRectContentDetectionError as exc:
        raise MetricsCalculationError(str(exc)) from exc
    return (
        propagate_resolved_aspect_ratio_evidence(
            clips=refined,
            detection=config.screenshots.active_rect_detection,
        ),
        warnings,
    )


def _fatal_selection_error(
    error: SelectionError,
    *,
    retry_failed: bool,
) -> ExclusionRecoverySelectionError:
    return ExclusionRecoverySelectionError(
        reason=(
            "full-window retry could not satisfy the requested frame selection"
            if retry_failed
            else "configured exclusions leave too little media for frame selection"
        ),
        requested=error.requested,
        found=error.found,
        hint=_RETRY_FAILED_HINT if retry_failed else _RECOVERY_HINT,
        details={"selection_reason": error.reason},
    )


__all__ = [
    "FullWindowRetryOverride",
    "FullWindowSelectionState",
    "compute_selection_window_with_recovery",
    "raise_if_full_window_retry_failed",
    "raise_if_full_window_retry_runtime_failed",
    "recover_from_exclusion_selection_failure",
]
