import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from frame_compare.analysis.errors import ExclusionRecoverySelectionError
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
            MINIMAL_CONFIG + "\n[audio_alignment]\nuse_vsview = true\n",
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
            "loc": ["audio_alignment", "use_vsview"],
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
        ("audio_alignment", "use_vsview"),
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
        ("audio_alignment", "use_vsview"),
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


def test_run_json_routes_typed_error_through_shared_formatter(
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


def test_run_json_exclusion_recovery_fails_closed_without_confirmation_dependency(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    error = ExclusionRecoverySelectionError(
        "configured exclusions leave too little media for frame selection",
        requested=8,
        found=4,
        hint="Reduce exclusions or use a clip-specific config",
    )

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        assert dependencies is None
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[analysis]\nignore_lead_seconds = 240.0\n",
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

    assert result.exit_code == int(ExitCode.PROCESSING_ERROR)
    assert result.stderr == ""
    assert json.loads(result.stdout) == format_error_json(error)


def test_run_quiet_exclusion_recovery_fails_closed_on_stderr_without_prompt(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    error = ExclusionRecoverySelectionError(
        "configured exclusions leave too little media for frame selection",
        requested=8,
        found=4,
        hint="Reduce exclusions or use a clip-specific config",
    )

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        assert dependencies is None
        raise error

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[analysis]\nignore_trail_seconds = 240.0\n",
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
                "--quiet",
            ],
        )

    assert result.exit_code == int(ExitCode.PROCESSING_ERROR)
    assert result.stdout == ""
    assert "[FC-4012]" in result.stderr
    assert "Analyze the full shared clip" not in result.stderr


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


@pytest.mark.parametrize(
    ("flag", "value", "loc"),
    [
        ("--tm-preset", "invalid", ["color", "preset"]),
        ("--overlay", "invalid", ["screenshots", "overlay_mode"]),
        ("--frames", "abc", ["analysis", "user_frames"]),
    ],
)
def test_run_json_invalid_choice_outputs_config_error_schema(
    monkeypatch: MonkeyPatch, tmp_path: Path, flag: str, value: str, loc: list[str]
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid CLI choices")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    result = _invoke_run_with_minimal_workspace(
        ["--json", flag, value], tmp_path=tmp_path, monkeypatch=monkeypatch
    )
    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["name"] == "CONFIG_VALIDATION_ERROR"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == loc


def test_run_json_redacts_secret_config_inputs_from_validation_errors(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for invalid config")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG
            + """
[slowpics]
webhook_url = ["sentinel-webhook-secret"]

[tmdb]
api_key = ["sentinel-tmdb-secret"]
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
    assert "sentinel-webhook-secret" not in result.stdout
    assert "sentinel-tmdb-secret" not in result.stdout
    payload = json.loads(result.stdout)
    validation_errors = payload["error"]["details"]["validation_errors"]
    assert {tuple(error["loc"]): error["input"] for error in validation_errors} == {
        ("slowpics", "webhook_url"): "<redacted>",
        ("tmdb", "api_key"): "<redacted>",
    }


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


@pytest.mark.parametrize(
    "source, content, code",
    [
        ("toml", "x = " + "{x=" * 1500 + "0" + "}" * 1500, "FC-1002"),
        ("toml", "x = " + "1" * 5000, "FC-1002"),
        ("env", "[" * 10000, "FC-1003"),
        ("env", "1" * 5000, "FC-1003"),
        ("toml", "[tmdb]\ntimeout_seconds = inf\n", "FC-1003"),
        ("timeout-env", "inf", "FC-1003"),
    ],
)
def test_run_json_reports_parser_limits_and_nonfinite_timeout(
    tmp_path: Path, monkeypatch: MonkeyPatch, source: str, content: str, code: str
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        path = _write_minimal_config(root)
        if source == "toml":
            path.write_text(content, encoding="utf-8")
        elif source == "env":
            monkeypatch.setenv("FRAME_COMPARE_TMDB", content)
        else:
            monkeypatch.setenv("FRAME_COMPARE_TMDB__TIMEOUT_SECONDS", content)
        result = runner.invoke(app, ["run", "--root", str(root), "--json"])
    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == code


@pytest.mark.parametrize(
    "variable, content",
    [
        ("FRAME_COMPARE_ANALYSIS", "[" * 2000 + '{"api_key":"sentinel-deep-secret"}' + "]" * 2000),
        ("FRAME_COMPARE_TMDB", "[" * 1000 + '{"api_key":"sentinel-deep-secret"}' + "]" * 1000),
        (
            "FRAME_COMPARE_TMDB",
            '{"api_key":' + '{"nested":' * 1000 + '"sentinel-deep-secret"' + "}" * 1000 + "}",
        ),
    ],
)
def test_run_json_balanced_deep_environment_errors_at_default_recursion(
    tmp_path: Path, variable: str, content: str
) -> None:
    _write_minimal_config(tmp_path)
    env = {key: value for key, value in os.environ.items() if not key.startswith("FRAME_COMPARE_")}
    env[variable] = content
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; assert sys.getrecursionlimit() == 1000; from frame_compare.cli.entry import app; app()",
            "run",
            "--root",
            str(tmp_path),
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == int(ExitCode.CONFIG_ERROR), result.stderr
    assert result.stderr == ""
    assert "sentinel-deep-secret" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    validation_errors = payload["error"]["details"]["validation_errors"]
    assert validation_errors[0]["type"] == (
        "string_type" if content.startswith('{"api_key":') else "model_type"
    )
    assert "input" in validation_errors[0]
    assert len(result.stdout) < 4000
