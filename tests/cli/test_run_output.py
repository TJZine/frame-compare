from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.utils.post_upload_actions import PostUploadActionResult

from .cli_helpers import (
    _invoke_run_with_minimal_workspace,
    _normalize_cli_output,
    _write_minimal_config,
    runner,
)


def test_run_respects_no_color_env_var_presence_even_if_empty(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeConsole:
        def __init__(self, *, stderr: bool, no_color: bool) -> None:
            captured["stderr"] = stderr
            captured["no_color"] = no_color

        def print(self, *_args: object, **_kwargs: object) -> None:
            return

    monkeypatch.setattr("frame_compare.cli.entry.Console", FakeConsole)
    monkeypatch.setattr(
        "frame_compare.cli.entry.runner.run",
        lambda _request, dependencies=None: RunResult(
            success=True, screenshot_dir=Path("screenshots").resolve()
        ),
    )

    result = _invoke_run_with_minimal_workspace(
        ["--quiet"],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "", "TERM": "dumb"},
    )

    assert result.exit_code == 0
    assert captured == {"stderr": False, "no_color": True}


def test_run_human_output_routes_summaries_and_runtime_diagnostics(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        assert dependencies is None
        print("Clip Overview", file=sys.stderr)
        print("Frame Alignment", file=sys.stderr)
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            warnings=["metadata skipped"],
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    stdout = _normalize_cli_output(result.stdout)
    stderr = _normalize_cli_output(result.stderr)
    assert "At-a-Glance" in stdout
    assert "Result" in stdout
    assert "Warnings" in stdout
    assert "metadata skipped" in stdout
    assert "Clip Overview" not in stdout
    assert "Frame Alignment" not in stdout
    assert "Clip Overview" in stderr
    assert "Frame Alignment" in stderr
    assert "At-a-Glance" not in stderr
    assert "Result" not in stderr


def test_run_quiet_suppresses_at_a_glance_but_keeps_minimal_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.entry.runner.run",
        lambda _request, dependencies=None: RunResult(
            success=True, screenshot_dir=Path("screenshots").resolve()
        ),
    )

    result = _invoke_run_with_minimal_workspace(["--quiet"])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "At-a-Glance" not in output
    assert output.splitlines()[-1].startswith("Screenshots:")


def test_run_json_is_machine_only_and_omits_post_upload_actions(
    monkeypatch: MonkeyPatch,
) -> None:
    warning = "slow.pics webhook: delivery failed"

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            slowpics_url="https://slow.pics/c/example",
            post_upload_actions=(
                PostUploadActionResult(
                    kind="shortcut",
                    success=True,
                    path=Path("Example.url"),
                    message="slow.pics URL shortcut written",
                ),
                PostUploadActionResult(kind="webhook", success=False, warning=warning),
            ),
            warnings=[warning],
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["slowpics_url"] == "https://slow.pics/c/example"
    assert "post_upload_actions" not in payload
    assert "warnings" not in payload
    assert "At-a-Glance" not in result.stdout
    assert "Screenshots:" not in result.stdout
    assert "Warnings" not in result.stdout
    assert result.stderr == ""


def test_run_env_no_color_propagates_to_request(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([], env={"NO_COLOR": "1", "TERM": "dumb"})

    assert result.exit_code == 0
    assert captured["request"].no_color is True


@pytest.mark.parametrize(
    ("configured_level", "configured_format", "args", "expected_level", "expected_format"),
    [
        ("ERROR", "json", [], "ERROR", "json"),
        ("ERROR", "json", ["--quiet"], "WARNING", "json"),
        ("ERROR", "json", ["--verbose"], "DEBUG", "json"),
        ("ERROR", "json", ["--quiet", "--verbose"], "WARNING", "json"),
        ("ERROR", "console", ["--json"], "ERROR", "json"),
    ],
)
def test_run_logging_config_and_cli_precedence(
    monkeypatch: MonkeyPatch,
    configured_level: str,
    configured_format: str,
    args: list[str],
    expected_level: str,
    expected_format: str,
) -> None:
    captured: dict[str, str] = {}

    def _configure_logging(*, level: str, format: str) -> None:
        captured["level"] = level
        captured["format"] = format

    monkeypatch.setattr("frame_compare.cli.entry.configure_logging", _configure_logging)
    monkeypatch.setattr(
        "frame_compare.cli.entry.runner.run",
        lambda _request, dependencies=None: RunResult(success=True),
    )

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        with config_path.open("a", encoding="utf-8") as config_file:
            config_file.write(
                f'\n[logging]\nlevel = "{configured_level}"\nformat = "{configured_format}"\n'
            )

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
                *args,
            ],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )

    assert result.exit_code == 0
    assert captured == {"level": expected_level, "format": expected_format}
