"""CLI entry point for frame-compare."""

# ruff: noqa: B008
from pathlib import Path

import typer
from rich.console import Console

from frame_compare import runner
from frame_compare.errors import FrameCompareError, get_exit_code
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
    typer.echo("[stub] wizard: Not yet implemented")


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    if json_output:
        typer.echo('{"status": "stub", "checks": []}')
    else:
        typer.echo("[stub] doctor: Not yet implemented")


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


if __name__ == "__main__":
    app()
