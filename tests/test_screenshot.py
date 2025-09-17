from pathlib import Path

import pytest

from src.datatypes import ScreenshotConfig
from src import screenshot


class FakeClip:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height


def test_plan_mod_crop_modulus():
    left, top, right, bottom = screenshot.plan_mod_crop(1919, 1079, mod=4, letterbox_pillarbox_aware=True)
    new_w = 1919 - left - right
    new_h = 1079 - top - bottom
    assert new_w % 4 == 0
    assert new_h % 4 == 0
    assert new_w > 0 and new_h > 0


def test_generate_screenshots_filenames(tmp_path, monkeypatch):
    clip = FakeClip(1280, 720)
    cfg = ScreenshotConfig(directory_name="screens")

    calls = []

    def fake_writer(clip, frame_idx, crop, scaled, path, cfg):
        calls.append({"frame": frame_idx, "crop": crop, "scaled": scaled})
        path.write_text("data", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_vapoursynth", fake_writer)

    frames = [5, 25]
    files = ["example_video.mkv"]
    metadata = [{"label": "Example Release"}]
    created = screenshot.generate_screenshots([clip], frames, files, metadata, tmp_path, cfg)
    assert len(created) == len(frames)
    for path in created:
        assert Path(path).exists()
        assert Path(path).name.startswith("Example Release")

    assert len(calls) == len(frames)


def test_compression_flag_passed(tmp_path, monkeypatch):
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True, compression_level=2)

    captured = {}

    def fake_writer(
        source,
        frame_idx,
        crop,
        scaled,
        path,
        cfg,
        width,
        height,
        *,
        trim_start=0,
        trim_end=None,
    ):
        captured[frame_idx] = screenshot._map_ffmpeg_compression(cfg.compression_level)
        path.write_text("ffmpeg", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_writer)

    screenshot.generate_screenshots([clip], [10], ["video.mkv"], [{"label": "video"}], tmp_path, cfg)
    assert captured[10] == 9


def test_generate_screenshots_passes_trim_offsets(tmp_path, monkeypatch):
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True)

    observed = []

    def fake_writer(
        source,
        frame_idx,
        crop,
        scaled,
        path,
        cfg,
        width,
        height,
        *,
        trim_start=0,
        trim_end=None,
    ):
        observed.append((trim_start, trim_end))
        path.write_text("ffmpeg", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_writer)

    trims = [(5, 42)]
    screenshot.generate_screenshots(
        [clip],
        [0, 1],
        ["video.mkv"],
        [{"label": "video"}],
        tmp_path,
        cfg,
        trims=trims,
    )

    assert observed == [(5, 42), (5, 42)]


def test_save_frame_with_ffmpeg_applies_trim_offset(monkeypatch, tmp_path):
    cfg = ScreenshotConfig(add_frame_info=False)

    monkeypatch.setattr(screenshot.shutil, "which", lambda _: "/usr/bin/ffmpeg")

    captured = {}

    class _Result:
        returncode = 0
        stderr = b""

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(screenshot.subprocess, "run", fake_run)

    output = tmp_path / "frame.png"
    screenshot._save_frame_with_ffmpeg(
        "source.mkv",
        frame_idx=3,
        crop=(0, 0, 0, 0),
        scaled=(1920, 1080),
        path=output,
        cfg=cfg,
        width=1920,
        height=1080,
        trim_start=5,
    )

    filters = captured["cmd"][captured["cmd"].index("-vf") + 1]
    assert "select=eq(n\\,8)" in filters


def test_save_frame_with_ffmpeg_enforces_trim_end(monkeypatch, tmp_path):
    cfg = ScreenshotConfig(add_frame_info=False)

    monkeypatch.setattr(screenshot.shutil, "which", lambda _: "/usr/bin/ffmpeg")

    with pytest.raises(screenshot.ScreenshotWriterError):
        screenshot._save_frame_with_ffmpeg(
            "source.mkv",
            frame_idx=5,
            crop=(0, 0, 0, 0),
            scaled=(1920, 1080),
            path=tmp_path / "frame.png",
            cfg=cfg,
            width=1920,
            height=1080,
            trim_start=2,
            trim_end=5,
        )
