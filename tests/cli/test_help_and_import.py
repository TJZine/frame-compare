import typer.rich_utils as typer_rich_utils
from _pytest.monkeypatch import MonkeyPatch
from click import Group
from typer.main import get_command

from frame_compare.cli.entry import _stabilize_typer_help_width, app

from .cli_helpers import _normalize_cli_output, runner


def test_app_help_lists_all_commands():
    result = runner.invoke(
        app,
        ["--help"],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    output = _normalize_cli_output(result.stdout)
    assert result.exit_code == 0
    assert "run" in output
    assert "wizard" in output
    assert "doctor" in output
    assert "preset" in output
    assert "version" in output


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
    command = get_command(app)
    assert isinstance(command, Group)
    run_command = command.commands["run"]
    declared_options = {
        opt
        for param in run_command.params
        for opt in (*getattr(param, "opts", ()), *getattr(param, "secondary_opts", ()))
    }

    assert set(REQUIRED_RUN_OPTIONS).issubset(declared_options)

    result = runner.invoke(
        app,
        ["run", "--help"],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    output = _normalize_cli_output(result.stdout)
    assert result.exit_code == 0
    for opt in ["--root", "--config", "--input", "--json", "--quiet", "--verbose"]:
        assert opt in output


def test_stabilize_typer_help_width_backfills_import_order_gap(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TERMINAL_WIDTH", "200")
    monkeypatch.setattr(typer_rich_utils, "MAX_WIDTH", None)
    _stabilize_typer_help_width()
    assert typer_rich_utils.MAX_WIDTH == 200


def test_import_does_not_mutate_terminal_width():
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env.pop("TERMINAL_WIDTH", None)
    cmd = [
        sys.executable,
        "-c",
        "import os; "
        "import frame_compare.cli.entry; "
        "assert 'TERMINAL_WIDTH' not in os.environ, 'should not set env on import'; "
        "import typer.rich_utils as tru; "
        "assert tru.MAX_WIDTH is None, 'should not set MAX_WIDTH on import'; ",
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
