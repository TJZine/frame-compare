"""Implementation for the ``doctor`` CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol, cast

import typer
from rich.console import Console
from rich.markup import escape

from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.errors import FrameCompareError, JSONValue

from .cli_helpers import HandleErrorFn

if TYPE_CHECKING:
    from frame_compare.orchestration.doctor import DoctorCheck, DoctorReport
    from frame_compare.utils.progress_protocol import ProgressReporter

# Status icons matching legacy doctor output style.
_STATUS_ICONS = {
    True: "\u2705",  # ✅
    False: "\u274c",  # ❌
}
_OPTIONAL_STATUS_ICON = "-"
_WARNING_STATUS_ICON = "\u26a0"  # ⚠


class RunDoctorFn(Protocol):
    def __call__(
        self,
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport: ...


def handle_doctor(
    json_output: bool,
    *,
    run_doctor: RunDoctorFn,
    handle_error: HandleErrorFn,
    no_color: bool,
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
                no_color=no_color,
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
    # Keep media-runtime imports on the doctor execution path. Importing the
    # root CLI must remain side-effect-free for dry-run and help commands.
    from frame_compare.vs.runtime_contract import (
        VAPOURSYNTH_RELEASE,
        runtime_environment_report,
        supported_media_runtime_report,
    )

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
        "baseline_version": VAPOURSYNTH_RELEASE,
        "media_runtime": cast(JSONValue, supported_media_runtime_report()),
        "runtime_environment": runtime_environment_report(),
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

    noncritical_failures = [
        check.name
        for check, result in report.checks
        if not result.passed and check.name not in critical_failures
    ]
    console.print()
    if critical_failures:
        console.print("[red]Core runtime is not ready; resolve required checks above.[/]")
    elif noncritical_failures:
        console.print(
            "[yellow]Core runtime checks passed; optional or network checks need attention.[/]"
        )
    else:
        console.print("[green]Core runtime checks passed.[/]")


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
    if not passed:
        return _OPTIONAL_STATUS_ICON if category == "optional" else _WARNING_STATUS_ICON
    return _STATUS_ICONS.get(passed, "\u2022")


def _is_optional_unavailable_status(
    *,
    check_name: str,
    category: str,
    available: bool | None,
) -> bool:
    if category != "optional":
        return False
    return available is False
