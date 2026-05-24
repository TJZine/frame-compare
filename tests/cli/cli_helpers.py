# pyright: reportUnusedFunction=false

import re
from pathlib import Path

from click.testing import Result
from typer.testing import CliRunner

from frame_compare.cli.entry import app

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(text: str) -> str:
    """Normalize styled CLI output for stable assertions across platforms."""
    return ANSI_ESCAPE_RE.sub("", text)


MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
"""


def _write_minimal_config(root: Path) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return config_path


def _invoke_run_with_minimal_workspace(
    args: list[str],
    *,
    color: bool = False,
    terminal_width: int | None = None,
    env: dict[str, str] | None = None,
) -> Result:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        return runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root)), *args],
            color=color,
            terminal_width=terminal_width,
            env=env,
        )
