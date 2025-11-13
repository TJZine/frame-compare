from __future__ import annotations

from click.testing import CliRunner

import frame_compare

STABLE_FLAGS = (
    "--root",
    "--config",
    "--input",
    "--diagnose-paths",
    "--write-config",
    "--html-report",
    "--no-html-report",
    "--tm-preset",
)


def test_help_lists_stable_flags() -> None:
    runner = CliRunner()
    result = runner.invoke(frame_compare.main, ["--help"])
    assert result.exit_code == 0, result.output
    for flag in STABLE_FLAGS:
        assert flag in result.output
