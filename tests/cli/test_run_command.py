import json
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
from typing import NoReturn

import pytest
import typer
from rich.console import Console

from frame_compare.cli.errors import ExitCode
from frame_compare.cli.run_command import (
    HandleErrorFn,
    LoadConfigFn,
    RunCliOptions,
    RunCliRawArgs,
    RunCommandDeps,
    WriteConfigFn,
    build_run_request_from_cli,
    handle_diagnose_paths,
    handle_json_output,
    handle_run,
    maybe_open_run_report,
)
from frame_compare.config.errors import ConfigNotFoundError, ConfigWriteError
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import (
    ConfigSchema,
    OverlayMode,
    PathsConfig,
    ReportConfig,
    ToneCurve,
    TonemapPreset,
)
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult


class RecordingRunner:
    def __init__(self, result: RunResult | None = None) -> None:
        self.result = result or RunResult(success=True)
        self.requests: list[RunRequest] = []

    def run(self, request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        self.requests.append(request)
        return self.result


def _base_args() -> RunCliRawArgs:
    return RunCliRawArgs(
        resolved_root=Path("/workspace"),
        config_path=Path("/workspace/config/config.toml"),
        input_dir=None,
        no_cache=False,
        from_cache_only=False,
        no_upload=False,
        tm_preset=None,
        tm_target=None,
        tm_curve=None,
        frame_count=None,
        seed=None,
        overlay=None,
        skip_analysis=False,
        skip_metadata=False,
        skip_dovi=False,
        force_interactive_alignment=False,
        json_output=False,
        no_color=False,
        write_config=False,
        diagnose_paths=False,
        quiet=True,
        verbose=False,
    )


def _console_factory(*, stderr: bool, no_color: bool) -> Console:
    return Console(file=StringIO(), stderr=stderr, no_color=no_color)


def _raise_unexpected_load(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> NoReturn:
    raise AssertionError("load_config should not be called")


def _raise_unexpected_write(path: Path, config: ConfigSchema) -> NoReturn:
    raise AssertionError("write_config_to should not be called")


def _handle_error(error: Exception, *, no_color: bool, verbose: bool) -> int:
    assert isinstance(error, ConfigWriteError)
    assert no_color is True
    assert verbose is False
    return int(ExitCode.CONFIG_ERROR)


@dataclass(frozen=True)
class DepsOptions:
    runner: RecordingRunner | None = None
    load_config: LoadConfigFn = _raise_unexpected_load
    write_config_to: WriteConfigFn = _raise_unexpected_write
    handle_error: HandleErrorFn = _handle_error
    stdout_is_tty: bool = False
    no_color_env_present: bool = False


def _deps(options: DepsOptions | None = None, opened: list[Path] | None = None) -> RunCommandDeps:
    opts = options or DepsOptions()
    opened_reports = [] if opened is None else opened

    def _open_report(report_path: Path) -> None:
        opened_reports.append(report_path)

    return RunCommandDeps(
        runner=opts.runner or RecordingRunner(),
        load_config=opts.load_config,
        write_config_to=opts.write_config_to,
        handle_error=opts.handle_error,
        configure_logging=lambda *, level, format: None,
        console_factory=_console_factory,
        open_report=_open_report,
        stdout_is_tty=opts.stdout_is_tty,
        no_color_env_present=opts.no_color_env_present,
    )


def test_build_run_request_from_cli_maps_all_runtime_options() -> None:
    request = build_run_request_from_cli(
        RunCliOptions(
            root=Path("/workspace"),
            config_path=Path("/workspace/config/custom.toml"),
            input_dir=Path("inputs"),
            no_cache=True,
            from_cache_only=True,
            no_upload=True,
            tm_preset=TonemapPreset.FILMIC,
            tm_target_nits=203,
            tm_curve=ToneCurve.SPLINE,
            frame_count=17,
            seed=42,
            overlay_mode=OverlayMode.DIAGNOSTIC,
            skip_analysis=True,
            skip_metadata=True,
            skip_dovi=True,
            force_interactive_alignment=True,
            json_output=True,
            no_color=True,
            quiet=True,
            verbose=True,
        )
    )

    assert request == RunRequest(
        root=Path("/workspace"),
        config_path=Path("/workspace/config/custom.toml"),
        input_dir=Path("inputs"),
        no_cache=True,
        from_cache_only=True,
        no_upload=True,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        force_interactive_alignment=True,
        tm_preset=TonemapPreset.FILMIC,
        tm_target_nits=203,
        tm_curve=ToneCurve.SPLINE,
        frame_count=17,
        seed=42,
        overlay_mode=OverlayMode.DIAGNOSTIC,
        no_color=True,
        quiet=True,
        verbose=True,
        json_output=True,
    )


def test_handle_diagnose_paths_outputs_pinned_json(capsys: pytest.CaptureFixture[str]) -> None:
    config = get_default_config().model_copy(
        update={
            "paths": PathsConfig(
                input_dir="inputs",
                screenshots_dir="shots",
                generated_dir="cache",
                config_dir="config",
            )
        }
    )

    handle_diagnose_paths(Path("/workspace"), Path("/workspace/config/config.toml"), config)

    assert json.loads(capsys.readouterr().out) == {
        "cache": "/workspace/cache",
        "config": "/workspace/config/config.toml",
        "input": "/workspace/inputs",
        "output": "/workspace/shots",
        "root": "/workspace",
    }


def test_handle_json_output_success_schema(capsys: pytest.CaptureFixture[str]) -> None:
    handle_json_output(
        RunResult(
            success=True,
            screenshot_dir=Path("screenshots"),
            slowpics_url="https://slow.pics/abc",
            report_path=Path("report.html"),
            frame_count=9,
            clips_processed=3,
            duration_seconds=1.5,
            cache_hit=True,
            errors=["warning-shaped error"],
        )
    )

    assert json.loads(capsys.readouterr().out) == {
        "cache_hit": True,
        "clips_processed": 3,
        "duration_seconds": 1.5,
        "errors": ["warning-shaped error"],
        "frame_count": 9,
        "report_path": "report.html",
        "screenshots_dir": "screenshots",
        "slowpics_url": "https://slow.pics/abc",
        "success": True,
    }


def test_handle_json_output_failure_exits_processing_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        handle_json_output(RunResult(success=False, errors=["failed"]))

    assert exc_info.value.exit_code == int(ExitCode.PROCESSING_ERROR)
    assert json.loads(capsys.readouterr().out)["errors"] == ["failed"]


def test_handle_run_write_config_applies_cli_overrides_and_skips_runner() -> None:
    runner = RecordingRunner()
    written_paths: list[Path] = []
    written_configs: list[ConfigSchema] = []

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        assert config_path == Path("/workspace/config/config.toml")
        assert overrides is None
        return get_default_config()

    def _write_config(path: Path, config: ConfigSchema) -> None:
        written_paths.append(path)
        written_configs.append(config)

    handle_run(
        replace(
            _base_args(),
            write_config=True,
            frame_count=17,
            tm_preset="filmic",
            overlay="diagnostic",
            no_upload=True,
        ),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=_load_config,
                write_config_to=_write_config,
            )
        ),
    )

    assert runner.requests == []
    assert written_paths == [Path("/workspace/config/config.toml")]
    assert written_configs[0].analysis.frame_count == 17
    assert written_configs[0].color.preset == TonemapPreset.FILMIC
    assert written_configs[0].screenshots.overlay_mode == OverlayMode.DIAGNOSTIC
    assert written_configs[0].slowpics.auto_upload is False


def test_handle_run_write_config_error_uses_injected_error_handler() -> None:
    error = ConfigWriteError(
        Path("/workspace/config/config.toml"),
        label="configuration file",
        cause=PermissionError("permission denied"),
    )

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return get_default_config()

    def _write_config(path: Path, config: ConfigSchema) -> NoReturn:
        raise error

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(_base_args(), write_config=True, no_color=True),
            _deps(DepsOptions(load_config=_load_config, write_config_to=_write_config)),
        )

    assert exc_info.value.exit_code == int(ExitCode.CONFIG_ERROR)


def test_handle_run_json_write_config_error_writes_machine_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = ConfigWriteError(
        Path("/workspace/config/config.toml"),
        label="configuration file",
        cause=PermissionError("permission denied"),
    )

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return get_default_config()

    def _write_config(path: Path, config: ConfigSchema) -> NoReturn:
        raise error

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(_base_args(), write_config=True, json_output=True),
            _deps(DepsOptions(load_config=_load_config, write_config_to=_write_config)),
        )

    assert exc_info.value.exit_code == int(ExitCode.CONFIG_ERROR)
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1007"


def test_maybe_open_run_report_requires_report_human_output_and_tty() -> None:
    opened: list[Path] = []
    result = RunResult(success=True, report_path=Path("report.html"))

    maybe_open_run_report(
        result,
        args=replace(_base_args(), json_output=True),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=get_default_config,
    )
    maybe_open_run_report(
        result,
        args=replace(_base_args(), quiet=True),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=get_default_config,
    )
    maybe_open_run_report(
        result,
        args=_base_args(),
        deps=_deps(DepsOptions(stdout_is_tty=False), opened),
        resolve_effective_config=get_default_config,
    )
    maybe_open_run_report(
        RunResult(success=True),
        args=_base_args(),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=get_default_config,
    )

    assert opened == []


def test_maybe_open_run_report_respects_config_and_reload_failure() -> None:
    opened: list[Path] = []
    enabled = get_default_config()
    disabled = enabled.model_copy(update={"report": ReportConfig(auto_open=False)})
    result = RunResult(success=True, report_path=Path("report.html"))

    maybe_open_run_report(
        result,
        args=replace(_base_args(), quiet=False),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=lambda: disabled,
    )
    maybe_open_run_report(
        result,
        args=replace(_base_args(), quiet=False),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=lambda: enabled,
    )
    maybe_open_run_report(
        result,
        args=replace(_base_args(), quiet=False),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=lambda: (_ for _ in ()).throw(
            ConfigNotFoundError(Path("missing.toml"))
        ),
    )

    assert opened == [Path("report.html"), Path("report.html")]
