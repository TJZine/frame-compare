"""VSView availability detection and launch orchestration wrapper.

This module provides the adapter between Frame Compare and the optional
VSView application for interactive alignment verification. It handles
availability probing, launch command resolution, TTY constraints, and subprocess
management.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import re
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import structlog

from frame_compare.vs.runtime_contract import runtime_kind
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewContractError,
    AlignmentReviewSession,
    alignment_review_session_from_script,
)
from frame_compare.vsview.errors import VSViewError, VSViewNotFoundError
from frame_compare.vsview.output import print_vsview_session
from frame_compare.vsview.session_script import write_vsview_session_script

log = structlog.get_logger()

_STARTUP_PROBE_TIMEOUT_SECONDS = 10.0
_REVIEW_PROCESS_TIMEOUT_SECONDS = 12 * 60 * 60
_PROCESS_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_STARTUP_STDERR_LIMIT = 4000
# Keep ``-c``/``-m`` imports out of the caller-controlled media workspace.
_CHILD_PROCESS_CWD = Path(sys.executable).resolve().parent
_PYTHON_INJECTION_ENV_KEYS = (
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
)
_ALIGNMENT_REVIEW_ENTRY_POINT_NAME = "frame-compare-alignment-review"
_ALIGNMENT_REVIEW_ENTRY_POINT_VALUE = "frame_compare.vsview.alignment_review_panel"
_MISSING_MODULE_PATTERN = re.compile(
    r"ModuleNotFoundError:\s+No module named ['\"]([A-Za-z0-9_.]+)['\"]"
)
_SENSITIVE_ENV_KEY_PATTERN = re.compile(
    r"(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|WEBHOOK_URL|AUTHORIZATION|"
    r"CREDENTIAL|PRIVATE_KEY|ACCESS_KEY|COOKIE)(?:_|$)",
    re.IGNORECASE,
)


class VSViewAvailabilityStatus(Enum):
    """Status enum for VSView availability."""

    AVAILABLE = "available"
    MISSING_RUNTIME = "missing_runtime"
    MISSING_PLUGIN = "missing_plugin"
    PROBE_FAILED = "probe_failed"


@dataclass(frozen=True)
class VSViewAvailability:
    """Detailed report of VSView availability."""

    status: VSViewAvailabilityStatus
    message: str
    hint: str | None = None
    error_details: dict[str, str] | None = None

    @property
    def is_available(self) -> bool:
        return self.status == VSViewAvailabilityStatus.AVAILABLE

    def public_probe_failure_details(self) -> dict[str, str]:
        """Return a redacted probe-failure payload safe for public diagnostics."""
        if self.status != VSViewAvailabilityStatus.PROBE_FAILED or not self.error_details:
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


def check_vsview_availability() -> VSViewAvailability:
    """Check if VSView is available, returning a structured availability report.

    Availability requires VSView, PySide6, and the packaged Frame Compare panel
    entry point in this Python environment.
    """
    try:
        vsview_spec = importlib.util.find_spec("vsview")
        pyside6_spec = importlib.util.find_spec("PySide6")
        if vsview_spec is None or pyside6_spec is None:
            return VSViewAvailability(
                status=VSViewAvailabilityStatus.MISSING_RUNTIME,
                message="VSView runtime is not installed in the Frame Compare environment",
                hint=(
                    "Install frame-compare[vsview] in this environment; see "
                    "https://tjzine.github.io/frame-compare/getting-started/native/"
                ),
            )
        entry_points = tuple(
            entry_point
            for entry_point in importlib.metadata.entry_points(group="vsview")
            if entry_point.name == _ALIGNMENT_REVIEW_ENTRY_POINT_NAME
            and entry_point.value == _ALIGNMENT_REVIEW_ENTRY_POINT_VALUE
        )
        if len(entry_points) != 1:
            return VSViewAvailability(
                status=VSViewAvailabilityStatus.MISSING_PLUGIN,
                message="Frame Compare alignment panel is not installed for VSView",
                hint=("Reinstall frame-compare[vsview] in this environment, then rerun doctor"),
            )
        return VSViewAvailability(
            status=VSViewAvailabilityStatus.AVAILABLE,
            message="VSView and the Frame Compare alignment panel are available",
        )
    except Exception as exc:
        return VSViewAvailability(
            status=VSViewAvailabilityStatus.PROBE_FAILED,
            message="VSView availability probe failed (optional for manual alignment)",
            hint=(
                "Check the optional VSView setup, then rerun doctor; see "
                "https://tjzine.github.io/frame-compare/getting-started/native/"
            ),
            error_details={
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            },
        )


@dataclass(frozen=True)
class VSViewConfig:
    """Configuration for VSView integration.

    Attributes:
        enabled: Whether to launch VSView for verification
        no_color: Whether diagnostics should omit terminal color
        verbose: Whether to print launch diagnostics
    """

    enabled: bool = False
    no_color: bool = False
    verbose: bool = False


@dataclass(frozen=True)
class VSViewSessionRequest:
    """Inputs needed to build an alignment VSView session."""

    reference: Path
    comparisons: list[Path]
    suggested_offsets_by_key: dict[str, int | None]
    cache_dir: Path
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None
    presentation_names_by_stem: dict[str, str] | None = None


def launch_alignment_verification_session(
    request: VSViewSessionRequest,
    config: VSViewConfig,
) -> AlignmentReviewSession:
    """Generate and optionally launch a VSView session script."""
    try:
        script_path = _write_vsview_session_script(request)
        session = alignment_review_session_from_script(script_path, require_result_absent=True)
    except (AlignmentReviewContractError, OSError, ValueError) as exc:
        raise VSViewError(f"VSView session setup failed ({type(exc).__name__})") from exc

    if not config.enabled:
        log.info(
            "vsview_script_generated",
            script_path=str(script_path),
            enabled=False,
        )
        return session

    availability = check_vsview_availability()
    if not availability.is_available:
        if availability.status == VSViewAvailabilityStatus.PROBE_FAILED:
            raise VSViewError(availability.public_probe_failure_reason())
        else:
            raise VSViewNotFoundError()

    command = _resolve_launch_command(script_path)

    if config.verbose:
        print_vsview_session(
            script_path=script_path,
            command=command,
            no_color=config.no_color,
        )

    try:
        env = _build_vsview_child_env(no_color=config.no_color)
        _check_startup_readiness(command, env=env)
        returncode = _run_vsview_command(command, env=env)
    except FileNotFoundError as e:
        raise VSViewError("launcher command was not found") from e
    except VSViewError:
        raise
    except Exception as e:
        raise VSViewError(f"unexpected launch error ({type(e).__name__})") from e

    if returncode != 0:
        public_reason = f"launch exited with code {returncode}"
        raise VSViewError(
            public_reason,
            command=tuple(command),
            returncode=returncode,
        )

    return session


def _build_vsview_child_env(*, no_color: bool) -> dict[str, str]:
    """Build the child-only environment without changing the parent process."""
    env = os.environ.copy()
    for key in _PYTHON_INJECTION_ENV_KEYS:
        env.pop(key, None)
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    if no_color:
        env["NO_COLOR"] = "1"
    return env


def _check_startup_readiness(command: list[str], *, env: dict[str, str]) -> None:
    """Boundedly prove the runtime and packaged panel load in this interpreter."""
    probe_code = (
        "import PySide6; import vsview; from vsview import set_output; "
        "from importlib.metadata import entry_points; "
        f"eps=[ep for ep in entry_points(group='vsview') if ep.name=={_ALIGNMENT_REVIEW_ENTRY_POINT_NAME!r} "
        f"and ep.value=={_ALIGNMENT_REVIEW_ENTRY_POINT_VALUE!r}]\n"
        "if len(eps) != 1:\n"
        "    raise RuntimeError('Frame Compare alignment panel entry point is unavailable')\n"
        "eps[0].load()\n"
    )
    if runtime_kind().casefold() == "windows-portable":
        probe_code = (
            "from frame_compare.vsview.launcher import preload_vapoursynth_runtime; "
            f"preload_vapoursynth_runtime(); {probe_code}"
        )
    probe_command = [sys.executable, "-c", probe_code]
    try:
        result = subprocess.run(  # nosec B603
            probe_command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=_STARTUP_PROBE_TIMEOUT_SECONDS,
            env=env,
            cwd=_CHILD_PROCESS_CWD,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_output: str | None = None
        raw_timeout_output = exc.stderr
        if isinstance(raw_timeout_output, str):
            timeout_output = raw_timeout_output
        elif isinstance(raw_timeout_output, bytes):
            timeout_output = raw_timeout_output.decode("utf-8", errors="replace")
        raise VSViewError(
            "startup dependency check timed out",
            command=tuple(command),
            startup_stderr=(
                None
                if timeout_output is None
                else _redact_inherited_secrets(timeout_output, env)[-_STARTUP_STDERR_LIMIT:]
            ),
        ) from exc
    except OSError as exc:
        raise VSViewError(
            "startup dependency check could not run",
            command=tuple(command),
        ) from exc
    if result.returncode == 0:
        return
    startup_stderr = _redact_inherited_secrets(result.stderr, env)[-_STARTUP_STDERR_LIMIT:]
    match = _MISSING_MODULE_PATTERN.search(startup_stderr)
    missing_module = match.group(1) if match else None
    public_reason = (
        f"Missing optional dependency: {missing_module}"
        if missing_module is not None
        else "VSView failed its startup dependency check."
    )
    raise VSViewError(
        public_reason,
        missing_module=missing_module,
        command=tuple(command),
        returncode=result.returncode,
        startup_stderr=startup_stderr,
    )


def _redact_inherited_secrets(text: str, env: dict[str, str]) -> str:
    """Redact exact sensitive environment values inherited by the child process."""
    sensitive_values = {
        value for key, value in env.items() if value and _SENSITIVE_ENV_KEY_PATTERN.search(key)
    }
    for value in sorted(sensitive_values, key=len, reverse=True):
        text = text.replace(value, "<redacted>")
    return text


def _run_vsview_command(command: list[str], *, env: dict[str, str]) -> int:
    # command is a list from _resolve_launch_command; shell=True is never used.
    with subprocess.Popen(  # nosec B603
        command,
        stdin=None,
        stdout=None,
        stderr=None,
        env=env,
        cwd=_CHILD_PROCESS_CWD,
    ) as process:
        try:
            return process.wait(timeout=_REVIEW_PROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            process.terminate()
            try:
                process.wait(timeout=_PROCESS_SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=_PROCESS_SHUTDOWN_TIMEOUT_SECONDS)
            raise VSViewError(
                "alignment review timed out before VSView closed",
                command=tuple(command),
            ) from exc


def _write_vsview_session_script(request: VSViewSessionRequest) -> Path:
    return write_vsview_session_script(
        reference=request.reference,
        comparisons=request.comparisons,
        suggested_offsets_by_key=request.suggested_offsets_by_key,
        cache_dir=request.cache_dir,
        frame_props_by_stem=request.frame_props_by_stem,
        presentation_names_by_stem=request.presentation_names_by_stem,
    )


def _resolve_launch_command(script_path: Path) -> list[str]:
    """Resolve the launch command for VSView.

    The managed launcher keeps VSView and the packaged Frame Compare panel in the
    current interpreter. On Windows it also preloads VapourSynth before Qt.
    """
    return [
        sys.executable,
        "-m",
        "frame_compare.vsview.launcher",
        str(script_path),
    ]
