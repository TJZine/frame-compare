"""Diagnostic execution surface for Frame Compare."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from frame_compare.orchestration.doctor_checks import collect_checks
from frame_compare.orchestration.doctor_types import CheckResult, DoctorCheck, DoctorReport

if TYPE_CHECKING:
    from frame_compare.utils.progress_protocol import ProgressReporter

__all__ = [
    "CheckResult",
    "DoctorCheck",
    "DoctorReport",
    "collect_checks",
    "run_doctor",
]

log = structlog.get_logger()


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
        except Exception as error:
            log.debug(
                "doctor_check_failed",
                check=check.name,
                exception_type=type(error).__name__,
                exc_info=True,
            )
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

        if reporter is not None:
            reporter.advance(1)

    if reporter is not None:
        reporter.complete_phase()

    all_passed = all(result.passed for _, result in results)

    return DoctorReport(
        checks=results,
        all_passed=all_passed,
        critical_failures=critical_failures,
    )
