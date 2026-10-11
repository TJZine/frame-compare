import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from pytest import MonkeyPatch
from structlog.testing import capture_logs

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode, format_error_json
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport, run_doctor
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal_theme import GLYPHS_ASCII
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

from .cli_helpers import runner


@pytest.mark.parametrize("json_output", [False, True], ids=["human", "json"])
def test_default_doctor_reports_local_checks_without_http(
    tmp_path: Path, monkeypatch: MonkeyPatch, json_output: bool
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("[tmdb]\nenabled = false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for key in ("TMDB_API_KEY", "FRAME_COMPARE_TMDB__API_KEY", "FRAME_COMPARE_TMDB__ENABLED"):
        monkeypatch.delenv(key, raising=False)
    # Exercise the real default registry and config check while isolating host runtimes.
    for name in ("vapoursynth", "lsmas", "vs_placebo", "ffms2", "ffmpeg", "vsview"):
        monkeypatch.setattr(
            f"frame_compare.orchestration.doctor_checks._check_{name}",
            lambda: CheckResult(passed=True, message="Runtime available"),
        )
    with (
        patch("httpx.Client.send", side_effect=AssertionError("Unexpected HTTP request")) as send,
        patch(
            "httpx.AsyncClient.send", side_effect=AssertionError("Unexpected HTTP request")
        ) as async_send,
    ):
        result = runner.invoke(app, ["doctor", "--json"] if json_output else ["doctor"])

    send.assert_not_called()
    async_send.assert_not_called()
    assert result.exit_code == 0
    assert result.stderr == ""
    assert "slowpics" not in result.stdout
    assert "slow.pics" not in result.stdout
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert [entry["id"] for entry in payload["doctor"]["checks"]] == [
            "vapoursynth",
            "lsmas",
            "vs_placebo",
            "ffms2",
            "ffmpeg",
            "vsview",
            "tmdb_api_key",
        ]
        assert _doctor_check_entry(payload, "tmdb_api_key")["message"] == (
            "TMDB metadata lookup disabled"
        )
    else:
        assert "TMDB metadata lookup disabled" in result.stdout
        assert "Runtime is ready for comparisons." in result.stdout


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
    "Fix config/config.toml syntax, then rerun doctor",
    "Fix the reported config/environment validation errors, then rerun doctor",
    "Replace the TMDB credential with a 32-character hexadecimal API key",
)


def _doctor_check_entry(payload: dict[str, object], check_id: str) -> dict[str, object]:
    checks = cast(dict[str, object], payload["doctor"])["checks"]
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
    assert payload["doctor"]["baseline_version"] == "R81"
    media_runtime = payload["doctor"]["media_runtime"]
    assert media_runtime["components"]["decoder"]["vapoursynth"]["release"] == "R81"
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
    assert result.stderr == ""
    normalized = " ".join(result.stdout.split())
    assert "✗ VapourSynth missing" in normalized
    assert normalized.endswith("✗ Runtime is not ready for comparisons. 1 required check failed")
    assert "Core runtime is not ready" not in result.stdout


def test_doctor_human_output_is_verdict_last_and_grouped(monkeypatch: MonkeyPatch) -> None:
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
            name="tmdb_api_key",
            category="network",
            check_fn=lambda: CheckResult(passed=True, message="TMDB API key configured"),
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
    assert (
        lines.index("Required") < lines.index("Optional") < lines.index("Network and credentials")
    )
    normalized = " ".join(result.stdout.split())
    assert "\u2713 VapourSynth VapourSynth available" in normalized
    assert "! FFmpeg FFmpeg not found" in normalized
    assert "\u2013 VSView VSView not installed" in normalized
    assert "hint Install VSView, then rerun doctor" in normalized
    assert "\u2713 TMDB API key TMDB API key configured" in normalized
    assert normalized.endswith("\u2713 Runtime is ready for comparisons. 1 warning")
    assert result.stdout.count("Runtime is ready for comparisons.") == 1
    assert "Core runtime" not in result.stdout
    assert "[WARN]" not in result.stdout
    assert "[OK]" not in result.stdout
    assert "[SKIP]" not in result.stdout
    assert "[FAIL]" not in result.stdout
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
    normalized_human = " ".join(human_result.stdout.split())
    assert "\u2717 FFmpeg FFmpeg executables do not match" in normalized_human
    assert normalized_human.endswith(
        "\u2717 Runtime is not ready for comparisons. 1 required check failed"
    )
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
        name="tmdb_api_key",
        category="network",
        check_fn=lambda: CheckResult(passed=False, message="TMDB API key not configured"),
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
    normalized = " ".join(result.stdout.split())
    assert "! TMDB API key TMDB API key not configured" in normalized
    assert normalized.endswith("\u2713 Runtime is ready for comparisons. 1 warning")
    assert "\u2717 TMDB API key" not in normalized
    assert "Core runtime checks passed" not in result.stdout


def test_doctor_credential_failure_is_warning_only(monkeypatch: MonkeyPatch) -> None:
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
    normalized = " ".join(result.stdout.split())
    assert "! FFmpeg FFmpeg not found in PATH" in normalized
    assert "\u2717 FFmpeg" not in normalized
    assert normalized.endswith("\u2713 Runtime is ready for comparisons. 1 warning")


@pytest.mark.parametrize(
    ("message", "available", "expected"),
    [
        (
            "VSView not installed (optional for manual alignment)",
            False,
            "– VSView VSView not installed",
        ),
        ("VSView availability probe failed", False, "– VSView VSView availability probe failed"),
        (
            "VSView is available for interactive alignment",
            True,
            "✓ VSView VSView is available for interactive alignment",
        ),
    ],
    ids=["unavailable", "probe-failure", "available"],
)
def test_doctor_optional_vsview_presentation(
    monkeypatch: MonkeyPatch, message: str, available: bool, expected: str
) -> None:
    check = DoctorCheck(
        name="vsview",
        category="optional",
        check_fn=lambda: CheckResult(passed=True, message=message, available=available),
    )
    report = DoctorReport(checks=[(check, check.check_fn())], all_passed=True, critical_failures=[])

    def _run_doctor(
        checks: list[DoctorCheck] | None = None, reporter: ProgressReporter | None = None
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert result.stderr == ""
    normalized = " ".join(result.stdout.split())
    assert expected in normalized
    if available:
        assert "– VSView" not in normalized
    else:
        assert "✓ VSView" not in normalized
        assert "✗ VSView" not in normalized
    assert normalized.endswith("✓ Runtime is ready for comparisons.")
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
    assert "hint install [ffmpeg]" in " ".join(result.stdout.split())
    assert "\x1b[" not in result.stdout


def test_doctor_preserves_supplied_hint_text_in_human_and_json_output(
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
    compact_human_output = "".join(human_result.stdout.split())
    for hint in _AUDITED_HINTS:
        assert "".join(f"hint {hint}".split()) in compact_human_output

    json_result = runner.invoke(app, ["doctor", "--json"])

    assert json_result.exit_code == 0
    assert json_result.stderr == ""
    payload = json.loads(json_result.stdout)
    assert [entry["install_hint"] for entry in payload["doctor"]["checks"]] == list(_AUDITED_HINTS)


def test_doctor_verdict_combines_failure_and_warning_counts(
    monkeypatch: MonkeyPatch,
) -> None:
    checks = [
        DoctorCheck(
            name="vapoursynth",
            category="core",
            check_fn=lambda: CheckResult(passed=False, message="missing"),
        ),
        DoctorCheck(
            name="lsmas",
            category="core",
            check_fn=lambda: CheckResult(passed=False, message="missing"),
        ),
        DoctorCheck(
            name="ffmpeg",
            category="optional",
            check_fn=lambda: CheckResult(passed=False, message="FFmpeg not found in PATH"),
        ),
    ]
    report = DoctorReport(
        checks=[(check, check.check_fn()) for check in checks],
        all_passed=False,
        critical_failures=["vapoursynth", "lsmas"],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == int(ExitCode.DEPENDENCY_ERROR)
    assert result.stderr == ""
    normalized = " ".join(result.stdout.split())
    assert normalized.endswith(
        "✗ Runtime is not ready for comparisons. 2 required checks failed · 1 warning"
    )


def test_doctor_ascii_fallback_uses_ascii_glyphs(monkeypatch: MonkeyPatch) -> None:
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
    monkeypatch.setattr(
        "frame_compare.cli.doctor_command.glyphs_for_console",
        lambda console: GLYPHS_ASCII,
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == int(ExitCode.DEPENDENCY_ERROR)
    assert result.stderr == ""
    normalized = " ".join(result.stdout.split())
    assert "x VapourSynth missing" in normalized
    assert normalized.endswith("x Runtime is not ready for comparisons. 1 required check failed")
    assert "✗" not in result.stdout
    assert "✓" not in result.stdout


def test_doctor_generic_check_failure_sanitizes_json_details(monkeypatch: MonkeyPatch) -> None:
    sentinel = "SECRET_DOCTOR_EXCEPTION"

    def _raise() -> CheckResult:
        raise RuntimeError(f"{sentinel} at /private/config.toml")

    check = DoctorCheck(name="custom_check", category="optional", check_fn=_raise)
    with capture_logs():
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
