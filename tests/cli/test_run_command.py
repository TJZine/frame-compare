import json
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

import pytest
import typer

from frame_compare.cli.errors import ExitCode
from frame_compare.cli.run_command import (
    RunCliOptions,
    build_run_request_from_cli,
    handle_diagnose_paths,
    handle_json_output,
    handle_run,
)
from frame_compare.config.errors import ConfigValidationError, ConfigWriteError
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import (
    ConfigSchema,
    OverlayMode,
    PathsConfig,
    ToneCurve,
    TonemapPreset,
)
from frame_compare.errors import PathEscapesRootError
from frame_compare.orchestration import RunRequest, RunResult

from .run_command_test_support import (
    DepsOptions,
    RecordingRunner,
    _base_args,
    _deps,
    _raise_unexpected_load,
    _raise_unexpected_write,
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
            user_frames=[12, 24],
            random_frame_count=17,
            dark_frame_count=3,
            bright_frame_count=4,
            motion_frame_count=5,
            seed=42,
            overlay_mode=OverlayMode.DIAGNOSTIC,
            skip_analysis=True,
            skip_metadata=True,
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
        force_interactive_alignment=True,
        tm_preset=TonemapPreset.FILMIC,
        tm_target_nits=203,
        tm_curve=ToneCurve.SPLINE,
        user_frames=[12, 24],
        random_frame_count=17,
        dark_frame_count=3,
        bright_frame_count=4,
        motion_frame_count=5,
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
    assert written_paths == [Path("/workspace/config/config.toml")]
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
                write_config_to=lambda _path, value: written.append(value),
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
                write_config_to=lambda _path, value: written.append(value),
            )
        ),
    )

    assert (len(runner.requests) == 1) is (mode == "run")
    assert (len(written) == 1) is (mode == "write")


def test_handle_run_allows_external_input_override() -> None:
    runner = RecordingRunner()
    external_input = Path("/external/media")

    handle_run(
        replace(_base_args(), input_dir=external_input),
        _deps(
            DepsOptions(
                runner=runner,
                load_config=lambda *_args, **_kwargs: get_default_config(),
            )
        ),
    )

    assert len(runner.requests) == 1
    assert runner.requests[0].input_dir == external_input


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
    assert runner.requests[0].config_path == portable_config


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
    assert runner.requests == []
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
    assert runner.requests == []
    assert written_paths == []
    assert {tuple(error["loc"]) for error in handled_errors[0].validation_errors} == {
        ("audio_alignment", "force_interactive"),
        ("audio_alignment", "previous_offsets"),
    }
