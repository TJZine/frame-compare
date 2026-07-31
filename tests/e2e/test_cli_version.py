"""E2E tests for CLI version command."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from frame_compare import __version__
from frame_compare.cli.entry import app


@pytest.mark.e2e
def test_cli_version_command_exits_zero() -> None:
    """GIVEN the CLI app WHEN 'version' is invoked THEN exit code is 0."""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


@pytest.mark.e2e
def test_cli_version_command_outputs_version_string() -> None:
    """GIVEN the CLI app WHEN 'version' is invoked THEN output matches package version."""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    # Typer's echo adds a newline; strip for comparison
    assert result.output.strip() == f"frame-compare {__version__}"


@pytest.mark.e2e
def test_cli_no_args_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output
