"""CLI entry point for frame-compare."""

import typer

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


if __name__ == "__main__":
    app()
