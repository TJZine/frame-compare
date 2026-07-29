from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import NoReturn

from rich.console import Console

from frame_compare.cli.errors import ExitCode
from frame_compare.cli.run_command import (
    HandleErrorFn,
    LoadConfigFn,
    RunCliRawArgs,
    RunCommandDeps,
    WriteConfigFn,
)
from frame_compare.config.errors import ConfigWriteError
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult


class RecordingRunner:
    def __init__(self, result: RunResult | None = None) -> None:
        self.result = result or RunResult(success=True)
        self.requests: list[RunRequest] = []
        self.dependencies: list[RunDependencies | None] = []

    def run(self, request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        self.requests.append(request)
        self.dependencies.append(dependencies)
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
        frames=None,
        random_frame_count=None,
        dark_frame_count=None,
        bright_frame_count=None,
        motion_frame_count=None,
        seed=None,
        overlay=None,
        skip_analysis=False,
        skip_metadata=False,
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


def _handle_error(
    error: Exception,
    *,
    no_color: bool,
    verbose: bool,
    verbose_hint: str | None = "--verbose",
) -> int:
    assert isinstance(error, ConfigWriteError)
    assert no_color is True
    assert verbose is False
    assert verbose_hint == "--verbose"
    return int(ExitCode.CONFIG_ERROR)


@dataclass(frozen=True)
class DepsOptions:
    runner: RecordingRunner | None = None
    load_config: LoadConfigFn = _raise_unexpected_load
    write_config_to: WriteConfigFn = _raise_unexpected_write
    handle_error: HandleErrorFn = _handle_error
    open_report: Callable[[Path], bool] | None = None
    stdout_is_tty: bool = False
    stdin_is_tty: bool = False
    no_color_env_present: bool = False
    copy_to_clipboard: Callable[[str], None] | None = None
    open_url: Callable[[str], bool] | None = None
    confirm_upload: Callable[..., bool] | None = None


def _deps(options: DepsOptions | None = None, opened: list[Path] | None = None) -> RunCommandDeps:
    opts = options or DepsOptions()
    opened_reports = [] if opened is None else opened

    def _open_report(report_path: Path) -> bool:
        opened_reports.append(report_path)
        return True

    return RunCommandDeps(
        runner=opts.runner or RecordingRunner(),
        load_config=opts.load_config,
        write_config_to=opts.write_config_to,
        handle_error=opts.handle_error,
        configure_logging=lambda *, level, log_format: None,
        console_factory=_console_factory,
        open_report=opts.open_report or _open_report,
        copy_to_clipboard=opts.copy_to_clipboard or (lambda _text: None),
        open_url=opts.open_url or (lambda _url: True),
        confirm_upload=opts.confirm_upload or (lambda _text, *, default: default),
        stdout_is_tty=opts.stdout_is_tty,
        stdin_is_tty=opts.stdin_is_tty,
        no_color_env_present=opts.no_color_env_present,
    )


def _prompt_required_config(*, report_enable: bool = True) -> ConfigSchema:
    config = get_default_config()
    config.slowpics.auto_upload = True
    config.slowpics.confirm_upload_after_report = True
    config.report.enable = report_enable
    return config
