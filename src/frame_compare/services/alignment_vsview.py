"""Native VSView alignment-review policy and result application."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog

from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_manual_overrides import ManualOverride, save_manual_override
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal import stream_is_tty
from frame_compare.utils.types import AlignmentClipRequest
from frame_compare.vsview.adapter import (
    VSViewAvailabilityStatus,
    VSViewConfig,
    VSViewSessionRequest,
    check_vsview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewContractError,
    AlignmentReviewExpectedComparison,
    AlignmentReviewResult,
    ConfirmedAlignmentReviewDecision,
    read_alignment_review_result,
)
from frame_compare.vsview.errors import VSViewError
from frame_compare.vsview.output import (
    print_vsview_failure_details,
    print_vsview_review_result,
    print_vsview_unavailable,
)

log = structlog.get_logger()


@dataclass(frozen=True)
class _TTYStatus:
    stdin: bool
    stdout: bool
    stderr: bool


@dataclass(frozen=True)
class _LaunchDecision:
    enabled: bool
    no_tty: bool


def _current_tty_status() -> _TTYStatus:
    return _TTYStatus(
        stdin=stream_is_tty(sys.stdin),
        stdout=stream_is_tty(sys.stdout),
        stderr=stream_is_tty(sys.stderr),
    )


def _launch_requested(config: AlignmentConfig) -> bool:
    return bool(config.use_vsview or config.force_interactive)


def _ensure_forced_availability(
    *,
    status: VSViewAvailabilityStatus,
    is_available: bool,
    probe_failure_reason: str,
) -> None:
    if is_available:
        return
    if status == VSViewAvailabilityStatus.PROBE_FAILED:
        raise AudioAlignmentError(
            f"Interactive alignment requested but VSView {probe_failure_reason}."
        )
    raise AudioAlignmentError(
        "Interactive alignment requested but VSView and the Frame Compare panel "
        "are not available in this Python environment."
    )


def _log_optional_unavailable(
    *,
    status: VSViewAvailabilityStatus,
    hint: str | None,
    error_details: dict[str, str] | None,
    config: AlignmentConfig,
    tty_status: _TTYStatus,
) -> None:
    if tty_status.stderr:
        reason = {
            VSViewAvailabilityStatus.MISSING_RUNTIME: (
                "VSView and PySide6 are not installed in the Frame Compare environment."
            ),
            VSViewAvailabilityStatus.MISSING_PLUGIN: (
                "The Frame Compare alignment panel is not installed for VSView."
            ),
            VSViewAvailabilityStatus.PROBE_FAILED: "VSView availability check failed.",
        }.get(status, "VSView is unavailable.")
        print_vsview_unavailable(reason=reason, no_color=config.no_color)
        log_method = log.debug
    else:
        log_method = log.warning
    if status == VSViewAvailabilityStatus.PROBE_FAILED:
        log_method(
            "vsview_availability_probe_failed",
            exception_type=(error_details or {}).get("exception_type"),
            hint=hint,
            use_vsview=config.use_vsview,
            force_interactive=config.force_interactive,
        )
    elif config.use_vsview and not config.force_interactive:
        log_method(
            "vsview_unavailable",
            status=status.value,
            hint=hint,
            use_vsview=config.use_vsview,
            force_interactive=config.force_interactive,
        )


def _log_no_tty(script_path: Path, tty_status: _TTYStatus) -> None:
    log.warning(
        "vsview_no_tty",
        hint="Cannot launch VSView without an interactive terminal (TTY)",
        script_path=str(script_path),
        stdin_tty=tty_status.stdin,
        stdout_tty=tty_status.stdout,
        stderr_tty=tty_status.stderr,
    )


def _present_optional_launch_failed(
    exc: VSViewError,
    config: AlignmentConfig,
    *,
    verbose: bool,
    tty_status: _TTYStatus,
) -> None:
    if tty_status.stderr:
        print_vsview_unavailable(reason=exc.public_reason, no_color=config.no_color)
        if verbose and exc.command:
            print_vsview_failure_details(
                command=exc.command,
                reason=exc.public_reason,
                returncode=exc.returncode,
                startup_stderr=exc.startup_stderr,
                no_color=config.no_color,
            )
        log.debug(
            "vsview_optional_launch_failed",
            reason=exc.context.message,
            code=exc.code,
            force_interactive=config.force_interactive,
            use_vsview=config.use_vsview,
        )
        return
    log.warning(
        "vsview_optional_launch_failed",
        reason=exc.context.message,
        code=exc.code,
        force_interactive=config.force_interactive,
        use_vsview=config.use_vsview,
    )


def _save_confirmed_offsets(
    *,
    reference: Path,
    comparisons: list[Path],
    cache_dir: Path,
    confirmed_offsets_by_key: dict[str, int],
) -> None:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for comparison in comparisons:
        key = alignment_key(reference, comparison)
        if key not in confirmed_offsets_by_key:
            continue
        save_manual_override(
            cache_dir,
            ManualOverride(
                reference_clip=reference.stem,
                comparison_clip=comparison.stem,
                frame_offset=confirmed_offsets_by_key[key],
                timestamp=timestamp,
                confirmed=True,
            ),
        )


def _suspend_progress_for_interaction(progress: ProgressReporter | None) -> bool:
    if progress is None:
        return False
    progress.suspend()
    return True


def _resolve_launch_decision(
    *,
    config: AlignmentConfig,
    is_available: bool,
    tty_status: _TTYStatus,
) -> _LaunchDecision:
    requested = _launch_requested(config)
    enabled = bool(requested and is_available and tty_status.stdin)
    return _LaunchDecision(
        enabled=enabled,
        no_tty=bool(requested and is_available and not tty_status.stdin),
    )


def _expected_comparisons(
    reference: AlignmentClipRequest,
    comparisons: list[AlignmentClipRequest],
) -> tuple[AlignmentReviewExpectedComparison, ...]:
    return tuple(
        AlignmentReviewExpectedComparison(
            comparison_key=alignment_key(reference.path, comparison.path),
            reference_source_frame_count=reference.source_frame_count,
            comparison_source_frame_count=comparison.source_frame_count,
        )
        for comparison in comparisons
    )


def _confirmed_offsets(result: AlignmentReviewResult) -> dict[str, int]:
    return {
        decision.comparison_key: (
            decision.reference_source_frame - decision.comparison_source_frame
        )
        for decision in result.decisions
        if isinstance(decision, ConfirmedAlignmentReviewDecision)
    }


def _handle_invalid_result(
    exc: AlignmentReviewContractError,
    *,
    config: AlignmentConfig,
    tty_status: _TTYStatus,
) -> None:
    reason = str(exc)
    if config.force_interactive:
        raise AudioAlignmentError(
            f"Interactive alignment did not return a valid VSView review result: {reason}."
        ) from exc
    if tty_status.stderr:
        print_vsview_review_result(
            accepted=False,
            message=f"{reason}; current offsets were retained.",
            no_color=config.no_color,
        )
        log.debug("vsview_review_result_rejected", reason=reason)
    else:
        log.warning("vsview_review_result_rejected", reason=reason)


def maybe_launch_alignment_vsview(
    *,
    reference: AlignmentClipRequest,
    comparisons: list[AlignmentClipRequest],
    offsets_by_key: dict[str, int | None],
    cache_dir: Path,
    config: AlignmentConfig,
    progress: ProgressReporter | None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    verbose: bool = False,
) -> dict[str, int] | None:
    """Launch one native review and apply only a complete, trusted result."""
    if not _launch_requested(config):
        return None

    availability = check_vsview_availability()
    if config.force_interactive:
        _ensure_forced_availability(
            status=availability.status,
            is_available=availability.is_available,
            probe_failure_reason=availability.public_probe_failure_reason(),
        )

    tty_status = _current_tty_status()
    if not availability.is_available:
        _log_optional_unavailable(
            status=availability.status,
            hint=availability.hint,
            error_details=availability.public_probe_failure_details(),
            config=config,
            tty_status=tty_status,
        )

    launch_decision = _resolve_launch_decision(
        config=config,
        is_available=availability.is_available,
        tty_status=tty_status,
    )
    if progress:
        progress.set_description("ALIGN | Native VSView review")
    if config.force_interactive and launch_decision.no_tty:
        raise AudioAlignmentError(
            "Interactive alignment requested but no interactive terminal (TTY) is available."
        )

    reference_path = reference.path
    comparison_paths = [comparison.path for comparison in comparisons]
    progress_suspended = _suspend_progress_for_interaction(progress)
    try:
        session = launch_alignment_verification_session(
            request=VSViewSessionRequest(
                reference=reference_path,
                comparisons=comparison_paths,
                suggested_offsets_by_key=offsets_by_key,
                cache_dir=cache_dir,
                frame_props_by_stem=frame_props_by_stem,
                presentation_names_by_stem={
                    reference_path.stem: reference.presentation_name or reference_path.stem,
                    **{
                        comparison.path.stem: (comparison.presentation_name or comparison.path.stem)
                        for comparison in comparisons
                    },
                },
            ),
            config=VSViewConfig(
                enabled=launch_decision.enabled,
                no_color=config.no_color,
                verbose=verbose,
            ),
        )
        if launch_decision.no_tty:
            _log_no_tty(session.script_path, tty_status)
        if not launch_decision.enabled:
            return None
        try:
            result = read_alignment_review_result(
                session,
                _expected_comparisons(reference, comparisons),
            )
        except AlignmentReviewContractError as exc:
            _handle_invalid_result(exc, config=config, tty_status=tty_status)
            return None

        confirmed_offsets = _confirmed_offsets(result)
        _save_confirmed_offsets(
            reference=reference_path,
            comparisons=comparison_paths,
            cache_dir=cache_dir,
            confirmed_offsets_by_key=confirmed_offsets,
        )
        kept_count = len(result.decisions) - len(confirmed_offsets)
        print_vsview_review_result(
            accepted=True,
            message=(
                f"Accepted {len(confirmed_offsets)} confirmed pair(s); "
                f"{kept_count} comparison(s) kept their current offset."
            ),
            no_color=config.no_color,
        )
        return confirmed_offsets
    except VSViewError as exc:
        if config.force_interactive:
            raise
        _present_optional_launch_failed(
            exc,
            config,
            verbose=verbose,
            tty_status=tty_status,
        )
    finally:
        if progress_suspended and progress is not None:
            progress.resume()
    return None
