"""Implementation for the ``run`` CLI command."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import typer
from rich.console import Console
from rich.markup import escape

from frame_compare.cli.errors import ExitCode, format_error_json, get_exit_code
from frame_compare.cli.output import (
    PostUploadActionPresentationResult,
    PostUploadActionPresentationResults,
    print_at_a_glance,
    print_result_summary,
)
from frame_compare.config.effective import load_effective_config
from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.errors import FrameCompareError, JSONValue
from frame_compare.orchestration.analysis_policy import (
    validate_skip_analysis_frame_selection_contract as validate_skip_analysis_policy,
)

from .cli_helpers import format_enum_expected

if TYPE_CHECKING:
    from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, RunResult
    from frame_compare.orchestration.types import (
        SlowpicsUploadConfirmationDecision,
        SlowpicsUploadConfirmationFn,
        SlowpicsUploadConfirmationRequest,
    )

type EffectiveConfigLoader = Callable[[], ConfigSchema]


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
    copy_to_clipboard: CopyToClipboardFn
    open_url: OpenUrlFn
    confirm_upload: ConfirmUploadPromptFn
    stdout_is_tty: bool
    stdin_is_tty: bool
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
    def __call__(
        self,
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int: ...


class OpenReportFn(Protocol):
    def __call__(self, report_path: Path) -> bool: ...


class CopyToClipboardFn(Protocol):
    def __call__(self, text: str) -> None: ...


class OpenUrlFn(Protocol):
    def __call__(self, url: str) -> bool: ...


class ConfirmUploadPromptFn(Protocol):
    def __call__(self, text: str, *, default: bool) -> bool: ...


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
    user_frames: list[int] | None
    random_frame_count: int | None
    dark_frame_count: int | None
    bright_frame_count: int | None
    motion_frame_count: int | None
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
        user_frames=options.user_frames,
        random_frame_count=options.random_frame_count,
        dark_frame_count=options.dark_frame_count,
        bright_frame_count=options.bright_frame_count,
        motion_frame_count=options.motion_frame_count,
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
    frames: str | None
    random_frame_count: str | None
    dark_frame_count: str | None
    bright_frame_count: str | None
    motion_frame_count: str | None
    removed_frame_count: str | None
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
        run_options = parse_run_options(args, no_color=effective_no_color)
        request = build_run_request_from_cli(run_options)
        resolve_effective_config, load_effective_config = build_effective_config_loaders(
            args,
            deps,
            request,
        )

        effective_config = load_effective_config()

        if args.diagnose_paths:
            handle_diagnose_paths(args.resolved_root, args.config_path, effective_config)
            return

        if args.write_config:
            validate_write_config_contracts(effective_config)
            deps.write_config_to(args.config_path, effective_config)
            return

        validate_run_contracts(args, deps, effective_config)

        if not args.json_output and not args.quiet:
            print_run_preview(console, args, request, load_effective_config)

        run_dependencies = build_runner_dependencies(
            args=args,
            deps=deps,
            config=load_effective_config(),
            console=console,
            resolve_effective_config=resolve_effective_config,
        )
        result = deps.runner.run(request, dependencies=run_dependencies)
    except FrameCompareError as error:
        raise run_error_exit(
            error,
            args=args,
            deps=deps,
            no_color=effective_no_color,
        ) from error
    except (KeyboardInterrupt, typer.Abort):
        raise typer.Exit(code=int(ExitCode.INTERRUPTED)) from None

    if args.json_output:
        handle_json_output(result)
        return

    if not result.success:
        raise typer.Exit(code=int(ExitCode.PROCESSING_ERROR))

    post_upload_actions = collect_interactive_slowpics_actions(
        result,
        args=args,
        deps=deps,
        config=load_effective_config(),
    )
    print_result_summary(
        console,
        result=result,
        quiet=args.quiet,
        post_upload_actions=post_upload_actions,
    )
    maybe_open_run_report(
        result,
        args=args,
        deps=deps,
        resolve_effective_config=resolve_effective_config,
        suppress_report_open=(
            slowpics_browser_open_attempted(post_upload_actions)
            or report_confirmed_slowpics_enabled(load_effective_config())
        ),
    )


def build_runner_dependencies(
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    config: ConfigSchema,
    console: Console,
    resolve_effective_config: EffectiveConfigLoader,
) -> RunDependencies | None:
    if not report_confirmed_slowpics_enabled(config):
        return None

    from frame_compare.orchestration.coordinator import RunDependencies

    return RunDependencies(
        confirm_slowpics_upload=build_confirm_slowpics_upload_callback(
            args=args,
            deps=deps,
            console=console,
            resolve_effective_config=resolve_effective_config,
        )
    )


def report_confirmed_slowpics_enabled(config: ConfigSchema) -> bool:
    return config.slowpics.auto_upload and config.slowpics.confirm_upload_after_report


def build_confirm_slowpics_upload_callback(
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    console: Console,
    resolve_effective_config: EffectiveConfigLoader,
) -> SlowpicsUploadConfirmationFn:
    def _confirm_slowpics_upload(
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        opened = maybe_open_report_path(
            request.report_path,
            args=args,
            deps=deps,
            resolve_effective_config=resolve_effective_config,
        )
        if not opened:
            console.print(f"Report: {escape(str(request.report_path))}", soft_wrap=True)
        if deps.confirm_upload(
            "Review the local report, then upload this comparison to slow.pics?",
            default=False,
        ):
            return "confirmed"
        return "declined"

    return _confirm_slowpics_upload


def parse_run_options(args: RunCliRawArgs, *, no_color: bool) -> RunCliOptions:
    parsed_tm_preset = coerce_cli_choice(args.tm_preset, TonemapPreset, ("color", "preset"))
    parsed_tm_curve = coerce_cli_choice(args.tm_curve, ToneCurve, ("color", "tone_curve"))
    parsed_overlay = coerce_cli_choice(args.overlay, OverlayMode, ("screenshots", "overlay_mode"))
    reject_removed_frame_count(args.removed_frame_count)

    return RunCliOptions(
        root=args.resolved_root,
        config_path=args.config_path,
        input_dir=args.input_dir,
        no_cache=args.no_cache,
        from_cache_only=args.from_cache_only,
        no_upload=args.no_upload,
        tm_preset=parsed_tm_preset,
        tm_target_nits=args.tm_target,
        tm_curve=parsed_tm_curve,
        user_frames=parse_frame_list(args.frames),
        random_frame_count=parse_non_negative_int_option(
            args.random_frame_count,
            option_name="--random-frame-count",
            loc=("analysis", "random_frame_count"),
        ),
        dark_frame_count=parse_non_negative_int_option(
            args.dark_frame_count,
            option_name="--dark-frame-count",
            loc=("analysis", "dark_frame_count"),
        ),
        bright_frame_count=parse_non_negative_int_option(
            args.bright_frame_count,
            option_name="--bright-frame-count",
            loc=("analysis", "bright_frame_count"),
        ),
        motion_frame_count=parse_non_negative_int_option(
            args.motion_frame_count,
            option_name="--motion-frame-count",
            loc=("analysis", "motion_frame_count"),
        ),
        seed=args.seed,
        overlay_mode=parsed_overlay,
        skip_analysis=args.skip_analysis,
        skip_metadata=args.skip_metadata,
        skip_dovi=args.skip_dovi,
        force_interactive_alignment=args.force_interactive_alignment,
        json_output=args.json_output,
        no_color=no_color,
        quiet=args.quiet,
        verbose=args.verbose,
    )


def reject_removed_frame_count(value: str | None) -> None:
    if value is None:
        return
    raise ConfigValidationError(
        [
            {
                "type": "removed_option",
                "loc": ["cli", "frame_count"],
                "msg": (
                    "--frame-count/-n has been removed; use --random-frame-count, "
                    "--dark-frame-count, --bright-frame-count, --motion-frame-count, "
                    "or --frames"
                ),
                "input": value,
            }
        ],
        message="--frame-count/-n has been removed",
        hint="Use explicit frame selection flags such as --random-frame-count or --frames",
    )


def parse_frame_list(value: str | None) -> list[int] | None:
    if value is None:
        return None
    if value == "":
        raise _frame_selection_cli_error(
            loc=("analysis", "user_frames"),
            msg="--frames must be a comma-separated list of non-negative integers",
            input_value=value,
        )
    frames: list[int] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if part == "":
            raise _frame_selection_cli_error(
                loc=("analysis", "user_frames"),
                msg="--frames must not contain empty entries",
                input_value=value,
            )
        try:
            frame = int(part, 10)
        except ValueError as exc:
            raise _frame_selection_cli_error(
                loc=("analysis", "user_frames"),
                msg="--frames must contain only non-negative integers",
                input_value=value,
            ) from exc
        if frame < 0:
            raise _frame_selection_cli_error(
                loc=("analysis", "user_frames"),
                msg="--frames must contain only non-negative integers",
                input_value=value,
            )
        frames.append(frame)
    return frames


def parse_non_negative_int_option(
    value: str | None,
    *,
    option_name: str,
    loc: tuple[str, str],
) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise _frame_selection_cli_error(
            loc=loc,
            msg=f"{option_name} must be a non-negative integer",
            input_value=value,
        ) from exc
    if parsed < 0:
        raise _frame_selection_cli_error(
            loc=loc,
            msg=f"{option_name} must be a non-negative integer",
            input_value=value,
        )
    return parsed


def _frame_selection_cli_error(
    *,
    loc: tuple[str, ...],
    msg: str,
    input_value: str,
) -> ConfigValidationError:
    return ConfigValidationError(
        [
            {
                "type": "value_error",
                "loc": list(loc),
                "msg": msg,
                "input": input_value,
            }
        ],
        message=msg,
    )


def build_effective_config_loaders(
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    request: RunRequest,
) -> tuple[EffectiveConfigLoader, EffectiveConfigLoader]:
    resolved_config: ConfigSchema | None = None
    cli_overrides = request.cli_config_overrides()

    def _resolve_effective_config() -> ConfigSchema:
        return load_effective_config(
            args.config_path,
            cli_overrides=cli_overrides,
            load_config_fn=deps.load_config,
        )

    def _load_effective_config() -> ConfigSchema:
        nonlocal resolved_config
        if resolved_config is None:
            resolved_config = _resolve_effective_config()
        return resolved_config

    return _resolve_effective_config, _load_effective_config


def validate_run_contracts(args: RunCliRawArgs, deps: RunCommandDeps, config: ConfigSchema) -> None:
    """Enforce public CLI mode combinations before entering the runtime pipeline."""
    validate_skip_analysis_frame_selection_contract(args, config)
    validation_errors: list[dict[str, JSONValue]] = []
    validation_errors.extend(json_interactive_alignment_contract_errors(args, config))
    validation_errors.extend(previous_offset_reuse_contract_errors(args, config))
    validation_errors.extend(report_confirmed_slowpics_contract_errors(args, deps, config))
    if not validation_errors:
        return

    raise ConfigValidationError(
        validation_errors,
        message=validation_error_message(args, config),
        hint=validation_error_hint(args, config),
    )


def validate_write_config_contracts(config: ConfigSchema) -> None:
    """Reject persisted effective configs that normal runs would not accept."""
    validation_errors = previous_offset_reuse_persisted_contract_errors(config)
    if not validation_errors:
        return
    raise ConfigValidationError(
        validation_errors,
        message="Previous offset reuse is not supported with this run configuration",
        hint=(
            "Set audio_alignment.previous_offsets to disabled, enable "
            "audio_alignment.cache_results, or disable force interactive alignment"
        ),
    )


def validate_skip_analysis_frame_selection_contract(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> None:
    validate_skip_analysis_policy(
        skip_analysis=args.skip_analysis,
        config=config.analysis,
    )


def validate_json_interactive_alignment_contract(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> None:
    validation_errors = json_interactive_alignment_contract_errors(args, config)
    if not validation_errors:
        return
    raise ConfigValidationError(
        validation_errors,
        message="Interactive alignment is not supported with --json",
        hint=(
            "Disable audio_alignment.use_vspreview and "
            "audio_alignment.force_interactive, or run without --json"
        ),
    )


def json_interactive_alignment_contract_errors(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    if not args.json_output:
        return []

    interactive_fields: list[tuple[str, str]] = []
    if config.audio_alignment.use_vspreview:
        interactive_fields.append(("audio_alignment", "use_vspreview"))
    if config.audio_alignment.force_interactive:
        interactive_fields.append(("audio_alignment", "force_interactive"))
    if not interactive_fields:
        return []

    return [
        {
            "type": "value_error",
            "loc": list(loc),
            "msg": "Interactive alignment is not supported with --json.",
            "input": True,
        }
        for loc in interactive_fields
    ]


def previous_offset_reuse_contract_errors(
    args: RunCliRawArgs,
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    previous_offsets = config.audio_alignment.previous_offsets
    if previous_offsets == "disabled":
        return []

    validation_errors: list[dict[str, JSONValue]] = []
    if args.json_output and previous_offsets == "prompt":
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["audio_alignment", "previous_offsets"],
                "msg": "Previous offset prompt mode is not supported with --json.",
                "input": previous_offsets,
            }
        )
    if args.quiet and previous_offsets == "prompt":
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "quiet"],
                "msg": "Previous offset prompt mode is not supported with --quiet.",
                "input": previous_offsets,
            }
        )
    validation_errors.extend(previous_offset_reuse_persisted_contract_errors(config))
    return validation_errors


def previous_offset_reuse_persisted_contract_errors(
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    previous_offsets = config.audio_alignment.previous_offsets
    if previous_offsets == "disabled":
        return []

    validation_errors: list[dict[str, JSONValue]] = []
    if config.audio_alignment.force_interactive:
        validation_errors.extend(
            [
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "force_interactive"],
                    "msg": "Previous offset reuse is not supported with force interactive alignment.",
                    "input": True,
                },
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "previous_offsets"],
                    "msg": "Previous offset reuse is not supported with force interactive alignment.",
                    "input": previous_offsets,
                },
            ]
        )
    if not config.audio_alignment.cache_results:
        validation_errors.extend(
            [
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "cache_results"],
                    "msg": "Previous offset reuse requires audio_alignment.cache_results = true.",
                    "input": False,
                },
                {
                    "type": "value_error",
                    "loc": ["audio_alignment", "previous_offsets"],
                    "msg": "Previous offset reuse requires audio_alignment.cache_results = true.",
                    "input": previous_offsets,
                },
            ]
        )
    return validation_errors


def validate_report_confirmed_slowpics_contract(
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    config: ConfigSchema,
) -> None:
    validation_errors = report_confirmed_slowpics_contract_errors(args, deps, config)
    if not validation_errors:
        return

    raise ConfigValidationError(
        validation_errors,
        message="Report-confirmed slow.pics upload requires an interactive report-enabled run",
        hint=(
            "Disable slowpics.confirm_upload_after_report, disable slowpics.auto_upload, "
            "enable reports, or run from an interactive terminal without --json/--quiet"
        ),
    )


def report_confirmed_slowpics_contract_errors(
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    config: ConfigSchema,
) -> list[dict[str, JSONValue]]:
    if not report_confirmed_slowpics_enabled(config):
        return []

    validation_errors: list[dict[str, JSONValue]] = []
    if args.json_output:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "json"],
                "msg": "Report-confirmed slow.pics upload is not supported with --json.",
                "input": True,
            }
        )
    if args.quiet:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["cli", "quiet"],
                "msg": "Report-confirmed slow.pics upload is not supported with --quiet.",
                "input": True,
            }
        )
    if not deps.stdin_is_tty:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["stdin"],
                "msg": "Report-confirmed slow.pics upload requires stdin to be attached to a TTY.",
                "input": False,
            }
        )
    if not deps.stdout_is_tty:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["stdout"],
                "msg": "Report-confirmed slow.pics upload requires stdout to be attached to a TTY.",
                "input": False,
            }
        )
    if not config.report.enable:
        validation_errors.append(
            {
                "type": "value_error",
                "loc": ["report", "enable"],
                "msg": "Report-confirmed slow.pics upload requires report.enable = true.",
                "input": False,
            }
        )
    return validation_errors


def validation_error_message(args: RunCliRawArgs, config: ConfigSchema) -> str:
    if args.json_output and (
        config.audio_alignment.use_vspreview or config.audio_alignment.force_interactive
    ):
        return "Interactive alignment is not supported with --json"
    if config.audio_alignment.previous_offsets != "disabled":
        return "Previous offset reuse is not supported with this run configuration"
    if report_confirmed_slowpics_enabled(config):
        return "Report-confirmed slow.pics upload requires an interactive report-enabled run"
    return "Run configuration is invalid"


def validation_error_hint(args: RunCliRawArgs, config: ConfigSchema) -> str:
    if args.json_output and (
        config.audio_alignment.use_vspreview or config.audio_alignment.force_interactive
    ):
        return (
            "Disable audio_alignment.use_vspreview and "
            "audio_alignment.force_interactive, or run without --json"
        )
    if config.audio_alignment.previous_offsets != "disabled":
        return (
            "Set audio_alignment.previous_offsets to disabled, enable "
            "audio_alignment.cache_results, disable force interactive alignment, "
            "or run without --json/--quiet prompt mode"
        )
    return (
        "Disable slowpics.confirm_upload_after_report, disable slowpics.auto_upload, "
        "enable reports, or run from an interactive terminal without --json/--quiet"
    )


def print_run_preview(
    console: Console,
    args: RunCliRawArgs,
    request: RunRequest,
    load_effective_config: EffectiveConfigLoader,
) -> None:
    print_at_a_glance(
        console,
        request=request,
        config=load_effective_config(),
        root=args.resolved_root,
        config_path=args.config_path,
    )


def run_error_exit(
    error: FrameCompareError,
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    no_color: bool,
) -> typer.Exit:
    if args.json_output:
        typer.echo(json.dumps(format_error_json(error), sort_keys=True, separators=(",", ":")))
        return typer.Exit(code=int(get_exit_code(error)))
    return typer.Exit(code=deps.handle_error(error, no_color=no_color, verbose=args.verbose))


def maybe_open_run_report(
    result: RunResult,
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    resolve_effective_config: EffectiveConfigLoader,
    suppress_report_open: bool = False,
) -> bool:
    if result.report_path is None:
        return False
    return maybe_open_report_path(
        result.report_path,
        args=args,
        deps=deps,
        resolve_effective_config=resolve_effective_config,
        suppress_report_open=suppress_report_open,
    )


def maybe_open_report_path(
    report_path: Path,
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    resolve_effective_config: EffectiveConfigLoader,
    suppress_report_open: bool = False,
) -> bool:
    if suppress_report_open or args.json_output or args.quiet or not deps.stdout_is_tty:
        return False

    try:
        cfg = resolve_effective_config()
    except FrameCompareError:
        # Default to opening when config cannot be reloaded so successful runs
        # still surface the generated report in interactive sessions.
        cfg = None

    if cfg is None or cfg.report.auto_open:
        return deps.open_report(report_path)
    return False


def collect_interactive_slowpics_actions(
    result: RunResult,
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    config: ConfigSchema,
) -> PostUploadActionPresentationResults:
    """Run enabled interactive slow.pics URL actions and collect presentation state."""
    url = result.slowpics_url
    if url is None or args.json_output or args.quiet or not deps.stdout_is_tty:
        return ()

    actions: list[PostUploadActionPresentationResult] = []
    if config.slowpics.copy_url_to_clipboard:
        actions.append(_copy_slowpics_url(url, copy_to_clipboard=deps.copy_to_clipboard))
    if config.slowpics.open_in_browser:
        actions.append(_open_slowpics_url(url, open_url=deps.open_url))
    return tuple(actions)


def _copy_slowpics_url(
    url: str,
    *,
    copy_to_clipboard: CopyToClipboardFn,
) -> PostUploadActionPresentationResult:
    try:
        copy_to_clipboard(url)
    except Exception as exc:
        return PostUploadActionPresentationResult(
            kind="clipboard",
            success=False,
            warning=f"slow.pics clipboard: failed to copy URL: {exc}",
        )
    return PostUploadActionPresentationResult(
        kind="clipboard",
        success=True,
        detail="slow.pics URL copied to clipboard",
    )


def _open_slowpics_url(
    url: str,
    *,
    open_url: OpenUrlFn,
) -> PostUploadActionPresentationResult:
    try:
        opened = open_url(url)
    except Exception as exc:
        return PostUploadActionPresentationResult(
            kind="browser",
            success=False,
            warning=f"slow.pics browser: failed to open URL: {exc}",
        )
    if not opened:
        return PostUploadActionPresentationResult(
            kind="browser",
            success=False,
            warning="slow.pics browser: failed to open URL: no browser accepted the request",
        )
    return PostUploadActionPresentationResult(
        kind="browser",
        success=True,
        detail="slow.pics URL opened in browser",
    )


def slowpics_browser_open_attempted(
    actions: PostUploadActionPresentationResults,
) -> bool:
    return any(action.kind == "browser" for action in actions)


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
