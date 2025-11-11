from __future__ import annotations

import importlib.util as importlib_util
import json
from pathlib import Path

from click.testing import CliRunner

import frame_compare
import pytest


def test_doctor_json_outputs_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    vspreview_env,
    which_map,
) -> None:
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

    vspreview_env(False)
    which_map({"ffmpeg", "ffprobe", "vspreview"})

    original_find_spec = importlib_util.find_spec

    def _patch_audio_deps(name: str, package: str | None = None):
        if name in {"librosa", "pyperclip", "soundfile"}:
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib_util, "find_spec", _patch_audio_deps)

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


def test_doctor_text_output_with_all_dependencies(
    tmp_path: Path,
    vspreview_env,
    which_map,
) -> None:
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

    vspreview_env(True)
    which_map(set())

    runner = CliRunner()
    result = runner.invoke(
        frame_compare.main,
        ["--root", str(tmp_path), "doctor"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "❌" not in result.output
    assert "✅ Config path writable" in result.output
