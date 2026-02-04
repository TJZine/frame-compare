import json
import tomllib
from pathlib import Path

import typer
from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from frame_compare.cli_entry import app
from frame_compare.errors import ConfigNotFoundError, format_error_json, get_exit_code
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport
from frame_compare.utils.progress import ProgressReporter

runner = CliRunner()

MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
"""


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


def test_run_builds_run_request_with_input_dir(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run", "--input", "custom_inputs"])
    assert result.exit_code == 0
    assert captured["request"].input_dir == Path("custom_inputs")


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
    with runner.isolated_filesystem():
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Zebra.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Zebra"]


def test_preset_apply_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nframe_count = 12\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["preset", "apply", "boost", "--root", str(root), "--config", "config/config.toml"],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 12


def test_preset_save_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "demo", "--root", str(root), "--config", "config/config.toml"],
        )
        assert result.exit_code == 0
        preset_path = root / "config" / "presets" / "demo.toml"
        assert preset_path.exists()


def test_preset_list_prints_names_sorted_case_insensitive() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Bravo.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')
        (presets_dir / "charlie.toml").write_text('[paths]\ninput_dir = "c"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Bravo", "charlie"]


def test_preset_save_respects_root_and_config_writes_preset_file() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "sample", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        preset_path = root / "config" / "presets" / "sample.toml"
        assert preset_path.exists()


def test_preset_apply_respects_root_and_config_updates_config_file() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nframe_count = 22\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["preset", "apply", "boost", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 22


def test_run_write_config_respects_root_and_config_and_does_not_invoke_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --write-config")

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            [
                "run",
                "--write-config",
                "--root",
                str(root),
                "--config",
                "configs/config.toml",
                "--frame-count",
                "17",
            ],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 17


def test_run_diagnose_paths_outputs_pinned_json_schema_and_does_not_invoke_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --diagnose-paths")

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            [
                "run",
                "--diagnose-paths",
                "--root",
                str(root),
                "--config",
                "config/config.toml",
                "--input",
                "inputs",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {"cache", "config", "input", "output", "root"}
        assert payload["root"] == str(root.resolve())
        assert payload["config"] == str(config_path.resolve())
        assert payload["input"] == str((root / "inputs").resolve())
        assert payload["output"] == str((root / "screenshots").resolve())
        assert payload["cache"] == str((root / "generated").resolve())


def test_run_json_outputs_pinned_success_schema_and_stdout_is_pure_json(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("shots"),
            slowpics_url="https://slow.pics/abc",
            report_path=Path("report.html"),
            frame_count=12,
            clips_processed=2,
            duration_seconds=1.25,
            cache_hit=True,
            errors=[],
        )

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "cache_hit": True,
        "clips_processed": 2,
        "duration_seconds": 1.25,
        "errors": [],
        "frame_count": 12,
        "report_path": "report.html",
        "screenshots_dir": "shots",
        "slowpics_url": "https://slow.pics/abc",
        "success": True,
    }


def test_run_json_outputs_error_schema_and_exit_code(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run", "--json"])
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    payload = json.loads(result.stdout)
    expected = format_error_json(ConfigNotFoundError(Path("missing.toml")))
    assert payload == expected


def test_run_no_color_error_output_has_no_rich_markup(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run", "--no-color"])
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr


def test_run_verbose_calls_configure_logging_debug(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def _configure_logging(*, level: str, format: str) -> None:
        captured["level"] = level
        captured["format"] = format

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli_entry.configure_logging", _configure_logging)
    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run", "--verbose"])
    assert result.exit_code == 0
    assert captured["level"] == "DEBUG"

    result = runner.invoke(app, ["run", "--quiet"])
    assert result.exit_code == 0
    assert captured["level"] == "WARNING"
