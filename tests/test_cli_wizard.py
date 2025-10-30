from __future__ import annotations

import sys
import tomllib
from io import TextIOBase
from pathlib import Path
from typing import Any, TextIO

from click.testing import CliRunner

import frame_compare


class _SysProxy:
    """Proxy sys module to force stdin.isatty() during CLI tests."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.stdin: TextIOBase = _StdinWrapper(inner.stdin, is_tty=True)  # type: ignore[reportUnknownMemberType]

    def __getattr__(self, name):  # pragma: no cover - passthrough
        return getattr(self._inner, name)


class _StdinWrapper(TextIOBase):
    def __init__(self, stream: TextIO, *, is_tty: bool) -> None:
        self._stream = stream
        self._is_tty = is_tty

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._stream, attr)

    def isatty(self) -> bool:
        return self._is_tty


class _NonTtySysProxy:
    """Proxy sys module that always reports stdin as non-interactive."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.stdin: TextIOBase = _StdinWrapper(inner.stdin, is_tty=False)  # type: ignore[reportUnknownMemberType]

    def __getattr__(self, name):  # pragma: no cover - passthrough
        return getattr(self._inner, name)


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


def test_auto_wizard_runs_during_write_config(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(frame_compare, "sys", _SysProxy(sys), raising=False)  # type: ignore[attr-defined]

    calls: dict[str, Any] = {}

    def fake_prompts(root: Path, config: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        calls["invoked"] = True
        config.setdefault("paths", {})["input_dir"] = "custom-dir"
        return root, config

    monkeypatch.setattr(frame_compare, "_run_wizard_prompts", fake_prompts)  # type: ignore[reportUnknownMemberType]

    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "--write-config"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert calls.get("invoked") is True
    config_path = tmp_path / "config" / "config.toml"
    assert config_path.exists()
    data = tomllib.loads(config_path.read_text(encoding="utf-8").lstrip("\ufeff"))
    assert data["paths"]["input_dir"] == "custom-dir"


def test_auto_wizard_skipped_when_not_tty(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(frame_compare, "sys", _NonTtySysProxy(sys), raising=False)  # type: ignore[attr-defined]

    def fail_prompts(*args, **kwargs):
        raise AssertionError("wizard should not run when stdin is not a TTY")

    monkeypatch.setattr(frame_compare, "_run_wizard_prompts", fail_prompts)  # type: ignore[reportUnknownMemberType]

    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "--write-config"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    config_path = tmp_path / "config" / "config.toml"
    assert config_path.exists()
    assert "frame-compare wizard" in result.output


def test_auto_wizard_skipped_with_no_wizard_flag(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(frame_compare, "sys", _SysProxy(sys), raising=False)  # type: ignore[attr-defined]

    def fail_prompts(*args, **kwargs):
        raise AssertionError("wizard should be skipped when --no-wizard is supplied")

    monkeypatch.setattr(frame_compare, "_run_wizard_prompts", fail_prompts)  # type: ignore[reportUnknownMemberType]

    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "--write-config", "--no-wizard"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    config_path = tmp_path / "config" / "config.toml"
    assert config_path.exists()
    assert "frame-compare wizard" in result.output
