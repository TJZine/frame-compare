"""Focused regression tests for alignment_runner helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import frame_compare as _frame_compare  # noqa: F401  # Ensure CLI shim initialises alignment_runner.
from src.audio_alignment import AlignmentMeasurement, AudioStreamInfo
from src.frame_compare import alignment_runner as alignment_runner_module
from src.frame_compare.cli_runtime import _ClipPlan
from tests.helpers.runner_env import _make_config, _RecordingOutputManager


def test_apply_audio_alignment_derives_frames_from_seconds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seconds-only measurements should still populate suggested frames using clip FPS."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.use_vspreview = False

    reference = _ClipPlan(path=tmp_path / "Ref.mkv", metadata={"label": "Reference"})
    target = _ClipPlan(path=tmp_path / "Target.mkv", metadata={"label": "Target"})
    for plan in (reference, target):
        plan.path.parent.mkdir(parents=True, exist_ok=True)
        plan.path.write_bytes(b"\x00")
        plan.effective_fps = (24000, 1001)

    plans = [reference, target]
    analyze_path = reference.path
    reporter = _RecordingOutputManager()

    def _fake_probe(_path: Path) -> list[AudioStreamInfo]:
        return [
            AudioStreamInfo(
                index=0,
                language="eng",
                codec_name="aac",
                channels=2,
                channel_layout="stereo",
                sample_rate=48000,
                bitrate=128000,
                is_default=True,
                is_forced=False,
            )
        ]

    monkeypatch.setattr(alignment_runner_module.audio_alignment, "probe_audio_streams", _fake_probe)

    offset_seconds = 47.78
    measurement = AlignmentMeasurement(
        file=target.path,
        offset_seconds=offset_seconds,
        frames=None,
        correlation=0.95,
        reference_fps=None,
        target_fps=None,
    )

    monkeypatch.setattr(
        alignment_runner_module.audio_alignment,
        "measure_offsets",
        lambda *args, **kwargs: [measurement],
    )

    def _fake_update(
        _path: Path,
        reference_name: str,
        measurements: Any,
        existing: Any = None,
        negative_override_notes: Any = None,
    ) -> tuple[dict[str, int], dict[str, str]]:
        applied = {}
        statuses = {}
        for item in measurements:
            if item.frames is not None:
                applied[item.file.name] = int(item.frames)
            statuses[item.file.name] = "auto"
        return applied, statuses

    monkeypatch.setattr(alignment_runner_module.audio_alignment, "update_offsets_file", _fake_update)

    summary, display = alignment_runner_module.apply_audio_alignment(
        plans,
        cfg,
        analyze_path,
        tmp_path,
        audio_track_overrides={},
        reporter=reporter,
    )

    fps_float = alignment_runner_module._fps_to_float(target.effective_fps)
    assert fps_float > 0
    expected_frames = int(round(offset_seconds * fps_float))
    assert summary is not None
    assert display is not None
    assert summary.suggested_frames[target.path.name] == expected_frames
    assert any(f"{expected_frames:+d}f" in line for line in display.offset_lines)
