"""Typer CLI entrypoint (Phase 0 scaffold).

This file is intentionally minimal: it exists so packaging, import-linter, and
`frame-compare --help` work immediately after copying the scaffold.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="frame-compare",
    help="Video frame comparison and HDR tonemapping tool",
    no_args_is_help=True,
)


@app.command()
def run() -> None:
    """Execute the comparison pipeline (implemented in later phases)."""
    raise typer.Exit(code=0)
