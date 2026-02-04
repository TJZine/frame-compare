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
from frame_compare.config import ConfigSchema, Visibility, get_default_config
from frame_compare.errors import ExitCode, FrameCompareError, JSONValue, get_exit_code
from frame_compare.orchestration import DoctorReport, run_doctor
from frame_compare.orchestration.coordinator import RunRequest

app = typer.Typer(
    name="frame-compare",
    help="Video frame comparison tool with tonemapping and slow.pics integration.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Video frame comparison tool."""


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
    request = RunRequest(
        root=root,
        config_path=config,
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

    try:
        result = runner.run(request, dependencies=None)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error)) from error
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None

    if not result.success:
        raise typer.Exit(code=5)


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
def preset_list() -> None:
    typer.echo("[stub] preset list: Not yet implemented")


@preset_app.command("apply")
def preset_apply(name: str) -> None:
    typer.echo("[stub] preset apply: Not yet implemented")


@preset_app.command("save")
def preset_save(name: str) -> None:
    typer.echo("[stub] preset save: Not yet implemented")


def handle_error(error: FrameCompareError) -> int:
    console = Console(stderr=True)
    console.print(f"[red]Error[/red] [{error.code}]: {error.context.message}")
    if error.hint:
        console.print(f"[yellow]Hint:[/yellow] {error.hint}")
    return int(get_exit_code(error))


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


def _prepare_toml_payload(data: dict[str, object]) -> dict[str, object]:
    """Prepare TOML-safe payload (TOML has no null)."""
    tmdb_section_raw = data.get("tmdb")
    tmdb_section: dict[str, object] = {}
    if isinstance(tmdb_section_raw, dict):
        tmdb_section = cast(dict[str, object], tmdb_section_raw)
    api_key = tmdb_section.get("api_key")
    if api_key is None:
        tmdb_section["api_key"] = ""
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
