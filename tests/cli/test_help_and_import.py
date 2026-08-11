import pytest
import typer.rich_utils as typer_rich_utils
from pytest import MonkeyPatch
from typer.main import get_command

from frame_compare.cli.entry import _stabilize_typer_help_width, app

from .cli_helpers import _normalize_cli_help, _normalize_cli_output, runner


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
        "--frames",
        "--random-frame-count",
        "--dark-frame-count",
        "--bright-frame-count",
        "--motion-frame-count",
        "--seed",
        "--overlay",
        "--skip-analysis",
        "--skip-metadata",
        "--force-interactive-alignment",
        "--dry-run",
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
    commands = getattr(command, "commands", None)
    assert isinstance(commands, dict)
    assert "run" in commands
    run_command = commands["run"]
    declared_options = {
        opt
        for param in run_command.params
        for opt in (*getattr(param, "opts", ()), *getattr(param, "secondary_opts", ()))
    }

    assert set(REQUIRED_RUN_OPTIONS).issubset(declared_options)
    assert "--frame-count" not in declared_options
    assert "-n" not in declared_options

    result = runner.invoke(
        app,
        ["run", "--help"],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    output = _normalize_cli_output(result.stdout)
    assert result.exit_code == 0
    for opt in [
        "--root",
        "--config",
        "--input",
        "--frames",
        "--random-frame-count",
        "--dark-frame-count",
        "--bright-frame-count",
        "--motion-frame-count",
        "--dry-run",
        "--json",
        "--quiet",
        "--verbose",
    ]:
        assert opt in output
    assert "--frame-count" not in output
    assert " -n " not in output


@pytest.mark.parametrize("retired_option", ["--frame-count", "-n"])
def test_run_rejects_retired_frame_count_options(
    retired_option: str, monkeypatch: MonkeyPatch
) -> None:
    def _unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("run handler must not execute for an unknown option")

    monkeypatch.setattr("frame_compare.cli.entry.handle_run", _unexpected_run)

    result = runner.invoke(
        app,
        ["run", retired_option, "7"],
        color=False,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    error_output = _normalize_cli_output(result.stderr)
    assert "No such option" in error_output
    assert retired_option in error_output


@pytest.mark.parametrize(
    ("args", "expected_fragments"),
    [
        (
            ["--help"],
            [
                "Compare video sources and generate screenshots",
                "Interactively configure input, reference, and frame selection.",
                "Check required runtimes and optional integrations.",
            ],
        ),
        (
            ["run", "--help"],
            [
                "Compare video sources and generate screenshots and an optional report.",
                "Workspace root containing config and output directories.",
                "persists with --write-config",
                "Require valid cached analysis",
                "Plan without probing, rendering, writing outputs, or publishing.",
                "Write the effective config, then exit without running.",
                "Print resolved workspace paths as JSON, then exit.",
            ],
        ),
        (
            ["wizard", "--help"],
            [
                "Interactively configure input, reference, and frame selection.",
                "Config file; relative paths resolve from --root.",
            ],
        ),
        (
            ["doctor", "--help"],
            [
                "Check required runtimes and optional integrations.",
                "Emit the diagnostic report as JSON.",
            ],
        ),
        (
            ["history", "list", "--help"],
            ["List recorded runs newest first.", "Emit the run list as JSON."],
        ),
        (
            ["preset", "list", "--help"],
            [
                "List available configuration presets.",
                "Accepted for consistency; preset list uses --root.",
            ],
        ),
        (
            ["preset", "apply", "--help"],
            ["Apply a named preset to the selected config file."],
        ),
        (
            ["preset", "save", "--help"],
            ["Save the selected config as a named preset."],
        ),
    ],
)
def test_public_help_explains_commands_and_option_effects(
    args: list[str],
    expected_fragments: list[str],
) -> None:
    result = runner.invoke(
        app,
        args,
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    output = _normalize_cli_help(result.stdout)

    assert result.exit_code == 0
    for fragment in expected_fragments:
        assert fragment in output


def test_root_generates_shell_completion_source(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("_TYPER_COMPLETE_TEST_DISABLE_SHELL_DETECTION", "True")
    result = runner.invoke(
        app,
        ["--show-completion", "bash"],
        color=False,
        env={
            "NO_COLOR": "1",
            "TERM": "dumb",
        },
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "frame-compare" in result.stdout
    assert "complete -o default -F" in result.stdout


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
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"CLI import subprocess timed out after {exc.timeout} seconds")
    assert res.returncode == 0, res.stderr
