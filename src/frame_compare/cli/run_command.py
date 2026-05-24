"""Implementation for the ``run`` CLI command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import typer
from rich.console import Console

from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.cli.output import print_at_a_glance, print_result_summary
from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.overrides import apply_cli_overrides
from frame_compare.config.schema import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.errors import FrameCompareError

from .cli_helpers import format_enum_expected

if TYPE_CHECKING:
    from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, RunResult


class RunnerLike(Protocol):
    def run(
        self, request: RunRequest, dependencies: RunDependencies | None = None
    ) -> RunResult: ...


class ConsoleFactory(Protocol):
    def __call__(self, *, stderr: bool, no_color: bool) -> Console: ...


class ConfigureLoggingFn(Protocol):
    def __call__(self, *, level: str, format: str) -> None: ...


@dataclass(frozen=True)
class RunCommandDeps:
    runner: RunnerLike
    load_config: LoadConfigFn
    write_config_to: WriteConfigFn
    handle_error: HandleErrorFn
    configure_logging: ConfigureLoggingFn
    console_factory: ConsoleFactory
    open_report: OpenReportFn
    stdout_is_tty: bool
    no_color_env_present: bool


class LoadConfigFn(Protocol):
    def __call__(
        self,
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema: ...


class WriteConfigFn(Protocol):
    def __call__(self, path: Path, config: ConfigSchema) -> None: ...


class HandleErrorFn(Protocol):
    def __call__(self, error: Exception, *, no_color: bool, verbose: bool) -> int: ...


class OpenReportFn(Protocol):
    def __call__(self, report_path: Path) -> None: ...


def coerce_cli_choice[CliChoiceT: Enum](
    value: str | None,
    enum_type: type[CliChoiceT],
    loc: tuple[str, ...],
) -> CliChoiceT | None:
    """Convert a CLI string choice after Typer parsing so JSON errors stay structured."""
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError as exc:
        expected = format_enum_expected(enum_type)
        raise ConfigValidationError(
            [
                {
                    "type": "enum",
                    "loc": list(loc),
                    "msg": f"Input should be {expected}",
                    "input": value,
                    "ctx": {"expected": expected},
                }
            ]
        ) from exc


@dataclass(frozen=True)
class RunCliOptions:
    """Typed, parsed CLI options for the run command."""

    root: Path
    config_path: Path
    input_dir: Path | None
    no_cache: bool
    from_cache_only: bool
    no_upload: bool
    tm_preset: TonemapPreset | None
    tm_target_nits: int | None
    tm_curve: ToneCurve | None
    frame_count: int | None
    seed: int | None
    overlay_mode: OverlayMode | None
    skip_analysis: bool
    skip_metadata: bool
    skip_dovi: bool
    force_interactive_alignment: bool
    json_output: bool
    no_color: bool
    quiet: bool
    verbose: bool


def build_run_request_from_cli(options: RunCliOptions) -> RunRequest:
    """Build the single CLI-to-runtime request mapping used by run branches."""
    from frame_compare.orchestration.coordinator import RunRequest

    return RunRequest(
        root=options.root,
        config_path=options.config_path,
        input_dir=options.input_dir,
        no_cache=options.no_cache,
        from_cache_only=options.from_cache_only,
        no_upload=options.no_upload,
        tm_preset=options.tm_preset,
        tm_target_nits=options.tm_target_nits,
        tm_curve=options.tm_curve,
        frame_count=options.frame_count,
        seed=options.seed,
        overlay_mode=options.overlay_mode,
        skip_analysis=options.skip_analysis,
        skip_metadata=options.skip_metadata,
        skip_dovi=options.skip_dovi,
        force_interactive_alignment=options.force_interactive_alignment,
        json_output=options.json_output,
        no_color=options.no_color,
        quiet=options.quiet,
        verbose=options.verbose,
    )


@dataclass(frozen=True)
class RunCliRawArgs:
    resolved_root: Path
    config_path: Path
    input_dir: Path | None
    no_cache: bool
    from_cache_only: bool
    no_upload: bool
    tm_preset: str | None
    tm_target: int | None
    tm_curve: str | None
    frame_count: int | None
    seed: int | None
    overlay: str | None
    skip_analysis: bool
    skip_metadata: bool
    skip_dovi: bool
    force_interactive_alignment: bool
    json_output: bool
    no_color: bool
    write_config: bool
    diagnose_paths: bool
    quiet: bool
    verbose: bool


def handle_run(args: RunCliRawArgs, deps: RunCommandDeps) -> None:
    effective_no_color = args.no_color or deps.no_color_env_present
    console = deps.console_factory(
        stderr=False,
        no_color=effective_no_color,
    )
    log_level = "WARNING" if args.quiet else ("DEBUG" if args.verbose else "INFO")
    log_format = "json" if args.json_output else "console"
    deps.configure_logging(level=log_level, format=log_format)

    try:
        parsed_tm_preset = coerce_cli_choice(args.tm_preset, TonemapPreset, ("color", "preset"))
        parsed_tm_curve = coerce_cli_choice(args.tm_curve, ToneCurve, ("color", "tone_curve"))
        parsed_overlay = coerce_cli_choice(
            args.overlay, OverlayMode, ("screenshots", "overlay_mode")
        )

        run_options = RunCliOptions(
            root=args.resolved_root,
            config_path=args.config_path,
            input_dir=args.input_dir,
            no_cache=args.no_cache,
            from_cache_only=args.from_cache_only,
            no_upload=args.no_upload,
            tm_preset=parsed_tm_preset,
            tm_target_nits=args.tm_target,
            tm_curve=parsed_tm_curve,
            frame_count=args.frame_count,
            seed=args.seed,
            overlay_mode=parsed_overlay,
            skip_analysis=args.skip_analysis,
            skip_metadata=args.skip_metadata,
            skip_dovi=args.skip_dovi,
            force_interactive_alignment=args.force_interactive_alignment,
            json_output=args.json_output,
            no_color=effective_no_color,
            quiet=args.quiet,
            verbose=args.verbose,
        )
        request = build_run_request_from_cli(run_options)

        resolved_config: ConfigSchema | None = None

        def _resolve_effective_config() -> ConfigSchema:
            return apply_cli_overrides(
                deps.load_config(args.config_path),
                cli_args=request.cli_config_overrides(),
            )

        def _load_effective_config() -> ConfigSchema:
            nonlocal resolved_config
            if resolved_config is None:
                resolved_config = _resolve_effective_config()
            return resolved_config

        if args.write_config:
            deps.write_config_to(args.config_path, _load_effective_config())
            return

        if args.diagnose_paths:
            handle_diagnose_paths(args.resolved_root, args.config_path, _load_effective_config())
            return

        if not args.json_output and not args.quiet:
            print_at_a_glance(
                console,
                request=request,
                config=_load_effective_config(),
                root=args.resolved_root,
                config_path=args.config_path,
            )

        result = deps.runner.run(request, dependencies=None)
    except FrameCompareError as error:
        if args.json_output:
            typer.echo(json.dumps(format_error_json(error), sort_keys=True, separators=(",", ":")))
            raise typer.Exit(code=int(get_exit_code(error))) from error
        raise typer.Exit(
            code=deps.handle_error(error, no_color=effective_no_color, verbose=args.verbose)
        ) from error
    except KeyboardInterrupt:
        raise typer.Exit(code=int(ExitCode.INTERRUPTED)) from None

    if args.json_output:
        handle_json_output(result)
        return

    if not result.success:
        raise typer.Exit(code=int(ExitCode.PROCESSING_ERROR))

    print_result_summary(console, result=result, quiet=args.quiet)

    if (
        result.report_path is not None
        and not args.json_output
        and not args.quiet
        and deps.stdout_is_tty
    ):
        try:
            cfg = _resolve_effective_config()
        except FrameCompareError:
            # Default to opening when config cannot be reloaded so successful runs
            # still surface the generated report in interactive sessions.
            cfg = None

        if cfg is None or cfg.report.auto_open:
            deps.open_report(result.report_path)


def handle_diagnose_paths(resolved_root: Path, config_path: Path, config: ConfigSchema) -> None:
    from frame_compare.orchestration.preflight import resolve_paths

    workspace = resolve_paths(config, resolved_root)
    payload = {
        "root": str(resolved_root),
        "config": str(config_path),
        "input": str(workspace.input_dir),
        "output": str(workspace.screenshots_dir),
        "cache": str(workspace.generated_dir),
    }
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def handle_json_output(result: RunResult) -> None:
    payload = {
        "success": result.success,
        "screenshots_dir": str(result.screenshot_dir) if result.screenshot_dir else None,
        "slowpics_url": result.slowpics_url,
        "report_path": str(result.report_path) if result.report_path else None,
        "frame_count": result.frame_count,
        "clips_processed": result.clips_processed,
        "duration_seconds": result.duration_seconds,
        "cache_hit": result.cache_hit,
        "errors": list(result.errors),
    }
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    if not result.success:
        raise typer.Exit(code=int(ExitCode.PROCESSING_ERROR))
