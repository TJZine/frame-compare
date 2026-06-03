"""Implementation for the ``doctor`` CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

import typer
from rich.console import Console
from rich.markup import escape

from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.errors import FrameCompareError, JSONValue

if TYPE_CHECKING:
    from frame_compare.orchestration.doctor import DoctorCheck, DoctorReport
    from frame_compare.utils.progress_protocol import ProgressReporter

# Status icons matching legacy doctor output style.
_STATUS_ICONS = {
    True: "\u2705",  # ✅
    False: "\u274c",  # ❌
}
_OPTIONAL_STATUS_ICON = "-"


class RunDoctorFn(Protocol):
    def __call__(
        self,
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport: ...


class HandleErrorFn(Protocol):
    def __call__(
        self,
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int: ...


def handle_doctor(
    json_output: bool,
    *,
    run_doctor: RunDoctorFn,
    handle_error: HandleErrorFn,
) -> None:
    """Run dependency diagnostics."""
    try:
        report = run_doctor(checks=None, reporter=None)
    except FrameCompareError as error:
        if json_output:
            typer.echo(json.dumps(format_error_json(error), sort_keys=True, separators=(",", ":")))
            raise typer.Exit(code=int(get_exit_code(error))) from error
        raise typer.Exit(
            code=handle_error(
                error,
                no_color=True,
                verbose=False,
                verbose_hint=None,
            )
        ) from error

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
        "baseline_version": "R76",
        "checks": checks_payload,
    }
    payload: dict[str, JSONValue] = {
        "success": len(report.critical_failures) == 0,
        "doctor": doctor_payload,
    }
    return payload


def print_doctor_report(report: DoctorReport) -> None:
    """Print human-readable doctor results with styled icons and aligned labels."""
    console = Console()
    if not report.checks:
        return

    label_width = max(len(check.name) for check, _result in report.checks)
    critical_failures = set(report.critical_failures)
    for check, result in report.checks:
        icon = _doctor_status_icon(
            check_name=check.name,
            category=check.category,
            passed=result.passed,
            available=result.available,
            critical_failures=critical_failures,
        )
        padded_name = check.name.ljust(label_width)
        console.print(f"{icon} {escape(padded_name)} \u2014 {escape(result.message)}")
        if result.hint:
            console.print(f"   {''.ljust(label_width)}   [dim]Hint: {escape(result.hint)}[/]")


def _doctor_status_icon(
    *,
    check_name: str,
    category: str,
    passed: bool,
    available: bool | None,
    critical_failures: set[str],
) -> str:
    if check_name in critical_failures:
        return _STATUS_ICONS[False]
    if _is_optional_unavailable_status(
        check_name=check_name,
        category=category,
        available=available,
    ):
        return _OPTIONAL_STATUS_ICON
    if not passed and category == "optional":
        return _OPTIONAL_STATUS_ICON
    return _STATUS_ICONS.get(passed, "\u2022")


def _is_optional_unavailable_status(
    *,
    check_name: str,
    category: str,
    available: bool | None,
) -> bool:
    if category != "optional":
        return False
    if check_name != "vspreview":
        return False
    return available is not True
