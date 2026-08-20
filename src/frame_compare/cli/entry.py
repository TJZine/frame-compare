"""CLI entry point for frame-compare."""

# ruff: noqa: B008
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from frame_compare.cli.cli_helpers import (
    FrameCompareTyperGroup,
    copy_text_to_clipboard,
    handle_error,
    open_url_in_browser,
    resolve_root_and_config,
    stabilize_typer_help_width,
    write_config_to,
)
from frame_compare.cli.cli_helpers import (
    maybe_open_report as _maybe_open_report,
)
from frame_compare.cli.doctor_command import handle_doctor
from frame_compare.cli.history_command import handle_history_list, handle_history_open
from frame_compare.cli.preset_command import (
    handle_preset_apply,
    handle_preset_list,
    handle_preset_save,
)
from frame_compare.cli.run_command import (
    RunCliRawArgs,
    RunCommandDeps,
    confirm_full_window_retry_on_stderr,
    handle_run,
)
from frame_compare.cli.wizard_command import (
    handle_wizard,
    prompt_generated_dir,
    prompt_input_dir,
    write_wizard_config_payload,
)
from frame_compare.config.loader import TomlPayload, load_config
from frame_compare.config.presets import apply_preset, list_presets, save_preset
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.logging import configure_logging
from frame_compare.utils.terminal import no_color_requested, stream_is_tty

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
    help=(
        "Reproducible video comparisons with deterministic frame selection, audio "
        "alignment, HDR-aware rendering, and offline review reports.\n\n"
        "Turn two or more local video sources into a repeatable comparison: discover "
        "and validate clips, select representative frames, align edits, render "
        "labeled screenshots, and build an offline HTML report."
    ),
    epilog=(
        "Examples:\n"
        "  First setup: frame-compare wizard\n"
        "  Preview a run: frame-compare run --dry-run\n"
        "  Compare locally: frame-compare run --no-upload"
    ),
    no_args_is_help=False,
    cls=FrameCompareTyperGroup,
)


_stabilize_typer_help_width = stabilize_typer_help_width
_resolve_root_and_config = resolve_root_and_config
_copy_text_to_clipboard = copy_text_to_clipboard
_open_url_in_browser = open_url_in_browser
_prompt_input_dir = prompt_input_dir
_prompt_generated_dir = prompt_generated_dir


def _sys_stream_isatty(name: str) -> bool:
    return stream_is_tty(getattr(sys, name, None))


if TYPE_CHECKING:

    def _option[T](default: T, *param_decls: str, **kwargs: object) -> T:
        return default

    def _path_option(default: str, *param_decls: str, **kwargs: object) -> Path:
        return Path(default)

else:
    _option = typer.Option
    _path_option = typer.Option


def _write_config_to(path: Path, config: ConfigSchema) -> None:
    write_config_to(path, config, text_writer=write_text_atomic)


def _write_wizard_config_payload(config_path: Path, data: TomlPayload) -> None:
    write_wizard_config_payload(config_path, data, text_writer=write_text_atomic)


def _prompt_text(text: str, *, default: str) -> str:
    return str(typer.prompt(text, default=default))


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
    root: Path = _path_option(
        ".",
        "--root",
        "-r",
        help="Workspace root containing configuration, input, and generated output.",
        rich_help_panel="Workspace and configuration",
    ),
    config: Path | None = _option(
        None,
        "--config",
        "-c",
        help="Config file; relative paths resolve from --root.",
        rich_help_panel="Workspace and configuration",
    ),
    input_dir: Path | None = _option(
        None,
        "--input",
        "-i",
        help="Use this source-video directory; persists with --write-config.",
        rich_help_panel="Sources and frame selection",
    ),
    frames: str | None = _option(
        None,
        "--frames",
        help="Select comma-separated reference source-frame numbers; persists with --write-config.",
        rich_help_panel="Sources and frame selection",
    ),
    random_frame_count: str | None = _option(
        None,
        "--random-frame-count",
        help="Set the random frame count; persists with --write-config.",
        rich_help_panel="Sources and frame selection",
    ),
    dark_frame_count: str | None = _option(
        None,
        "--dark-frame-count",
        help="Set the dark-frame count; requires analysis and persists.",
        rich_help_panel="Sources and frame selection",
    ),
    bright_frame_count: str | None = _option(
        None,
        "--bright-frame-count",
        help="Set the bright-frame count; requires analysis and persists.",
        rich_help_panel="Sources and frame selection",
    ),
    motion_frame_count: str | None = _option(
        None,
        "--motion-frame-count",
        help="Set the motion-frame count; requires analysis and persists.",
        rich_help_panel="Sources and frame selection",
    ),
    seed: int | None = _option(
        None,
        "--seed",
        help="Set the frame-selection seed; persists with --write-config.",
        rich_help_panel="Sources and frame selection",
    ),
    tm_preset: str | None = _option(
        None,
        "--tm-preset",
        help="Override the tonemap preset; persists with --write-config.",
        rich_help_panel="Rendering and alignment",
    ),
    tm_target: int | None = _option(
        None,
        "--tm-target",
        help="Override tonemap target nits; persists with --write-config.",
        rich_help_panel="Rendering and alignment",
    ),
    tm_curve: str | None = _option(
        None,
        "--tm-curve",
        help="Override the tonemap curve; persists with --write-config.",
        rich_help_panel="Rendering and alignment",
    ),
    overlay: str | None = _option(
        None,
        "--overlay",
        help="Override screenshot overlay mode; persists with --write-config.",
        rich_help_panel="Rendering and alignment",
    ),
    force_interactive_alignment: bool = _option(
        False,
        "--force-interactive-alignment",
        help="Force VSPreview alignment; persists with --write-config.",
        rich_help_panel="Rendering and alignment",
    ),
    no_upload: bool = _option(
        False,
        "--no-upload",
        help="Do not publish to slow.pics; persists with --write-config.",
        rich_help_panel="Reports and publishing",
    ),
    skip_analysis: bool = _option(
        False,
        "--skip-analysis",
        help="Skip metric analysis; dark, bright, and motion counts must be zero.",
        rich_help_panel="Planning and diagnostics",
    ),
    skip_metadata: bool = _option(
        False,
        "--skip-metadata",
        help="Skip TMDB metadata lookup for this run.",
        rich_help_panel="Planning and diagnostics",
    ),
    no_cache: bool = _option(
        False,
        "--no-cache",
        help="Disable analysis cache reads and writes for this run.",
        rich_help_panel="Planning and diagnostics",
    ),
    from_cache_only: bool = _option(
        False,
        "--from-cache-only",
        help="Require valid cached analysis; never recompute missing metrics.",
        rich_help_panel="Planning and diagnostics",
    ),
    dry_run: bool = _option(
        False,
        "--dry-run",
        help="Preview what a run would use and create without probing or side effects.",
        rich_help_panel="Planning and diagnostics",
    ),
    write_config: bool = _option(
        False,
        "--write-config",
        help="Write the effective config, then exit without running.",
        rich_help_panel="Planning and diagnostics",
    ),
    diagnose_paths: bool = _option(
        False,
        "--diagnose-paths",
        help="Print resolved workspace paths as JSON, then exit.",
        rich_help_panel="Planning and diagnostics",
    ),
    json_output: bool = _option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of human summaries.",
        rich_help_panel="Output modes",
    ),
    no_color: bool = _option(
        False,
        "--no-color",
        help="Disable colored output.",
        rich_help_panel="Output modes",
    ),
    quiet: bool = _option(
        False,
        "--quiet",
        "-q",
        help="Suppress progress and detailed human summaries.",
        rich_help_panel="Output modes",
    ),
    verbose: bool = _option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging and verbose error details.",
        rich_help_panel="Output modes",
    ),
) -> None:
    """Compare video sources and generate screenshots and an optional report."""
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
        frames=frames,
        random_frame_count=random_frame_count,
        dark_frame_count=dark_frame_count,
        bright_frame_count=bright_frame_count,
        motion_frame_count=motion_frame_count,
        seed=seed,
        overlay=overlay,
        skip_analysis=skip_analysis,
        skip_metadata=skip_metadata,
        force_interactive_alignment=force_interactive_alignment,
        json_output=json_output,
        no_color=no_color,
        dry_run=dry_run,
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
        copy_to_clipboard=_copy_text_to_clipboard,
        open_url=_open_url_in_browser,
        confirm_upload=typer.confirm,
        confirm_full_window_retry=confirm_full_window_retry_on_stderr,
        stdout_is_tty=_sys_stream_isatty("stdout"),
        stdin_is_tty=_sys_stream_isatty("stdin"),
        no_color_env_present=no_color_requested(),
    )
    handle_run(args, deps)


@app.command()
def wizard(
    root: Path = _path_option(
        ".", "--root", "-r", help="Workspace root containing config and media paths."
    ),
    config: Path | None = _option(
        None, "--config", "-c", help="Config file; relative paths resolve from --root."
    ),
) -> None:
    """Interactively configure input, reference, and frame selection."""
    resolved_root, config_path = _resolve_root_and_config(root, config)
    effective_no_color = no_color_requested()
    handle_wizard(
        resolved_root,
        config_path,
        prompt_input_dir=_prompt_input_dir,
        prompt_generated_dir=_prompt_generated_dir,
        prompt=_prompt_text,
        confirm=typer.confirm,
        write_payload=_write_wizard_config_payload,
        handle_error=handle_error,
        stdin_is_tty=_sys_stream_isatty("stdin"),
        stdout_is_tty=_sys_stream_isatty("stdout"),
        no_color=effective_no_color,
    )


@app.command()
def doctor(
    json_output: bool = _option(False, "--json", help="Emit the diagnostic report as JSON."),
) -> None:
    """Check required runtimes and optional integrations."""
    handle_doctor(
        json_output,
        run_doctor=run_doctor,
        handle_error=handle_error,
        no_color=no_color_requested(),
    )


preset_app = typer.Typer(name="preset", help="Manage configuration presets.", no_args_is_help=True)
app.add_typer(preset_app, name="preset")

history_app = typer.Typer(name="history", help="Inspect recorded runs.", no_args_is_help=True)
app.add_typer(history_app, name="history")


@history_app.command("list")
def history_list(
    root: Path = _path_option(".", "--root", "-r", help="Workspace root containing recorded runs."),
    config: Path | None = _option(
        None, "--config", "-c", help="Config file; relative paths resolve from --root."
    ),
    json_output: bool = _option(False, "--json", help="Emit the run list as JSON."),
) -> None:
    """List recorded runs newest first."""
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_history_list(
        resolved_root,
        config_path,
        json_output=json_output,
        handle_error=handle_error,
        no_color=no_color_requested(),
    )


@history_app.command("open")
def history_open(
    run_name: str,
    root: Path = _path_option(".", "--root", "-r", help="Workspace root containing recorded runs."),
    config: Path | None = _option(
        None, "--config", "-c", help="Config file; relative paths resolve from --root."
    ),
) -> None:
    """Open one exact-name recorded report."""
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_history_open(
        run_name,
        resolved_root,
        config_path,
        open_report=_maybe_open_report,
        handle_error=handle_error,
        no_color=no_color_requested(),
    )


@preset_app.command("list")
def preset_list(
    root: Path = _path_option(
        ".", "--root", "-r", help="Workspace root containing configuration presets."
    ),
    config: Path | None = _option(
        None,
        "--config",
        "-c",
        help="Accepted for consistency; ignored here. Presets are located under --root.",
    ),
) -> None:
    """List available configuration presets."""
    resolved_root, _ = _resolve_root_and_config(root, config)
    handle_preset_list(
        resolved_root,
        list_presets=list_presets,
        handle_error=handle_error,
        no_color=no_color_requested(),
    )


@preset_app.command("apply")
def preset_apply(
    name: str,
    root: Path = _path_option(
        ".", "--root", "-r", help="Workspace root containing config and presets."
    ),
    config: Path | None = _option(
        None, "--config", "-c", help="Config file; relative paths resolve from --root."
    ),
) -> None:
    """Apply a named preset to the selected config file."""
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_preset_apply(
        name,
        resolved_root,
        config_path,
        load_config=load_config,
        apply_preset=apply_preset,
        write_config_to=_write_config_to,
        handle_error=handle_error,
        no_color=no_color_requested(),
    )


@preset_app.command("save")
def preset_save(
    name: str,
    root: Path = _path_option(
        ".", "--root", "-r", help="Workspace root containing config and presets."
    ),
    config: Path | None = _option(
        None, "--config", "-c", help="Config file; relative paths resolve from --root."
    ),
) -> None:
    """Save the selected config as a named preset."""
    resolved_root, config_path = _resolve_root_and_config(root, config)
    handle_preset_save(
        name,
        resolved_root,
        config_path,
        load_config=load_config,
        save_preset=save_preset,
        handle_error=handle_error,
        no_color=no_color_requested(),
    )


if __name__ == "__main__":
    app()
