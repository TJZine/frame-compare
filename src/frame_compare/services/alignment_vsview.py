"""Alignment-specific VSView launch policy."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog

from frame_compare.services.alignment_manual_overrides import ManualOverride, save_manual_override
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal import stream_is_tty
from frame_compare.vsview.adapter import (
    VSViewAvailabilityStatus,
    VSViewConfig,
    VSViewSessionRequest,
    check_vsview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vsview.errors import VSViewError
from frame_compare.vsview.output import (
    print_vsview_confirmation_footer,
    print_vsview_confirmation_header,
    print_vsview_failure_details,
    print_vsview_input_hint,
    print_vsview_unavailable,
    write_vsview_prompt,
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


def _raise_for_forced_unavailable(availability: VSViewAvailabilityStatus) -> None:
    if availability == VSViewAvailabilityStatus.PROBE_FAILED:
        raise AudioAlignmentError(
            "Interactive alignment requested but VSView availability probe failed."
        )
    raise AudioAlignmentError("Interactive alignment requested but VSView is not available.")


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
    _raise_for_forced_unavailable(status)


def _log_optional_unavailable(
    *,
    status: VSViewAvailabilityStatus,
    hint: str | None,
    error_details: dict[str, str] | None,
    use_vsview: bool,
    force_interactive: bool,
    probe_failure_reason: str,
    probe_failure_details: dict[str, str],
    tty_status: _TTYStatus,
    no_color: bool,
) -> None:
    if tty_status.stderr:
        reason = {
            VSViewAvailabilityStatus.MISSING_EXEC_AND_MODULE: "VSView is not installed.",
            VSViewAvailabilityStatus.MISSING_QT_BACKEND: ("Missing optional VSView Qt backend."),
            VSViewAvailabilityStatus.PROBE_FAILED: ("VSView availability check failed."),
        }.get(status, "VSView is unavailable.")
        print_vsview_unavailable(reason=reason, no_color=no_color)
        log_method = log.debug
    else:
        log_method = log.warning
    if status == VSViewAvailabilityStatus.PROBE_FAILED:
        log_method(
            "vsview_availability_probe_failed",
            reason=probe_failure_reason,
            exception_type=probe_failure_details.get("exception_type"),
            hint=hint,
            use_vsview=use_vsview,
            force_interactive=force_interactive,
        )
        if error_details:
            log.debug(
                "vsview_availability_probe_failed_debug",
                error_details=error_details,
            )
    elif use_vsview and not force_interactive:
        log_method(
            "vsview_unavailable",
            hint=hint,
            use_vsview=use_vsview,
            force_interactive=force_interactive,
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


def _read_vsview_prompt(
    *,
    label: str,
    suggested_offset: int | None,
    no_color: bool,
) -> str:
    write_vsview_prompt(
        label=label,
        suggested_offset=suggested_offset,
        no_color=no_color,
    )
    raw_value = sys.stdin.readline()
    if raw_value == "":
        raise EOFError
    return raw_value


def _parse_source_frame_pair(raw_value: str) -> tuple[int, int] | None:
    tokens = raw_value.replace(",", " ").split()
    if len(tokens) != 2:
        return None
    if not all(token.isascii() and token.isdecimal() for token in tokens):
        return None
    return int(tokens[0]), int(tokens[1])


def _prompt_for_confirmed_offsets(
    *,
    reference: Path,
    comparisons: list[Path],
    offsets_by_key: dict[str, int | None],
    presentation_names_by_stem: dict[str, str] | None = None,
    no_color: bool = False,
) -> dict[str, int] | None:
    if not comparisons:
        return {}

    presentation_names = presentation_names_by_stem or {}
    print_vsview_confirmation_header(
        reference_name=presentation_names.get(reference.stem, reference.stem),
        no_color=no_color,
    )

    confirmed: dict[str, int] = {}
    for comparison_number, comparison in enumerate(comparisons, start=1):
        key = f"{reference.stem}:{comparison.stem}"
        suggested_offset = offsets_by_key.get(key)
        while True:
            try:
                raw_value = _read_vsview_prompt(
                    label=(
                        f"Comparison {comparison_number} | "
                        f"{presentation_names.get(comparison.stem, comparison.stem)}"
                    ),
                    suggested_offset=suggested_offset,
                    no_color=no_color,
                ).strip()
            except (EOFError, OSError):
                print_vsview_input_hint(
                    "No terminal input available; keeping current offsets.",
                    no_color=no_color,
                )
                return None
            if raw_value == "":
                print_vsview_input_hint(
                    "Enter both source frames, for example '120 108', or 'skip'.",
                    no_color=no_color,
                )
                continue
            if raw_value.lower() in {"skip", "s"}:
                break
            source_frames = _parse_source_frame_pair(raw_value)
            if source_frames is None:
                print_vsview_input_hint(
                    "Enter two non-negative integer source frames, for example '120 108', "
                    "or 'skip'.",
                    no_color=no_color,
                )
                continue
            reference_source_frame, comparison_source_frame = source_frames
            confirmed[key] = reference_source_frame - comparison_source_frame
            break
    print_vsview_confirmation_footer(no_color=no_color)
    return confirmed


def _save_confirmed_offsets(
    *,
    reference: Path,
    comparisons: list[Path],
    cache_dir: Path,
    confirmed_offsets_by_key: dict[str, int],
) -> None:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for comparison in comparisons:
        key = f"{reference.stem}:{comparison.stem}"
        if key not in confirmed_offsets_by_key:
            continue
        save_manual_override(
            cache_dir,
            ManualOverride(
                reference_clip=reference.stem,
                comparison_clip=comparison.stem,
                frame_offset=int(confirmed_offsets_by_key[key]),
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
    has_prompt_input = tty_status.stdin
    enabled = bool(requested and is_available and has_prompt_input)
    return _LaunchDecision(
        enabled=enabled,
        no_tty=bool(requested and is_available and not has_prompt_input),
    )


def maybe_launch_alignment_vsview(
    *,
    reference: Path,
    comparisons: list[Path],
    offsets_by_key: dict[str, int | None],
    cache_dir: Path,
    config: AlignmentConfig,
    progress: ProgressReporter | None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
    verbose: bool = False,
) -> dict[str, int] | None:
    """Best-effort VSView alignment verification.

    This is intended for interactive verification/inspection only. Actual offsets
    used by the pipeline are still sourced from:
      1) manual overrides (highest precedence)
      2) cached offsets
      3) computed offsets (cross-correlation)
    """
    if not (config.use_vsview or config.force_interactive):
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
            error_details=availability.error_details,
            use_vsview=config.use_vsview,
            force_interactive=config.force_interactive,
            probe_failure_reason=availability.public_probe_failure_reason(),
            probe_failure_details=availability.public_probe_failure_details(),
            tty_status=tty_status,
            no_color=config.no_color,
        )

    launch_decision = _resolve_launch_decision(
        config=config,
        is_available=availability.is_available,
        tty_status=tty_status,
    )

    if progress:
        progress.set_description("ALIGN | Interactive verification")

    if config.force_interactive and launch_decision.no_tty:
        raise AudioAlignmentError(
            "Interactive alignment requested but no interactive terminal (TTY) is available."
        )

    interactive_progress = progress
    progress_suspended = _suspend_progress_for_interaction(interactive_progress)
    try:
        script_path = launch_alignment_verification_session(
            request=VSViewSessionRequest(
                reference=reference,
                comparisons=comparisons,
                suggested_offsets_by_key=offsets_by_key,
                cache_dir=cache_dir,
                frame_props_by_stem=frame_props_by_stem,
                presentation_names_by_stem=presentation_names_by_stem,
            ),
            config=VSViewConfig(
                enabled=launch_decision.enabled,
                no_color=config.no_color,
                verbose=verbose,
            ),
        )
        if launch_decision.no_tty:
            _log_no_tty(script_path, tty_status)
        if not launch_decision.enabled:
            return None
        confirmed_offsets = _prompt_for_confirmed_offsets(
            reference=reference,
            comparisons=comparisons,
            offsets_by_key=offsets_by_key,
            presentation_names_by_stem=presentation_names_by_stem,
            no_color=config.no_color,
        )
        if confirmed_offsets is None:
            return None
        _save_confirmed_offsets(
            reference=reference,
            comparisons=comparisons,
            cache_dir=cache_dir,
            confirmed_offsets_by_key=confirmed_offsets,
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
        if progress_suspended and interactive_progress is not None:
            interactive_progress.resume()
    return None
