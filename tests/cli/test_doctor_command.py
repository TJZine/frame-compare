import json
from pathlib import Path

from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode, format_error_json
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

from .cli_helpers import runner

_AUDITED_HINTS = (
    (
        "Run Frame Compare with Python 3.13+; see "
        "https://github.com/TJZine/frame-compare#requirements"
    ),
    "Make VapourSynth importable; see https://github.com/TJZine/frame-compare#quick-start",
    (
        "Make L-SMASH-Works available to VapourSynth; see "
        "https://github.com/TJZine/frame-compare#quick-start"
    ),
    (
        "Make VapourSynth importable before checking L-SMASH-Works; see "
        "https://github.com/TJZine/frame-compare#quick-start"
    ),
    (
        "Check the VapourSynth/plugin setup, then rerun doctor; see "
        "https://github.com/TJZine/frame-compare#quick-start"
    ),
    (
        "Provide FFmpeg and ffprobe executables; see "
        "https://github.com/TJZine/frame-compare#requirements"
    ),
    "Install the supported vs-placebo wheel or use a complete Frame Compare runtime",
    "Repair the supported media runtime, then rerun doctor",
    "Repair the complete Docker media runtime, then rerun doctor",
    "Repair or replace the FFmpeg runtime, then rerun doctor",
    ("Provide VSPreview; see https://tjzine.github.io/frame-compare/getting-started/native/"),
    (
        "Provide a supported Qt backend for VSPreview; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/"
    ),
    (
        "Check the optional VSPreview setup, then rerun doctor; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/"
    ),
    "Review the returned HTTP status before retrying",
    "Check network access to slow.pics, then retry",
    "Review the request failure and network path to slow.pics before retrying",
    "Fix config/config.toml syntax, then rerun doctor",
    "Fix the reported config/environment validation errors, then rerun doctor",
    "Replace the TMDB credential with a 32-character hexadecimal API key",
    "Move the credential to FRAME_COMPARE_TMDB__API_KEY and remove TMDB_API_KEY",
)


def _doctor_check_entry(payload: dict[str, object], check_id: str) -> dict[str, object]:
    checks = payload["doctor"]["checks"]
    assert isinstance(checks, list)
    for entry in checks:
        assert isinstance(entry, dict)
        if entry.get("id") == check_id:
            return entry
    raise AssertionError(f"doctor check {check_id!r} missing from payload")


def test_doctor_json_conforms_to_schema_shape(monkeypatch: MonkeyPatch) -> None:
    expected_runtime_fingerprint = media_runtime_fingerprint("full")
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "test-runtime")
    monkeypatch.setenv("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", expected_runtime_fingerprint)
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1")
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
    assert payload["doctor"]["baseline_version"] == "R78"
    media_runtime = payload["doctor"]["media_runtime"]
    assert media_runtime["components"]["decoder"]["vapoursynth"]["release"] == "R78"
    assert media_runtime["fingerprints"]["full"] == expected_runtime_fingerprint
    runtime_environment = payload["doctor"]["runtime_environment"]
    assert runtime_environment == {
        "runtime_kind": "test-runtime",
        "expected_full_fingerprint": expected_runtime_fingerprint,
        "declared_full_fingerprint": expected_runtime_fingerprint,
        "declared_full_fingerprint_valid": True,
        "declared_full_fingerprint_match": True,
        "ffms2_required": True,
    }
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
    assert "Core runtime is not ready; resolve required checks above." in result.stdout


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
    assert "\u26a0 slowpics" in result.stdout
    assert "\u274c slowpics" not in result.stdout
    assert "Core runtime checks passed; optional or network checks need attention." in result.stdout


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
    assert "Core runtime checks passed; optional or network checks need attention." in result.stdout


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
    assert "Core runtime checks passed." in result.stdout

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


def test_doctor_audited_hints_are_deterministic_in_human_and_json_output(
    monkeypatch: MonkeyPatch,
) -> None:
    checks = [
        DoctorCheck(
            name=f"hint_{index}",
            category="optional",
            check_fn=lambda hint=hint: CheckResult(passed=False, message="unavailable", hint=hint),
        )
        for index, hint in enumerate(_AUDITED_HINTS)
    ]
    report = DoctorReport(
        checks=[(check, check.check_fn()) for check in checks],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    human_result = runner.invoke(
        app,
        ["doctor"],
        color=False,
        terminal_width=240,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )

    assert human_result.exit_code == 0
    assert human_result.stderr == ""
    normalized_human_output = " ".join(human_result.stdout.split())
    for hint in _AUDITED_HINTS:
        assert f"Hint: {hint}" in normalized_human_output

    json_result = runner.invoke(app, ["doctor", "--json"])

    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    payload = json.loads(json_result.stdout)
    assert [entry["install_hint"] for entry in payload["doctor"]["checks"]] == list(_AUDITED_HINTS)


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
