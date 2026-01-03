"""Orchestration module for Frame Compare 2.0.

This module coordinates the end-to-end comparison workflow, managing preflight checks,
phase execution, progress reporting, and error handling at the application level.
"""

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

__all__ = [
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
]
