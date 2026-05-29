import json
from pathlib import Path

from pytest import MonkeyPatch

from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.errors import ErrorContext, FrameCompareError
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult

from .cli_helpers import _invoke_run_with_minimal_workspace


def test_run_write_config_json_write_error_outputs_error_schema(
    monkeypatch: MonkeyPatch,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    result = _invoke_run_with_minimal_workspace(["--write-config", "--json"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1007"
    assert payload["error"]["name"] == "CONFIG_WRITE_ERROR"
    assert "Failed to write configuration file" in payload["error"]["message"]
    assert "path" in payload["error"]["details"]
    assert payload["error"]["details"]["error"] == "permission denied"


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

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--json"])
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

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--json"])
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    expected = format_error_json(ConfigNotFoundError(Path("missing.toml")))
    assert payload == expected


def test_run_exit_code_maps_by_error_category_prefix_in_json_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    error = FrameCompareError(
        ErrorContext(code="FC-3001", name="GENERIC_INPUT", message="bad input")
    )

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--json"])
    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    payload = json.loads(result.stdout)
    assert payload == format_error_json(error)


def test_run_json_invalid_tm_preset_outputs_config_error_schema(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI choices")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--json", "--tm-preset", "invalid"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["name"] == "CONFIG_VALIDATION_ERROR"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == ["color", "preset"]


def test_run_json_invalid_overlay_outputs_config_error_schema(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI choices")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--json", "--overlay", "invalid"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["name"] == "CONFIG_VALIDATION_ERROR"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == [
        "screenshots",
        "overlay_mode",
    ]


def test_run_exit_code_is_130_on_keyboard_interrupt(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise KeyboardInterrupt()

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])
    assert result.exit_code == int(ExitCode.INTERRUPTED)


def test_run_no_color_error_output_has_no_rich_markup(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--no-color"])
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert "\x1b[" not in result.stderr
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr


def test_run_env_no_color_error_output_has_no_rich_markup(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        [],
        env={"NO_COLOR": "1", "TERM": "dumb"},
    )
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert "\x1b[" not in result.stderr
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr


def test_run_no_color_error_output_preserves_literal_brackets(
    monkeypatch: MonkeyPatch,
) -> None:
    error = FrameCompareError(
        ErrorContext(
            code="FC-3001",
            name="BRACKETED_VALUE",
            message="File [1080p] missing",
            hint="Try [literal] brackets",
        )
    )

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--quiet", "--no-color"])

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stdout == ""
    assert "Error [FC-3001]: File [1080p] missing" in result.stderr
    assert "[[FC-3001]]" not in result.stderr
    assert "Hint: Try [literal] brackets" in result.stderr
    assert "\x1b[" not in result.stderr
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr
    assert "Traceback" not in result.stderr
