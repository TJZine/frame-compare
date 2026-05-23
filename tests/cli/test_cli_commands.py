import json
import re
import tomllib
import webbrowser
from pathlib import Path
from types import SimpleNamespace

import typer
import typer.rich_utils as typer_rich_utils
from _pytest.monkeypatch import MonkeyPatch
from click import Group
from click.testing import Result
from typer.main import get_command
from typer.testing import CliRunner

from frame_compare.cli.entry import _maybe_open_report, _stabilize_typer_help_width, app
from frame_compare.config import OverlayMode, ToneCurve, TonemapPreset
from frame_compare.config.loader import get_default_config
from frame_compare.errors import (
    ConfigNotFoundError,
    ErrorContext,
    ExitCode,
    FrameCompareError,
    format_error_json,
    get_exit_code,
)
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport
from frame_compare.utils.progress import ProgressReporter

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(text: str) -> str:
    """Normalize styled CLI output for stable assertions across platforms."""
    return ANSI_ESCAPE_RE.sub("", text)


MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
"""


def _write_minimal_config(root: Path) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return config_path


def _invoke_run_with_minimal_workspace(
    args: list[str],
    *,
    color: bool = False,
    terminal_width: int | None = None,
    env: dict[str, str] | None = None,
) -> Result:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        return runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root)), *args],
            color=color,
            terminal_width=terminal_width,
            env=env,
        )


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
        assert "tonemap.preset" in output
        assert "reference" in output
        assert "tonemap.target_nits" in output
        assert "203" in output
        assert "tonemap.curve" in output
        assert "bt2390" in output
        assert "slow.pics.auto_upload" in output
        assert "slow.pics.visibility" in output
        assert "unlisted" in output
        assert "report.enabled" in output
        assert "report.auto_open" in output


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
    assert "probe failed (RuntimeError: no display)" in output


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
    assert "- warning 1" in output
    assert "- warning 8" in output
    assert "- ... (2 more)" in output
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
    assert "- metadata skipped" in output
    assert "- upload reused" in output
    assert "more)" not in output


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


def test_run_opens_report_for_interactive_tty_when_auto_open_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert opened["path"] == Path("report.html")


def test_run_does_not_open_report_when_auto_open_disabled_in_config(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        config_path.write_text(
            MINIMAL_CONFIG + "\n[report]\nauto_open = false\n",
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
    assert "path" not in opened


def test_run_does_not_open_report_when_stdout_is_not_a_tty(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: False)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_does_not_open_report_when_quiet(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace(["--quiet"])

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_does_not_open_report_when_json_output_requested(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace(["--json"])

    assert result.exit_code == 0
    assert "path" not in opened


def test_run_opens_report_when_post_run_config_reload_fails(monkeypatch: MonkeyPatch) -> None:
    opened: dict[str, Path] = {}
    load_calls = 0

    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(
            success=True,
            screenshot_dir=Path("screenshots").resolve(),
            report_path=Path("report.html"),
        )

    def _load_config(_path: Path):
        nonlocal load_calls
        load_calls += 1
        if load_calls == 1:
            return get_default_config()
        raise ConfigNotFoundError(Path("missing.toml"))

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
    monkeypatch.setattr("frame_compare.cli.entry.load_config", _load_config)
    monkeypatch.setattr(
        "frame_compare.cli.entry.sys",
        SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(
        "frame_compare.cli.entry._maybe_open_report",
        lambda report_path: opened.setdefault("path", report_path),
    )

    result = _invoke_run_with_minimal_workspace([])

    assert result.exit_code == 0
    assert load_calls == 2
    assert opened["path"] == Path("report.html")


def test_run_reloads_config_after_runner_and_respects_mid_run_auto_open_change(
    monkeypatch: MonkeyPatch,
) -> None:
    opened: dict[str, Path] = {}

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)

        def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
            config_path.write_text(
                MINIMAL_CONFIG + "\n[report]\nauto_open = false\n",
                encoding="utf-8",
            )
            return RunResult(
                success=True,
                screenshot_dir=Path("screenshots").resolve(),
                report_path=Path("report.html"),
            )

        monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)
        monkeypatch.setattr(
            "frame_compare.cli.entry.sys",
            SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True)),
        )
        monkeypatch.setattr(
            "frame_compare.cli.entry._maybe_open_report",
            lambda report_path: opened.setdefault("path", report_path),
        )

        result = runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root))],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )

    assert result.exit_code == 0
    assert "path" not in opened


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


def test_maybe_open_report_swallows_webbrowser_error(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("frame_compare.cli.entry.os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(
        "frame_compare.cli.entry.webbrowser.open",
        lambda _uri: (_ for _ in ()).throw(webbrowser.Error("no browser")),
    )

    _maybe_open_report(Path("report.html"))


def test_maybe_open_report_keeps_startfile_path_on_windows(monkeypatch: MonkeyPatch) -> None:
    called: dict[str, str] = {}
    fake_os = SimpleNamespace(
        name="nt",
        startfile=lambda value: called.setdefault("path", value),
    )
    monkeypatch.setattr("frame_compare.cli.entry.os", fake_os)
    monkeypatch.setattr(
        "frame_compare.cli.entry.webbrowser.open",
        lambda _uri: (_ for _ in ()).throw(AssertionError("webbrowser.open should not be called")),
    )

    _maybe_open_report(Path("report.html"))
    assert called["path"] == "report.html"


def test_maybe_open_report_falls_back_to_webbrowser_when_startfile_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def _raise_startfile(_value: str) -> None:
        raise OSError("boom")

    fake_os = SimpleNamespace(name="nt", startfile=_raise_startfile)
    monkeypatch.setattr("frame_compare.cli.entry.os", fake_os)
    monkeypatch.setattr(
        "frame_compare.cli.entry.webbrowser.open",
        lambda uri: called.setdefault("uri", uri),
    )

    _maybe_open_report(Path("report.html"))

    assert called["uri"].startswith("file:")


def test_wizard_writer_uses_atomic_write(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from frame_compare.cli.entry import _write_wizard_config_payload

    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _fake_write)

    destination = tmp_path / "config" / "config.toml"
    _write_wizard_config_payload(destination, {"paths": {}, "slowpics": {}})

    assert calls == [destination]


def test_run_exits_processing_error_when_runner_returns_unsuccessful(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        return RunResult(success=False)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace([])
    assert result.exit_code == 5


def test_run_builds_run_request_from_cli_args(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        [
            "--tm-target",
            "203",
            "--overlay",
            "diagnostic",
            "--force-interactive-alignment",
        ]
    )
    assert result.exit_code == 0

    request = captured["request"]
    assert request.tm_target_nits == 203
    assert request.overlay_mode == OverlayMode.DIAGNOSTIC
    assert request.force_interactive_alignment is True


def test_run_builds_run_request_with_typed_choice_overrides(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(
        [
            "--tm-preset",
            "filmic",
            "--tm-curve",
            "spline",
            "--overlay",
            "diagnostic",
        ]
    )

    assert result.exit_code == 0
    request = captured["request"]
    assert request.tm_preset == TonemapPreset.FILMIC
    assert request.tm_curve == ToneCurve.SPLINE
    assert request.overlay_mode == OverlayMode.DIAGNOSTIC


def test_run_builds_run_request_with_input_dir(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, RunRequest] = {}

    def _run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        captured["request"] = request
        return RunResult(success=True)

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    result = _invoke_run_with_minimal_workspace(["--input", "custom_inputs"])
    assert result.exit_code == 0
    assert captured["request"].input_dir == Path("custom_inputs")


def _run_wizard_and_assert_config() -> None:
    with runner.isolated_filesystem():
        Path("inputs").mkdir()
        result = runner.invoke(
            app,
            ["wizard"],
            input="inputs\ny\npublic\ny\nabc123\n",
        )
        assert result.exit_code == 0
        assert "slow.pics visibility (public|unlisted)" in result.stdout
        assert "private" not in result.stdout

        config_path = Path("config") / "config.toml"
        assert config_path.exists()

        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert set(data.keys()) == {"paths", "slowpics", "tmdb"}
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["auto_upload"] is True
        assert data["slowpics"]["visibility"] == "public"
        assert data["slowpics"]["delete_after_upload"] is True
        assert data["tmdb"]["api_key"] == "abc123"


def test_wizard_writes_valid_config_toml():
    _run_wizard_and_assert_config()


def test_wizard_writer_writes_to_explicit_config_path(tmp_path: Path) -> None:
    from frame_compare.cli.entry import _write_wizard_config_payload

    destination = tmp_path / "custom" / "config.toml"
    payload: dict[str, object] = {
        "paths": {"input_dir": "comparison_videos"},
        "slowpics": {"auto_upload": False},
        "tmdb": {"api_key": None},
    }

    _write_wizard_config_payload(destination, payload)

    assert destination.exists()
    text = destination.read_text(encoding="utf-8")
    assert "[paths]" in text
    assert 'input_dir = "comparison_videos"' in text
    data = tomllib.loads(text)
    assert "tmdb" not in data


def test_wizard_cancel_exits_130_and_writes_nothing(monkeypatch: MonkeyPatch) -> None:
    def _abort(*_args: object, **_kwargs: object) -> None:
        raise typer.Abort()

    monkeypatch.setattr("frame_compare.cli.entry.typer.prompt", _abort)

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["wizard"])
        assert result.exit_code == 130
        assert not (Path("config") / "config.toml").exists()


def test_wizard_write_error_uses_cli_error_contract(monkeypatch: MonkeyPatch) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr(
        "frame_compare.cli.entry._prompt_input_dir",
        lambda *_args, **_kwargs: "inputs",
    )
    monkeypatch.setattr("frame_compare.cli.entry.typer.confirm", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "frame_compare.cli.entry._prompt_visibility",
        lambda _default: "unlisted",
    )
    monkeypatch.setattr("frame_compare.cli.entry.typer.prompt", lambda *_args, **_kwargs: "")
    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(app, ["wizard", "--root", str(root)])

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert result.stdout == ""
        assert "FC-1007" in result.stderr
        assert "Failed to write configuration file" in result.stderr
        assert "Traceback" not in result.stderr
        assert not (root / "config" / "config.toml").exists()


def test_wizard_root_validates_relative_input_dir_against_root() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["wizard", "--root", str(root)],
            input="inputs\ny\nunlisted\ny\nabc123\n",
        )
        assert result.exit_code == 0

        config_path = root / "config" / "config.toml"
        assert config_path.exists()
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["visibility"] == "unlisted"


def test_wizard_root_reprompts_on_missing_input_dir() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        root.mkdir()
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["wizard", "--root", str(root)],
            input="missing\ninputs\ny\nprivate\nunlisted\ny\nabc123\n",
        )
        assert result.exit_code == 0
        assert "Invalid visibility. Choose public or unlisted." in result.stdout

        config_path = root / "config" / "config.toml"
        assert config_path.exists()
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["visibility"] == "unlisted"


def test_prepare_toml_payload_copies_paths_and_slowpics_sections() -> None:
    from frame_compare.cli.entry import _prepare_toml_payload

    paths = {"input_dir": "inputs"}
    slowpics = {"auto_upload": True}
    payload: dict[str, object] = {
        "paths": paths,
        "slowpics": slowpics,
        "tmdb": {"api_key": ""},
    }

    prepared = _prepare_toml_payload(payload)
    assert prepared["paths"] == paths
    assert prepared["slowpics"] == slowpics
    assert prepared["paths"] is not paths
    assert prepared["slowpics"] is not slowpics
    assert "tmdb" not in prepared


def test_doctor_json_conforms_to_schema_shape(monkeypatch: MonkeyPatch) -> None:
    checks = [
        DoctorCheck(
            name="python_version",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="ok"),
        ),
        DoctorCheck(
            name="ffmpeg",
            category="optional",
            check_fn=lambda: CheckResult(
                passed=False,
                message="missing",
                hint="install ffmpeg",
                details={"path": None},
            ),
        ),
    ]
    report = DoctorReport(
        checks=[(checks[0], checks[0].check_fn()), (checks[1], checks[1].check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["doctor"]["baseline_version"] == "R73"
    assert len(payload["doctor"]["checks"]) == 2
    first = payload["doctor"]["checks"][0]
    second = payload["doctor"]["checks"][1]
    assert first["id"] == "python_version"
    assert first["category"] == "core"
    assert first["status"] == "pass"
    assert "message" in first
    assert second["id"] == "ffmpeg"
    assert second["category"] == "optional"
    assert second["status"] == "fail"
    assert second["install_hint"] == "install ffmpeg"
    assert "details" in second


def test_preset_apply_missing_preset_exits_with_error_code() -> None:
    with runner.isolated_filesystem():
        root = Path(".")
        config_path = _write_minimal_config(root)
        result = runner.invoke(
            app,
            [
                "preset",
                "apply",
                "missing",
                "--root",
                str(root),
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 2
        assert "FC-1004" in result.output


def test_preset_apply_invalid_name_exits_with_error_code() -> None:
    with runner.isolated_filesystem():
        root = Path(".")
        config_path = _write_minimal_config(root)
        result = runner.invoke(
            app,
            [
                "preset",
                "apply",
                "../escape",
                "--root",
                str(root),
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 2
        assert "FC-1006" in result.output


def test_doctor_exit_code_is_3_on_core_failure(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="vapoursynth",
        category="core",
        check_fn=lambda: CheckResult(passed=False, message="missing"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=["vapoursynth"],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3


def _run_doctor_optional_failure_and_assert(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="slowpics",
        category="network",
        check_fn=lambda: CheckResult(passed=False, message="offline"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_doctor_exit_code_is_0_on_optional_or_network_failure(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_doctor_stub_text(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_preset_list_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Zebra.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Zebra"]


def test_preset_apply_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nframe_count = 12\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["preset", "apply", "boost", "--root", str(root), "--config", "config/config.toml"],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 12


def test_preset_save_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "demo", "--root", str(root), "--config", "config/config.toml"],
        )
        assert result.exit_code == 0
        preset_path = root / "config" / "presets" / "demo.toml"
        assert preset_path.exists()


def test_preset_list_prints_names_sorted_case_insensitive() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Bravo.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')
        (presets_dir / "charlie.toml").write_text('[paths]\ninput_dir = "c"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Bravo", "charlie"]


def test_preset_list_uses_root_presets_even_when_config_path_is_nondefault() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')

        result = runner.invoke(
            app,
            ["preset", "list", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha"]


def test_preset_save_respects_root_and_config_writes_preset_file() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "sample", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        preset_path = root / "config" / "presets" / "sample.toml"
        assert preset_path.exists()


def test_preset_save_write_error_uses_cli_error_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.config.presets.write_text_atomic", _write_text_atomic)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "demo", "--root", str(root), "--config", "config/config.toml"],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stdout == ""
    assert "FC-1007" in result.stderr
    assert "Failed to write preset file" in result.stderr
    assert "Traceback" not in result.stderr


def test_preset_apply_respects_root_and_config_updates_config_file() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nframe_count = 22\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["preset", "apply", "boost", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 22


def test_run_write_config_respects_root_and_config_and_does_not_invoke_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --write-config")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            [
                "run",
                "--write-config",
                "--root",
                str(root),
                "--config",
                "configs/config.toml",
                "--frame-count",
                "17",
            ],
        )
        assert result.exit_code == 0
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 17


def test_run_write_config_write_error_uses_cli_error_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    result = _invoke_run_with_minimal_workspace(["--write-config"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stdout == ""
    assert "FC-1007" in result.stderr
    assert "Failed to write configuration file" in result.stderr
    assert "Traceback" not in result.stderr


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


def test_run_diagnose_paths_outputs_pinned_json_schema_and_does_not_invoke_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    def _run(_request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        raise AssertionError("runner.run should not be invoked for --diagnose-paths")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _run)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            [
                "run",
                "--diagnose-paths",
                "--root",
                str(root),
                "--config",
                "config/config.toml",
                "--input",
                "inputs",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {"cache", "config", "input", "output", "root"}
        assert payload["root"] == str(root.resolve())
        assert payload["config"] == str(config_path.resolve())
        assert payload["input"] == str((root / "inputs").resolve())
        assert payload["output"] == str((root / "screenshots").resolve())
        assert payload["cache"] == str((root / "generated").resolve())


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

    result = runner.invoke(app, ["run", "--json"])
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

    result = runner.invoke(app, ["run", "--json"])
    assert result.exit_code == int(get_exit_code(ConfigNotFoundError(Path("missing.toml"))))
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

    result = runner.invoke(app, ["run", "--json"])
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
    assert "[red]" not in result.stderr
    assert "[yellow]" not in result.stderr


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
