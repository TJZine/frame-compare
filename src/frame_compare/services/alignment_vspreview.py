"""Alignment-specific VSPreview launch policy."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import structlog

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vspreview.adapter import (
    VSPreviewAvailabilityStatus,
    VSPreviewConfig,
    VSPreviewSessionRequest,
    check_vspreview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vspreview.errors import VSPreviewError

log = structlog.get_logger()


@dataclass(frozen=True)
class _TTYStatus:
    stdin: bool
    stdout: bool
    stderr: bool

    @property
    def has_any(self) -> bool:
        return self.stdin or self.stdout or self.stderr


@dataclass(frozen=True)
class _LaunchDecision:
    enabled: bool
    no_tty: bool


def _current_tty_status() -> _TTYStatus:
    return _TTYStatus(
        stdin=sys.stdin.isatty(),
        stdout=sys.stdout.isatty(),
        stderr=sys.stderr.isatty(),
    )


def _raise_for_forced_unavailable(availability: VSPreviewAvailabilityStatus) -> None:
    if availability == VSPreviewAvailabilityStatus.PROBE_FAILED:
        raise AudioAlignmentError(
            "Interactive alignment requested but VSPreview availability probe failed."
        )
    raise AudioAlignmentError("Interactive alignment requested but VSPreview is not available.")


def _launch_requested(config: AlignmentConfig) -> bool:
    return bool(config.use_vspreview or config.force_interactive)


def _ensure_forced_availability(
    *,
    status: VSPreviewAvailabilityStatus,
    is_available: bool,
    probe_failure_reason: str,
) -> None:
    if is_available:
        return
    if status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        raise AudioAlignmentError(
            f"Interactive alignment requested but VSPreview {probe_failure_reason}."
        )
    _raise_for_forced_unavailable(status)


def _log_optional_unavailable(
    *,
    status: VSPreviewAvailabilityStatus,
    hint: str | None,
    error_details: dict[str, str] | None,
    use_vspreview: bool,
    force_interactive: bool,
    probe_failure_reason: str,
    probe_failure_details: dict[str, str],
) -> None:
    if status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        log.warning(
            "vspreview_availability_probe_failed",
            reason=probe_failure_reason,
            exception_type=probe_failure_details.get("exception_type"),
            hint=hint,
            use_vspreview=use_vspreview,
            force_interactive=force_interactive,
        )
        if error_details:
            log.debug(
                "vspreview_availability_probe_failed_debug",
                error_details=error_details,
            )
    elif use_vspreview and not force_interactive:
        log.warning(
            "vspreview_unavailable",
            hint=hint,
            use_vspreview=use_vspreview,
            force_interactive=force_interactive,
        )


def _log_no_tty(script_path: Path, tty_status: _TTYStatus) -> None:
    log.warning(
        "vspreview_no_tty",
        hint="Cannot launch VSPreview without an interactive terminal (TTY)",
        script_path=str(script_path),
        stdin_tty=tty_status.stdin,
        stdout_tty=tty_status.stdout,
        stderr_tty=tty_status.stderr,
    )


def _log_optional_launch_failed(exc: VSPreviewError, config: AlignmentConfig) -> None:
    log.warning(
        "vspreview_optional_launch_failed",
        reason=exc.context.message,
        code=exc.code,
        force_interactive=config.force_interactive,
        use_vspreview=config.use_vspreview,
    )


def _resolve_launch_decision(
    *,
    config: AlignmentConfig,
    is_available: bool,
    tty_status: _TTYStatus,
) -> _LaunchDecision:
    requested = _launch_requested(config)
    enabled = bool(requested and is_available and tty_status.has_any)
    return _LaunchDecision(
        enabled=enabled,
        no_tty=bool(requested and is_available and not tty_status.has_any),
    )


def maybe_launch_alignment_vspreview(
    *,
    reference: Path,
    comparisons: list[Path],
    offsets_by_key: dict[str, int],
    cache_dir: Path,
    config: AlignmentConfig,
    progress: ProgressReporter | None,
) -> None:
    """Best-effort VSPreview alignment verification.

    This is intended for interactive verification/inspection only. Actual offsets
    used by the pipeline are still sourced from:
      1) manual overrides (highest precedence)
      2) cached offsets
      3) computed offsets (cross-correlation)
    """
    if not (config.use_vspreview or config.force_interactive):
        return

    availability = check_vspreview_availability()

    if config.force_interactive:
        _ensure_forced_availability(
            status=availability.status,
            is_available=availability.is_available,
            probe_failure_reason=availability.public_probe_failure_reason(),
        )

    if not availability.is_available:
        _log_optional_unavailable(
            status=availability.status,
            hint=availability.hint,
            error_details=availability.error_details,
            use_vspreview=config.use_vspreview,
            force_interactive=config.force_interactive,
            probe_failure_reason=availability.public_probe_failure_reason(),
            probe_failure_details=availability.public_probe_failure_details(),
        )

    tty_status = _current_tty_status()
    launch_decision = _resolve_launch_decision(
        config=config,
        is_available=availability.is_available,
        tty_status=tty_status,
    )

    if progress:
        progress.set_description("Alignment verification")

    if config.force_interactive and launch_decision.no_tty:
        raise AudioAlignmentError(
            "Interactive alignment requested but no interactive terminal (TTY) is available."
        )

    try:
        script_path = launch_alignment_verification_session(
            request=VSPreviewSessionRequest(
                reference=reference,
                comparisons=comparisons,
                suggested_offsets_by_key=offsets_by_key,
                cache_dir=cache_dir,
            ),
            config=VSPreviewConfig(enabled=launch_decision.enabled),
        )
        if launch_decision.no_tty:
            _log_no_tty(script_path, tty_status)
    except VSPreviewError as exc:
        if config.force_interactive:
            raise
        _log_optional_launch_failed(exc, config)
