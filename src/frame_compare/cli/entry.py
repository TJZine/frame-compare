"""CLI entry point for frame-compare."""

# ruff: noqa: B008
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from frame_compare.cli.cli_helpers import (
    FrameCompareTyperGroup,
    handle_error,
    prepare_toml_payload,
    resolve_root_and_config,
    stabilize_typer_help_width,
    write_config_to,
)
from frame_compare.cli.cli_helpers import (
    maybe_open_report as _maybe_open_report,
)
from frame_compare.cli.doctor_command import (
    doctor_report_json,
    handle_doctor,
    print_doctor_report,
)
from frame_compare.cli.preset_command import (
    handle_preset_apply,
    handle_preset_list,
    handle_preset_save,
)
from frame_compare.cli.run_command import (
    RunCliOptions,
    RunCliRawArgs,
    RunCommandDeps,
    build_run_request_from_cli,
    coerce_cli_choice,
    handle_diagnose_paths,
    handle_json_output,
    handle_run,
)
from frame_compare.cli.wizard_command import (
    build_minimal_config,
    handle_wizard,
    prompt_input_dir,
    prompt_visibility,
    validate_config,
    write_wizard_config_payload,
)
from frame_compare.config.loader import load_config
from frame_compare.config.presets import apply_preset, list_presets, save_preset
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.logging import configure_logging

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, RunResult
    from frame_compare.orchestration.doctor import DoctorCheck, DoctorReport
    from frame_compare.utils.progress_protocol import ProgressReporter


class _RunnerProxy:
    """Lazy runner proxy to avoid importing VS-dependent modules at CLI import time."""

    def run(self, request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
        from frame_compare import runner as runtime_runner

        return runtime_runner.run(request, dependencies=dependencies)


runner = _RunnerProxy()


def run_doctor(
    checks: list[DoctorCheck] | None = None, reporter: ProgressReporter | None = None
) -> DoctorReport:
    """Lazy doctor entry point to keep CLI import VS-independent."""
    from frame_compare.orchestration.doctor import run_doctor as runtime_run_doctor

    return runtime_run_doctor(checks=checks, reporter=reporter)


app = typer.Typer(
    name="frame-compare",
    help="Video frame comparison tool with tonemapping and slow.pics integration.",
    no_args_is_help=False,
    cls=FrameCompareTyperGroup,
)


_stabilize_typer_help_width = stabilize_typer_help_width
_prepare_toml_payload = prepare_toml_payload
_resolve_root_and_config = resolve_root_and_config
_doctor_report_json = doctor_report_json
_print_doctor_report = print_doctor_report
_prompt_input_dir = prompt_input_dir
_prompt_visibility = prompt_visibility
_RunCliOptions = RunCliOptions
_build_run_request_from_cli = build_run_request_from_cli
_coerce_cli_choice = coerce_cli_choice
_handle_diagnose_paths = handle_diagnose_paths
_handle_json_output = handle_json_output
_build_minimal_config = build_minimal_config
_validate_config = validate_config

if TYPE_CHECKING:

    def _option[T](default: T, *param_decls: str) -> T:
        return default

    def _path_option(default: str, *param_decls: str) -> Path:
        return Path(default)

else:
    _option = typer.Option
    _path_option = typer.Option


def _write_config_to(path: Path, config: ConfigSchema) -> None:
    write_config_to(path, config, text_writer=write_text_atomic)


def _write_wizard_config_payload(config_path: Path, data: dict[str, object]) -> None:
    write_wizard_config_payload(config_path, data, text_writer=write_text_atomic)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Video frame comparison tool."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def version() -> None:
    """Print version and exit."""
    from frame_compare import __version__

    typer.echo(f"frame-compare {__version__}")


@app.command()
def run(
    root: Path = _path_option(".", "--root", "-r"),
    config: Path | None = _option(None, "--config", "-c"),
    input_dir: Path | None = _option(None, "--input", "-i"),
    no_cache: bool = _option(False, "--no-cache"),
    from_cache_only: bool = _option(False, "--from-cache-only"),
    no_upload: bool = _option(False, "--no-upload"),
    tm_preset: str | None = _option(None, "--tm-preset"),
    tm_target: int | None = _option(None, "--tm-target"),
    tm_curve: str | None = _option(None, "--tm-curve"),
    frame_count: int | None = _option(None, "--frame-count", "-n"),
    seed: int | None = _option(None, "--seed"),
    overlay: str | None = _option(None, "--overlay"),
    skip_analysis: bool = _option(False, "--skip-analysis"),
    skip_metadata: bool = _option(False, "--skip-metadata"),
    skip_dovi: bool = _option(False, "--skip-dovi"),
    force_interactive_alignment: bool = _option(False, "--force-interactive-alignment"),
    json_output: bool = _option(False, "--json"),
    no_color: bool = _option(False, "--no-color"),
    write_config: bool = _option(False, "--write-config"),
    diagnose_paths: bool = _option(False, "--diagnose-paths"),
    quiet: bool = _option(False, "--quiet", "-q"),
    verbose: bool = _option(False, "--verbose", "-v"),
) -> None:
    resolved_root, config_path = _resolve_root_and_config(root, config)
    args = RunCliRawArgs(
        resolved_root=resolved_root,
        config_path=config_path,
        input_dir=input_dir,
        no_cache=no_cache,
        from_cache_only=from_cache_only,
        no_upload=no_upload,
        tm_preset=tm_preset,
        tm_target=tm_target,
        tm_curve=tm_curve,
        frame_count=frame_count,
        seed=seed,
        overlay=overlay,
        skip_analysis=skip_analysis,
        skip_metadata=skip_metadata,
        skip_dovi=skip_dovi,
        force_interactive_alignment=force_interactive_alignment,
        json_output=json_output,
        no_color=no_color,
        write_config=write_config,
        diagnose_paths=diagnose_paths,
        quiet=quiet,
        verbose=verbose,
    )
    deps = RunCommandDeps(
        runner=runner,
        load_config=load_config,
        write_config_to=_write_config_to,
        handle_error=handle_error,
        configure_logging=configure_logging,
        console_factory=Console,
        open_report=_maybe_open_report,
        stdout_is_tty=sys.stdout.isatty(),
        no_color_env_present="NO_COLOR" in os.environ,
    )
    handle_run(args, deps)


@app.command()
def wizard(
    root: Path = _path_option(".", "--root", "-r"),
    config: Path | None = _option(None, "--config", "-c"),
) -> None:
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_wizard(
        resolved_root,
        config_path,
        prompt_input_dir=_prompt_input_dir,
        prompt_visibility=_prompt_visibility,
        confirm=typer.confirm,
        prompt_secret=typer.prompt,
        write_payload=_write_wizard_config_payload,
        handle_error=handle_error,
        stdin_is_tty=sys.stdin.isatty(),
    )


@app.command()
def doctor(json_output: bool = _option(False, "--json")) -> None:
    handle_doctor(json_output, run_doctor=run_doctor, handle_error=handle_error)


preset_app = typer.Typer(name="preset", help="Manage configuration presets.", no_args_is_help=True)
app.add_typer(preset_app, name="preset")


@preset_app.command("list")
def preset_list(
    root: Path = _path_option(".", "--root", "-r"),
    config: Path | None = _option(None, "--config", "-c"),
) -> None:
    resolved_root, _ = _resolve_root_and_config(root, config)
    handle_preset_list(
        resolved_root,
        list_presets=list_presets,
        handle_error=handle_error,
    )


@preset_app.command("apply")
def preset_apply(
    name: str,
    root: Path = _path_option(".", "--root", "-r"),
    config: Path | None = _option(None, "--config", "-c"),
) -> None:
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_preset_apply(
        name,
        resolved_root,
        config_path,
        load_config=load_config,
        apply_preset=apply_preset,
        write_config_to=_write_config_to,
        handle_error=handle_error,
    )


@preset_app.command("save")
def preset_save(
    name: str,
    root: Path = _path_option(".", "--root", "-r"),
    config: Path | None = _option(None, "--config", "-c"),
) -> None:
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_preset_save(
        name,
        resolved_root,
        config_path,
        load_config=load_config,
        save_preset=save_preset,
        handle_error=handle_error,
    )


if __name__ == "__main__":
    app()
