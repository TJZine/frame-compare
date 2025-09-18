from pathlib import Path

import pytest

from src.datatypes import ScreenshotConfig
from src import screenshot


class FakeClip:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height


def test_sanitise_label_replaces_forbidden_characters(monkeypatch):
    monkeypatch.setattr(screenshot.os, "name", "nt")
    raw = 'Group: Episode? 01*<>"| '
    cleaned = screenshot._sanitise_label(raw)
    assert cleaned
    for forbidden in ':?*<>"|':
        assert forbidden not in cleaned
    assert not cleaned.endswith((" ", "."))


def test_sanitise_label_falls_back_when_blank():
    cleaned = screenshot._sanitise_label("   ")
    assert cleaned == "comparison"


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

    def fake_writer(clip, frame_idx, crop, scaled, path, cfg, label, requested_frame, selection_label=None):
        calls.append({"frame": frame_idx, "crop": crop, "scaled": scaled, "label": label, "requested": requested_frame})
        path.write_text("data", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_writer)

    frames = [5, 25]
    files = ["example_video.mkv"]
    metadata = [{"label": "Example Release"}]
    created = screenshot.generate_screenshots(
        [clip],
        frames,
        files,
        metadata,
        tmp_path,
        cfg,
        trim_offsets=[0],
    )
    assert len(created) == len(frames)
    expected_names = {f"{frame} - Example Release.png" for frame in frames}
    assert {Path(path).name for path in created} == expected_names
    for entry in calls:
        assert entry["label"] == "Example Release"
        assert entry["requested"] == entry["frame"]

    assert len(calls) == len(frames)


def test_compression_flag_passed(tmp_path, monkeypatch):
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True, compression_level=2)

    captured = {}

    def fake_writer(source, frame_idx, crop, scaled, path, cfg, width, height, selection_label):
        captured[frame_idx] = screenshot._map_ffmpeg_compression(cfg.compression_level)
        path.write_text("ffmpeg", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_writer)

    screenshot.generate_screenshots(
        [clip],
        [10],
        ["video.mkv"],
        [{"label": "video"}],
        tmp_path,
        cfg,
        trim_offsets=[0],
    )
    assert captured[10] == 9


def test_ffmpeg_respects_trim_offsets(tmp_path, monkeypatch):
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True)

    calls: list[int] = []

    def fake_ffmpeg(source, frame_idx, crop, scaled, path, cfg, width, height, selection_label):
        calls.append(frame_idx)
        path.write_text("ff", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", lambda *args, **kwargs: None)

    screenshot.generate_screenshots(
        [clip],
        [0, 5],
        ["video.mkv"],
        [{"label": "video"}],
        tmp_path,
        cfg,
        trim_offsets=[3],
    )

    assert calls == [3, 8]


def test_global_upscale_coordination(tmp_path, monkeypatch):
    clips = [FakeClip(1280, 720), FakeClip(1920, 1080), FakeClip(640, 480)]
    cfg = ScreenshotConfig(upscale=True, use_ffmpeg=False, add_frame_info=False)

    scaled: list[tuple[int, int]] = []

    def fake_vs_writer(clip, frame_idx, crop, scaled_dims, path, cfg, label, requested_frame, selection_label=None):
        scaled.append(scaled_dims)
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    metadata = [{"label": f"clip{i}"} for i in range(len(clips))]
    screenshot.generate_screenshots(
        clips,
        [0],
        [f"clip{i}.mkv" for i in range(len(clips))],
        metadata,
        tmp_path,
        cfg,
        trim_offsets=[0, 0, 0],
    )

    assert scaled == [(1920, 1080), (1920, 1080), (1440, 1080)]


def test_placeholder_logging(tmp_path, caplog, monkeypatch):
    clip = FakeClip(1280, 720)
    cfg = ScreenshotConfig(use_ffmpeg=False)

    def failing_writer(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", failing_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    with caplog.at_level("WARNING"):
        created = screenshot.generate_screenshots(
            [clip],
            [0],
            ["clip.mkv"],
            [{"label": "clip"}],
            tmp_path,
            cfg,
            trim_offsets=[0],
        )

    assert "Falling back to placeholder" in caplog.text
    placeholder = Path(created[0])
    assert placeholder.read_bytes() == b"placeholder\n"
