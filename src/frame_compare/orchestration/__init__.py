"""Orchestration public API.

Exports are resolved lazily to avoid importing VS-dependent modules when
consumers only need lightweight surfaces (for example `doctor` checks).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frame_compare.orchestration.context import (
        ClipAlignmentState,
        ClipFingerprint,
        ClipProbeSnapshot,
        ClipState,
        ClipTrimState,
        RunContext,
    )
    from frame_compare.orchestration.coordinator import (
        RunDependencies,
        RunRequest,
        RunResult,
        execute_run,
    )
    from frame_compare.orchestration.doctor import (
        CheckResult,
        DoctorCheck,
        DoctorReport,
        collect_checks,
        run_doctor,
    )
    from frame_compare.orchestration.preflight import (
        PreflightResult,
        discover_inputs,
        prepare_preflight,
        resolve_paths,
        resolve_workspace,
    )
    from frame_compare.orchestration.probe_cache import compute_probe_cache_key
    from frame_compare.orchestration.probe_props import (
        compute_preserved_frame_props,
        compute_tonemap_prop_keys,
        normalize_probe_prop_key,
    )
    from frame_compare.orchestration.progress import select_reporter

_EXPORTS: dict[str, tuple[str, str]] = {
    # Context
    "ClipAlignmentState": ("frame_compare.orchestration.context", "ClipAlignmentState"),
    "ClipFingerprint": ("frame_compare.orchestration.context", "ClipFingerprint"),
    "ClipProbeSnapshot": ("frame_compare.orchestration.context", "ClipProbeSnapshot"),
    "ClipState": ("frame_compare.orchestration.context", "ClipState"),
    "ClipTrimState": ("frame_compare.orchestration.context", "ClipTrimState"),
    "RunContext": ("frame_compare.orchestration.context", "RunContext"),
    # Coordinator
    "RunDependencies": ("frame_compare.orchestration.coordinator", "RunDependencies"),
    "RunRequest": ("frame_compare.orchestration.coordinator", "RunRequest"),
    "RunResult": ("frame_compare.orchestration.coordinator", "RunResult"),
    "execute_run": ("frame_compare.orchestration.coordinator", "execute_run"),
    # Preflight
    "PreflightResult": ("frame_compare.orchestration.preflight", "PreflightResult"),
    "prepare_preflight": ("frame_compare.orchestration.preflight", "prepare_preflight"),
    "resolve_workspace": ("frame_compare.orchestration.preflight", "resolve_workspace"),
    "resolve_paths": ("frame_compare.orchestration.preflight", "resolve_paths"),
    "discover_inputs": ("frame_compare.orchestration.preflight", "discover_inputs"),
    # Doctor
    "CheckResult": ("frame_compare.orchestration.doctor", "CheckResult"),
    "DoctorCheck": ("frame_compare.orchestration.doctor", "DoctorCheck"),
    "DoctorReport": ("frame_compare.orchestration.doctor", "DoctorReport"),
    "collect_checks": ("frame_compare.orchestration.doctor", "collect_checks"),
    "run_doctor": ("frame_compare.orchestration.doctor", "run_doctor"),
    # Probe Cache
    "compute_probe_cache_key": (
        "frame_compare.orchestration.probe_cache",
        "compute_probe_cache_key",
    ),
    # Probe Props
    "normalize_probe_prop_key": (
        "frame_compare.orchestration.probe_props",
        "normalize_probe_prop_key",
    ),
    "compute_tonemap_prop_keys": (
        "frame_compare.orchestration.probe_props",
        "compute_tonemap_prop_keys",
    ),
    "compute_preserved_frame_props": (
        "frame_compare.orchestration.probe_props",
        "compute_preserved_frame_props",
    ),
    # Progress
    "select_reporter": ("frame_compare.orchestration.progress", "select_reporter"),
}

__all__ = (
    "ClipAlignmentState",
    "ClipFingerprint",
    "ClipProbeSnapshot",
    "ClipState",
    "ClipTrimState",
    "RunContext",
    "RunDependencies",
    "RunRequest",
    "RunResult",
    "execute_run",
    "PreflightResult",
    "prepare_preflight",
    "resolve_workspace",
    "resolve_paths",
    "discover_inputs",
    "CheckResult",
    "DoctorCheck",
    "DoctorReport",
    "collect_checks",
    "run_doctor",
    "compute_probe_cache_key",
    "normalize_probe_prop_key",
    "compute_tonemap_prop_keys",
    "compute_preserved_frame_props",
    "select_reporter",
)


def __getattr__(name: str) -> Any:
    export = _EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = export
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
