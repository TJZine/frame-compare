import json
from pathlib import Path

from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode, format_error_json
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport
from frame_compare.utils.progress_protocol import ProgressReporter

from .cli_helpers import runner


def _doctor_check_entry(payload: dict[str, object], check_id: str) -> dict[str, object]:
    checks = payload["doctor"]["checks"]
    assert isinstance(checks, list)
    for entry in checks:
        assert isinstance(entry, dict)
        if entry.get("id") == check_id:
            return entry
    raise AssertionError(f"doctor check {check_id!r} missing from payload")


def test_doctor_json_conforms_to_schema_shape(monkeypatch: MonkeyPatch) -> None:
    checks = [
        DoctorCheck(
            name="python_version",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="ok"),
        ),
        DoctorCheck(
            name="ffmpeg",
            category="optional",
            check_fn=lambda: CheckResult(
                passed=False,
                message="missing",
                hint="install ffmpeg",
                details={"path": None},
            ),
        ),
    ]
    report = DoctorReport(
        checks=[(checks[0], checks[0].check_fn()), (checks[1], checks[1].check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert result.stderr == ""

    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["doctor"]["baseline_version"] == "R76"
    assert len(payload["doctor"]["checks"]) == 2
    first = payload["doctor"]["checks"][0]
    second = payload["doctor"]["checks"][1]
    assert first["id"] == "python_version"
    assert first["category"] == "core"
    assert first["status"] == "pass"
    assert "message" in first
    assert second["id"] == "ffmpeg"
    assert second["category"] == "optional"
    assert second["status"] == "fail"
    assert second["install_hint"] == "install ffmpeg"
    assert "details" in second


def test_doctor_exit_code_is_3_on_core_failure(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="vapoursynth",
        category="core",
        check_fn=lambda: CheckResult(passed=False, message="missing"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=["vapoursynth"],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3
    assert "\u274c vapoursynth" in result.stdout


def _run_doctor_optional_failure_and_assert(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="slowpics",
        category="network",
        check_fn=lambda: CheckResult(passed=False, message="offline"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert result.stderr == ""
    assert "\u274c slowpics" in result.stdout


def test_doctor_exit_code_is_0_on_optional_or_network_failure(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_doctor_stub_text(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_doctor_human_marks_optional_failed_check_neutrally(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="ffmpeg",
        category="optional",
        check_fn=lambda: CheckResult(passed=False, message="FFmpeg not found in PATH"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "- ffmpeg" in result.stdout
    assert "\u274c ffmpeg" not in result.stdout


def test_doctor_human_marks_optional_vspreview_unavailable_neutrally(
    monkeypatch: MonkeyPatch,
) -> None:
    check = DoctorCheck(
        name="vspreview",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=True,
            message="VSPreview not installed (optional for manual alignment)",
            available=False,
        ),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=True,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "- vspreview" in result.stdout
    assert "\u2705 vspreview" not in result.stdout
    assert "\u274c vspreview" not in result.stdout

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    check_entry = _doctor_check_entry(json.loads(json_result.stdout), "vspreview")
    assert check_entry["status"] == "pass"
    assert "available" not in check_entry


def test_doctor_human_marks_optional_vspreview_probe_failure_neutrally(
    monkeypatch: MonkeyPatch,
) -> None:
    check = DoctorCheck(
        name="vspreview",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=True,
            message="VSPreview availability probe failed",
            available=False,
        ),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=True,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "- vspreview" in result.stdout
    assert "\u2705 vspreview" not in result.stdout
    assert "\u274c vspreview" not in result.stdout

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    check_entry = _doctor_check_entry(json.loads(json_result.stdout), "vspreview")
    assert check_entry["status"] == "pass"
    assert "available" not in check_entry


def test_doctor_human_marks_available_optional_vspreview_as_pass(
    monkeypatch: MonkeyPatch,
) -> None:
    check = DoctorCheck(
        name="vspreview",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=True,
            message="VSPreview is available for interactive alignment",
            available=True,
        ),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=True,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "\u2705 vspreview" in result.stdout
    assert "- vspreview" not in result.stdout

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    check_entry = _doctor_check_entry(json.loads(json_result.stdout), "vspreview")
    assert check_entry["status"] == "pass"
    assert "available" not in check_entry


def test_doctor_text_preserves_literal_brackets(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="ffmpeg[optional]",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=False,
            message="missing [ffmpeg]",
            hint="install [ffmpeg]",
        ),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(
        app,
        ["doctor"],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "ffmpeg[optional]" in result.stdout
    assert "missing [ffmpeg]" in result.stdout
    assert "Hint: install [ffmpeg]" in result.stdout


def test_doctor_top_level_frame_compare_error_uses_cli_error_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    error = ConfigNotFoundError(Path("missing.toml"))

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stdout == ""
    assert "FC-1001" in result.stderr
    assert "--verbose" not in result.stderr
    assert "Details:" in result.stderr
    assert "Traceback" not in result.stderr


def test_doctor_top_level_error_uses_default_terminal_color_policy(
    monkeypatch: MonkeyPatch,
) -> None:
    error = ConfigNotFoundError(Path("missing.toml"))
    captured: dict[str, object] = {}
    monkeypatch.delenv("NO_COLOR", raising=False)

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        raise error

    def _handle_error(
        _error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int:
        captured["no_color"] = no_color
        captured["verbose"] = verbose
        captured["verbose_hint"] = verbose_hint
        return int(ExitCode.CONFIG_ERROR)

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)
    monkeypatch.setattr("frame_compare.cli.entry.handle_error", _handle_error)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert captured == {
        "no_color": False,
        "verbose": False,
        "verbose_hint": None,
    }


def test_doctor_json_top_level_frame_compare_error_uses_standard_error_schema(
    monkeypatch: MonkeyPatch,
) -> None:
    error = ConfigNotFoundError(Path("missing.toml"))

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    assert json.loads(result.stdout) == format_error_json(error)
