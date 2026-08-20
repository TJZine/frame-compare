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
                "Reproducible video comparisons with deterministic frame selection, audio alignment, HDR-aware rendering, and offline review reports.",
                "Turn two or more local video sources into a repeatable comparison",
                "First setup: frame-compare wizard",
                "Preview a run: frame-compare run --dry-run",
                "Compare locally: frame-compare run --no-upload",
            ],
        ),
        (
            ["run", "--help"],
            [
                "Compare video sources and generate screenshots and an optional report.",
                "Workspace root containing configuration, input, and generated output.",
                "persists with --write-config",
                "Require valid cached analysis",
                "Preview what a run would use and create without probing or side effects.",
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
                "Accepted for consistency; ignored here. Presets are located under --root.",
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


@pytest.mark.parametrize("terminal_width", [60, 80, 120])
@pytest.mark.parametrize("args", [["--help"], ["run", "--help"]])
def test_help_uses_requested_terminal_width(args: list[str], terminal_width: int) -> None:
    result = runner.invoke(
        app,
        args,
        color=False,
        terminal_width=terminal_width,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )

    assert result.exit_code == 0
    assert max((len(line) for line in result.stdout.splitlines()), default=0) <= terminal_width


def test_run_help_groups_options_by_task() -> None:
    result = runner.invoke(
        app,
        ["run", "--help"],
        color=False,
        terminal_width=80,
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    output = _normalize_cli_help(result.stdout)
    panels = [
        "Workspace and configuration",
        "Sources and frame selection",
        "Rendering and alignment",
        "Reports and publishing",
        "Planning and diagnostics",
        "Output modes",
    ]

    assert result.exit_code == 0
    positions = [output.index(panel) for panel in panels]
    assert positions == sorted(positions)


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


@pytest.mark.parametrize("terminal_width", [0, -1])
def test_stabilize_typer_help_width_ignores_non_positive_explicit_width(
    terminal_width: int,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(typer_rich_utils, "MAX_WIDTH", 120)

    _stabilize_typer_help_width(terminal_width)

    assert typer_rich_utils.MAX_WIDTH == 120


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
