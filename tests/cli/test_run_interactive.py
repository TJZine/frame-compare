from dataclasses import replace
from io import StringIO
from pathlib import Path

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from frame_compare.cli.errors import ExitCode
from frame_compare.cli.run_command import (
    build_confirm_full_window_retry_callback,
    build_confirm_slowpics_upload_callback,
    build_runner_dependencies,
    collect_interactive_slowpics_actions,
    confirm_full_window_retry_on_stderr,
    handle_run,
    maybe_open_run_report,
    slowpics_browser_open_attempted,
)
from frame_compare.config.errors import ConfigNotFoundError, ConfigValidationError
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import (
    ConfigSchema,
    ReportConfig,
)
from frame_compare.orchestration import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.types import (
    FullWindowRetryConfirmationRequest,
    SlowpicsUploadConfirmationRequest,
)

from .run_command_test_support import (
    DepsOptions,
    RecordingRunner,
    _base_args,
    _deps,
    _prompt_required_config,
)


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
    assert expected_message in {str(error["msg"]) for error in handled_errors[0].validation_errors}


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


def test_full_window_retry_callback_uses_exact_default_no_stderr_prompt() -> None:
    calls: list[str] = []

    def _confirm(text: str) -> bool:
        calls.append(text)
        return True

    callback = build_confirm_full_window_retry_callback(
        deps=_deps(DepsOptions(confirm_full_window_retry=_confirm))
    )

    decision = callback(
        FullWindowRetryConfirmationRequest(
            requested_frame_count=8,
            eligible_frame_count=4,
            ignore_lead_seconds=240.0,
            ignore_trail_seconds=240.0,
        )
    )

    assert decision == "confirmed"
    assert calls == [
        "Configured lead/trail exclusions leave too little media to satisfy the\n"
        "requested frame selection. Analyze the full shared clip for this run? [y/N] "
    ]


@pytest.mark.parametrize(
    ("prompt_input", "expected_exit_code", "stderr_suffix"),
    [("\n", 0, " "), ("maybe\nn\n", 0, " "), ("", 1, " Aborted.\n")],
)
def test_full_window_retry_prompt_keeps_visible_text_on_stderr(
    prompt_input: str,
    expected_exit_code: int,
    stderr_suffix: str,
) -> None:
    app = typer.Typer()

    @app.command()
    def confirm() -> None:
        callback = build_confirm_full_window_retry_callback(
            deps=_deps(DepsOptions(confirm_full_window_retry=confirm_full_window_retry_on_stderr))
        )
        callback(
            FullWindowRetryConfirmationRequest(
                requested_frame_count=8,
                eligible_frame_count=4,
                ignore_lead_seconds=240.0,
                ignore_trail_seconds=240.0,
            )
        )

    result = CliRunner().invoke(app, input=prompt_input, color=False)

    expected_prompt = (
        "Configured lead/trail exclusions leave too little media to satisfy the\n"
        "requested frame selection. Analyze the full shared clip for this run? [y/N]"
    )
    assert result.exit_code == expected_exit_code
    assert result.stdout == ""
    assert result.stderr == expected_prompt + stderr_suffix


@pytest.mark.parametrize(
    "args_update,deps_update",
    [
        ({"json_output": True}, {"stdin_is_tty": True}),
        ({"quiet": True}, {"stdin_is_tty": True}),
        ({"quiet": False}, {"stdin_is_tty": False}),
        ({"quiet": False, "from_cache_only": True}, {"stdin_is_tty": True}),
        ({"quiet": False, "skip_analysis": True}, {"stdin_is_tty": True}),
    ],
)
def test_full_window_retry_confirmation_is_not_injected_for_unattended_modes(
    args_update: dict[str, object],
    deps_update: dict[str, object],
) -> None:
    config = get_default_config()
    config.analysis.ignore_lead_seconds = 240.0
    dependencies = build_runner_dependencies(
        args=replace(_base_args(), **args_update),
        deps=_deps(DepsOptions(**deps_update)),
        config=config,
        console=Console(file=StringIO(), no_color=True),
        resolve_effective_config=lambda: config,
    )

    assert dependencies is None


def test_full_window_retry_confirmation_is_injected_only_for_nonzero_interactive_config() -> None:
    interactive_deps = _deps(DepsOptions(stdin_is_tty=True))
    config = get_default_config()
    config.analysis.ignore_trail_seconds = 240.0

    dependencies = build_runner_dependencies(
        args=replace(_base_args(), quiet=False),
        deps=interactive_deps,
        config=config,
        console=Console(file=StringIO(), no_color=True),
        resolve_effective_config=lambda: config,
    )
    zero_margin_dependencies = build_runner_dependencies(
        args=replace(_base_args(), quiet=False),
        deps=interactive_deps,
        config=get_default_config(),
        console=Console(file=StringIO(), no_color=True),
        resolve_effective_config=get_default_config,
    )

    assert dependencies is not None
    assert dependencies.confirm_full_window_retry is not None
    assert zero_margin_dependencies is None


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
                    confirm_upload=lambda _text, *, default: (_ for _ in ()).throw(typer.Abort()),
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
