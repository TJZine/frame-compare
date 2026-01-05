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
from frame_compare.orchestration.progress import select_reporter

__all__ = [
    # Context
    "ClipAlignmentState",
    "ClipFingerprint",
    "ClipProbeSnapshot",
    "ClipState",
    "ClipTrimState",
    "RunContext",
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
    # Progress
    "select_reporter",
]
