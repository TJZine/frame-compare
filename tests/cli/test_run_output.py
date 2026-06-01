import json
from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.types import PostUploadActionResult

from .cli_helpers import (
    MINIMAL_CONFIG,
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

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True, screenshot_dir=Path("screenshots").resolve())

    monkeypatch.setattr("frame_compare.cli.entry.Console", FakeConsole)
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        ["--quiet"],
        color=False,
        terminal_width=200,
        env={"NO_COLOR": "", "TERM": "dumb"},
    )
    assert result.exit_code == 0
    assert captured["no_color"] is True


def test_run_exits_zero_when_runner_returns_success(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])
    assert result.exit_code == 0


def test_run_default_prints_at_a_glance_and_result_summary(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            slowpics_url=None,
            report_path=None,
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)

        result = runner.invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--config",
                str(config_path.relative_to(root)),
            ],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )
        assert result.exit_code == 0
        output = _normalize_cli_output(result.stdout)
        assert "At-a-Glance" in output
        assert "Result" in output
        assert "root" in output
        assert "config" in output
        assert "input" in output
        assert "screenshots" in output
        assert "run_folders" in output
        assert "base paths" in output
        assert "tonemap.preset" in output
        assert "reference" in output
        assert "tonemap.target_nits" in output
        assert "100" in output
        assert "tonemap.curve" in output
        assert "bt2390" in output
        assert "slow.pics" in output
        assert "auto_upload" in output
        assert "visibility" in output
        assert "unlisted" in output
        assert "report" in output
        assert "enabled" in output
        assert "auto_open" in output


def test_run_at_a_glance_prints_resolved_tonemap_preset_settings(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--tm-preset", "filmic"])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "tonemap.preset" in output
    assert "filmic" in output
    assert "tonemap.target_nits" in output
    assert "203" in output
    assert "tonemap.curve" in output
    assert "spline" in output


def test_run_at_a_glance_prints_vspreview_availability_when_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    from frame_compare.vspreview.adapter import VSPreviewAvailability, VSPreviewAvailabilityStatus

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="VSPreview is available for interactive alignment",
        ),
    )

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[audio_alignment]\nuse_vspreview = true\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root))],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "audio_alignment.use_vspreview" in output
    assert "vspreview.available" in output
    assert "true" in output


def test_run_at_a_glance_prints_vspreview_probe_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    from frame_compare.vspreview.adapter import VSPreviewAvailability, VSPreviewAvailabilityStatus

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.PROBE_FAILED,
            message="VSPreview availability probe failed",
            error_details={
                "exception_type": "RuntimeError",
                "exception": "no display",
            },
        ),
    )

    result = _invoke_run_with_minimal_workspace(["--force-interactive-alignment"])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "audio_alignment.force_interactive" in output
    assert "vspreview.available" in output
    assert "probe failed (RuntimeError)" in output
    assert "no display" not in output


def test_run_result_summary_prints_status_and_truncated_warnings(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            warnings=[f"warning {index}" for index in range(1, 11)],
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "Result" in output
    assert "status" in output
    assert "success" in output
    assert "Warnings" in output
    assert "• warning 1" in output
    assert "• warning 8" in output
    assert "• ... (2 more)" in output
    assert "warning 9" not in output


def test_run_result_summary_prints_slowpics_url_and_untruncated_warnings(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
            warnings=["metadata skipped", "upload reused"],
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "slow.pics" in output
    assert "https://slow.pics/c/example" in output
    assert "• metadata skipped" in output
    assert "• upload reused" in output
    assert "more)" not in output


def test_run_result_summary_prints_interactive_slowpics_action_outcomes(
    monkeypatch: MonkeyPatch,
) -> None:
    copied: list[str] = []
    opened: list[str] = []

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True, slowpics_url="https://slow.pics/c/example")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr("frame_compare.cli.entry._copy_text_to_clipboard", copied.append)
    monkeypatch.setattr(
        "frame_compare.cli.entry._open_url_in_browser",
        lambda url: opened.append(url) is None or True,
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert copied == ["https://slow.pics/c/example"]
    assert opened == ["https://slow.pics/c/example"]
    output = _normalize_cli_output(result.stdout)
    assert "slow.pics" in output
    assert "https://slow.pics/c/example" in output
    assert "clipboard" in output
    assert "slow.pics URL copied to clipboard" in output
    assert "browser" in output
    assert "slow.pics URL opened in browser" in output


def test_run_result_summary_merges_interactive_slowpics_action_warnings(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True, slowpics_url="https://slow.pics/c/example")

    def _copy_url(_url: str) -> None:
        raise RuntimeError("clipboard unavailable")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr("frame_compare.cli.entry._copy_text_to_clipboard", _copy_url)
    monkeypatch.setattr("frame_compare.cli.entry._open_url_in_browser", lambda _url: False)

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "Warnings" in output
    assert "• slow.pics clipboard: failed to copy URL: clipboard unavailable" in output
    assert "• slow.pics browser: failed to open URL: no browser accepted the request" in output


def test_run_result_summary_prints_duplicate_post_upload_warning_once(
    monkeypatch: MonkeyPatch,
) -> None:
    warning = "slow.pics shortcut: failed to write URL shortcut"

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            slowpics_url="https://slow.pics/c/example",
            post_upload_actions=(
                PostUploadActionResult(
                    kind="shortcut",
                    success=False,
                    warning=warning,
                ),
            ),
            warnings=[warning],
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.stdout)
    assert "Warnings" in output
    assert output.count(warning) == 1


def test_run_quiet_suppresses_at_a_glance_but_keeps_minimal_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True, screenshot_dir=Path("screenshots").resolve())

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)

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
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )
        assert result.exit_code == 0
        output = _normalize_cli_output(result.stdout)
        assert "At-a-Glance" not in output
        assert output.splitlines()[-1].startswith("Screenshots:")


def test_run_json_outputs_json_only(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True, screenshot_dir=Path("screenshots").resolve())

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)

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
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert "At-a-Glance" not in result.stdout
        assert "Screenshots:" not in result.stdout


def test_run_stub_executes(monkeypatch: MonkeyPatch) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])
    assert result.exit_code == 0


def test_run_env_no_color_sets_request_no_color(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([], env={"NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0
    assert captured["request"].no_color is True


def test_run_verbose_calls_configure_logging_debug(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def _configure_logging(*, level: str, format: str) -> None:
        captured["level"] = level
        captured["format"] = format

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.configure_logging", _configure_logging)
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--verbose"])
    assert result.exit_code == 0
    assert captured["level"] == "DEBUG"

    result = _invoke_run_with_minimal_workspace(["--quiet"])
    assert result.exit_code == 0
    assert captured["level"] == "WARNING"
