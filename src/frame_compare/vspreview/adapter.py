"""VSPreview availability detection and launch orchestration wrapper.

This module provides the adapter between Frame Compare and the optional
VSPreview application for interactive alignment verification. It handles
availability probing, launch command resolution, TTY constraints, and subprocess
management.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import structlog

from frame_compare.vspreview.errors import VSPreviewError, VSPreviewNotFoundError
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
        timeout_seconds: Max time to wait for user input
        auto_close: Close VSPreview after user confirms
    """

    enabled: bool = False
    timeout_seconds: float = 300.0  # 5 minutes
    auto_close: bool = True


def launch_alignment_verification_session(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
    cache_dir: Path,
    config: VSPreviewConfig,
) -> Path:
    """Generate and optionally launch a VSPreview session script."""
    script_path = write_vspreview_session_script(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        cache_dir=cache_dir,
    )

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
            err_msg = availability.message
            if availability.error_details:
                err_msg += f" ({availability.error_details.get('exception_type')}: {availability.error_details.get('exception')})"
            raise VSPreviewError(err_msg)
        else:
            raise VSPreviewNotFoundError()

    command = _resolve_launch_command(script_path)

    # Print telemetry per vspreview spec §3.2.3
    print(f"VSPreview script: {script_path}")
    print(f"Launch command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
        )

        if result.returncode != 0:
            # Emit warning telemetry before surfacing a launch failure.
            log.warning(
                "vspreview_non_zero_exit",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else None,
                stdout=result.stdout[:500] if result.stdout else None,
                hint="Re-run with verbose mode to capture full output",
            )
            raise VSPreviewError(
                f"VSPreview exited with code {result.returncode}: "
                f"{result.stderr[:200] if result.stderr else 'no stderr'}"
            )

    except subprocess.TimeoutExpired as e:
        raise VSPreviewError(f"VSPreview timed out after {config.timeout_seconds}s") from e
    except FileNotFoundError as e:
        raise VSPreviewError(f"Failed to launch VSPreview: {e}") from e
    except Exception as e:
        if isinstance(e, (VSPreviewError, VSPreviewNotFoundError)):
            raise
        raise VSPreviewError(f"Unexpected error launching VSPreview: {e}") from e

    return script_path


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
