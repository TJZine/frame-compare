"""Doctor check registry and diagnostic check implementations."""

from __future__ import annotations

import importlib.metadata
import subprocess
from collections.abc import Callable, Iterable, Mapping
from typing import cast

import httpx

from frame_compare.config.errors import ConfigParseError, ConfigValidationError
from frame_compare.config.loader import load_config
from frame_compare.errors import JSONValue
from frame_compare.orchestration.doctor_types import CheckResult, DoctorCheck
from frame_compare.orchestration.preflight import resolve_workspace
from frame_compare.services.metadata import is_valid_tmdb_api_key
from frame_compare.utils.subproc import resolve_executable, run_subprocess
from frame_compare.vs.env import (
    candidate_lsmas_plugin_path_details,
    import_vapoursynth_module,
    try_load_lsmas_plugin,
)
from frame_compare.vs.runtime_contract import (
    DEBIAN_FFMPEG_PACKAGE_VERSION,
    FFMS2_RELEASE,
    FFMS2_RUNTIME_VERSION,
    FFMS2_SOURCE_COMMIT,
    LSMASH_WORKS_PYPI_RELEASE,
    LSMASH_WORKS_RELEASE,
    LSMASH_WORKS_SOURCE_COMMIT,
    VAPOURSYNTH_API_MAJOR,
    VAPOURSYNTH_RELEASE,
    VS_PLACEBO_RELEASE,
    WINDOWS_FFMPEG_EXECUTABLE_TOKEN,
    WINDOWS_FFMPEG_RELEASE,
    runtime_ffms2_required,
    runtime_kind,
)

__all__ = ["SLOWPICS_HEALTHCHECK_URL", "collect_checks"]


# Canonical check ordering
_CHECK_ORDER: list[tuple[str, str]] = [
    ("vapoursynth", "core"),
    ("lsmas", "core"),
    ("vs_placebo", "optional"),
    ("ffms2", "optional"),
    ("ffmpeg", "optional"),
    ("vspreview", "optional"),
    ("slowpics", "network"),
    ("tmdb_api_key", "network"),
]

SLOWPICS_HEALTHCHECK_URL = "https://slow.pics/"
_LSMAS_REQUIRED_FUNCTIONS = ("LibavSMASHSource", "LWLibavSource")
# FFMS2's pinned C++ callback is named GetVersion internally, but VapourSynth
# registers the public function as Version. Keep the registered name here.
_FFMS2_REQUIRED_FUNCTIONS = ("Source", "Version")
_VS_PLACEBO_REQUIRED_FUNCTIONS = ("Tonemap",)


def _check_vapoursynth() -> CheckResult:
    """Check VapourSynth availability and report its public version identity."""
    try:
        vs = import_vapoursynth_module()
    except ImportError:
        return CheckResult(
            passed=False,
            message="VapourSynth not found",
            hint=(
                "Make VapourSynth importable; see "
                "https://github.com/TJZine/frame-compare#quick-start"
            ),
        )

    version = getattr(vs, "__version__", None)
    api_version = getattr(vs, "__api_version__", None)
    expected_major = int(VAPOURSYNTH_RELEASE.removeprefix("R"))
    expected_api_major = VAPOURSYNTH_API_MAJOR
    details: dict[str, JSONValue] = {
        "expected_release": VAPOURSYNTH_RELEASE,
        "expected_api_major": expected_api_major,
    }
    if version is None or api_version is None:
        details["observed_version"] = None if version is None else str(version)
        details["observed_release"] = None
        details["observed_api_version"] = None if api_version is None else str(api_version)
        return CheckResult(
            passed=False,
            available=True,
            message="VapourSynth available, but its release/API identity is unavailable",
            hint="Install the supported VapourSynth runtime, then rerun doctor",
            details=details,
        )

    details["observed_version"] = str(version)
    details["observed_api_version"] = str(api_version)
    for attribute in ("release_major", "release_minor"):
        value = getattr(version, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool):
            details[attribute] = value
    for attribute in ("api_major", "api_minor"):
        value = getattr(api_version, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool):
            details[attribute] = value
    release_major = details.get("release_major")
    api_major = details.get("api_major")
    release_matches = isinstance(release_major, int) and release_major == expected_major
    api_matches = isinstance(api_major, int) and api_major == expected_api_major
    details["observed_release"] = f"R{release_major}" if isinstance(release_major, int) else None
    details["expected_release_match"] = release_matches
    details["expected_api_match"] = api_matches
    if not release_matches or not api_matches:
        return CheckResult(
            passed=False,
            available=True,
            message=(
                f"VapourSynth {version} (API {api_version}) does not match the supported "
                f"{VAPOURSYNTH_RELEASE}/API {expected_api_major} runtime"
            ),
            hint="Install or reinstall the complete supported media runtime, then rerun doctor",
            details=details,
        )
    return CheckResult(
        passed=True,
        available=True,
        message=f"VapourSynth {version} (API {api_version})",
        details=details,
    )


def _lsmas_plugin_path_details() -> dict[str, JSONValue]:
    candidates = [
        {"source": candidate.source, "path": candidate.path}
        for candidate in candidate_lsmas_plugin_path_details()
    ]
    return {"checked_plugin_paths": cast(JSONValue, candidates)}


def _lsmas_setup_failure(error: Exception) -> CheckResult:
    return CheckResult(
        passed=False,
        message="lsmas check failed",
        hint=(
            "Check the VapourSynth/plugin setup, then rerun doctor; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        ),
        details={"exception_type": type(error).__name__},
    )


def _check_lsmas() -> CheckResult:
    """Check the supported L-SMASH-Works namespace and function surface."""
    try:
        vs = import_vapoursynth_module()
    except ImportError:
        return CheckResult(
            passed=False,
            message="Cannot check lsmas (VapourSynth not available)",
            hint=(
                "Make VapourSynth importable before checking L-SMASH-Works; "
                "see https://github.com/TJZine/frame-compare#quick-start"
            ),
        )
    except Exception as error:
        return _lsmas_setup_failure(error)

    try:
        core = vs.core
        namespace = "lsmas" if hasattr(core, "lsmas") else None
        loaded_path: str | None = None
        if namespace is None:
            loaded_path = try_load_lsmas_plugin(core)
            namespace = "lsmas" if hasattr(core, "lsmas") else None

        if namespace is None:
            return CheckResult(
                passed=False,
                message="L-SMASH-Works plugin not found in core.lsmas namespace",
                hint=(
                    "Make L-SMASH-Works available under core.lsmas; see "
                    "https://github.com/TJZine/frame-compare#quick-start"
                ),
                details=_lsmas_plugin_path_details(),
            )

        plugin = getattr(core, namespace)
        details = _lsmas_runtime_details(
            core,
            namespace=namespace,
            plugin_path=loaded_path,
        )
        missing_functions = _plugin_missing_functions(plugin, _LSMAS_REQUIRED_FUNCTIONS)
        if missing_functions:
            details["missing_functions"] = cast(JSONValue, missing_functions)
            return CheckResult(
                passed=False,
                available=True,
                message="L-SMASH-Works plugin is missing required source functions",
                hint="Install or reinstall the complete supported media runtime, then rerun doctor",
                details=details,
            )
        return CheckResult(
            passed=True,
            available=True,
            message=(
                "L-SMASH-Works required source functions available "
                f"(core.{namespace}; native version is not observable)"
            ),
            details=details,
        )
    except Exception as error:
        return _lsmas_setup_failure(error)


def _plugin_function_names(plugin: object) -> list[str]:
    functions = getattr(plugin, "functions", None)
    if not callable(functions):
        return []
    try:
        raw_functions = functions()
    except Exception:
        return []
    if not isinstance(raw_functions, Iterable) or isinstance(raw_functions, str | bytes):
        return []
    return sorted(
        name
        for function in cast(Iterable[object], raw_functions)
        if isinstance((name := getattr(function, "name", None)), str)
    )


def _plugin_missing_functions(plugin: object, required: tuple[str, ...]) -> list[str]:
    discovered = set(_plugin_function_names(plugin))
    return [
        name
        for name in required
        if name not in discovered and not callable(getattr(plugin, name, None))
    ]


def _plugin_version_string(plugin: object) -> str | None:
    version_fn = getattr(plugin, "Version", None)
    if not callable(version_fn):
        return None
    try:
        result = version_fn()
    except Exception:
        return None

    value: object = result
    if isinstance(result, Mapping):
        version_mapping = cast(Mapping[object, object], result)
        value = version_mapping.get("version")
    else:
        value = getattr(result, "version", result)

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return value if isinstance(value, str) else None


def _lsmas_runtime_details(
    core: object,
    *,
    namespace: str,
    plugin_path: str | None = None,
) -> dict[str, JSONValue]:
    details: dict[str, JSONValue] = {
        "namespace": namespace,
        "expected_native_release": LSMASH_WORKS_RELEASE,
        "expected_windows_distribution_version": LSMASH_WORKS_PYPI_RELEASE,
        "expected_source_commit": LSMASH_WORKS_SOURCE_COMMIT,
        "runtime_version_observable": False,
        "runtime_identity_status": "unverifiable",
        "required_functions": cast(JSONValue, list(_LSMAS_REQUIRED_FUNCTIONS)),
    }
    plugin = getattr(core, namespace, None)
    functions = _plugin_function_names(plugin)
    if functions:
        details["functions"] = cast(JSONValue, functions)
    if plugin_path is not None:
        details["plugin_path"] = plugin_path
    return details


def _check_vs_placebo() -> CheckResult:
    """Report the vs-placebo distribution and registered plugin surface."""
    details: dict[str, JSONValue] = {
        "expected_distribution_version": VS_PLACEBO_RELEASE,
        "observed_available": False,
    }
    try:
        observed_distribution = importlib.metadata.version("vs-placebo")
    except importlib.metadata.PackageNotFoundError:
        observed_distribution = None
    except Exception as error:
        details["distribution_probe_exception_type"] = type(error).__name__
        observed_distribution = None
    details["observed_distribution_version"] = observed_distribution
    details["expected_distribution_match"] = observed_distribution == VS_PLACEBO_RELEASE

    try:
        vs = import_vapoursynth_module()
        plugin = getattr(vs.core, "placebo", None)
        missing_functions = (
            _plugin_missing_functions(plugin, _VS_PLACEBO_REQUIRED_FUNCTIONS)
            if plugin is not None
            else list(_VS_PLACEBO_REQUIRED_FUNCTIONS)
        )
        available = plugin is not None and not missing_functions
        functions = _plugin_function_names(plugin) if plugin is not None else []
    except ImportError:
        return CheckResult(
            passed=False,
            available=False,
            message="Cannot check vs-placebo (VapourSynth not available)",
            details=details,
        )
    except Exception as error:
        details["exception_type"] = type(error).__name__
        return CheckResult(
            passed=False,
            available=False,
            message="vs-placebo check failed",
            hint="Repair the supported media runtime, then rerun doctor",
            details=details,
        )

    details["observed_available"] = available
    if functions:
        details["functions"] = cast(JSONValue, functions)
    if plugin is not None and missing_functions:
        details["missing_functions"] = cast(JSONValue, missing_functions)
    if not available:
        return CheckResult(
            passed=False,
            available=False,
            message=(
                "vs-placebo plugin is missing placebo.Tonemap"
                if plugin is not None
                else "vs-placebo plugin not available"
            ),
            hint="Install the supported vs-placebo wheel or use a complete Frame Compare runtime",
            details=details,
        )
    if observed_distribution != VS_PLACEBO_RELEASE:
        observed_label = observed_distribution or "unavailable"
        return CheckResult(
            passed=False,
            available=True,
            message=(
                "vs-placebo plugin available, but distribution version "
                f"{observed_label} does not match {VS_PLACEBO_RELEASE}"
            ),
            hint="Install or reinstall the complete supported media runtime, then rerun doctor",
            details=details,
        )
    return CheckResult(
        passed=True,
        available=True,
        message=f"vs-placebo {VS_PLACEBO_RELEASE} available (placebo.Tonemap)",
        details=details,
    )


def _check_ffms2() -> CheckResult:
    """Report FFMS2 availability and enforce the active runtime policy."""
    selected_runtime_kind = runtime_kind().casefold()
    # Docker's supported media stack always includes FFMS2.  Keep the
    # deployment-kind policy authoritative so an absent, false, or malformed
    # requirement declaration cannot make a partial Docker runtime look valid.
    required = selected_runtime_kind == "docker" or runtime_ffms2_required()
    details: dict[str, JSONValue] = {
        "expected_release": FFMS2_RELEASE,
        "expected_runtime_version": FFMS2_RUNTIME_VERSION,
        "expected_source_commit": FFMS2_SOURCE_COMMIT,
        "required_functions": cast(JSONValue, list(_FFMS2_REQUIRED_FUNCTIONS)),
        "windows_baseline": "excluded",
        "docker_runtime": "included",
        "current_runtime_kind": selected_runtime_kind,
        "required_in_current_runtime": required,
        "observed_available": False,
    }
    try:
        vs = import_vapoursynth_module()
        plugin = getattr(vs.core, "ffms2", None)
    except ImportError:
        return CheckResult(
            passed=not required,
            available=False,
            message=(
                "FFMS2 cannot be checked because VapourSynth is unavailable"
                if required
                else "FFMS2 not checked (VapourSynth unavailable; optional on Windows)"
            ),
            hint=(
                "Repair the complete Docker media runtime, then rerun doctor" if required else None
            ),
            details=details,
        )
    except Exception as error:
        details["exception_type"] = type(error).__name__
        return CheckResult(
            passed=not required,
            available=False,
            message="FFMS2 check failed",
            hint="Repair the supported media runtime, then rerun doctor" if required else None,
            details=details,
        )

    missing_functions = (
        _plugin_missing_functions(plugin, _FFMS2_REQUIRED_FUNCTIONS)
        if plugin is not None
        else list(_FFMS2_REQUIRED_FUNCTIONS)
    )
    available = plugin is not None and not missing_functions
    functions = _plugin_function_names(plugin) if plugin is not None else []
    details["observed_available"] = available
    if functions:
        details["functions"] = cast(JSONValue, functions)
    if plugin is not None and missing_functions:
        details["missing_functions"] = cast(JSONValue, missing_functions)
    if plugin is not None and selected_runtime_kind == "windows-portable":
        return CheckResult(
            passed=False,
            available=available,
            message="FFMS2 is loaded, but the Windows portable baseline excludes it",
            hint="Reinstall the complete supported Windows portable runtime, then rerun doctor",
            details=details,
        )
    if not available:
        return CheckResult(
            passed=not required,
            available=False,
            message=(
                "FFMS2 plugin not available with Source and Version "
                "(required by this Docker runtime)"
                if required
                else "FFMS2 not loaded (expected for the Windows baseline; required in Docker)"
            ),
            hint=(
                "Repair the complete Docker media runtime, then rerun doctor" if required else None
            ),
            details=details,
        )

    observed_version = _plugin_version_string(plugin)
    details["observed_runtime_version"] = observed_version
    details["expected_runtime_version_match"] = observed_version == FFMS2_RUNTIME_VERSION
    if observed_version != FFMS2_RUNTIME_VERSION:
        return CheckResult(
            passed=not required,
            available=True,
            message=(
                "FFMS2 plugin available, but runtime version "
                f"{observed_version or 'unavailable'} does not match {FFMS2_RUNTIME_VERSION}"
            ),
            hint=(
                "Repair the complete Docker media runtime, then rerun doctor" if required else None
            ),
            details=details,
        )
    return CheckResult(
        passed=True,
        available=True,
        message=f"FFMS2 {observed_version} available (ffms2.Source)",
        details=details,
    )


def _check_ffmpeg() -> CheckResult:
    """Check FFmpeg and ffprobe executables and report their actual versions."""
    details: dict[str, JSONValue] = {
        "windows_supported_release": WINDOWS_FFMPEG_RELEASE,
        "windows_license_profile": "LGPL-only",
        "linux_policy": "Debian Trixie supported packages",
    }
    resolved: dict[str, str] = {}
    for executable in ("ffmpeg", "ffprobe"):
        try:
            resolved[executable] = resolve_executable(executable)
        except FileNotFoundError:
            return CheckResult(
                passed=False,
                message=f"{executable} not found in the configured runtime",
                hint=(
                    "Provide FFmpeg and ffprobe executables; see "
                    "https://github.com/TJZine/frame-compare#requirements"
                ),
                details=details,
            )

    for executable, executable_path in resolved.items():
        details[f"{executable}_path"] = executable_path
        try:
            completed = run_subprocess(
                [executable_path, "-version"],
                timeout_seconds=5.0,
            )
        except (OSError, subprocess.SubprocessError) as error:
            details["exception_type"] = type(error).__name__
            return CheckResult(
                passed=False,
                message=f"{executable} at {executable_path} could not report its version",
                hint="Repair or replace the FFmpeg runtime, then rerun doctor",
                details=details,
            )
        lines = completed.stdout.decode("utf-8", errors="replace").splitlines()
        details[f"{executable}_version_line"] = lines[0] if lines else ""

    ffmpeg_version_line = str(details["ffmpeg_version_line"])
    selected_runtime_kind = runtime_kind().casefold()
    expected_fragment: str | None = None
    if selected_runtime_kind == "windows-portable":
        expected_fragment = WINDOWS_FFMPEG_EXECUTABLE_TOKEN
    elif selected_runtime_kind == "docker":
        _, separator, remainder = DEBIAN_FFMPEG_PACKAGE_VERSION.partition(":")
        expected_fragment = remainder if separator and remainder else DEBIAN_FFMPEG_PACKAGE_VERSION
    details["current_runtime_kind"] = selected_runtime_kind
    details["expected_version_fragment"] = expected_fragment
    if expected_fragment is not None:
        version_matches = all(
            expected_fragment in str(details[f"{executable}_version_line"]).split()
            for executable in ("ffmpeg", "ffprobe")
        )
        details["expected_version_match"] = version_matches
        if not version_matches:
            return CheckResult(
                passed=False,
                available=True,
                message=(
                    "FFmpeg executables do not match the selected managed runtime "
                    f"version {expected_fragment}"
                ),
                hint="Repair or reinstall the complete supported media runtime, then rerun doctor",
                details=details,
            )
    return CheckResult(
        passed=True,
        message=ffmpeg_version_line or f"FFmpeg found at {resolved['ffmpeg']}",
        details=details,
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
                hint="Review the returned HTTP status before retrying",
                details={"status_code": response.status_code},
            )
    except httpx.TimeoutException:
        return CheckResult(
            passed=False,
            message="slow.pics connection timed out",
            hint="Check network access to slow.pics, then retry",
            details={"timeout": timeout},
        )
    except httpx.RequestError as e:
        return CheckResult(
            passed=False,
            message=f"slow.pics connection failed: {e}",
            hint="Review the request failure and network path to slow.pics before retrying",
        )


def _check_tmdb_api_key() -> CheckResult:
    """Check TMDB API key is configured through the normal runtime config chain."""
    tmdb_enabled, resolved_api_key, config_error = _resolve_tmdb_config()

    if config_error is not None:
        return CheckResult(
            passed=False,
            message="TMDB configuration could not be loaded",
            hint=_tmdb_config_error_hint(config_error),
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
                hint="Replace the TMDB credential with a 32-character hexadecimal API key",
            )
        return CheckResult(
            passed=True,
            message="TMDB API key configured",
        )

    return CheckResult(
        passed=False,
        message="TMDB API key not configured",
        hint="Set FRAME_COMPARE_TMDB__API_KEY or tmdb.api_key in config/config.toml",
    )


def _tmdb_config_error_hint(config_error: dict[str, JSONValue]) -> str:
    if config_error.get("exception_type") == "ConfigParseError":
        return "Fix config/config.toml syntax, then rerun doctor"
    return "Fix the reported config/environment validation errors, then rerun doctor"


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
        1. vapoursynth (core)
        2. lsmas (core)
        3. vs_placebo (optional)
        4. ffms2 (optional)
        5. ffmpeg (optional)
        6. vspreview (optional)
        7. slowpics (network)
        8. tmdb_api_key (network)
    """
    check_fns: dict[str, Callable[[], CheckResult]] = {
        "vapoursynth": _check_vapoursynth,
        "lsmas": _check_lsmas,
        "vs_placebo": _check_vs_placebo,
        "ffms2": _check_ffms2,
        "ffmpeg": _check_ffmpeg,
        "vspreview": _check_vspreview,
        "slowpics": _check_slowpics,
        "tmdb_api_key": _check_tmdb_api_key,
    }
    managed_runtime = runtime_kind().casefold() in {"docker", "windows-portable"}

    return [
        DoctorCheck(
            name=name,
            category=category,
            check_fn=check_fns[name],
            critical_if_failed=managed_runtime and name in {"ffms2", "ffmpeg"},
        )
        for name, category in _CHECK_ORDER
    ]
