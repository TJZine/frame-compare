"""Implementation for the ``run`` CLI command."""

from __future__ import annotations

import json
import sys
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
from frame_compare.config.overrides import cli_config_overrides_from
from frame_compare.config.schema import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.errors import FrameCompareError
from frame_compare.orchestration.preflight import (
    resolve_selected_config_path,
    validate_and_normalize_config_paths,
)

from .cli_helpers import HandleErrorFn, LoadConfigFn, WriteConfigFn, format_enum_expected
from .run_contracts import (
    report_confirmed_slowpics_enabled,
    validate_dry_run_cache_contract,
    validate_dry_run_mode_contract,
    validate_run_contracts,
    validate_write_config_contracts,
)

if TYPE_CHECKING:
    from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, RunResult
    from frame_compare.orchestration.types import (
        FullWindowRetryConfirmationDecision,
        FullWindowRetryConfirmationFn,
        FullWindowRetryConfirmationRequest,
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
    def __call__(self, *, level: str, log_format: str) -> None: ...


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
    confirm_full_window_retry: ConfirmFullWindowRetryPromptFn
    stdout_is_tty: bool
    stdin_is_tty: bool
    no_color_env_present: bool


class OpenReportFn(Protocol):
    def __call__(self, report_path: Path) -> bool: ...


class CopyToClipboardFn(Protocol):
    def __call__(self, text: str) -> None: ...


class OpenUrlFn(Protocol):
    def __call__(self, url: str) -> bool: ...


class ConfirmUploadPromptFn(Protocol):
    def __call__(self, text: str, *, default: bool) -> bool: ...


class ConfirmFullWindowRetryPromptFn(Protocol):
    def __call__(self, text: str) -> bool: ...


def confirm_full_window_retry_on_stderr(text: str) -> bool:
    """Read one default-No response without allowing Click to reprompt."""
    typer.echo(text, nl=False, err=True)
    try:
        response = sys.stdin.readline()
    except KeyboardInterrupt:
        raise typer.Abort() from None
    if response == "":
        raise typer.Abort()
    return response.strip().lower() in {"y", "yes"}


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
    seed: int | None
    overlay: str | None
    skip_analysis: bool
    skip_metadata: bool
    force_interactive_alignment: bool
    json_output: bool
    no_color: bool
    write_config: bool
    diagnose_paths: bool
    quiet: bool
    verbose: bool
    dry_run: bool = False


def handle_run(args: RunCliRawArgs, deps: RunCommandDeps) -> None:
    effective_no_color = args.no_color or deps.no_color_env_present
    console = deps.console_factory(
        stderr=False,
        no_color=effective_no_color,
    )

    try:
        resolve_selected_config_path(args.config_path, args.resolved_root)
        run_options = parse_run_options(args, no_color=effective_no_color)
        resolve_effective_config, load_effective_config = build_effective_config_loaders(
            args,
            deps,
            run_options,
        )

        effective_config = load_effective_config()
        normalized_config = validate_and_normalize_config_paths(
            effective_config,
            args.resolved_root,
        )
        validate_dry_run_mode_contract(args)
        if args.dry_run:
            validate_run_contracts(args, deps, normalized_config)
            validate_dry_run_cache_contract(args)
            handle_dry_run(args, normalized_config, console)
            return

        log_level = (
            "WARNING"
            if args.quiet
            else ("DEBUG" if args.verbose else normalized_config.logging.level.value)
        )
        log_format = "json" if args.json_output else normalized_config.logging.format.value
        deps.configure_logging(level=log_level, log_format=log_format)

        if args.diagnose_paths:
            handle_diagnose_paths(args.resolved_root, args.config_path, normalized_config)
            return

        if args.write_config:
            validate_write_config_contracts(effective_config)
            deps.write_config_to(args.config_path, effective_config)
            return

        validate_run_contracts(args, deps, normalized_config)
        request = build_run_request_from_cli(run_options)

        if not args.json_output and not args.quiet:
            print_run_preview(console, args, request, load_effective_config)

        run_dependencies = build_runner_dependencies(
            args=args,
            deps=deps,
            config=normalized_config,
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
    confirm_slowpics_upload = (
        build_confirm_slowpics_upload_callback(
            args=args,
            deps=deps,
            console=console,
            resolve_effective_config=resolve_effective_config,
        )
        if report_confirmed_slowpics_enabled(config)
        else None
    )
    confirm_full_window_retry = (
        build_confirm_full_window_retry_callback(deps=deps)
        if full_window_retry_prompt_is_legal(args=args, deps=deps, config=config)
        else None
    )
    if confirm_slowpics_upload is None and confirm_full_window_retry is None:
        return None

    from frame_compare.orchestration.coordinator import RunDependencies

    return RunDependencies(
        confirm_slowpics_upload=confirm_slowpics_upload,
        confirm_full_window_retry=confirm_full_window_retry,
    )


def full_window_retry_prompt_is_legal(
    *,
    args: RunCliRawArgs,
    deps: RunCommandDeps,
    config: ConfigSchema,
) -> bool:
    analysis = config.analysis
    return (
        (analysis.ignore_lead_seconds > 0.0 or analysis.ignore_trail_seconds > 0.0)
        and not args.json_output
        and not args.quiet
        and deps.stdin_is_tty
        and not args.from_cache_only
        and not args.skip_analysis
    )


def build_confirm_full_window_retry_callback(
    *,
    deps: RunCommandDeps,
) -> FullWindowRetryConfirmationFn:
    def _confirm_full_window_retry(
        request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision:
        del request
        confirmed = deps.confirm_full_window_retry(
            "Configured lead/trail exclusions leave too little media to satisfy the\n"
            "requested frame selection. Analyze the full shared clip for this run? [y/N] "
        )
        return "confirmed" if confirmed else "declined"

    return _confirm_full_window_retry


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
        force_interactive_alignment=args.force_interactive_alignment,
        json_output=args.json_output,
        no_color=no_color,
        quiet=args.quiet,
        verbose=args.verbose,
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
    options: RunCliOptions,
) -> tuple[EffectiveConfigLoader, EffectiveConfigLoader]:
    resolved_config: ConfigSchema | None = None
    cli_overrides = cli_config_overrides_from(options)

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


def handle_dry_run(args: RunCliRawArgs, config: ConfigSchema, console: Console) -> None:
    """Build and render the CLI-owned plan before runtime request construction."""
    from frame_compare.cli.dry_run import (
        build_dry_run_plan,
        dry_run_plan_json,
        print_dry_run_plan,
    )

    plan = build_dry_run_plan(
        root=args.resolved_root,
        config=config,
        from_cache_only=args.from_cache_only,
    )
    if args.json_output:
        typer.echo(json.dumps(dry_run_plan_json(plan), sort_keys=True, separators=(",", ":")))
        return
    print_dry_run_plan(console, plan, quiet=args.quiet)


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
        "output": str(workspace.generated_root),
        "cache": str(workspace.generated_root / "cache"),
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
