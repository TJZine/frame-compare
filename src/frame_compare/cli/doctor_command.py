"""Implementation for the ``doctor`` CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

import typer

from frame_compare.cli.errors import ExitCode
from frame_compare.errors import JSONValue

if TYPE_CHECKING:
    from frame_compare.orchestration.doctor import DoctorCheck, DoctorReport
    from frame_compare.utils.progress_protocol import ProgressReporter


class RunDoctorFn(Protocol):
    def __call__(
        self,
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport: ...


def handle_doctor(json_output: bool, *, run_doctor: RunDoctorFn) -> None:
    """Run dependency diagnostics."""
    report = run_doctor(checks=None, reporter=None)
    if json_output:
        payload = doctor_report_json(report)
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print_doctor_report(report)

    if report.critical_failures:
        raise typer.Exit(code=int(ExitCode.DEPENDENCY_ERROR))


def doctor_report_json(report: DoctorReport) -> dict[str, JSONValue]:
    """Convert DoctorReport to JSON payload per schema."""
    checks_payload: list[JSONValue] = []
    for check, result in report.checks:
        entry: dict[str, JSONValue] = {
            "id": check.name,
            "category": check.category,
            "status": "pass" if result.passed else "fail",
            "message": result.message,
        }
        if result.hint:
            entry["install_hint"] = result.hint
        if result.details:
            entry["details"] = result.details
        checks_payload.append(entry)

    doctor_payload: dict[str, JSONValue] = {
        "baseline_version": "R73",
        "checks": checks_payload,
    }
    payload: dict[str, JSONValue] = {
        "success": len(report.critical_failures) == 0,
        "doctor": doctor_payload,
    }
    return payload


def print_doctor_report(report: DoctorReport) -> None:
    """Print human-readable doctor results."""
    for check, result in report.checks:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {check.name}: {result.message}")
        if result.hint:
            typer.echo(f"  Hint: {result.hint}")
