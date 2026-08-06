import json
from pathlib import Path

from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.errors import ErrorContext, FrameCompareError
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult

from .cli_helpers import (
    MINIMAL_CONFIG,
    _invoke_run_with_minimal_workspace,
    _write_minimal_config,
    isolated_cli_filesystem,
    runner,
)


def test_run_write_config_json_write_error_outputs_error_schema(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    result = _invoke_run_with_minimal_workspace(
        ["--write-config", "--json"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1007"
    assert payload["error"]["name"] == "CONFIG_WRITE_ERROR"
    assert "Failed to write configuration file" in payload["error"]["message"]
    assert "path" in payload["error"]["details"]
    assert payload["error"]["details"]["error"] == "permission denied"


def test_run_json_rejects_external_config_before_load_write_or_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external config must be rejected before side effects")

    monkeypatch.setattr("frame_compare.cli.entry.load_config", _unexpected)
    monkeypatch.setattr("frame_compare.cli.entry.write_config_to", _unexpected)
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _unexpected)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        root.mkdir()
        external_config = Path("outside") / "config.toml"
        resolved_root = root.resolve()
        resolved_external_config = external_config.resolve()
        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(resolved_external_config),
                "--json",
            ],
        )

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-3009"
    assert payload["error"]["details"] == {
        "path": str(resolved_external_config),
        "root": str(resolved_root),
    }


def test_run_json_outputs_pinned_success_schema_and_stdout_is_pure_json(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
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

    result = _invoke_run_with_minimal_workspace(
        ["--json"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )
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


def test_run_json_success_omits_warnings_from_stdout(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            warnings=["cleanup: failed to delete uploaded screenshot shots/a.png: locked"],
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert "warnings" not in payload
    assert "cleanup:" not in result.stdout


def test_run_json_rejects_interactive_alignment_from_config_before_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI/config combinations")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[audio_alignment]\nuse_vspreview = true\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
                "--json",
            ],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["message"] == "Interactive alignment is not supported with --json"
    assert payload["error"]["details"]["validation_errors"] == [
        {
            "input": True,
            "loc": ["audio_alignment", "use_vspreview"],
            "msg": "Interactive alignment is not supported with --json.",
            "type": "value_error",
        }
    ]


def test_run_json_rejects_force_interactive_alignment_before_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI/config combinations")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json", "--force-interactive-alignment"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    validation_errors = payload["error"]["details"]["validation_errors"]
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["message"] == "Interactive alignment is not supported with --json"
    assert {tuple(entry["loc"]) for entry in validation_errors} == {
        ("audio_alignment", "force_interactive"),
        ("audio_alignment", "use_vspreview"),
    }


def test_run_json_aggregates_previous_offset_prompt_conflicts_before_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI/config combinations")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG
            + """
[audio_alignment]
previous_offsets = "prompt"
cache_results = false
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
                "--json",
                "--force-interactive-alignment",
            ],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    validation_errors = payload["error"]["details"]["validation_errors"]
    assert payload["error"]["message"] == "Interactive alignment is not supported with --json"
    assert {tuple(entry["loc"]) for entry in validation_errors} == {
        ("audio_alignment", "force_interactive"),
        ("audio_alignment", "use_vspreview"),
        ("audio_alignment", "previous_offsets"),
        ("audio_alignment", "cache_results"),
    }
    assert (
        sum(
            1
            for entry in validation_errors
            if entry["loc"] == ["audio_alignment", "previous_offsets"]
        )
        == 3
    )


def test_run_json_rejects_report_confirmed_slowpics_before_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI/config combinations")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG
            + "\n[slowpics]\nauto_upload = true\nconfirm_upload_after_report = true\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
                "--json",
            ],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["message"] == (
        "Report-confirmed slow.pics upload requires an interactive report-enabled run"
    )
    assert "warnings" not in payload
    assert result.stdout.count("\n") == 1
    assert {
        tuple(entry["loc"]): entry["msg"]
        for entry in payload["error"]["details"]["validation_errors"]
    }[("cli", "json")] == "Report-confirmed slow.pics upload is not supported with --json."


def test_run_json_report_confirmed_slowpics_message_uses_actual_failure(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI/config combinations")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG
            + """
[audio_alignment]
previous_offsets = "always"

[slowpics]
auto_upload = true
confirm_upload_after_report = true
""",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
                "--json",
            ],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["message"] == (
        "Report-confirmed slow.pics upload requires an interactive report-enabled run"
    )
    assert payload["error"]["hint"] == (
        "Disable slowpics.confirm_upload_after_report, disable slowpics.auto_upload, "
        "enable reports, or run from an interactive terminal without --json/--quiet"
    )
    validation_locs = {
        tuple(entry["loc"]) for entry in payload["error"]["details"]["validation_errors"]
    }
    assert ("cli", "json") in validation_locs
    assert ("audio_alignment", "previous_offsets") not in validation_locs


def test_run_json_outputs_error_schema_and_exit_code(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    expected = format_error_json(ConfigNotFoundError(Path("missing.toml")))
    assert payload == expected


def test_run_exit_code_maps_by_error_category_prefix_in_json_mode(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    error = FrameCompareError(
        ErrorContext(code="FC-3001", name="GENERIC_INPUT", message="bad input")
    )

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )
    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    payload = json.loads(result.stdout)
    assert payload == format_error_json(error)


def test_run_json_invalid_tm_preset_outputs_config_error_schema(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI choices")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json", "--tm-preset", "invalid"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["name"] == "CONFIG_VALIDATION_ERROR"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == ["color", "preset"]


def test_run_json_invalid_overlay_outputs_config_error_schema(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI choices")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json", "--overlay", "invalid"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

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


def test_run_json_invalid_frames_outputs_config_error_schema(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid frame selectors")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json", "--frames", "abc"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == [
        "analysis",
        "user_frames",
    ]


def test_run_json_skip_analysis_rejects_metric_frame_count_before_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --skip-analysis conflict")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--json", "--skip-analysis", "--dark-frame-count", "1"],
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["message"] == "Metric-based frame selection requires analysis"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == [
        "analysis",
        "dark_frame_count",
    ]


def test_run_json_stale_analysis_config_keys_fail_before_runner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for stale analysis config")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + '\n[analysis]\nselection_mode = "mixed"\nframe_count = 12\n',
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
                "--json",
            ],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "FC-1003"
    assert {tuple(entry["loc"]) for entry in payload["error"]["details"]["validation_errors"]} == {
        ("analysis", "selection_mode"),
        ("analysis", "frame_count"),
    }


def test_run_exit_code_is_130_on_keyboard_interrupt(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise KeyboardInterrupt()

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([], tmp_path=tmp_path, monkeypatch=monkeypatch)
    assert result.exit_code == int(ExitCode.INTERRUPTED)


def test_run_no_color_error_output_has_no_rich_markup(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--no-color"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert "\x1b[" not in result.stderr
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr


def test_run_env_no_color_error_output_has_no_rich_markup(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        [],
        env={"NO_COLOR": "1", "TERM": "dumb"},
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
    assert "\x1b[" not in result.stderr
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr


def test_run_no_color_error_output_preserves_literal_brackets(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
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

    result = _invoke_run_with_minimal_workspace(
        ["--quiet", "--no-color"], tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stdout == ""
    assert "Error [FC-3001]: File [1080p] missing" in result.stderr
    assert "[[FC-3001]]" not in result.stderr
    assert "Hint: Try [literal] brackets" in result.stderr
    assert "\x1b[" not in result.stderr
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr
    assert "Traceback" not in result.stderr
