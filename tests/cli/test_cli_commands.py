import json
import tomllib
from pathlib import Path

import typer
from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from frame_compare.cli_entry import app
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport
from frame_compare.utils.progress import ProgressReporter

runner = CliRunner()


def test_app_help_lists_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "wizard" in result.stdout
    assert "doctor" in result.stdout
    assert "preset" in result.stdout
    assert "version" in result.stdout


def test_run_help_shows_all_options():
    REQUIRED_RUN_OPTIONS = [
        "--root",
        "-r",
        "--config",
        "-c",
        "--input",
        "-i",
        "--no-cache",
        "--from-cache-only",
        "--no-upload",
        "--tm-preset",
        "--tm-target",
        "--tm-curve",
        "--frame-count",
        "-n",
        "--seed",
        "--overlay",
        "--skip-analysis",
        "--skip-metadata",
        "--skip-dovi",
        "--force-interactive-alignment",
        "--json",
        "--no-color",
        "--write-config",
        "--diagnose-paths",
        "--quiet",
        "-q",
        "--verbose",
        "-v",
    ]
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    for opt in REQUIRED_RUN_OPTIONS:
        assert opt in result.stdout


def test_run_exits_zero_when_runner_returns_success(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


def test_run_stub_executes(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


def test_run_exits_processing_error_when_runner_returns_unsuccessful(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=False)

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 5


def test_run_builds_run_request_from_cli_args(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(
        app,
        [
            "run",
            "--tm-target",
            "203",
            "--overlay",
            "diagnostic",
            "--force-interactive-alignment",
        ],
    )
    assert result.exit_code == 0

    request = captured["request"]
    assert request.tm_target_nits == 203
    assert request.overlay_mode == "diagnostic"
    assert request.force_interactive_alignment is True


def _run_wizard_and_assert_config() -> None:
    with runner.isolated_filesystem():
        Path("inputs").mkdir()
        result = runner.invoke(
            app,
            ["wizard"],
            input="inputs\ny\nprivate\ny\nabc123\n",
        )
        assert result.exit_code == 0

        config_path = Path("config") / "config.toml"
        assert config_path.exists()

        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert set(data.keys()) == {"paths", "slowpics", "tmdb"}
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["auto_upload"] is True
        assert data["slowpics"]["visibility"] == "private"
        assert data["slowpics"]["delete_after_upload"] is True
        assert data["tmdb"]["api_key"] == "abc123"


def test_wizard_writes_valid_config_toml():
    _run_wizard_and_assert_config()


def test_wizard_stub():
    _run_wizard_and_assert_config()


def test_wizard_cancel_exits_130_and_writes_nothing(monkeypatch: MonkeyPatch) -> None:
    def _abort(*_args: object, **_kwargs: object) -> None:
        raise typer.Abort()

    monkeypatch.setattr("frame_compare.cli_entry.typer.prompt", _abort)

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["wizard"])
        assert result.exit_code == 130
        assert not (Path("config") / "config.toml").exists()


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

    monkeypatch.setattr("frame_compare.cli_entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["doctor"]["baseline_version"] == "R73"
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

    monkeypatch.setattr("frame_compare.cli_entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3


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

    monkeypatch.setattr("frame_compare.cli_entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_doctor_exit_code_is_0_on_optional_or_network_failure(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_doctor_stub_text(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_preset_list_stub():
    result = runner.invoke(app, ["preset", "list"])
    assert result.exit_code == 0
    assert "[stub] preset list: Not yet implemented" in result.stdout


def test_preset_apply_stub():
    result = runner.invoke(app, ["preset", "apply", "test"])
    assert result.exit_code == 0
    assert "[stub] preset apply: Not yet implemented" in result.stdout


def test_preset_save_stub():
    result = runner.invoke(app, ["preset", "save", "test"])
    assert result.exit_code == 0
    assert "[stub] preset save: Not yet implemented" in result.stdout
