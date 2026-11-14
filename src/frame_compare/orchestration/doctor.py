"""Diagnostic execution surface for Frame Compare."""

from __future__ import annotations

from frame_compare.orchestration.doctor_checks import collect_checks
from frame_compare.orchestration.doctor_types import (
    CheckResult,
    DoctorCheck,
    DoctorConfigSelection,
    DoctorReport,
)

__all__ = [
    "CheckResult",
    "DoctorCheck",
    "DoctorReport",
    "collect_checks",
    "run_doctor",
]


def run_doctor(
    checks: list[DoctorCheck] | None = None,
    selection: DoctorConfigSelection | None = None,
) -> DoctorReport:
    """Execute diagnostic checks and report results.

    Args:
        checks: Specific checks to run (default: all from collect_checks())
        selection: Workspace and config selection for the default checks

    Returns:
        DoctorReport with all check results
    """
    if checks is None:
        checks = collect_checks(selection)

    results: list[tuple[DoctorCheck, CheckResult]] = []
    critical_failures: list[str] = []

    for check in checks:
        try:
            result = check.check_fn()
        except Exception as error:
            result = CheckResult(
                passed=False,
                message=f"{check.name} check failed",
                details={"exception_type": type(error).__name__},
            )
        results.append((check, result))

        # Core checks are always critical. Managed runtimes may also promote a
        # profile-specific policy check without changing its public category.
        if not result.passed and (check.category == "core" or check.critical_if_failed):
            critical_failures.append(check.name)

    return DoctorReport(
        checks=results,
        critical_failures=critical_failures,
    )
