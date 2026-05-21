"""Diagnostic checks for Frame Compare 2.0.

This module provides diagnostic checks for validating the runtime environment,
including dependency availability, network connectivity, and system requirements.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING

import httpx

from frame_compare.errors import JSONValue
from frame_compare.vs.env import register_windows_dll_dirs

if TYPE_CHECKING:
    from frame_compare.utils.progress import ProgressReporter


# Canonical check ordering per SSOT §4.2.1
_CHECK_ORDER: list[tuple[str, str]] = [
    ("python_version", "core"),
    ("vapoursynth", "core"),
    ("lsmas", "core"),
    ("ffmpeg", "optional"),
    ("dovi_tool", "optional"),
    ("vspreview", "optional"),
    ("slowpics", "network"),
    ("tmdb_api_key", "network"),
]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of a diagnostic check.

    Attributes:
        passed: Whether the check passed
        message: Human-readable result message
        hint: Optional hint for failed checks
        details: Optional structured details
    """

    passed: bool
    message: str
    hint: str | None = None
    details: dict[str, JSONValue] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """Single diagnostic check.

    Attributes:
        name: Unique identifier for this check
        category: Check category ("core", "optional", "network")
        check_fn: Zero-argument callable returning CheckResult
    """

    name: str
    category: str
    check_fn: Callable[[], CheckResult]


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Complete diagnostic report.

    Attributes:
        checks: List of (check, result) tuples in execution order
        all_passed: True if ALL checks passed, regardless of category
        critical_failures: Names of failed core-category checks only
    """

    checks: list[tuple[DoctorCheck, CheckResult]]
    all_passed: bool
    critical_failures: list[str]


# ─── Check Implementations ────────────────────────────────────────────────────


def _import_vapoursynth() -> ModuleType:
    """Import VapourSynth, falling back to runtime-path registration on failure."""
    try:
        return __import__("vapoursynth")
    except ImportError:
        register_windows_dll_dirs()
        return __import__("vapoursynth")


def _candidate_lsmas_plugin_paths() -> list[str]:
    """Return candidate absolute paths for libvslsmashsource.dll."""
    candidates: list[str] = []
    plugin_env = os.environ.get("VAPOURSYNTH_PLUGIN_PATH", "")
    if plugin_env:
        for plugin_dir in plugin_env.split(os.pathsep):
            if plugin_dir:
                candidates.append(os.path.join(plugin_dir, "libvslsmashsource.dll"))

    python_dir = os.path.dirname(sys.executable)
    bundle_root = os.path.dirname(python_dir)
    candidates.append(os.path.join(bundle_root, "vs", "plugins", "libvslsmashsource.dll"))

    seen: set[str] = set()
    unique_candidates: list[str] = []
    for candidate in candidates:
        normalized = os.path.normcase(os.path.normpath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def _try_load_lsmas_plugin(core: object) -> str | None:
    """Try loading the bundled lsmas plugin and return loaded path, if any."""
    std_ns = getattr(core, "std", None)
    if std_ns is None:
        return None
    load_plugin = getattr(std_ns, "LoadPlugin", None)
    if not callable(load_plugin):
        return None

    for plugin_path in _candidate_lsmas_plugin_paths():
        if not os.path.isfile(plugin_path):
            continue
        load_plugin(path=plugin_path)
        return plugin_path
    return None


def _check_python_version() -> CheckResult:
    """Check Python version is >= 3.13 per ADR-001."""
    version = sys.version_info
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    if version >= (3, 13):
        return CheckResult(
            passed=True,
            message=f"Python {version_str}",
        )
    return CheckResult(
        passed=False,
        message=f"Python {version_str} (requires 3.13+)",
        hint="Upgrade to Python 3.13 or later",
        details={"current": version_str},
    )


def _check_vapoursynth() -> CheckResult:
    """Check VapourSynth is available."""
    try:
        _import_vapoursynth()
        return CheckResult(passed=True, message="VapourSynth available")
    except ImportError:
        return CheckResult(
            passed=False,
            message="VapourSynth not found",
            hint="Install VapourSynth (pip install VapourSynth)",
        )


def _check_lsmas() -> CheckResult:
    """Check L-SMASH-Works plugin is available."""
    try:
        vs = _import_vapoursynth()
        core = vs.core
        # Check for lsmas namespace (preferred) or lw (legacy)
        if hasattr(core, "lsmas") or hasattr(core, "lw"):
            namespace = "lsmas" if hasattr(core, "lsmas") else "lw"
            return CheckResult(
                passed=True,
                message=f"L-SMASH-Works plugin available ({namespace})",
                details={"namespace": namespace},
            )

        loaded_path = _try_load_lsmas_plugin(core)
        if loaded_path and (hasattr(core, "lsmas") or hasattr(core, "lw")):
            namespace = "lsmas" if hasattr(core, "lsmas") else "lw"
            return CheckResult(
                passed=True,
                message=f"L-SMASH-Works plugin available ({namespace})",
                details={"namespace": namespace, "plugin_path": loaded_path},
            )
        return CheckResult(
            passed=False,
            message="L-SMASH-Works plugin not found",
            hint="Install L-SMASH-Works VapourSynth plugin",
        )
    except ImportError:
        return CheckResult(
            passed=False,
            message="Cannot check lsmas (VapourSynth not available)",
            hint="Install VapourSynth first",
        )
    except Exception as e:
        return CheckResult(
            passed=False,
            message=f"lsmas check failed: {e}",
            hint="Check VapourSynth installation",
        )


def _check_ffmpeg() -> CheckResult:
    """Check FFmpeg is in PATH."""
    path = shutil.which("ffmpeg")
    if path:
        return CheckResult(
            passed=True,
            message=f"FFmpeg found at {path}",
            details={"path": path},
        )
    return CheckResult(
        passed=False,
        message="FFmpeg not found in PATH",
        hint="Install FFmpeg and add to PATH",
    )


def _check_dovi_tool() -> CheckResult:
    """Check dovi_tool is in PATH."""
    path = shutil.which("dovi_tool")
    if path:
        return CheckResult(
            passed=True,
            message=f"dovi_tool found at {path}",
            details={"path": path},
        )
    return CheckResult(
        passed=False,
        message="dovi_tool not found in PATH",
        hint="Install dovi_tool for Dolby Vision support",
    )


def _check_vspreview() -> CheckResult:
    """Check VSPreview is available.

    Uses frame_compare.vspreview.is_vspreview_available() for consistent detection.
    Per vspreview spec §6.1, this is an optional check that reports passed=True
    even when VSPreview is missing or the availability probe itself fails.
    """
    try:
        from frame_compare.vspreview.adapter import is_vspreview_available

        available = is_vspreview_available()
    except Exception as exc:
        return CheckResult(
            passed=True,
            message="VSPreview availability probe failed (optional for manual alignment)",
            hint="Check the VSPreview/PySide6 installation if interactive alignment is needed",
            details={
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            },
        )

    if available:
        return CheckResult(
            passed=True,
            message="VSPreview is available for interactive alignment",
        )
    return CheckResult(
        passed=True,  # Not a failure, just optional per spec §6.1
        message="VSPreview not installed (optional for manual alignment)",
        hint="Install with: pip install vspreview PySide6 (or: pip install vspreview PyQt5)",
    )


def _check_slowpics() -> CheckResult:
    """Check slow.pics reachability per SSOT §4.2.2.

    URL: https://slow.pics/
    Method: HEAD
    Timeout: 5.0 seconds
    Pass if status < 400; fail on status >= 400 or request errors.
    """
    url = "https://slow.pics/"
    timeout = 5.0

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.head(url)
            if response.status_code < 400:
                return CheckResult(
                    passed=True,
                    message="slow.pics reachable",
                    details={"status_code": response.status_code},
                )
            return CheckResult(
                passed=False,
                message=f"slow.pics returned status {response.status_code}",
                hint="slow.pics may be experiencing issues",
                details={"status_code": response.status_code},
            )
    except httpx.TimeoutException:
        return CheckResult(
            passed=False,
            message="slow.pics connection timed out",
            hint="Check internet connection",
            details={"timeout": timeout},
        )
    except httpx.RequestError as e:
        return CheckResult(
            passed=False,
            message=f"slow.pics connection failed: {e}",
            hint="Check internet connection",
        )


def _check_tmdb_api_key() -> CheckResult:
    """Check TMDB API key is configured (env var check only)."""
    if os.environ.get("FRAME_COMPARE_TMDB__API_KEY"):
        return CheckResult(
            passed=True,
            message="TMDB API key configured",
        )
    legacy_tmdb_env_var = "_".join(("TMDB", "API", "KEY"))
    if os.environ.get(legacy_tmdb_env_var):
        return CheckResult(
            passed=False,
            message="TMDB API key configured via legacy variable",
            hint=(
                "Set FRAME_COMPARE_TMDB__API_KEY; legacy TMDB API key alias is no longer supported"
            ),
        )
    return CheckResult(
        passed=False,
        message="TMDB API key not configured",
        hint="Set FRAME_COMPARE_TMDB__API_KEY environment variable",
    )


# ─── Public API ───────────────────────────────────────────────────────────────


def collect_checks() -> list[DoctorCheck]:
    """Collect all diagnostic checks in deterministic order per SSOT §4.2.1.

    Returns:
        List of DoctorCheck in canonical order:
        1. python_version (core)
        2. vapoursynth (core)
        3. lsmas (core)
        4. ffmpeg (optional)
        5. dovi_tool (optional)
        6. vspreview (optional)
        7. slowpics (network)
        8. tmdb_api_key (network)
    """
    check_fns: dict[str, Callable[[], CheckResult]] = {
        "python_version": _check_python_version,
        "vapoursynth": _check_vapoursynth,
        "lsmas": _check_lsmas,
        "ffmpeg": _check_ffmpeg,
        "dovi_tool": _check_dovi_tool,
        "vspreview": _check_vspreview,
        "slowpics": _check_slowpics,
        "tmdb_api_key": _check_tmdb_api_key,
    }

    return [
        DoctorCheck(name=name, category=category, check_fn=check_fns[name])
        for name, category in _CHECK_ORDER
    ]


def run_doctor(
    checks: list[DoctorCheck] | None = None,
    reporter: ProgressReporter | None = None,
) -> DoctorReport:
    """Execute diagnostic checks and report results.

    Args:
        checks: Specific checks to run (default: all from collect_checks())
        reporter: Progress reporter for output (optional)

    Returns:
        DoctorReport with all check results
    """
    if checks is None:
        checks = collect_checks()

    if reporter is not None:
        reporter.start_phase("doctor", total=len(checks))

    results: list[tuple[DoctorCheck, CheckResult]] = []
    critical_failures: list[str] = []

    for check in checks:
        try:
            result = check.check_fn()
        except Exception as e:
            result = CheckResult(
                passed=False,
                message=f"{check.name} check raised: {e}",
                details={
                    "exception_type": type(e).__name__,
                    "exception": str(e),
                },
            )
        results.append((check, result))

        # Track core category failures as critical
        if not result.passed and check.category == "core":
            critical_failures.append(check.name)

        if reporter is not None:
            reporter.advance(1)

    if reporter is not None:
        reporter.complete_phase()

    # all_passed is False if ANY check failed (regardless of category)
    all_passed = all(result.passed for _, result in results)

    return DoctorReport(
        checks=results,
        all_passed=all_passed,
        critical_failures=critical_failures,
    )
