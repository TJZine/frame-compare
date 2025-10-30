from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

import frame_compare


def _patch_find_spec(monkeypatch: pytest.MonkeyPatch, missing: set[str]) -> None:
    original = frame_compare.importlib.util.find_spec

    def fake(name: str, *args: Any, **kwargs: Any):
        if name in missing:
            return None
        return original(name, *args, **kwargs)

    monkeypatch.setattr(frame_compare.importlib.util, "find_spec", fake)


def _patch_which(monkeypatch: pytest.MonkeyPatch, missing: set[str]) -> None:
    original = frame_compare.shutil.which

    def fake(cmd: str, *args: Any, **kwargs: Any):
        if cmd in missing:
            return None
        return original(cmd, *args, **kwargs)

    monkeypatch.setattr(frame_compare.shutil, "which", fake)


def test_doctor_json_outputs_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(
        """
[screenshots]
use_ffmpeg = false

[audio_alignment]
enable = true
use_vspreview = true

[slowpics]
auto_upload = true
""",
        encoding="utf-8",
    )

    _patch_find_spec(
        monkeypatch,
        {"vapoursynth", "librosa", "soundfile", "vspreview", "PySide6", "pyperclip"},
    )
    _patch_which(monkeypatch, {"ffmpeg", "ffprobe", "vspreview"})

    runner = CliRunner()
    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "doctor", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    payload = json.loads(result.output)
    statuses = {check["id"]: check["status"] for check in payload["checks"]}
    assert statuses["vapoursynth"] == "fail"
    assert statuses["ffmpeg"] == "fail"
    assert statuses["audio"] == "fail"
    assert statuses["vspreview"] == "fail"
    assert statuses["slowpics"] == "warn"
    assert statuses["pyperclip"] == "warn"


def test_doctor_text_output_with_all_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(
        """
[screenshots]
use_ffmpeg = true

[audio_alignment]
enable = false
use_vspreview = false

[slowpics]
auto_upload = false
""",
        encoding="utf-8",
    )

    _patch_find_spec(monkeypatch, set())

    def fake_which(cmd: str) -> str:
        return f"/usr/bin/{cmd}"

    monkeypatch.setattr(frame_compare.shutil, "which", fake_which)

    runner = CliRunner()
    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "doctor"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "❌" not in result.output
    assert "✅ Config path writable" in result.output
