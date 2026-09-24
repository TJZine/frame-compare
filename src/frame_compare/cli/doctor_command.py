"""Implementation for the ``doctor`` CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol, cast

import typer
from rich.markup import escape
from rich.table import Table

from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.errors import FrameCompareError, JSONValue
from frame_compare.utils.terminal_theme import (
    ACCENT,
    FAIL,
    MUTED,
    OK,
    WARN,
    GlyphSet,
    glyphs_for_console,
    human_console,
)

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
    "vsview": "VSView",
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
        print_doctor_report(report, no_color=no_color)

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


def print_doctor_report(report: DoctorReport, *, no_color: bool = False) -> None:
    """Print the grouped human-readable doctor results and the readiness verdict."""
    console = human_console(no_color=no_color)
    glyphs = glyphs_for_console(console)
    critical_failures = set(report.critical_failures)

    rendered_groups = [
        (
            heading,
            [(check, result) for check, result in report.checks if check.category == category],
        )
        for category, heading in _DOCTOR_GROUPS
    ]
    started = False
    name_width = max(
        [len(_doctor_display_label(check.name)) for check, _ in report.checks],
        default=0,
    )
    for heading, grouped_checks in rendered_groups:
        if not grouped_checks:
            continue
        if started:
            console.print()
        started = True
        console.print(f"[bold {ACCENT}]{escape(heading)}[/]")
        table = Table(box=None, show_header=False, padding=(0, 1, 0, 2), show_edge=False)
        table.add_column("status", width=1)
        table.add_column("check", style="bold", width=name_width)
        table.add_column("message", overflow="fold")
        for check, result in grouped_checks:
            status = _doctor_status(
                check_name=check.name,
                category=check.category,
                passed=result.passed,
                available=result.available,
                critical_failures=critical_failures,
            )
            table.add_row(
                _doctor_status_glyph(glyphs, status),
                escape(_doctor_display_label(check.name)),
                escape(result.message),
            )
            if result.hint:
                table.add_row("", "", f"[{MUTED}]hint[/] {escape(result.hint)}")
        console.print(table)

    failed_count = len(critical_failures)
    warning_count = sum(
        _doctor_status(
            check_name=check.name,
            category=check.category,
            passed=result.passed,
            available=result.available,
            critical_failures=critical_failures,
        )
        == "WARN"
        for check, result in report.checks
    )
    if critical_failures:
        verdict = f"[bold {FAIL}]{glyphs.failed} Runtime is not ready for comparisons.[/]"
    else:
        verdict = f"[bold {OK}]{glyphs.ok} Runtime is ready for comparisons.[/]"
    parts: list[str] = []
    if failed_count:
        noun = "check" if failed_count == 1 else "checks"
        parts.append(f"{failed_count} required {noun} failed")
    if warning_count:
        noun = "warning" if warning_count == 1 else "warnings"
        parts.append(f"{warning_count} {noun}")
    if parts:
        verdict += f" [{MUTED}]{escape(' · '.join(parts))}[/]"
    console.print()
    console.print(verdict)


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


def _doctor_status_glyph(glyphs: GlyphSet, status: str) -> str:
    if status == "FAIL":
        return f"[{FAIL}]{glyphs.failed}[/]"
    if status == "WARN":
        return f"[{WARN}]{glyphs.warning}[/]"
    if status == "SKIP":
        return f"[{MUTED}]{glyphs.skipped}[/]"
    return f"[{OK}]{glyphs.ok}[/]"
