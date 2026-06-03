"""VSPreview availability detection and launch orchestration wrapper.

This module provides the adapter between Frame Compare and the optional
VSPreview application for interactive alignment verification. It handles
availability probing, launch command resolution, TTY constraints, and subprocess
management.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import structlog

from frame_compare.vspreview.errors import VSPreviewError, VSPreviewNotFoundError
from frame_compare.vspreview.output import print_vspreview_session
from frame_compare.vspreview.session_script import write_vspreview_session_script

log = structlog.get_logger()


class VSPreviewAvailabilityStatus(Enum):
    """Status enum for VSPreview availability."""

    AVAILABLE = "available"
    MISSING_EXEC_AND_MODULE = "missing_exec_and_module"
    MISSING_QT_BACKEND = "missing_qt_backend"
    PROBE_FAILED = "probe_failed"


@dataclass(frozen=True)
class VSPreviewAvailability:
    """Detailed report of VSPreview availability."""

    status: VSPreviewAvailabilityStatus
    message: str
    hint: str | None = None
    error_details: dict[str, str] | None = None

    @property
    def is_available(self) -> bool:
        return self.status == VSPreviewAvailabilityStatus.AVAILABLE

    def public_probe_failure_details(self) -> dict[str, str]:
        """Return a redacted probe-failure payload safe for public diagnostics."""
        if self.status != VSPreviewAvailabilityStatus.PROBE_FAILED or not self.error_details:
            return {}

        exception_type = self.error_details.get("exception_type")
        if not exception_type:
            return {}

        return {"exception_type": exception_type}

    def public_probe_failure_status(self) -> str:
        """Return a short probe-failure status string safe for CLI summaries."""
        details = self.public_probe_failure_details()
        exception_type = details.get("exception_type")
        if exception_type is None:
            return "probe failed"
        return f"probe failed ({exception_type})"

    def public_probe_failure_reason(self) -> str:
        """Return a probe-failure reason suitable for user-facing errors."""
        details = self.public_probe_failure_details()
        exception_type = details.get("exception_type")
        if exception_type is None:
            return "availability probe failed"
        return f"availability probe failed ({exception_type})"


def check_vspreview_availability() -> VSPreviewAvailability:
    """Check if VSPreview is available, returning a structured availability report.

    Availability rules:
        - Return AVAILABLE if `shutil.which("vspreview")` is non-None, OR
        - `importlib.util.find_spec("vspreview")` is non-None AND
          (`find_spec("PyQt6")` OR `find_spec("PySide6")` OR `find_spec("PyQt5")`) is non-None.
    """
    try:
        # Priority 1: Check if vspreview executable exists in PATH
        if shutil.which("vspreview") is not None:
            return VSPreviewAvailability(
                status=VSPreviewAvailabilityStatus.AVAILABLE,
                message="VSPreview is available for interactive alignment",
            )

        # Priority 2: Check if vspreview module is importable + Qt backend
        vspreview_spec = importlib.util.find_spec("vspreview")
        if vspreview_spec is None:
            return VSPreviewAvailability(
                status=VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE,
                message="VSPreview not installed (optional for manual alignment)",
                hint="Install with: pip install vspreview PyQt6 (or: pip install vspreview PySide6)",
            )

        # Need at least one Qt backend
        pyqt6_spec = importlib.util.find_spec("PyQt6")
        pyside6_spec = importlib.util.find_spec("PySide6")
        pyqt5_spec = importlib.util.find_spec("PyQt5")

        if pyqt6_spec is not None or pyside6_spec is not None or pyqt5_spec is not None:
            return VSPreviewAvailability(
                status=VSPreviewAvailabilityStatus.AVAILABLE,
                message="VSPreview is available for interactive alignment",
            )

        return VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.MISSING_QT_BACKEND,
            message="Qt backend missing for VSPreview (optional for manual alignment)",
            hint="Install with: pip install PyQt6 (or: pip install PySide6)",
        )
    except Exception as exc:
        return VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.PROBE_FAILED,
            message="VSPreview availability probe failed (optional for manual alignment)",
            hint="Check the VSPreview/PyQt6/PySide6 installation if interactive alignment is needed",
            error_details={
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            },
        )


@dataclass(frozen=True)
class VSPreviewConfig:
    """Configuration for VSPreview integration.

    Attributes:
        enabled: Whether to launch VSPreview for verification
        timeout_seconds: Reserved for future bounded interactive confirmation flows
        auto_close: Close VSPreview after user confirms
    """

    enabled: bool = False
    timeout_seconds: float = 300.0  # 5 minutes
    auto_close: bool = True
    no_color: bool = False


@dataclass(frozen=True)
class VSPreviewSessionRequest:
    """Inputs needed to build an alignment VSPreview session."""

    reference: Path
    comparisons: list[Path]
    suggested_offsets_by_key: dict[str, int | None]
    cache_dir: Path
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None


def launch_alignment_verification_session(
    request: VSPreviewSessionRequest,
    config: VSPreviewConfig,
) -> Path:
    """Generate and optionally launch a VSPreview session script."""
    script_path = _write_vspreview_session_script(request)

    if not config.enabled:
        log.info(
            "vspreview_script_generated",
            script_path=str(script_path),
            enabled=False,
        )
        return script_path

    availability = check_vspreview_availability()
    if not availability.is_available:
        if availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            raise VSPreviewError(availability.public_probe_failure_reason())
        else:
            raise VSPreviewNotFoundError()

    command = _resolve_launch_command(script_path)

    # Print telemetry per vspreview spec §3.2.3.
    print_vspreview_session(
        script_path=script_path,
        command=command,
        no_color=config.no_color,
    )

    try:
        env = os.environ.copy()
        if config.no_color:
            env["NO_COLOR"] = "1"
        # command is a list from _resolve_launch_command; shell=True is never used.
        result = subprocess.run(  # nosec B603
            command,
            check=False,
            stdin=None,
            stdout=None,
            stderr=None,
            text=True,
            env=env,
        )
    except FileNotFoundError as e:
        raise VSPreviewError("launcher command was not found") from e
    except Exception as e:
        log.debug(
            "vspreview_launch_unexpected_debug",
            exception_type=type(e).__name__,
            error=str(e),
        )
        raise VSPreviewError(f"unexpected launch error ({type(e).__name__})") from e

    if result.returncode != 0:
        public_reason = f"launch exited with code {result.returncode}"
        log.warning(
            "vspreview_launch_failed",
            reason=public_reason,
            returncode=result.returncode,
            hint="Re-run with verbose mode to inspect VSPreview output",
        )
        raise VSPreviewError(public_reason)

    return script_path


def _write_vspreview_session_script(request: VSPreviewSessionRequest) -> Path:
    return write_vspreview_session_script(
        reference=request.reference,
        comparisons=request.comparisons,
        suggested_offsets_by_key=request.suggested_offsets_by_key,
        cache_dir=request.cache_dir,
        frame_props_by_stem=request.frame_props_by_stem,
    )


def _resolve_launch_command(script_path: Path) -> list[str]:
    """Resolve the launch command for VSPreview.

    Priority per vspreview spec §6.3:
    1. If `vspreview` executable exists in PATH: `vspreview {script_path}`
    2. Else: `{sys.executable} -m vspreview {script_path}`
    """
    vspreview_path = shutil.which("vspreview")
    if vspreview_path is not None:
        return [vspreview_path, str(script_path)]
    return [sys.executable, "-m", "vspreview", str(script_path)]
