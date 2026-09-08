import json
from pathlib import Path

from pytest import MonkeyPatch
from structlog.testing import capture_logs

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode, format_error_json
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport, run_doctor
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

from .cli_helpers import runner

_AUDITED_HINTS = (
    "Make VapourSynth importable; see https://tjzine.github.io/frame-compare/getting-started/native/#native-source",
    (
        "Make L-SMASH-Works available under core.lsmas; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/#native-source"
    ),
    (
        "Make VapourSynth importable before checking L-SMASH-Works; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/#native-source"
    ),
    (
        "Check the VapourSynth/plugin setup, then rerun doctor; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/#native-source"
    ),
    (
        "Provide FFmpeg and ffprobe executables; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/#native-source"
    ),
    "Install the supported vs-placebo wheel or use a complete Frame Compare runtime",
    "Install or reinstall the complete supported media runtime, then rerun doctor",
    "Repair the supported media runtime, then rerun doctor",
    "Repair the complete Docker media runtime, then rerun doctor",
    "Repair or reinstall the complete supported media runtime, then rerun doctor",
    "Repair or replace the FFmpeg runtime, then rerun doctor",
    ("Provide VSView; see https://tjzine.github.io/frame-compare/getting-started/native/"),
    (
        "Provide a supported Qt backend for VSView; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/"
    ),
    (
        "Check the optional VSView setup, then rerun doctor; see "
        "https://tjzine.github.io/frame-compare/getting-started/native/"
    ),
    "Review the returned HTTP status before retrying",
    "Check network access to slow.pics, then retry",
    "Review the request failure and network path to slow.pics before retrying",
    "Fix config/config.toml syntax, then rerun doctor",
    "Fix the reported config/environment validation errors, then rerun doctor",
    "Replace the TMDB credential with a 32-character hexadecimal API key",
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
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "test-runtime")
    expected_runtime_fingerprint = media_runtime_fingerprint("full")
    monkeypatch.setenv("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", expected_runtime_fingerprint)
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1")
    checks = [
        DoctorCheck(
            name="vapoursynth",
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
    assert payload["doctor"]["baseline_version"] == "R79"
    media_runtime = payload["doctor"]["media_runtime"]
    assert media_runtime["components"]["decoder"]["vapoursynth"]["release"] == "R79"
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
    assert first["id"] == "vapoursynth"
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
    assert result.stdout.splitlines()[0] == "[FAIL] Runtime is not ready for comparisons."
    assert "[FAIL] VapourSynth — missing" in result.stdout
    assert "Core runtime is not ready" not in result.stdout


def test_doctor_human_output_is_readiness_first_and_grouped(monkeypatch: MonkeyPatch) -> None:
    checks = [
        DoctorCheck(
            name="vapoursynth",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="VapourSynth available"),
        ),
        DoctorCheck(
            name="ffmpeg",
            category="optional",
            check_fn=lambda: CheckResult(passed=False, message="FFmpeg not found"),
        ),
        DoctorCheck(
            name="vsview",
            category="optional",
            check_fn=lambda: CheckResult(
                passed=True,
                available=False,
                message="VSView not installed",
                hint="Install VSView, then rerun doctor",
            ),
        ),
        DoctorCheck(
            name="slowpics",
            category="network",
            check_fn=lambda: CheckResult(passed=True, message="slow.pics reachable"),
        ),
    ]
    report = run_doctor(checks=checks)

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
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    lines = result.stdout.splitlines()
    assert lines[0] == (
        "[WARN] Ready for local comparisons; optional or network checks need attention."
    )
    assert (
        lines.index("Required") < lines.index("Optional") < lines.index("Network and credentials")
    )
    assert "[OK] VapourSynth — VapourSynth available" in result.stdout
    assert "[WARN] FFmpeg — FFmpeg not found" in result.stdout
    assert "[SKIP] VSView — VSView not installed" in result.stdout
    assert "[OK] slow.pics — slow.pics reachable" in result.stdout
    assert result.stdout.count("Ready for local comparisons") == 1
    assert "Core runtime" not in result.stdout
    assert "\u2705" not in result.stdout
    assert "\u274c" not in result.stdout
    assert "\u26a0" not in result.stdout
    assert "\x1b[" not in result.stdout


def test_doctor_managed_optional_policy_failure_blocks_human_and_json_output(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "docker")
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1")
    check = DoctorCheck(
        name="ffmpeg",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=False,
            available=True,
            message="FFmpeg executables do not match the selected managed runtime version",
        ),
        critical_if_failed=True,
    )
    report = run_doctor(checks=[check])

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    human_result = runner.invoke(app, ["doctor"])
    assert human_result.exit_code == int(ExitCode.DEPENDENCY_ERROR)
    assert human_result.stderr == ""
    assert human_result.stdout.splitlines()[0] == "[FAIL] Runtime is not ready for comparisons."
    assert "[FAIL] FFmpeg — FFmpeg executables do not match" in human_result.stdout
    assert "Core runtime is not ready" not in human_result.stdout

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == int(ExitCode.DEPENDENCY_ERROR)
    assert json_result.stderr == ""
    payload = json.loads(json_result.stdout)
    assert payload["success"] is False
    check_entry = _doctor_check_entry(payload, "ffmpeg")
    assert check_entry["category"] == "optional"
    assert check_entry["status"] == "fail"


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
    assert result.stdout.splitlines()[0] == (
        "[WARN] Ready for local comparisons; optional or network checks need attention."
    )
    assert "[WARN] slow.pics — offline" in result.stdout
    assert "[FAIL] slow.pics" not in result.stdout
    assert "Core runtime checks passed" not in result.stdout


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
    assert "[WARN] FFmpeg — FFmpeg not found in PATH" in result.stdout
    assert "[FAIL] FFmpeg" not in result.stdout
    assert result.stdout.splitlines()[0].startswith("[WARN] Ready for local comparisons;")


def test_doctor_human_marks_optional_vsview_unavailable_neutrally(
    monkeypatch: MonkeyPatch,
) -> None:
    check = DoctorCheck(
        name="vsview",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=True,
            message="VSView not installed (optional for manual alignment)",
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
    assert "[SKIP] VSView — VSView not installed" in result.stdout
    assert "[OK] VSView" not in result.stdout
    assert "[FAIL] VSView" not in result.stdout
    assert result.stdout.splitlines()[0] == (
        "[WARN] Ready for local comparisons; optional or network checks need attention."
    )

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    check_entry = _doctor_check_entry(json.loads(json_result.stdout), "vsview")
    assert check_entry["status"] == "pass"
    assert "available" not in check_entry


def test_doctor_human_marks_optional_vsview_probe_failure_neutrally(
    monkeypatch: MonkeyPatch,
) -> None:
    check = DoctorCheck(
        name="vsview",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=True,
            message="VSView availability probe failed",
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
    assert "[SKIP] VSView — VSView availability probe failed" in result.stdout
    assert "[OK] VSView" not in result.stdout
    assert "[FAIL] VSView" not in result.stdout
    assert result.stdout.splitlines()[0] == (
        "[WARN] Ready for local comparisons; optional or network checks need attention."
    )

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    check_entry = _doctor_check_entry(json.loads(json_result.stdout), "vsview")
    assert check_entry["status"] == "pass"
    assert "available" not in check_entry


def test_doctor_human_marks_available_optional_vsview_as_pass(
    monkeypatch: MonkeyPatch,
) -> None:
    check = DoctorCheck(
        name="vsview",
        category="optional",
        check_fn=lambda: CheckResult(
            passed=True,
            message="VSView is available for interactive alignment",
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
    assert "[OK] VSView — VSView is available" in result.stdout
    assert "[SKIP] VSView" not in result.stdout
    assert result.stdout.splitlines()[0] == "[OK] Runtime is ready for comparisons."

    json_result = runner.invoke(app, ["doctor", "--json"])
    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    check_entry = _doctor_check_entry(json.loads(json_result.stdout), "vsview")
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
    assert "\x1b[" not in result.stdout


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


def test_doctor_generic_check_failure_sanitizes_json_details(monkeypatch: MonkeyPatch) -> None:
    sentinel = "SECRET_DOCTOR_EXCEPTION"

    def _raise() -> CheckResult:
        raise RuntimeError(f"{sentinel} at /private/config.toml")

    check = DoctorCheck(name="custom_check", category="optional", check_fn=_raise)
    with capture_logs() as captured_logs:
        report = run_doctor(checks=[check])

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
    entry = _doctor_check_entry(payload, "custom_check")
    assert entry["message"] == "custom_check check failed"
    assert entry["details"] == {"exception_type": "RuntimeError"}
    assert sentinel not in result.stdout
    assert "/private/config.toml" not in result.stdout
    record = next(item for item in captured_logs if item["event"] == "doctor_check_failed")
    assert record["event"] == "doctor_check_failed"
    assert record["check"] == "custom_check"
    assert record["exception_type"] == "RuntimeError"
    assert record["exc_info"] is True
    assert record["log_level"] == "debug"


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
