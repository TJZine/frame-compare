# pyright: reportUnusedFunction=false

import contextlib
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from frame_compare.cli.entry import app

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
RICH_BOX_DRAWING_RE = re.compile(r"[\u2500-\u257f]")


@contextlib.contextmanager
def isolated_cli_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Run one CLI test block in a pytest-owned temporary working directory."""
    index = 0
    while True:
        working_directory = tmp_path / f"cli-cwd-{index}"
        try:
            working_directory.mkdir()
        except FileExistsError:
            index += 1
            continue
        break

    with monkeypatch.context() as scoped_monkeypatch:
        scoped_monkeypatch.chdir(working_directory)
        yield working_directory


def _normalize_cli_output(text: str) -> str:
    """Normalize styled CLI output for stable assertions across platforms."""
    return ANSI_ESCAPE_RE.sub("", text)


def _normalize_cli_help(text: str) -> str:
    """Normalize Rich help into width-independent semantic text."""
    output = _normalize_cli_output(text)
    return " ".join(RICH_BOX_DRAWING_RE.sub(" ", output).split())


MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    color: bool = False,
    terminal_width: int | None = None,
    env: dict[str, str] | None = None,
) -> Result:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        return runner.invoke(
            app,
            ["run", "--root", str(root), "--config", str(config_path.relative_to(root)), *args],
            color=color,
            terminal_width=terminal_width,
            env=env,
        )
