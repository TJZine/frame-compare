from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from io import TextIOBase
from typing import Any, TextIO

from click.testing import CliRunner

import frame_compare


class _SysProxy:
    """Proxy sys module to force stdin.isatty() during CLI tests."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.stdin: TextIOBase = _StdinWrapper(inner.stdin)  # type: ignore[reportUnknownMemberType]

    def __getattr__(self, name):  # pragma: no cover - passthrough
        return getattr(self._inner, name)


class _StdinWrapper(TextIOBase):
    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._stream, attr)

    def isatty(self) -> bool:
        return True


def test_preset_list_outputs_known_names() -> None:
    runner = CliRunner()
    result = runner.invoke(frame_compare.main, ["preset", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "quick-compare" in result.output
    assert "hdr-vs-sdr" in result.output


def test_preset_apply_creates_config(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "preset", "apply", "quick-compare"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    config_path = tmp_path / "config" / "config.toml"
    assert config_path.exists()
    data = tomllib.loads(config_path.read_text(encoding="utf-8").lstrip("\ufeff"))
    assert data["screenshots"]["use_ffmpeg"] is True
    assert data["slowpics"]["auto_upload"] is False


def test_wizard_requires_preset_when_not_tty(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(frame_compare.main, ["--root", str(tmp_path), "wizard"])
    assert result.exit_code != 0
    assert "requires an interactive terminal" in result.output


def test_wizard_interactive_prompts(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(frame_compare, "sys", _SysProxy(sys), raising=False)  # type: ignore[attr-defined]

    input_sequence = "\n"  # workspace root
    input_sequence += "\n"  # input directory
    input_sequence += "\n"  # auto upload (default false)
    input_sequence += "\n"  # tmdb prompt (default false)
    input_sequence += "\n"  # cleanup prompt (default true)
    input_sequence += "y\n"  # enable audio alignment
    input_sequence += "ffmpeg\n"  # renderer choice
    input_sequence += "y\n"  # continue despite doctor warnings
    input_sequence += "y\n"  # write config confirmation

    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "wizard"],
        input=input_sequence,
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "Dependency check:" in result.output
    config_path = tmp_path / "config" / "config.toml"
    data = tomllib.loads(config_path.read_text(encoding="utf-8").lstrip("\ufeff"))
    assert data["audio_alignment"]["enable"] is True
    assert data["screenshots"]["use_ffmpeg"] is True
