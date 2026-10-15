import json
from dataclasses import replace
from pathlib import Path
from typing import NoReturn, cast

import pytest
import typer

from frame_compare.cli.errors import ExitCode
from frame_compare.cli.run_command import (
    RunCliOptions,
    build_run_request_from_cli,
    coerce_cli_choice,
    handle_diagnose_paths,
    handle_json_output,
    handle_run,
)
from frame_compare.config.errors import ConfigValidationError, ConfigWriteError
from frame_compare.config.loader import get_default_config
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.config.schema import (
    ConfigSchema,
    OverlayMode,
    PathsConfig,
    ToneCurve,
    TonemapPreset,
)
from frame_compare.errors import PathEscapesRootError
from frame_compare.orchestration import RunResult
from frame_compare.orchestration.run_inputs import acquire_run_config, resolve_run_workspace

from .run_command_test_support import (
    DepsOptions,
    RecordingRunner,
    _raise_unexpected_load,
    _raise_unexpected_write,
)
from .run_command_test_support import (
    base_args as _base_args,
)
from .run_command_test_support import (
    deps as _deps,
)


def test_build_run_request_from_cli_maps_all_runtime_options(tmp_path: Path) -> None:
    options = RunCliOptions(
        root=tmp_path,
        config_path=tmp_path / "config/config.toml",
        config_overrides=CLIConfigOverrides(no_upload=True),
        no_cache=True,
        from_cache_only=True,
        skip_analysis=True,
        skip_metadata=True,
        json_output=True,
        no_color=True,
        quiet=True,
        verbose=True,
    )
    inputs = acquire_run_config(
        root=tmp_path,
        overrides=options.config_overrides,
        load_config_fn=lambda config_path=None, overrides=None: get_default_config(),
    )
    request = build_run_request_from_cli(options, inputs)
    assert request.inputs is inputs
    assert request.no_cache and request.from_cache_only and request.skip_analysis
    assert request.skip_metadata and request.json_output and request.no_color
    assert request.quiet and request.verbose
    assert request.inputs.config.slowpics.auto_upload is False


@pytest.mark.parametrize(
    ("enum_type", "flag", "loc"),
    [
        (OverlayMode, "--overlay", ("screenshots", "overlay_mode")),
        (TonemapPreset, "--tm-preset", ("color", "preset")),
        (ToneCurve, "--tm-curve", ("color", "tone_curve")),
    ],
)
def test_coerce_cli_choice_invalid_value_names_flag_and_enum_choices(
    enum_type: type[OverlayMode] | type[TonemapPreset] | type[ToneCurve],
    flag: str,
    loc: tuple[str, str],
) -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        coerce_cli_choice("banana", enum_type, loc, flag=flag)

    error = exc_info.value
    expected_choices = ", ".join(member.value for member in enum_type)
    assert error.context.message == f"Invalid value for {flag}: banana"
    assert error.context.hint == f"Choose one of: {expected_choices}."
    assert error.validation_errors[0]["loc"] == list(loc)
    assert error.validation_errors[0]["input"] == "banana"


def test_coerce_cli_choice_returns_none_for_missing_value() -> None:
    assert (
        coerce_cli_choice(None, OverlayMode, ("screenshots", "overlay_mode"), flag="--overlay")
        is None
    )


def test_coerce_cli_choice_bounds_long_echoed_value() -> None:
    huge_value = "x" * 500

    with pytest.raises(ConfigValidationError) as exc_info:
        coerce_cli_choice(
            huge_value, OverlayMode, ("screenshots", "overlay_mode"), flag="--overlay"
        )

    message = exc_info.value.context.message
    assert "--overlay" in message
    assert "truncated" in message
    assert len(message) < len(huge_value)


def test_coerce_cli_choice_escapes_control_characters_in_echoed_value() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        coerce_cli_choice(
            "bad\n\x1b[31mred", OverlayMode, ("screenshots", "overlay_mode"), flag="--overlay"
        )

    message = exc_info.value.context.message
    assert message == "Invalid value for --overlay: bad\\n\\x1b[31mred"


def test_handle_diagnose_paths_outputs_pinned_json(capsys: pytest.CaptureFixture[str]) -> None:
    config = get_default_config().model_copy(
        update={
            "paths": PathsConfig(
                input_dir="inputs",
                generated_dir="cache",
                config_dir="config",
            )
        }
    )

    handle_diagnose_paths(Path("/workspace"), Path("/workspace/config/config.toml"), config)

    assert json.loads(capsys.readouterr().out) == {
        "cache": str((Path("/workspace") / "cache" / "cache").resolve()),
        "config": str(Path("/workspace/config/config.toml")),
        "input": str((Path("/workspace") / "inputs").resolve()),
        "output": str((Path("/workspace") / "cache").resolve()),
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


def test_handle_json_output_omits_memory_only_review_wait(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handle_json_output(
        RunResult(
            success=True,
            duration_seconds=60.0,
            phase_timings={"align": 50.0},
            vsview_review_seconds=42.5,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "cache_hit": False,
        "clips_processed": 0,
        "duration_seconds": 60.0,
        "errors": [],
        "frame_count": 0,
        "report_path": None,
        "screenshots_dir": None,
        "slowpics_url": None,
        "success": True,
    }


def test_handle_run_write_config_applies_cli_overrides_and_skips_runner(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    expected_config = workspace / "config" / "config.toml"
    runner = RecordingRunner()
    written_paths: list[Path] = []
    written_configs: list[ConfigSchema] = []

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        assert config_path == expected_config
        assert overrides is None
        return get_default_config()

    def _write_config(path: Path, config: ConfigSchema) -> None:
        written_paths.append(path)
        written_configs.append(config)

    handle_run(
        replace(
            _base_args(),
            resolved_root=workspace,
            config_path=expected_config,
            write_config=True,
            frames="3,5,8",
            random_frame_count="17",
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
    assert written_paths == [expected_config]
    assert written_configs[0].analysis.user_frames == [3, 5, 8]
    assert written_configs[0].analysis.random_frame_count == 17
    assert written_configs[0].color.preset == TonemapPreset.FILMIC
    assert written_configs[0].screenshots.overlay_mode == OverlayMode.DIAGNOSTIC
    assert written_configs[0].slowpics.auto_upload is False


def test_handle_run_write_config_preserves_authored_generated_directory() -> None:
    runner = RecordingRunner()
    config = get_default_config().model_copy(
        update={
            "paths": get_default_config().paths.model_copy(
                update={"generated_dir": "../external-generated"}
            )
        }
    )
    written: list[ConfigSchema] = []

    handle_run(
        replace(_base_args(), write_config=True),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=lambda *_args, **_kwargs: config,
                write_config_to=lambda path, config: written.append(config),
            )
        ),
    )

    assert runner.requests == []
    assert written == [config]
    assert written[0].paths.generated_dir == "../external-generated"


@pytest.mark.parametrize("mode", ["run", "diagnose", "write"])
def test_handle_run_rejects_external_config_before_load_or_side_effects(mode: str) -> None:
    runner = RecordingRunner()
    handled: list[PathEscapesRootError] = []

    def _handle_path_error(
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int:
        del no_color, verbose, verbose_hint
        assert isinstance(error, PathEscapesRootError)
        handled.append(error)
        return int(ExitCode.INPUT_ERROR)

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(
                _base_args(),
                config_path=Path("/outside/config.toml"),
                diagnose_paths=mode == "diagnose",
                write_config=mode == "write",
            ),
            _deps(
                DepsOptions(
                    runner=runner,
                    load_config=_raise_unexpected_load,
                    write_config_to=_raise_unexpected_write,
                    handle_error=_handle_path_error,
                )
            ),
        )

    assert exc_info.value.exit_code == int(ExitCode.INPUT_ERROR)
    assert runner.requests == []
    assert len(handled) == 1


@pytest.mark.parametrize("mode", ["run", "diagnose", "write"])
def test_handle_run_allows_external_generated_root(mode: str) -> None:
    runner = RecordingRunner()
    config = get_default_config().model_copy(
        update={
            "paths": get_default_config().paths.model_copy(
                update={"generated_dir": "/outside/generated"}
            )
        }
    )
    written: list[ConfigSchema] = []

    handle_run(
        replace(
            _base_args(),
            diagnose_paths=mode == "diagnose",
            write_config=mode == "write",
        ),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=lambda *_args, **_kwargs: config,
                write_config_to=lambda path, config: written.append(config),
            )
        ),
    )

    assert (len(runner.requests) == 1) is (mode == "run")
    assert (len(written) == 1) is (mode == "write")


def test_handle_run_allows_external_input_override(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = RecordingRunner()
    external_input = tmp_path / "external" / "media"
    external_input.mkdir(parents=True)

    handle_run(
        replace(
            _base_args(),
            resolved_root=workspace,
            config_path=workspace / "config" / "config.toml",
            input_dir=external_input,
        ),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=lambda *_args, **_kwargs: get_default_config(),
            )
        ),
    )

    assert len(runner.requests) == 1
    assert resolve_run_workspace(runner.requests[0].inputs).input_dir == external_input


def test_handle_run_allows_exact_windows_portable_state_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    portable_config = tmp_path / "portable-state" / "config.toml"
    monkeypatch.setattr(
        "frame_compare.orchestration.preflight._windows_portable_state_config_path",
        lambda: portable_config,
    )
    runner = RecordingRunner()

    handle_run(
        replace(
            _base_args(),
            resolved_root=root,
            config_path=portable_config,
        ),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=lambda *_args, **_kwargs: get_default_config(),
            )
        ),
    )

    assert len(runner.requests) == 1
    assert runner.requests[0].inputs.config_path == portable_config


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


def test_handle_run_rejects_previous_offset_prompt_with_quiet_before_runner() -> None:
    runner = RecordingRunner()
    handled_errors: list[ConfigValidationError] = []

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        config = get_default_config()
        config.audio_alignment.previous_offsets = "prompt"
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
        return int(ExitCode.CONFIG_ERROR)

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(_base_args(), quiet=True),
            _deps(
                DepsOptions(
                    runner=runner,
                    load_config=_load_config,
                    handle_error=_handle_validation_error,
                )
            ),
        )

    assert exc_info.value.exit_code == int(ExitCode.CONFIG_ERROR)
    assert handled_errors
    assert handled_errors[0].validation_errors == [
        {
            "type": "value_error",
            "loc": ["cli", "quiet"],
            "msg": "Previous offset prompt mode is not supported with --quiet.",
            "input": "prompt",
        }
    ]


def test_handle_run_write_config_rejects_previous_offsets_before_writing() -> None:
    runner = RecordingRunner()
    handled_errors: list[ConfigValidationError] = []
    written_paths: list[Path] = []

    def _load_config(
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema:
        config = get_default_config()
        config.audio_alignment.previous_offsets = "always"
        config.audio_alignment.force_interactive = True
        return config

    def _write_config(path: Path, config: ConfigSchema) -> None:
        written_paths.append(path)

    def _handle_validation_error(
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int:
        assert isinstance(error, ConfigValidationError)
        handled_errors.append(error)
        return int(ExitCode.CONFIG_ERROR)

    with pytest.raises(typer.Exit) as exc_info:
        handle_run(
            replace(_base_args(), write_config=True),
            _deps(
                DepsOptions(
                    runner=runner,
                    load_config=_load_config,
                    write_config_to=_write_config,
                    handle_error=_handle_validation_error,
                )
            ),
        )

    assert exc_info.value.exit_code == int(ExitCode.CONFIG_ERROR)
    assert written_paths == []
    assert {
        tuple(cast(list[str], error["loc"])) for error in handled_errors[0].validation_errors
    } == {
        ("audio_alignment", "force_interactive"),
        ("audio_alignment", "previous_offsets"),
    }


@pytest.mark.parametrize("json_output", [False, True], ids=["human", "json"])
def test_run_keeps_admission_config_and_refreshes_only_report_preference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    json_output: bool,
) -> None:
    import frame_compare.cli.run_command as command
    from frame_compare.config.loader import load_config

    config_file = tmp_path / "config/config.toml"
    config_file.parent.mkdir()
    config_file.write_text(
        "[audio_alignment]\nuse_vsview = false\n"
        "[analysis]\nignore_lead_seconds = 5\n[slowpics]\nauto_upload = false\n"
        "[report]\nauto_open = true\n"
    )
    calls: list[Path | None] = []
    acquisitions = 0
    original_acquire = command.acquire_run_config

    def acquire(**kwargs):
        nonlocal acquisitions
        acquisitions += 1
        return original_acquire(**kwargs)

    monkeypatch.setattr(command, "acquire_run_config", acquire)

    def load(config_path=None, overrides=None):
        calls.append(config_path)
        return load_config(config_path, overrides)

    class ChangingRunner(RecordingRunner):
        def run(self, request, dependencies=None):
            config_file.write_text(
                "[audio_alignment]\nuse_vsview = true\n"
                "[analysis]\nignore_lead_seconds = 0\n[slowpics]\nauto_upload = true\n"
                "confirm_upload_after_report = true\n[report]\nauto_open = false\n"
            )
            assert request.inputs.config.audio_alignment.use_vsview is False
            assert request.inputs.config.analysis.ignore_lead_seconds == 5
            assert request.inputs.config.slowpics.auto_upload is False
            if json_output:
                assert dependencies is None
            else:
                assert dependencies is not None
                assert dependencies.confirm_full_window_retry is not None
                assert dependencies.confirm_slowpics_upload is None
            return RunResult(success=True, report_path=tmp_path / "report.html")

    opened: list[Path] = []
    deps = _deps(
        DepsOptions(
            runner=ChangingRunner(), load_config=load, stdin_is_tty=True, stdout_is_tty=True
        ),
        opened,
    )
    handle_run(
        replace(
            _base_args(),
            resolved_root=tmp_path,
            config_path=config_file,
            quiet=False,
            json_output=json_output,
        ),
        deps,
    )
    assert acquisitions == 1
    assert calls == [config_file] * (1 if json_output else 2)
    assert opened == []
    if json_output:
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True


@pytest.mark.parametrize("write", [False, True], ids=["diagnose", "write"])
def test_environment_selected_config_path_is_used_for_read_and_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    write: bool,
) -> None:
    selected = tmp_path / "config/selected.toml"
    selected.parent.mkdir()
    selected.write_text("[paths]\ninput_dir = 'inputs'\n")
    monkeypatch.setenv("P5_SELECTED_CONFIG", str(selected))
    from frame_compare.config.loader import load_config

    writes: list[Path] = []
    deps = _deps(
        DepsOptions(
            load_config=load_config, write_config_to=lambda path, config: writes.append(path)
        )
    )
    handle_run(
        replace(
            _base_args(),
            resolved_root=tmp_path,
            config_path=Path("$P5_SELECTED_CONFIG"),
            diagnose_paths=not write,
            write_config=write,
        ),
        deps,
    )
    if write:
        assert writes == [selected]
    else:
        assert json.loads(capsys.readouterr().out)["config"] == str(selected)
