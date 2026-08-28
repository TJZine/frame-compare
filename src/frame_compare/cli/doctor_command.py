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

_DOCTOR_DISPLAY_LABELS = {
    "vapoursynth": "VapourSynth",
    "lsmas": "L-SMASH-Works",
    "vs_placebo": "vs-placebo",
    "ffms2": "FFMS2",
    "ffmpeg": "FFmpeg",
    "vspreview": "VSPreview",
    "slowpics": "slow.pics",
    "tmdb_api_key": "TMDB API key",
}
_DOCTOR_GROUPS = (
    ("core", "Required"),
    ("optional", "Optional"),
    ("network", "Network and credentials"),
)


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
    """Print the readiness outcome and grouped human-readable doctor results."""
    console = Console()
    critical_failures = set(report.critical_failures)
    needs_attention = any(
        check.name not in critical_failures
        and (not result.passed or (check.category == "optional" and result.available is False))
        for check, result in report.checks
    )
    if critical_failures:
        readiness_status = "FAIL"
        readiness_message = "Runtime is not ready for comparisons."
    elif needs_attention:
        readiness_status = "WARN"
        readiness_message = (
            "Ready for local comparisons; optional or network checks need attention."
        )
    else:
        readiness_status = "OK"
        readiness_message = "Runtime is ready for comparisons."

    console.print(f"{_doctor_status_marker(readiness_status)} {readiness_message}")

    for category, heading in _DOCTOR_GROUPS:
        grouped_checks = [
            (check, result) for check, result in report.checks if check.category == category
        ]
        if not grouped_checks:
            continue

        console.print()
        console.print(escape(heading))
        for check, result in grouped_checks:
            status = _doctor_status(
                check_name=check.name,
                category=check.category,
                passed=result.passed,
                available=result.available,
                critical_failures=critical_failures,
            )
            label = _doctor_display_label(check.name)
            console.print(
                f"  {_doctor_status_marker(status)} {escape(label)} — {escape(result.message)}"
            )
            if result.hint:
                console.print(f"    Hint: {escape(result.hint)}")


def _doctor_display_label(check_name: str) -> str:
    return _DOCTOR_DISPLAY_LABELS.get(check_name, check_name.replace("_", " "))


def _doctor_status(
    *,
    check_name: str,
    category: str,
    passed: bool,
    available: bool | None,
    critical_failures: set[str],
) -> str:
    if check_name in critical_failures:
        return "FAIL"
    if not passed:
        return "WARN"
    if category == "optional" and available is False:
        return "SKIP"
    return "OK"


def _doctor_status_marker(status: str) -> str:
    return escape(f"[{status}]")
