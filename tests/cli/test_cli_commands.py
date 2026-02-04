from typer.testing import CliRunner

from frame_compare.cli_entry import app

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


def test_run_exits_zero_when_runner_returns_success(monkeypatch):
    def _run(_request, dependencies=None):
        return type("RunResult", (), {"success": True})()

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


def test_run_stub_executes(monkeypatch):
    def _run(_request, dependencies=None):
        return type("RunResult", (), {"success": True})()

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


def test_run_exits_processing_error_when_runner_returns_unsuccessful(monkeypatch):
    def _run(_request, dependencies=None):
        return type("RunResult", (), {"success": False})()

    monkeypatch.setattr("frame_compare.cli_entry.runner.run", _run)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 5


def test_run_builds_run_request_from_cli_args(monkeypatch):
    captured = {}

    def _run(request, dependencies=None):
        captured["request"] = request
        return type("RunResult", (), {"success": True})()

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


def test_wizard_stub():
    result = runner.invoke(app, ["wizard"])
    assert result.exit_code == 0
    assert "[stub] wizard: Not yet implemented" in result.stdout


def test_doctor_stub_text():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "[stub] doctor: Not yet implemented" in result.stdout


def test_doctor_stub_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert '{"status": "stub", "checks": []}' in result.stdout


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
