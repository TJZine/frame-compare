"""CLI entry point for frame-compare."""

# ruff: noqa: B008
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import tomli_w
import typer
from rich.console import Console

from frame_compare import runner
from frame_compare.config import (
    ConfigSchema,
    Visibility,
    apply_cli_overrides,
    apply_preset,
    get_default_config,
    list_presets,
    load_config,
    save_preset,
)
from frame_compare.errors import (
    ExitCode,
    FrameCompareError,
    JSONValue,
    format_error_console,
    format_error_json,
    get_exit_code,
)
from frame_compare.orchestration import DoctorReport, run_doctor
from frame_compare.orchestration.coordinator import RunRequest
from frame_compare.orchestration.preflight import resolve_paths
from frame_compare.utils.logging import configure_logging

app = typer.Typer(
    name="frame-compare",
    help="Video frame comparison tool with tonemapping and slow.pics integration.",
    no_args_is_help=False,
)


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
    root: Path = typer.Option(".", "--root", "-r"),
    config: Path | None = typer.Option(None, "--config", "-c"),
    input_dir: Path | None = typer.Option(None, "--input", "-i"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    from_cache_only: bool = typer.Option(False, "--from-cache-only"),
    no_upload: bool = typer.Option(False, "--no-upload"),
    tm_preset: str | None = typer.Option(None, "--tm-preset"),
    tm_target: int | None = typer.Option(None, "--tm-target"),
    tm_curve: str | None = typer.Option(None, "--tm-curve"),
    frame_count: int | None = typer.Option(None, "--frame-count", "-n"),
    seed: int | None = typer.Option(None, "--seed"),
    overlay: str | None = typer.Option(None, "--overlay"),
    skip_analysis: bool = typer.Option(False, "--skip-analysis"),
    skip_metadata: bool = typer.Option(False, "--skip-metadata"),
    skip_dovi: bool = typer.Option(False, "--skip-dovi"),
    force_interactive_alignment: bool = typer.Option(False, "--force-interactive-alignment"),
    json_output: bool = typer.Option(False, "--json"),
    no_color: bool = typer.Option(False, "--no-color"),
    write_config: bool = typer.Option(False, "--write-config"),
    diagnose_paths: bool = typer.Option(False, "--diagnose-paths"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    resolved_root, config_path = _resolve_root_and_config(root, config)
    log_level = "WARNING" if quiet else ("DEBUG" if verbose else "INFO")
    log_format = "json" if json_output else "console"
    configure_logging(level=log_level, format=log_format)

    cli_args: dict[str, object] = {
        "tm_preset": tm_preset,
        "tm_target": tm_target,
        "tm_curve": tm_curve,
        "frame_count": frame_count,
        "seed": seed,
        "overlay": overlay,
        "no_upload": no_upload,
        "force_interactive_alignment": force_interactive_alignment,
        "input": str(input_dir) if input_dir is not None else None,
    }

    try:
        if write_config:
            config_data = load_config(config_path)
            config_override = apply_cli_overrides(config_data, cli_args=cli_args)
            _write_config_to(config_path, config_override)
            return

        if diagnose_paths:
            config_data = load_config(config_path)
            config_override = apply_cli_overrides(config_data, cli_args=cli_args)
            workspace = resolve_paths(config_override, resolved_root)
            payload = {
                "root": str(resolved_root),
                "config": str(config_path),
                "input": str(workspace.input_dir),
                "output": str(workspace.screenshots_dir),
                "cache": str(workspace.generated_dir),
            }
            typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            return

        request = RunRequest(
            root=resolved_root,
            config_path=config_path,
            input_dir=input_dir,
            no_cache=no_cache,
            from_cache_only=from_cache_only,
            no_upload=no_upload,
            tm_preset=tm_preset,
            tm_target_nits=tm_target,
            tm_curve=tm_curve,
            frame_count=frame_count,
            seed=seed,
            overlay_mode=overlay,
            skip_analysis=skip_analysis,
            skip_metadata=skip_metadata,
            skip_dovi=skip_dovi,
            force_interactive_alignment=force_interactive_alignment,
            json_output=json_output,
            no_color=no_color,
            quiet=quiet,
            verbose=verbose,
        )

        result = runner.run(request, dependencies=None)
    except FrameCompareError as error:
        if json_output:
            typer.echo(json.dumps(format_error_json(error), sort_keys=True, separators=(",", ":")))
            raise typer.Exit(code=int(get_exit_code(error))) from error
        raise typer.Exit(code=handle_error(error, no_color=no_color, verbose=verbose)) from error
    except KeyboardInterrupt:
        raise typer.Exit(code=int(ExitCode.INTERRUPTED)) from None

    if json_output:
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


@app.command()
def wizard() -> None:
    """Interactive configuration wizard."""
    defaults = get_default_config()

    try:
        input_dir = _prompt_input_dir(defaults.paths.input_dir)
        auto_upload = typer.confirm(
            "Enable slow.pics auto-upload?",
            default=defaults.slowpics.auto_upload,
        )
        visibility = _prompt_visibility(defaults.slowpics.visibility)
        delete_after_upload = typer.confirm(
            "Delete after upload?",
            default=defaults.slowpics.delete_after_upload,
        )
        tmdb_api_key = typer.prompt(
            "TMDB API key (optional)",
            default="",
            hide_input=True,
        ).strip()
    except (KeyboardInterrupt, typer.Abort):
        raise typer.Exit(code=int(ExitCode.INTERRUPTED)) from None

    tmdb_value: str | None = tmdb_api_key if tmdb_api_key else None
    config_data = _build_minimal_config(
        input_dir=input_dir,
        auto_upload=auto_upload,
        visibility=visibility,
        delete_after_upload=delete_after_upload,
        tmdb_api_key=tmdb_value,
    )
    _validate_config(config_data)
    _write_config(config_data)


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    """Run dependency diagnostics."""
    report = run_doctor(checks=None, reporter=None)
    if json_output:
        payload = _doctor_report_json(report)
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        _print_doctor_report(report)

    if report.critical_failures:
        raise typer.Exit(code=int(ExitCode.DEPENDENCY_ERROR))


preset_app = typer.Typer(name="preset", help="Manage configuration presets.", no_args_is_help=True)
app.add_typer(preset_app, name="preset")


@preset_app.command("list")
def preset_list(
    root: Path = typer.Option(".", "--root", "-r"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    try:
        resolved_root, _ = _resolve_root_and_config(root, config)
        presets_dir = resolved_root / "config" / "presets"
        for name in list_presets(presets_dir=presets_dir):
            typer.echo(name)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error, no_color=True, verbose=False)) from error


@preset_app.command("apply")
def preset_apply(
    name: str,
    root: Path = typer.Option(".", "--root", "-r"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    try:
        resolved_root, config_path = _resolve_root_and_config(root, config)
        presets_dir = resolved_root / "config" / "presets"
        config_data = load_config(config_path)
        updated = apply_preset(config_data, name, presets_dir=presets_dir)
        _write_config_to(config_path, updated)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error, no_color=True, verbose=False)) from error


@preset_app.command("save")
def preset_save(
    name: str,
    root: Path = typer.Option(".", "--root", "-r"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    try:
        resolved_root, config_path = _resolve_root_and_config(root, config)
        presets_dir = resolved_root / "config" / "presets"
        config_data = load_config(config_path)
        save_preset(name, config_data, presets_dir=presets_dir)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error, no_color=True, verbose=False)) from error


def handle_error(error: Exception, *, no_color: bool, verbose: bool) -> int:
    """Render errors to stderr and return exit code.

    Raises:
        None.
    """
    if isinstance(error, FrameCompareError):
        message = format_error_console(error, verbose=verbose)
        if no_color:
            typer.echo(message, err=True)
        else:
            console = Console(stderr=True)
            console.print(message)
        return int(get_exit_code(error))
    typer.echo("Unexpected error: please report this bug.", err=True)
    return int(ExitCode.GENERAL_ERROR)


def _prompt_input_dir(default: str) -> str:
    """Prompt for input directory and validate existence."""
    while True:
        value = typer.prompt("Input directory", default=default)
        path = Path(value)
        if not path.is_absolute():
            path = Path(".") / path
        if path.exists() and path.is_dir():
            return value
        typer.echo("Input directory does not exist or is not a directory.")


def _prompt_visibility(default: Visibility) -> str:
    """Prompt for slow.pics visibility."""
    allowed = {v.value for v in Visibility}
    default_value = default.value
    while True:
        value = typer.prompt(
            "slow.pics visibility (public|unlisted|private)",
            default=default_value,
        ).strip()
        if value in allowed:
            return value
        typer.echo("Invalid visibility. Choose public, unlisted, or private.")


def _build_minimal_config(
    *,
    input_dir: str,
    auto_upload: bool,
    visibility: str,
    delete_after_upload: bool,
    tmdb_api_key: str | None,
) -> dict[str, object]:
    """Build minimal config payload for wizard output."""
    return {
        "paths": {"input_dir": input_dir},
        "slowpics": {
            "auto_upload": auto_upload,
            "visibility": visibility,
            "delete_after_upload": delete_after_upload,
        },
        "tmdb": {"api_key": tmdb_api_key},
    }


def _validate_config(data: dict[str, object]) -> None:
    """Validate config data against ConfigSchema."""
    ConfigSchema.model_validate(data)


def _write_config(data: dict[str, object]) -> None:
    """Write config/config.toml with minimal sections."""
    config_dir = Path("config")
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    toml_text = tomli_w.dumps(_prepare_toml_payload(data))
    config_path.write_text(toml_text, encoding="utf-8")


def _doctor_report_json(report: DoctorReport) -> dict[str, JSONValue]:
    """Convert DoctorReport to JSON payload per schema."""
    checks_payload: list[JSONValue] = []
    for check, result in report.checks:
        entry: dict[str, JSONValue] = {
            "id": check.name,
            "category": check.category,
            "status": "pass" if result.passed else "fail",
            "message": result.message,
        }
        if result.hint:
            entry["install_hint"] = result.hint
        if result.details:
            entry["details"] = result.details
        checks_payload.append(entry)

    doctor_payload: dict[str, JSONValue] = {
        "baseline_version": "R73",
        "checks": checks_payload,
    }
    payload: dict[str, JSONValue] = {
        "success": len(report.critical_failures) == 0,
        "doctor": doctor_payload,
    }
    return payload


def _resolve_root_and_config(root: Path, config: Path | None) -> tuple[Path, Path]:
    resolved_root = Path(root).resolve()
    if config is not None:
        config_path = Path(config)
        if not config_path.is_absolute():
            config_path = (resolved_root / config_path).resolve()
        else:
            config_path = config_path.resolve()
    else:
        config_path = (resolved_root / "config" / "config.toml").resolve()
    return resolved_root, config_path


def _write_config_to(path: Path, config: ConfigSchema) -> None:
    data = config.model_dump(mode="json", exclude_none=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    toml_text = tomli_w.dumps(data)
    path.write_text(toml_text, encoding="utf-8")


def _prepare_toml_payload(data: dict[str, object]) -> dict[str, object]:
    """Prepare TOML-safe payload (TOML has no null)."""
    tmdb_section_raw = data.get("tmdb")
    tmdb_section: dict[str, object] = {}
    if isinstance(tmdb_section_raw, dict):
        tmdb_section = cast(dict[str, object], tmdb_section_raw)
    api_key = tmdb_section.get("api_key")
    if api_key is None or api_key == "":
        tmdb_section.pop("api_key", None)
    paths_section: dict[str, object] = {}
    slowpics_section: dict[str, object] = {}
    paths_raw = data.get("paths")
    slowpics_raw = data.get("slowpics")
    if isinstance(paths_raw, dict):
        paths_section = cast(dict[str, object], paths_raw)
    if isinstance(slowpics_raw, dict):
        slowpics_section = cast(dict[str, object], slowpics_raw)
    return {
        "paths": paths_section,
        "slowpics": slowpics_section,
        "tmdb": tmdb_section,
    }


def _print_doctor_report(report: DoctorReport) -> None:
    """Print human-readable doctor results."""
    for check, result in report.checks:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {check.name}: {result.message}")
        if result.hint:
            typer.echo(f"  Hint: {result.hint}")


if __name__ == "__main__":
    app()
