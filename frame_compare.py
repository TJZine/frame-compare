"""CLI entry point and orchestration logic for frame comparison runs."""

from __future__ import annotations

import builtins
import copy
import json
import os
import shutil
import sys
import webbrowser
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, MutableMapping, Optional, cast

import click
from rich import print
from rich.console import Console as _Console

import src.frame_compare.cli_runtime as _cli_runtime
import src.frame_compare.config_writer as config_writer
import src.frame_compare.core as _core
import src.frame_compare.doctor as doctor_module
import src.frame_compare.preflight as _preflight
import src.frame_compare.presets as presets_lib
import src.frame_compare.tmdb_workflow as tmdb_workflow
import src.frame_compare.vspreview as _vspreview
import src.frame_compare.wizard as _wizard
from src.config_loader import ConfigError, load_config
from src.frame_compare import runner
from src.frame_compare import vs as _vs_core
from src.frame_compare.cli_runtime import JsonTail, ReportJSON, _ensure_slowpics_block
from src.frame_compare.config_helpers import env_flag_enabled as _env_flag_enabled
from src.frame_compare.core import (
    _DEFAULT_CONFIG_HELP,
    NO_WIZARD_ENV_VAR,
    CLIAppError,
)
from src.frame_compare.preflight import (
    PreflightResult,
    _fresh_app_config,
    _path_is_within_root,
    prepare_preflight,
    resolve_subdir,
    resolve_workspace_root,
)
from src.frame_compare.preflight import (
    collect_path_diagnostics as _collect_path_diagnostics,
)
from src.frame_compare.render.errors import ScreenshotError
from src.frame_compare.slowpics import build_shortcut_filename

collect_doctor_checks = doctor_module.collect_checks


# Legacy compatibility surface: enumerate the few core helpers we still expose.
_COMPAT_EXPORTS: dict[str, object] = {
    "cli_runtime": _cli_runtime,
    "core": _core,
    "config_writer": config_writer,
    "presets": presets_lib,
    "preflight": _preflight,
    "tmdb_workflow": tmdb_workflow,
    "vspreview": _vspreview,
    "vs_core": _vs_core,
    "collect_doctor_checks": collect_doctor_checks,
    "emit_doctor_results": doctor_module.emit_results,
    "DoctorCheck": doctor_module.DoctorCheck,
    "Console": _Console,
    "CliOutputManager": _cli_runtime.CliOutputManager,
    "NullCliOutputManager": _cli_runtime.NullCliOutputManager,
    "collect_path_diagnostics": _preflight.collect_path_diagnostics,
    "prepare_preflight": _preflight.prepare_preflight,
    "resolve_workspace_root": _preflight.resolve_workspace_root,
    "resolve_subdir": _preflight.resolve_subdir,
    "run_wizard_prompts": _wizard.run_wizard_prompts,
    "resolve_wizard_paths": _wizard.resolve_wizard_paths,
    "prompt_workspace_root": _wizard.prompt_workspace_root,
    "prompt_input_directory": _wizard.prompt_input_directory,
    "prompt_slowpics_options": _wizard.prompt_slowpics_options,
    "prompt_audio_alignment_option": _wizard.prompt_audio_alignment_option,
    "prompt_renderer_preference": _wizard.prompt_renderer_preference,
    "render_collection_name": tmdb_workflow.render_collection_name,
    "resolve_tmdb_workflow": tmdb_workflow.resolve_workflow,
    "TMDBLookupResult": tmdb_workflow.TMDBLookupResult,
    "ScreenshotError": ScreenshotError,
}
for _name, _value in _COMPAT_EXPORTS.items():
    globals()[_name] = _value

resolve_tmdb_workflow = tmdb_workflow.resolve_workflow
TMDBLookupResult = tmdb_workflow.TMDBLookupResult
render_collection_name = tmdb_workflow.render_collection_name
collect_path_diagnostics = _collect_path_diagnostics
emit_doctor_results = doctor_module.emit_results
DoctorCheck = doctor_module.DoctorCheck
vs_core = _vs_core

RunResult = runner.RunResult
RunRequest = runner.RunRequest

__all__ = (
    "run_cli",
    "main",
    "RunRequest",
    "RunResult",
    "CLIAppError",
    "ScreenshotError",
    "resolve_tmdb_workflow",
    "TMDBLookupResult",
    "render_collection_name",
    "prepare_preflight",
    "resolve_workspace_root",
    "PreflightResult",
    "collect_path_diagnostics",
    "collect_doctor_checks",
    "emit_doctor_results",
    "DoctorCheck",
    "vs_core",
)


def run_cli(
    config_path: str | None,
    input_dir: str | None = None,
    *,
    root_override: str | None = None,
    audio_track_overrides: Iterable[str] | None = None,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
    report_enable_override: Optional[bool] = None,
    skip_wizard: bool = False,
    debug_color: bool = False,
    tonemap_overrides: Optional[Dict[str, Any]] = None,
) -> RunResult:
    """Delegate to the shared runner module."""
    request = RunRequest(
        config_path=config_path,
        input_dir=input_dir,
        root_override=root_override,
        audio_track_overrides=audio_track_overrides,
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        report_enable_override=report_enable_override,
        skip_wizard=skip_wizard,
        debug_color=debug_color,
        tonemap_overrides=tonemap_overrides,
        impl_module=sys.modules.get(__name__),
    )
    return runner.run(request)


def _run_cli_entry(
    *,
    root_path: str | None,
    config_path: str | None,
    input_dir: str | None,
    audio_align_track_option: tuple[str, ...],
    quiet: bool,
    verbose: bool,
    no_color: bool,
    json_pretty: bool,
    diagnose_paths: bool,
    write_config: bool,
    skip_wizard: bool,
    html_report_enable: bool,
    html_report_disable: bool,
    debug_color: bool,
    tm_preset: str | None,
    tm_curve: str | None,
    tm_target: float | None,
    tm_dst_min: float | None,
    tm_knee: float | None,
    tm_dpd_preset: str | None,
    tm_dpd_black_cutoff: float | None,
    tm_gamma: float | None,
    tm_gamma_disable: bool,
    tm_smoothing: float | None,
    tm_scene_low: float | None,
    tm_scene_high: float | None,
    tm_percentile: float | None,
    tm_contrast: float | None,
    tm_metadata: str | None,
    tm_use_dovi: bool | None,
    tm_visualize_lut: bool | None,
    tm_show_clipping: bool | None,
) -> None:
    """Execute the primary CLI workflow with the provided options."""

    skip_wizard = skip_wizard or _env_flag_enabled(os.environ.get(NO_WIZARD_ENV_VAR))

    if html_report_enable and html_report_disable:
        raise click.ClickException("Cannot use both --html-report and --no-html-report.")
    report_override: Optional[bool]
    if html_report_enable:
        report_override = True
    elif html_report_disable:
        report_override = False
    else:
        report_override = None

    if tm_gamma_disable and tm_gamma is not None:
        raise click.ClickException("Cannot use --tm-gamma-disable together with --tm-gamma.")

    tonemap_override: Dict[str, Any] = {}
    if tm_preset:
        tonemap_override["preset"] = tm_preset
    if tm_curve:
        tonemap_override["tone_curve"] = tm_curve
    if tm_target is not None:
        tonemap_override["target_nits"] = tm_target
    if tm_dst_min is not None:
        tonemap_override["dst_min_nits"] = tm_dst_min
    if tm_knee is not None:
        tonemap_override["knee_offset"] = tm_knee
    if tm_dpd_preset:
        tonemap_override["dpd_preset"] = tm_dpd_preset
    if tm_dpd_black_cutoff is not None:
        tonemap_override["dpd_black_cutoff"] = tm_dpd_black_cutoff
    if tm_gamma is not None:
        tonemap_override["post_gamma"] = tm_gamma
        tonemap_override["post_gamma_enable"] = True
    elif tm_gamma_disable:
        tonemap_override["post_gamma_enable"] = False
    if tm_smoothing is not None:
        tonemap_override["smoothing_period"] = tm_smoothing
    if tm_scene_low is not None:
        tonemap_override["scene_threshold_low"] = tm_scene_low
    if tm_scene_high is not None:
        tonemap_override["scene_threshold_high"] = tm_scene_high
    if tm_percentile is not None:
        tonemap_override["percentile"] = tm_percentile
    if tm_contrast is not None:
        tonemap_override["contrast_recovery"] = tm_contrast
    if tm_metadata is not None:
        tonemap_override["metadata"] = tm_metadata
    if tm_use_dovi is not None:
        tonemap_override["use_dovi"] = tm_use_dovi
    if tm_visualize_lut is not None:
        tonemap_override["visualize_lut"] = tm_visualize_lut
    if tm_show_clipping is not None:
        tonemap_override["show_clipping"] = tm_show_clipping

    preflight_for_write: PreflightResult | None = None
    if write_config:
        try:
            preflight_for_write = prepare_preflight(
                cli_root=root_path,
                config_override=config_path,
                input_override=input_dir,
                ensure_config=True,
                create_dirs=True,
                create_media_dir=False,
                allow_auto_wizard=True,
                skip_auto_wizard=skip_wizard,
            )
        except CLIAppError as exc:
            print(exc.rich_message)
            raise click.exceptions.Exit(exc.code) from exc
        else:
            print(f"Config ensured at {preflight_for_write.config_path}")
        if not diagnose_paths:
            return

    if diagnose_paths:
        try:
            diagnostics = _preflight.collect_path_diagnostics(
                cli_root=root_path,
                config_override=config_path,
                input_override=input_dir,
            )
        except CLIAppError as exc:
            print(exc.rich_message)
            raise click.exceptions.Exit(exc.code) from exc
        if preflight_for_write is not None:
            diagnostics.setdefault("warnings", []).extend(
                warning for warning in preflight_for_write.warnings if warning not in diagnostics.get("warnings", [])
            )
        print(json.dumps(diagnostics, separators=(",", ":")))
        return

    try:
        result = run_cli(
            config_path,
            input_dir,
            root_override=root_path,
            audio_track_overrides=audio_align_track_option,
            quiet=quiet,
            verbose=verbose,
            no_color=no_color,
            report_enable_override=report_override,
            skip_wizard=skip_wizard,
            debug_color=debug_color,
            tonemap_overrides=tonemap_override or None,
        )
    except CLIAppError as exc:
        print(exc.rich_message)
        raise click.exceptions.Exit(exc.code) from exc

    slowpics_url = result.slowpics_url
    cfg = result.config
    out_dir = result.out_dir
    json_tail = (
        cast(JsonTail, result.json_tail)
        if result.json_tail is not None
        else cast(JsonTail, {})
    )

    slowpics_block = json_tail.get("slowpics")
    shortcut_path_str: Optional[str] = None
    deleted_dir = False
    clipboard_hint = ""

    if slowpics_url:
        if cfg.slowpics.open_in_browser:
            try:
                webbrowser.open(slowpics_url)
            except Exception:
                print("[yellow]Warning:[/yellow] Unable to open browser for slow.pics URL")
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(slowpics_url)
        except Exception:
            clipboard_hint = ""
        else:
            clipboard_hint = " (copied to clipboard)"

        if cfg.slowpics.create_url_shortcut:
            shortcut_filename = build_shortcut_filename(cfg.slowpics.collection_name, slowpics_url)
            if shortcut_filename:
                shortcut_path_str = str(out_dir / shortcut_filename)

        print("[✓] slow.pics: verifying & saving shortcut")
        url_line = f"slow.pics URL: {slowpics_url}{clipboard_hint}"
        print(url_line)
        if shortcut_path_str:
            print(f"Shortcut: {shortcut_path_str}")
        else:
            print("Shortcut: (disabled)")

        if cfg.slowpics.delete_screen_dir_after_upload:
            created_path = result.out_dir_created_path if result.out_dir_created else None
            if created_path is None:
                if result.out_dir_created:
                    print(
                        "[yellow]Warning:[/yellow] Unable to resolve created screenshots "
                        "directory; skipping automatic cleanup."
                    )
                else:
                    print(
                        "[yellow]Warning:[/yellow] Screenshot directory existed before this run; "
                        "skipping automatic cleanup."
                    )
            else:
                try:
                    resolved_created = created_path.resolve()
                except OSError:
                    resolved_created = created_path
                try:
                    resolved_out_dir = out_dir.resolve()
                except OSError:
                    resolved_out_dir = out_dir
                if not _path_is_within_root(result.root, resolved_created):
                    print(
                        "[yellow]Warning:[/yellow] Skipping screenshot cleanup because the output"
                        f" directory {resolved_created} is outside the input root {result.root}"
                    )
                elif resolved_created != resolved_out_dir:
                    print(
                        "[yellow]Warning:[/yellow] Skipping screenshot cleanup because the "
                        "resolved screenshots directory changed during the run."
                    )
                else:
                    try:
                        shutil.rmtree(resolved_created)
                        deleted_dir = True
                        print("Cleaned up screenshots after upload")
                        builtins.print(f"  {resolved_created}")
                    except OSError as exc:
                        print(
                            f"[yellow]Warning:[/yellow] Failed to delete screenshot directory: {exc}"
                        )
        slowpics_block = _ensure_slowpics_block(json_tail, cfg)
        slowpics_block["url"] = slowpics_url
        slowpics_block["shortcut_path"] = shortcut_path_str
        slowpics_block["deleted_screens_dir"] = deleted_dir
    elif isinstance(slowpics_block, dict):
        _ensure_slowpics_block(json_tail, cfg)

    report_block_obj = json_tail.get("report")
    if isinstance(report_block_obj, dict):
        report_block = cast(ReportJSON, report_block_obj)
    else:
        report_block = cast(
            ReportJSON,
            {
                "enabled": False,
                "path": None,
                "opened": False,
                "open_after_generate": getattr(cfg.report, "open_after_generate", True),
            },
        )
        json_tail["report"] = report_block
    report_mapping = cast(MutableMapping[str, object], report_block)
    report_path = result.report_path
    report_enabled_output = bool(report_mapping.get("enabled"))
    if report_enabled_output and report_path is not None:
        print(f"[✓] HTML report: {report_path}")
        opened_flag = False
        open_after_generate = bool(
            report_mapping.get("open_after_generate", getattr(cfg.report, "open_after_generate", True))
        )
        if open_after_generate:
            try:
                opened_flag = bool(webbrowser.open(report_path.resolve().as_uri()))
            except Exception:
                print("[yellow]Warning:[/yellow] Unable to open browser for HTML report")
                opened_flag = False
        report_block["path"] = str(report_path)
        report_block["opened"] = opened_flag
        existing_mode = report_mapping.get("mode")
        if isinstance(existing_mode, str) and existing_mode:
            report_block["mode"] = existing_mode
        else:
            report_block["mode"] = getattr(cfg.report, "default_mode", "slider")
    elif report_enabled_output and report_path is None:
        print("[yellow]Warning:[/yellow] HTML report generation failed.")
        report_block["enabled"] = False
        report_block["path"] = None
        report_block["opened"] = False
    else:
        report_block["enabled"] = False
        report_block["path"] = None
        report_block["opened"] = False

    emit_json_tail_flag = True
    if hasattr(cfg, "cli"):
        cli_cfg = cfg.cli
        emit_json_tail_flag = bool(getattr(cli_cfg, "emit_json_tail", True))

    if emit_json_tail_flag:
        if json_pretty:
            json_output = json.dumps(json_tail, indent=2)
        else:
            json_output = json.dumps(json_tail, separators=(",", ":"))
        print(json_output)


@click.group(invoke_without_command=True)
@click.option(
    "--root",
    "root_path",
    default=None,
    help="Workspace root override. Defaults to FRAME_COMPARE_ROOT or sentinel discovery.",
)
@click.option(
    "--config",
    "config_path",
    default=None,
    show_default=False,
    help=_DEFAULT_CONFIG_HELP,
)
@click.option("--input", "input_dir", default=None, help="Override [paths.input_dir] from config.toml")
@click.option(
    "--audio-align-track",
    "audio_align_track_option",
    type=str,
    multiple=True,
    help="Manual audio track override in the form label=index. Repeatable.",
)
@click.option("--quiet", is_flag=True, help="Suppress verbose output; show At-a-Glance, progress, and JSON only.")
@click.option("--verbose", is_flag=True, help="Show additional diagnostic output during run.")
@click.option("--no-color", is_flag=True, help="Disable ANSI colour output.")
@click.option("--json-pretty", is_flag=True, help="Pretty-print the JSON tail output.")
@click.option(
    "--diagnose-paths",
    is_flag=True,
    help="Print the resolved config/input/output paths as JSON and exit.",
)
@click.option(
    "--write-config",
    is_flag=True,
    help="Ensure the workspace config exists (seeds ROOT/config/config.toml when missing) and exit.",
)
@click.option(
    "--no-wizard",
    is_flag=True,
    help="Skip automatic wizard prompts when creating a new config.",
)
@click.option(
    "--html-report",
    "html_report_enable",
    is_flag=True,
    help="Enable HTML report generation regardless of config.",
)
@click.option(
    "--no-html-report",
    "html_report_disable",
    is_flag=True,
    help="Disable HTML report generation regardless of config.",
)
@click.option(
    "--debug-color",
    is_flag=True,
    help="Enable colour pipeline debugging (logs plane stats, dumps intermediate PNGs).",
)
@click.option("--tm-preset", "tm_preset", default=None, help="Override [color].preset for this run.")
@click.option("--tm-curve", "tm_curve", default=None, help="Override [color].tone_curve for this run.")
@click.option("--tm-target", "tm_target", type=float, default=None, help="Override [color].target_nits for this run.")
@click.option("--tm-dst-min", "tm_dst_min", type=float, default=None, help="Override [color].dst_min_nits for this run.")
@click.option("--tm-knee", "tm_knee", type=float, default=None, help="Override [color].knee_offset for this run.")
@click.option(
    "--tm-dpd-preset",
    "tm_dpd_preset",
    type=click.Choice(["off", "fast", "balanced", "high_quality"], case_sensitive=False),
    default=None,
    help="Override [color].dpd_preset.",
)
@click.option(
    "--tm-dpd-black-cutoff",
    "tm_dpd_black_cutoff",
    type=float,
    default=None,
    help="Override [color].dpd_black_cutoff (0.0–0.05) for this run.",
)
@click.option(
    "--tm-gamma",
    "tm_gamma",
    type=float,
    default=None,
    help="Override [color].post_gamma and enable post-tonemap gamma lift for this run.",
)
@click.option(
    "--tm-gamma-disable",
    is_flag=True,
    help="Disable post-tonemap gamma lift for this run regardless of config.",
)
@click.option("--tm-smoothing", "tm_smoothing", type=float, default=None, help="Override [color].smoothing_period.")
@click.option("--tm-scene-low", "tm_scene_low", type=float, default=None, help="Override [color].scene_threshold_low.")
@click.option("--tm-scene-high", "tm_scene_high", type=float, default=None, help="Override [color].scene_threshold_high.")
@click.option("--tm-percentile", "tm_percentile", type=float, default=None, help="Override [color].percentile.")
@click.option("--tm-contrast", "tm_contrast", type=float, default=None, help="Override [color].contrast_recovery.")
@click.option(
    "--tm-metadata",
    "tm_metadata",
    default=None,
    help="Override [color].metadata (auto|none|hdr10|hdr10+|luminance or 0-4).",
)
@click.option(
    "--tm-use-dovi",
    "tm_use_dovi",
    flag_value=True,
    default=None,
    help="Force Dolby Vision metadata usage during tonemapping.",
)
@click.option(
    "--tm-no-dovi",
    "tm_use_dovi",
    flag_value=False,
    help="Disable Dolby Vision metadata usage during tonemapping.",
)
@click.option(
    "--tm-visualize-lut",
    "tm_visualize_lut",
    flag_value=True,
    default=None,
    help="Enable libplacebo tone-mapping LUT visualization for this run.",
)
@click.option(
    "--tm-no-visualize-lut",
    "tm_visualize_lut",
    flag_value=False,
    help="Disable libplacebo tone-mapping LUT visualization for this run.",
)
@click.option(
    "--tm-show-clipping",
    "tm_show_clipping",
    flag_value=True,
    default=None,
    help="Highlight clipped pixels during tonemapping for this run.",
)
@click.option(
    "--tm-no-show-clipping",
    "tm_show_clipping",
    flag_value=False,
    help="Do not highlight clipped pixels during tonemapping for this run.",
)
@click.pass_context
def main(
    ctx: click.Context,
    root_path: str | None,
    config_path: str | None,
    input_dir: str | None,
    *,
    audio_align_track_option: tuple[str, ...],
    quiet: bool,
    verbose: bool,
    no_color: bool,
    json_pretty: bool,
    diagnose_paths: bool,
    write_config: bool,
    no_wizard: bool,
    html_report_enable: bool,
    html_report_disable: bool,
    debug_color: bool,
    tm_preset: str | None,
    tm_curve: str | None,
    tm_target: float | None,
    tm_dst_min: float | None,
    tm_knee: float | None,
    tm_dpd_preset: str | None,
    tm_dpd_black_cutoff: float | None,
    tm_gamma: float | None,
    tm_gamma_disable: bool,
    tm_smoothing: float | None,
    tm_scene_low: float | None,
    tm_scene_high: float | None,
    tm_percentile: float | None,
    tm_contrast: float | None,
    tm_metadata: str | None,
    tm_use_dovi: bool | None,
    tm_visualize_lut: bool | None,
    tm_show_clipping: bool | None,
) -> None:
    """Command group entry point that dispatches to subcommands or the default run."""

    params = {
        "root_path": root_path,
        "config_path": config_path,
        "input_dir": input_dir,
        "audio_align_track_option": audio_align_track_option,
        "quiet": quiet,
        "verbose": verbose,
        "no_color": no_color,
        "json_pretty": json_pretty,
        "diagnose_paths": diagnose_paths,
        "write_config": write_config,
        "skip_wizard": no_wizard,
        "html_report_enable": html_report_enable,
        "html_report_disable": html_report_disable,
        "debug_color": debug_color,
        "tm_preset": tm_preset,
        "tm_curve": tm_curve,
        "tm_target": tm_target,
        "tm_dst_min": tm_dst_min,
        "tm_knee": tm_knee,
        "tm_dpd_preset": tm_dpd_preset,
        "tm_dpd_black_cutoff": tm_dpd_black_cutoff,
        "tm_gamma": tm_gamma,
        "tm_gamma_disable": tm_gamma_disable,
        "tm_smoothing": tm_smoothing,
        "tm_scene_low": tm_scene_low,
        "tm_scene_high": tm_scene_high,
        "tm_percentile": tm_percentile,
        "tm_contrast": tm_contrast,
        "tm_metadata": tm_metadata,
        "tm_use_dovi": tm_use_dovi,
        "tm_visualize_lut": tm_visualize_lut,
        "tm_show_clipping": tm_show_clipping,
    }
    params_map = cast(Dict[str, Any], ctx.ensure_object(dict))
    params_map.update(params)
    ctx.obj = params_map

    if ctx.invoked_subcommand is None:
        _run_cli_entry(**params)


@main.command("run")
@click.pass_context
def run_command(ctx: click.Context) -> None:
    """Explicit subcommand to run the primary pipeline."""

    params = cast(Dict[str, Any], ctx.ensure_object(dict))
    _run_cli_entry(
        root_path=params.get("root_path"),
        config_path=params.get("config_path"),
        input_dir=params.get("input_dir"),
        audio_align_track_option=tuple(params.get("audio_align_track_option", ())),
        quiet=bool(params.get("quiet", False)),
        verbose=bool(params.get("verbose", False)),
        no_color=bool(params.get("no_color", False)),
        json_pretty=bool(params.get("json_pretty", False)),
        diagnose_paths=bool(params.get("diagnose_paths", False)),
        write_config=bool(params.get("write_config", False)),
        skip_wizard=bool(params.get("skip_wizard", False)),
        html_report_enable=bool(params.get("html_report_enable", False)),
        html_report_disable=bool(params.get("html_report_disable", False)),
        debug_color=bool(params.get("debug_color", False)),
        tm_preset=params.get("tm_preset"),
        tm_curve=params.get("tm_curve"),
        tm_target=params.get("tm_target"),
        tm_dst_min=params.get("tm_dst_min"),
        tm_knee=params.get("tm_knee"),
        tm_dpd_preset=params.get("tm_dpd_preset"),
        tm_dpd_black_cutoff=params.get("tm_dpd_black_cutoff"),
        tm_gamma=params.get("tm_gamma"),
        tm_gamma_disable=bool(params.get("tm_gamma_disable", False)),
        tm_smoothing=params.get("tm_smoothing"),
        tm_scene_low=params.get("tm_scene_low"),
        tm_scene_high=params.get("tm_scene_high"),
        tm_percentile=params.get("tm_percentile"),
        tm_contrast=params.get("tm_contrast"),
        tm_metadata=params.get("tm_metadata"),
        tm_use_dovi=params.get("tm_use_dovi"),
        tm_visualize_lut=params.get("tm_visualize_lut"),
        tm_show_clipping=params.get("tm_show_clipping"),
    )


@main.command("doctor")
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable diagnostics.")
@click.pass_context
def doctor(ctx: click.Context, json_mode: bool) -> None:
    """Summarise dependency readiness without altering workspace state."""

    params = cast(Dict[str, Any], ctx.ensure_object(dict))
    root_override = params.get("root_path")
    config_override = params.get("config_path")
    input_override = params.get("input_dir")

    root_issue: Optional[str] = None
    try:
        workspace_root = resolve_workspace_root(root_override)
    except CLIAppError as exc:
        root_issue = str(exc)
        if root_override:
            workspace_root = Path(root_override).expanduser()
        else:
            workspace_root = Path.cwd()

    config_path = Path(config_override).expanduser() if config_override else workspace_root / "config" / "config.toml"

    config_issue: Optional[str] = None
    config_mapping: Mapping[str, Any]
    try:
        cfg_obj = load_config(str(config_path))
        if input_override is not None:
            cfg_obj.paths.input_dir = input_override
        config_mapping = asdict(cfg_obj)
    except FileNotFoundError:
        config_issue = f"Config file not found at {config_path}; using defaults."
        config_mapping = asdict(_fresh_app_config())
        if input_override is not None:
            config_mapping.setdefault("paths", {})["input_dir"] = input_override
    except ConfigError as exc:
        config_issue = f"Config parsing failed: {exc}" if not root_issue else str(exc)
        config_mapping = asdict(_fresh_app_config())
    except Exception as exc:  # pragma: no cover - unexpected I/O failure
        config_issue = f"Unable to load config: {exc}"
        config_mapping = asdict(_fresh_app_config())

    checks, notes = doctor_module.collect_checks(
        workspace_root,
        config_path,
        config_mapping,
        root_issue=root_issue,
        config_issue=config_issue,
    )

    doctor_module.emit_results(
        checks,
        notes,
        json_mode=json_mode,
        workspace_root=workspace_root,
        config_path=config_path,
    )


def _execute_wizard_session(
    *,
    root_override: str | None,
    config_override: str | None,
    input_override: str | None,
    preset_name: str | None,
    auto_launch: bool = False,
) -> tuple[Path, Path]:
    """Shared wizard flow used by both the CLI command and auto-launch path."""

    root, config_path = _wizard.resolve_wizard_paths(root_override, config_override)
    template_text = config_writer.read_template_text()
    template_config = config_writer.load_template_config()
    final_config = copy.deepcopy(template_config)

    if preset_name:
        preset_data = presets_lib.load_preset_data(preset_name)
        config_writer._deep_merge(final_config, preset_data)

    interactive = sys.stdin.isatty()
    if not interactive and not preset_name:
        raise click.ClickException("wizard requires an interactive terminal or --preset.")

    if auto_launch and interactive:
        click.echo("No config found. Launching interactive wizard...")

    if interactive:
        click.echo("Starting interactive wizard. Press Enter to accept defaults.")
        root, final_config = _wizard.run_wizard_prompts(root, final_config)
        if config_override is None:
            config_path = root / "config" / "config.toml"
    else:
        click.echo("Non-interactive mode detected; applying preset configuration.")

    if input_override:
        try:
            resolve_subdir(root, input_override, purpose="[paths].input_dir")
        except CLIAppError as exc:
            raise click.ClickException(str(exc)) from exc
        paths_section = cast(Dict[str, Any], final_config.setdefault("paths", {}))
        paths_section["input_dir"] = input_override

    doctor_checks, doctor_notes = doctor_module.collect_checks(root, config_path, final_config)
    click.echo("\nDependency check:")
    doctor_module.emit_results(
        doctor_checks,
        doctor_notes,
        json_mode=False,
        workspace_root=root,
        config_path=config_path,
    )

    blocking = [check for check in doctor_checks if check["status"] != "pass"]
    if interactive and blocking:
        if not click.confirm("Continue despite missing dependencies?", default=False):
            click.echo("Aborted.")
            raise click.exceptions.Exit(1)

    updated_text = config_writer.render_config_text(template_text, template_config, final_config)
    config_writer._present_diff(template_text, updated_text)

    if interactive:
        if not click.confirm("Write config?", default=True):
            click.echo("Aborted.")
            raise click.exceptions.Exit(1)
    else:
        click.echo("Writing config without confirmation (non-interactive).")

    config_writer.write_config_file(config_path, updated_text)
    click.echo(f"Wrote config to {config_path}")
    return root, config_path


@main.command("wizard")
@click.option("--preset", "preset_name", default=None, help="Apply preset defaults before prompting.")
@click.pass_context
def wizard(ctx: click.Context, preset_name: str | None) -> None:
    """Interactive configuration wizard with optional preset overlays."""

    params = cast(Dict[str, Any], ctx.ensure_object(dict))
    root_override = params.get("root_path")
    config_override = params.get("config_path")
    input_override = params.get("input_dir")

    _execute_wizard_session(
        root_override=root_override,
        config_override=config_override,
        input_override=input_override,
        preset_name=preset_name,
        auto_launch=False,
    )


@main.group()
@click.pass_context
def preset(ctx: click.Context) -> None:
    """Preset management helpers."""

    if ctx.parent is not None:
        ctx.obj = ctx.parent.ensure_object(dict)
    else:
        ctx.obj = ctx.ensure_object(dict)


@preset.command("list")
def preset_list() -> None:
    """List available configuration presets."""

    presets = presets_lib.list_preset_paths()
    if not presets:
        click.echo("No presets available.")
        return
    for name in sorted(presets):
        description = presets_lib.PRESET_DESCRIPTIONS.get(name, "")
        if description:
            click.echo(f"{name}: {description}")
        else:
            click.echo(name)


@preset.command("apply")
@click.argument("name")
@click.pass_context
def preset_apply(ctx: click.Context, name: str) -> None:
    """Apply a preset without running the full wizard."""

    params = cast(Dict[str, Any], ctx.ensure_object(dict))
    root_override = params.get("root_path")
    config_override = params.get("config_path")
    input_override = params.get("input_dir")

    root, config_path = _wizard.resolve_wizard_paths(root_override, config_override)
    template_text = config_writer.read_template_text()
    template_config = config_writer.load_template_config()
    final_config = copy.deepcopy(template_config)

    preset_data = presets_lib.load_preset_data(name)
    config_writer._deep_merge(final_config, preset_data)

    if input_override:
        try:
            resolve_subdir(root, input_override, purpose="[paths].input_dir")
        except CLIAppError as exc:
            raise click.ClickException(str(exc)) from exc
        final_config.setdefault("paths", {})["input_dir"] = input_override

    updated_text = config_writer.render_config_text(template_text, template_config, final_config)
    config_writer._present_diff(template_text, updated_text)

    if sys.stdin.isatty():
        if not click.confirm("Write config?", default=True):
            click.echo("Aborted.")
            return
    else:
        click.echo("Writing config without confirmation (non-interactive).")

    config_writer.write_config_file(config_path, updated_text)
    click.echo(f"Wrote config to {config_path}")


if __name__ == "__main__":
    _entry_point = cast(Callable[[], None], main)
    _entry_point()
