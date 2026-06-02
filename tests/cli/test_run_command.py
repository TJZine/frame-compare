import json
from collections.abc import Callable
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
    build_confirm_slowpics_upload_callback,
    build_run_request_from_cli,
    collect_interactive_slowpics_actions,
    handle_diagnose_paths,
    handle_json_output,
    handle_run,
    maybe_open_run_report,
    slowpics_browser_open_attempted,
)
from frame_compare.config.errors import ConfigNotFoundError, ConfigValidationError, ConfigWriteError
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
from frame_compare.orchestration.types import SlowpicsUploadConfirmationRequest


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
        configure_logging=lambda *, level, format: None,
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
        "cache": str((Path("/workspace") / "cache").resolve()),
        "config": str(Path("/workspace/config/config.toml")),
        "input": str((Path("/workspace") / "inputs").resolve()),
        "output": str((Path("/workspace") / "shots").resolve()),
        "root": str(Path("/workspace")),
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


@pytest.mark.parametrize(
    ("args_update", "deps_update", "config", "expected_message"),
    [
        (
            {"quiet": True},
            {"stdin_is_tty": True, "stdout_is_tty": True},
            _prompt_required_config(),
            "Report-confirmed slow.pics upload is not supported with --quiet.",
        ),
        (
            {"quiet": False},
            {"stdin_is_tty": False, "stdout_is_tty": True},
            _prompt_required_config(),
            "Report-confirmed slow.pics upload requires stdin to be attached to a TTY.",
        ),
        (
            {"quiet": False},
            {"stdin_is_tty": True, "stdout_is_tty": False},
            _prompt_required_config(),
            "Report-confirmed slow.pics upload requires stdout to be attached to a TTY.",
        ),
        (
            {"quiet": False},
            {"stdin_is_tty": True, "stdout_is_tty": True},
            _prompt_required_config(report_enable=False),
            "Report-confirmed slow.pics upload requires report.enable = true.",
        ),
    ],
)
def test_handle_run_rejects_report_confirmed_slowpics_preflight_before_runner(
    args_update: dict[str, object],
    deps_update: dict[str, object],
    config: ConfigSchema,
    expected_message: str,
) -> None:
    runner = RecordingRunner()
    handled_errors: list[ConfigValidationError] = []

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return config

    def _handle_validation_error(
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int:
        assert isinstance(error, ConfigValidationError)
        handled_errors.append(error)
        assert no_color is False
        assert verbose is False
        assert verbose_hint == "--verbose"
        return int(ExitCode.CONFIG_ERROR)

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(_base_args(), **args_update),
            _deps(
                DepsOptions(
                    runner=runner,
                    load_config=_load_config,
                    handle_error=_handle_validation_error,
                    **deps_update,
                )
            ),
        )

    assert exc_info.value.exit_code == int(ExitCode.CONFIG_ERROR)
    assert runner.requests == []
    assert handled_errors
    assert expected_message in {
        str(error["msg"]) for error in handled_errors[0].validation_errors
    }


def test_handle_run_report_confirmed_slowpics_preflight_allows_no_upload_override() -> None:
    runner = RecordingRunner()

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return _prompt_required_config()

    handle_run(
        replace(_base_args(), no_upload=True, quiet=False),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=_load_config,
                stdin_is_tty=False,
                stdout_is_tty=False,
            )
        ),
    )

    assert len(runner.requests) == 1


def test_handle_run_injects_confirmation_dependency_only_for_prompt_required_path() -> None:
    prompt_runner = RecordingRunner()
    normal_runner = RecordingRunner()

    def _prompt_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return _prompt_required_config()

    def _normal_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return get_default_config()

    handle_run(
        replace(_base_args(), quiet=False),
        _deps(
            DepsOptions(
                runner=prompt_runner,
                load_config=_prompt_config,
                stdin_is_tty=True,
                stdout_is_tty=True,
            )
        ),
    )
    handle_run(
        replace(_base_args(), quiet=False),
        _deps(
            DepsOptions(
                runner=normal_runner,
                load_config=_normal_config,
                stdin_is_tty=True,
                stdout_is_tty=True,
            )
        ),
    )

    assert prompt_runner.dependencies[0] is not None
    assert prompt_runner.dependencies[0].confirm_slowpics_upload is not None
    assert normal_runner.dependencies == [None]


def test_confirmation_callback_opens_report_before_prompt_and_defaults_decline() -> None:
    opened: list[Path] = []

    def _confirm_upload(text: str, *, default: bool) -> bool:
        assert opened == [Path("report.html")]
        assert text == "Review the local report, then upload this comparison to slow.pics?"
        assert default is False
        return True

    callback = build_confirm_slowpics_upload_callback(
        args=replace(_base_args(), quiet=False),
        deps=_deps(
            DepsOptions(
                stdout_is_tty=True,
                confirm_upload=_confirm_upload,
            ),
            opened,
        ),
        console=Console(file=StringIO(), no_color=True),
        resolve_effective_config=get_default_config,
    )

    assert callback(SlowpicsUploadConfirmationRequest(report_path=Path("report.html"))) == (
        "confirmed"
    )


def test_confirmation_callback_prints_report_path_when_auto_open_disabled() -> None:
    disabled_auto_open = get_default_config()
    disabled_auto_open.report.auto_open = False
    output = StringIO()

    callback = build_confirm_slowpics_upload_callback(
        args=replace(_base_args(), quiet=False),
        deps=_deps(
            DepsOptions(
                stdout_is_tty=True,
                confirm_upload=lambda _text, *, default: False,
            )
        ),
        console=Console(file=output, no_color=True, force_terminal=False),
        resolve_effective_config=lambda: disabled_auto_open,
    )

    assert callback(SlowpicsUploadConfirmationRequest(report_path=Path("report.html"))) == (
        "declined"
    )
    assert "Report: report.html" in output.getvalue()


def test_confirmation_callback_prints_report_path_when_auto_open_attempt_fails() -> None:
    output = StringIO()

    callback = build_confirm_slowpics_upload_callback(
        args=replace(_base_args(), quiet=False),
        deps=_deps(
            DepsOptions(
                stdout_is_tty=True,
                open_report=lambda _path: False,
                confirm_upload=lambda _text, *, default: False,
            )
        ),
        console=Console(file=output, no_color=True, force_terminal=False),
        resolve_effective_config=get_default_config,
    )

    assert callback(SlowpicsUploadConfirmationRequest(report_path=Path("report.html"))) == (
        "declined"
    )
    assert "Report: report.html" in output.getvalue()


def test_handle_run_interrupts_when_confirmation_prompt_aborts() -> None:
    class PromptAbortRunner(RecordingRunner):
        def run(
            self, request: RunRequest, dependencies: RunDependencies | None = None
        ) -> RunResult:
            self.requests.append(request)
            self.dependencies.append(dependencies)
            assert dependencies is not None
            assert dependencies.confirm_slowpics_upload is not None
            dependencies.confirm_slowpics_upload(
                SlowpicsUploadConfirmationRequest(report_path=Path("report.html"))
            )
            raise AssertionError("upload should not continue after prompt abort")

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return _prompt_required_config()

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(_base_args(), quiet=False),
            _deps(
                DepsOptions(
                    runner=PromptAbortRunner(),
                    load_config=_load_config,
                    stdin_is_tty=True,
                    stdout_is_tty=True,
                    confirm_upload=lambda _text, *, default: (_ for _ in ()).throw(
                        typer.Abort()
                    ),
                )
            ),
        )

    assert exc_info.value.exit_code == int(ExitCode.INTERRUPTED)


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


def test_interactive_slowpics_actions_require_url_enabled_config_human_tty() -> None:
    copied: list[str] = []
    opened: list[str] = []
    deps = _deps(
        DepsOptions(
            stdout_is_tty=True,
            copy_to_clipboard=copied.append,
            open_url=lambda url: opened.append(url) is None or True,
        )
    )
    result = RunResult(success=True, slowpics_url="https://slow.pics/c/example")

    actions = collect_interactive_slowpics_actions(
        result,
        args=replace(_base_args(), quiet=False),
        deps=deps,
        config=get_default_config(),
    )

    assert copied == ["https://slow.pics/c/example"]
    assert opened == ["https://slow.pics/c/example"]
    assert [(action.kind, action.success) for action in actions] == [
        ("clipboard", True),
        ("browser", True),
    ]

    copied.clear()
    opened.clear()
    disabled = get_default_config()
    disabled.slowpics.copy_url_to_clipboard = False
    disabled.slowpics.open_in_browser = False

    assert (
        collect_interactive_slowpics_actions(
            result,
            args=replace(_base_args(), quiet=False),
            deps=deps,
            config=disabled,
        )
        == ()
    )
    assert (
        collect_interactive_slowpics_actions(
            result,
            args=replace(_base_args(), quiet=False, json_output=True),
            deps=deps,
            config=get_default_config(),
        )
        == ()
    )
    assert (
        collect_interactive_slowpics_actions(
            result,
            args=replace(_base_args(), quiet=True),
            deps=deps,
            config=get_default_config(),
        )
        == ()
    )
    assert (
        collect_interactive_slowpics_actions(
            result,
            args=replace(_base_args(), quiet=False),
            deps=_deps(DepsOptions(stdout_is_tty=False)),
            config=get_default_config(),
        )
        == ()
    )
    assert (
        collect_interactive_slowpics_actions(
            RunResult(success=True),
            args=replace(_base_args(), quiet=False),
            deps=deps,
            config=get_default_config(),
        )
        == ()
    )
    assert copied == []
    assert opened == []


def test_interactive_slowpics_action_failures_are_warning_only() -> None:
    deps = _deps(
        DepsOptions(
            stdout_is_tty=True,
            copy_to_clipboard=lambda _url: (_ for _ in ()).throw(RuntimeError("clipboard denied")),
            open_url=lambda _url: False,
        )
    )

    actions = collect_interactive_slowpics_actions(
        RunResult(success=True, slowpics_url="https://slow.pics/c/example"),
        args=replace(_base_args(), quiet=False),
        deps=deps,
        config=get_default_config(),
    )

    assert [(action.kind, action.success) for action in actions] == [
        ("clipboard", False),
        ("browser", False),
    ]
    assert actions[0].warning == "slow.pics clipboard: failed to copy URL: clipboard denied"
    assert actions[1].warning == (
        "slow.pics browser: failed to open URL: no browser accepted the request"
    )
    assert slowpics_browser_open_attempted(actions) is True


def test_report_auto_open_can_be_suppressed_by_slowpics_browser_attempt() -> None:
    opened: list[Path] = []

    maybe_open_run_report(
        RunResult(success=True, report_path=Path("report.html")),
        args=replace(_base_args(), quiet=False),
        deps=_deps(DepsOptions(stdout_is_tty=True), opened),
        resolve_effective_config=get_default_config,
        suppress_report_open=True,
    )

    assert opened == []


def test_handle_run_executes_interactive_actions_before_summary(monkeypatch) -> None:
    events: list[str] = []
    runner = RecordingRunner(RunResult(success=True, slowpics_url="https://slow.pics/c/example"))

    def _print_summary(*_args: object, **_kwargs: object) -> None:
        events.append("summary")

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return get_default_config()

    def _copy_url(_url: str) -> None:
        events.append("copy")

    def _open_url(_url: str) -> bool:
        events.append("open")
        return True

    monkeypatch.setattr("frame_compare.cli.run_command.print_result_summary", _print_summary)

    handle_run(
        replace(_base_args(), quiet=False),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=_load_config,
                stdout_is_tty=True,
                copy_to_clipboard=_copy_url,
                open_url=_open_url,
            )
        ),
    )

    assert events == ["copy", "open", "summary"]


def test_handle_run_confirmed_workflow_presents_report_before_post_upload_actions(
    monkeypatch,
) -> None:
    events: list[str] = []
    opened_reports: list[Path] = []

    class ConfirmingRunner(RecordingRunner):
        def run(
            self, request: RunRequest, dependencies: RunDependencies | None = None
        ) -> RunResult:
            self.requests.append(request)
            self.dependencies.append(dependencies)
            assert dependencies is not None
            assert dependencies.confirm_slowpics_upload is not None
            decision = dependencies.confirm_slowpics_upload(
                SlowpicsUploadConfirmationRequest(report_path=Path("report.html"))
            )
            return RunResult(
                success=True,
                slowpics_url="https://slow.pics/c/example",
                report_path=Path("report.html"),
                slowpics_upload_confirmation_status=decision,
            )

    def _print_summary(*_args: object, **_kwargs: object) -> None:
        events.append("summary")

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        return _prompt_required_config()

    def _confirm_upload(_text: str, *, default: bool) -> bool:
        assert default is False
        assert opened_reports == [Path("report.html")]
        events.append("prompt")
        return True

    def _copy_url(_url: str) -> None:
        events.append("copy")

    def _open_url(_url: str) -> bool:
        events.append("slowpics-browser")
        return True

    monkeypatch.setattr("frame_compare.cli.run_command.print_result_summary", _print_summary)

    handle_run(
        replace(_base_args(), quiet=False),
        _deps(
            DepsOptions(
                runner=ConfirmingRunner(),
                load_config=_load_config,
                stdin_is_tty=True,
                stdout_is_tty=True,
                copy_to_clipboard=_copy_url,
                open_url=_open_url,
                confirm_upload=_confirm_upload,
            ),
            opened_reports,
        ),
    )

    assert events == ["prompt", "copy", "slowpics-browser", "summary"]
    assert opened_reports == [Path("report.html")]
