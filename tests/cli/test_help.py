from __future__ import annotations

from click.testing import CliRunner

import frame_compare


def test_cli_help_lists_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(frame_compare.main, ["--help"], catch_exceptions=False)
    assert result.exit_code == 0
    output = result.output
    assert "wizard" in output
    assert "preset" in output
    assert "doctor" in output
    assert "--html-report" in output
    assert "--no-html-report" in output
