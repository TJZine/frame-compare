"""Doctor check registry and diagnostic check implementations."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from typing import cast

import httpx

from frame_compare.config.errors import ConfigParseError, ConfigValidationError
from frame_compare.config.loader import load_config
from frame_compare.errors import JSONValue
from frame_compare.orchestration.doctor_types import CheckResult, DoctorCheck
from frame_compare.orchestration.preflight import resolve_workspace
from frame_compare.services.metadata import is_valid_tmdb_api_key
from frame_compare.vs.env import (
    candidate_lsmas_plugin_path_details,
    import_vapoursynth_module,
    try_load_lsmas_plugin,
)

__all__ = ["SLOWPICS_HEALTHCHECK_URL", "collect_checks"]


# Canonical check ordering
_CHECK_ORDER: list[tuple[str, str]] = [
    ("python_version", "core"),
    ("vapoursynth", "core"),
    ("lsmas", "core"),
    ("ffmpeg", "optional"),
    ("vspreview", "optional"),
    ("slowpics", "network"),
    ("tmdb_api_key", "network"),
]

SLOWPICS_HEALTHCHECK_URL = "https://slow.pics/"


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
        import_vapoursynth_module()
        return CheckResult(passed=True, message="VapourSynth available")
    except ImportError:
        return CheckResult(
            passed=False,
            message="VapourSynth not found",
            hint="Install VapourSynth (pip install VapourSynth)",
        )


def _lsmas_plugin_path_details() -> dict[str, JSONValue]:
    candidates = [
        {"source": candidate.source, "path": candidate.path}
        for candidate in candidate_lsmas_plugin_path_details()
    ]
    return {"checked_plugin_paths": cast(JSONValue, candidates)}


def _check_lsmas() -> CheckResult:
    """Check L-SMASH-Works plugin is available."""
    try:
        vs = import_vapoursynth_module()
        core = vs.core
        # Check for lsmas namespace (preferred) or lw (legacy)
        if hasattr(core, "lsmas") or hasattr(core, "lw"):
            namespace = "lsmas" if hasattr(core, "lsmas") else "lw"
            return CheckResult(
                passed=True,
                message=f"L-SMASH-Works plugin available ({namespace})",
                details={"namespace": namespace},
            )

        loaded_path = try_load_lsmas_plugin(core)
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
            details=_lsmas_plugin_path_details(),
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
            message="lsmas check failed",
            hint="Check VapourSynth installation",
            details={"exception_type": type(e).__name__},
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


def _check_vspreview() -> CheckResult:
    """Check VSPreview is available.

    Uses frame_compare.vspreview.adapter.check_vspreview_availability() for consistent detection.
    Per vspreview spec §6.1, this is an optional check that reports passed=True
    even when VSPreview is missing or the availability probe itself fails.
    """
    from frame_compare.vspreview.adapter import (
        VSPreviewAvailabilityStatus,
        check_vspreview_availability,
    )

    availability = check_vspreview_availability()

    if availability.is_available:
        return CheckResult(
            passed=True,
            message="VSPreview is available for interactive alignment",
            available=True,
        )

    if availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        return CheckResult(
            passed=True,
            message=availability.message,
            available=False,
            hint=availability.hint,
            details=cast(dict[str, JSONValue], availability.public_probe_failure_details()),
        )

    return CheckResult(
        passed=True,  # Not a failure, just optional per spec §6.1
        message=availability.message,
        available=False,
        hint=availability.hint,
    )


def _check_slowpics() -> CheckResult:
    """Check slow.pics reachability per docs/current-architecture.md.

    URL: SLOWPICS_HEALTHCHECK_URL
    Method: HEAD
    Timeout: 5.0 seconds
    Pass if status < 400; fail on status >= 400 or request errors.
    """
    timeout = 5.0

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.head(SLOWPICS_HEALTHCHECK_URL)
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
    """Check TMDB API key is configured through the normal runtime config chain."""
    legacy_tmdb_env_var = "_".join(("TMDB", "API", "KEY"))
    tmdb_enabled, resolved_api_key, config_error = _resolve_tmdb_config()

    if config_error is not None:
        return CheckResult(
            passed=False,
            message="TMDB configuration could not be loaded",
            hint="Fix config/config.toml or set FRAME_COMPARE_TMDB__API_KEY",
            details=config_error,
        )

    if tmdb_enabled is False:
        return CheckResult(
            passed=True,
            message="TMDB metadata lookup disabled",
            details={"enabled": False},
        )

    if resolved_api_key:
        if not is_valid_tmdb_api_key(resolved_api_key):
            return CheckResult(
                passed=False,
                message="TMDB API key has invalid format",
                hint="Set a 32-character hexadecimal TMDB API key",
            )
        return CheckResult(
            passed=True,
            message="TMDB API key configured",
        )

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
        hint="Set FRAME_COMPARE_TMDB__API_KEY or tmdb.api_key in config/config.toml",
    )


def _resolve_tmdb_config() -> tuple[bool | None, str | None, dict[str, JSONValue] | None]:
    """Resolve TMDB enablement and credentials through the runtime config path."""
    root = resolve_workspace(None)
    config_path = root / "config" / "config.toml"
    effective_config_path = config_path if config_path.exists() else None

    try:
        config = load_config(effective_config_path)
    except ConfigParseError as exc:
        details: dict[str, JSONValue] = {
            "config_file": str(config_path),
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        }
        return None, None, details
    except ConfigValidationError as exc:
        details: dict[str, JSONValue] = {
            "config_file": str(config_path),
            "exception_type": type(exc).__name__,
            "validation_errors": cast(JSONValue, exc.validation_errors),
        }
        return None, None, details

    return config.tmdb.enabled, config.tmdb.api_key, None


def collect_checks() -> list[DoctorCheck]:
    """Collect all diagnostic checks in deterministic order.

    Returns:
        List of DoctorCheck in canonical order:
        1. python_version (core)
        2. vapoursynth (core)
        3. lsmas (core)
        4. ffmpeg (optional)
        5. vspreview (optional)
        6. slowpics (network)
        7. tmdb_api_key (network)
    """
    check_fns: dict[str, Callable[[], CheckResult]] = {
        "python_version": _check_python_version,
        "vapoursynth": _check_vapoursynth,
        "lsmas": _check_lsmas,
        "ffmpeg": _check_ffmpeg,
        "vspreview": _check_vspreview,
        "slowpics": _check_slowpics,
        "tmdb_api_key": _check_tmdb_api_key,
    }

    return [
        DoctorCheck(name=name, category=category, check_fn=check_fns[name])
        for name, category in _CHECK_ORDER
    ]
