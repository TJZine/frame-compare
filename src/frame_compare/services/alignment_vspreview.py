"""Alignment-specific VSPreview launch policy."""

from __future__ import annotations

import sys
from pathlib import Path

import structlog

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vspreview.adapter import (
    VSPreviewAvailabilityStatus,
    VSPreviewConfig,
    check_vspreview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vspreview.errors import VSPreviewError

log = structlog.get_logger()


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

    if config.force_interactive and not availability.is_available:
        if availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            raise AudioAlignmentError(
                "Interactive alignment requested but "
                f"VSPreview {availability.public_probe_failure_reason()}."
            )
        raise AudioAlignmentError("Interactive alignment requested but VSPreview is not available.")

    if not availability.is_available:
        if availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            public_details = availability.public_probe_failure_details()
            log.warning(
                "vspreview_availability_probe_failed",
                reason=availability.public_probe_failure_reason(),
                exception_type=public_details.get("exception_type"),
                hint=availability.hint,
                use_vspreview=config.use_vspreview,
                force_interactive=config.force_interactive,
            )
            if availability.error_details:
                log.debug(
                    "vspreview_availability_probe_failed_debug",
                    error_details=availability.error_details,
                )
        elif config.use_vspreview and not config.force_interactive:
            log.warning(
                "vspreview_unavailable",
                hint=availability.hint,
                use_vspreview=config.use_vspreview,
                force_interactive=config.force_interactive,
            )

    stdin_tty = sys.stdin.isatty()
    stdout_tty = sys.stdout.isatty()
    stderr_tty = sys.stderr.isatty()
    has_tty = stdin_tty or stdout_tty or stderr_tty

    launch_requested = bool(config.use_vspreview or config.force_interactive)
    should_launch = bool(launch_requested and availability.is_available and has_tty)

    if progress:
        progress.set_description("Alignment verification")

    try:
        script_path = launch_alignment_verification_session(
            reference=reference,
            comparisons=comparisons,
            suggested_offsets_by_key=offsets_by_key,
            cache_dir=cache_dir,
            config=VSPreviewConfig(enabled=should_launch),
        )
        if launch_requested and availability.is_available and not has_tty:
            log.warning(
                "vspreview_no_tty",
                hint="Cannot launch VSPreview without an interactive terminal (TTY)",
                script_path=str(script_path),
                stdin_tty=stdin_tty,
                stdout_tty=stdout_tty,
                stderr_tty=stderr_tty,
            )
    except VSPreviewError as exc:
        if config.force_interactive:
            raise
        log.warning(
            "vspreview_optional_launch_failed",
            reason=exc.context.message,
            code=exc.code,
            force_interactive=config.force_interactive,
            use_vspreview=config.use_vspreview,
        )
