"""Orchestration module for Frame Compare 2.0.

This module coordinates the end-to-end comparison workflow, managing preflight checks,
phase execution, progress reporting, and error handling at the application level.
"""

from frame_compare.orchestration.context import (
    ClipAlignmentState,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    ClipTrimState,
    RunContext,
)
from frame_compare.orchestration.coordinator import RunRequest, RunResult
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

__all__ = [
    # Context
    "ClipAlignmentState",
    "ClipFingerprint",
    "ClipProbeSnapshot",
    "ClipState",
    "ClipTrimState",
    "RunContext",
    # Coordinator
    "RunRequest",
    "RunResult",
    # Preflight
    "PreflightResult",
    "prepare_preflight",
    "resolve_workspace",
    "resolve_paths",
    "discover_inputs",
    # Doctor
    "CheckResult",
    "DoctorCheck",
    "DoctorReport",
    "collect_checks",
    "run_doctor",
    # Probe Cache
    "compute_probe_cache_key",
    # Probe Props
    "normalize_probe_prop_key",
    "compute_tonemap_prop_keys",
    "compute_preserved_frame_props",
    # Progress
    "select_reporter",
]
