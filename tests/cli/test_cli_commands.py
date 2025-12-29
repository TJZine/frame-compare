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


def test_run_stub_executes():
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "[stub] run: Not yet implemented" in result.stdout


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
