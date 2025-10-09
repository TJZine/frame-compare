from pathlib import Path
import types

import pytest

from src.datatypes import ColorConfig, ScreenshotConfig
from src import screenshot, vs_core


class FakeClip:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height


@pytest.fixture(autouse=True)
def _stub_process_clip(monkeypatch):
    def _stub(clip, file_name, color_cfg, **kwargs):
        return types.SimpleNamespace(
            clip=clip,
            overlay_text=None,
            verification=None,
            tonemap=vs_core.TonemapInfo(
                applied=False,
                tone_curve=None,
                dpd=0,
                target_nits=100.0,
                dst_min_nits=0.1,
                src_csp_hint=None,
                reason="SDR source",
            ),
            source_props={},
        )

    monkeypatch.setattr(screenshot.vs_core, "process_clip_for_screenshot", _stub)


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


def test_plan_geometry_letterbox_alignment(tmp_path, monkeypatch):
    clips = [FakeClip(3840, 2160), FakeClip(3840, 1800)]
    cfg = ScreenshotConfig(directory_name="screens", add_frame_info=False)
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_writer(
        clip,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"crop": crop, "scaled": scaled, "pad": pad, "label": label})
        path.write_text("data", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    frames = [0]
    files = ["clip_a.mkv", "clip_b.mkv"]
    metadata = [{"label": "Clip A"}, {"label": "Clip B"}]

    screenshot.generate_screenshots(
        clips,
        frames,
        files,
        metadata,
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert len(captured) == 2
    assert captured[0]["crop"] == (0, 180, 0, 180)
    assert captured[0]["scaled"] == (3840, 1800)
    assert captured[1]["crop"] == (0, 0, 0, 0)
    assert captured[1]["scaled"] == (3840, 1800)


def test_generate_screenshots_filenames(tmp_path, monkeypatch):
    clip = FakeClip(1280, 720)
    cfg = ScreenshotConfig(directory_name="screens")
    color_cfg = ColorConfig()

    calls = []

    def fake_writer(
        clip,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        calls.append(
            {
                "frame": frame_idx,
                "crop": crop,
                "scaled": scaled,
                "pad": pad,
                "label": label,
                "requested": requested_frame,
            }
        )
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
        color_cfg,
        trim_offsets=[0],
    )
    assert len(created) == len(frames)
    expected_names = {f"{frame} - Example Release.png" for frame in frames}
    assert {Path(path).name for path in created} == expected_names
    for entry in calls:
        assert entry["label"] == "Example Release"
        assert entry["requested"] == entry["frame"]

    assert len(calls) == len(frames)


def _make_plan(
    width=1920,
    height=1080,
    cropped_w=1920,
    cropped_h=1080,
    scaled=(1920, 1080),
    pad=(0, 0, 0, 0),
    final=(1920, 1080),
):
    return {
        "width": width,
        "height": height,
        "crop": (0, 0, 0, 0),
        "cropped_w": cropped_w,
        "cropped_h": cropped_h,
        "scaled": scaled,
        "pad": pad,
        "final": final,
    }


def test_compose_overlay_text_minimal_returns_base_block():
    color_cfg = ColorConfig(overlay_mode="minimal")
    plan = _make_plan()
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    tonemap_info = vs_core.TonemapInfo(
        applied=True,
        tone_curve="bt.2390",
        dpd=1,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
    )

    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Dark",
        source_props={},
        tonemap_info=tonemap_info,
    )

    assert composed == base_text


def test_compose_overlay_text_diagnostic_appends_required_lines():
    color_cfg = ColorConfig(overlay_mode="diagnostic")
    plan = _make_plan(
        scaled=(3840, 2160),
        final=(3840, 2160),
    )
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    tonemap_info = vs_core.TonemapInfo(
        applied=True,
        tone_curve="bt.2390",
        dpd=1,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
    )
    props = {
        "_MasteringDisplayMinLuminance": 0.0001,
        "_MasteringDisplayMaxLuminance": 1000.0,
    }

    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Dark",
        source_props=props,
        tonemap_info=tonemap_info,
        measurement=(200.0, 47.25),
    )

    assert composed is not None
    lines = composed.split("\n")
    assert lines[0] == base_text
    assert lines[1] == "1920 × 1080 → 3840 × 2160  (original → target)"
    assert lines[2] == "MDL: min: 0.0001 cd/m², max: 1000.0 cd/m²"
    assert lines[3] == "Frame Selection Type: Dark"


def test_compose_overlay_text_skips_hdr_details_for_sdr():
    color_cfg = ColorConfig(overlay_mode="diagnostic")
    plan = _make_plan()
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    tonemap_info = vs_core.TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=0,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
        reason="SDR source",
    )

    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Cached",
        source_props={},
        tonemap_info=tonemap_info,
    )

    assert composed is not None
    lines = composed.split("\n")
    assert "MDL:" not in composed
    assert "Measurement" not in composed
    assert lines[-1] == "Frame Selection Type: Cached"


def test_compression_flag_passed(tmp_path, monkeypatch):
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True, compression_level=2)
    color_cfg = ColorConfig()

    captured = {}

    def fake_writer(
        source,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        width,
        height,
        selection_label,
        *,
        overlay_text=None,
    ):
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
        color_cfg,
        trim_offsets=[0],
    )
    assert captured[10] == 9


def test_ffmpeg_respects_trim_offsets(tmp_path, monkeypatch):
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True)
    color_cfg = ColorConfig()

    calls: list[int] = []

    def fake_ffmpeg(
        source,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        width,
        height,
        selection_label,
        *,
        overlay_text=None,
    ):
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
        color_cfg,
        trim_offsets=[3],
    )

    assert calls == [3, 8]


def test_global_upscale_coordination(tmp_path, monkeypatch):
    clips = [FakeClip(1280, 720), FakeClip(1920, 1080), FakeClip(640, 480)]
    cfg = ScreenshotConfig(upscale=True, use_ffmpeg=False, add_frame_info=False)
    color_cfg = ColorConfig()

    scaled: list[tuple[int, int]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        scaled.append((scaled_dims, pad))
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
        color_cfg,
        trim_offsets=[0, 0, 0],
    )

    assert [dims for dims, _ in scaled] == [(1920, 1080), (1920, 1080), (1440, 1080)]
    assert all(pad == (0, 0, 0, 0) for _, pad in scaled)


def test_upscale_clamps_letterbox_width(tmp_path, monkeypatch):
    clips = [FakeClip(3840, 2160), FakeClip(3832, 1384)]
    cfg = ScreenshotConfig(upscale=True, use_ffmpeg=False, add_frame_info=False)
    color_cfg = ColorConfig()

    recorded: list[tuple[int, int]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        recorded.append((scaled_dims, pad))
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    metadata = [{"label": "hdr"}, {"label": "scope"}]
    screenshot.generate_screenshots(
        clips,
        [0],
        ["hdr.mkv", "scope.mkv"],
        metadata,
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert recorded[0][0] == (3840, 2160)
    assert recorded[0][1] == (0, 0, 0, 0)
    expected_height = int(round(1384 * (3840 / 3832)))
    assert recorded[1][0] == (3840, expected_height)
    assert recorded[1][1] == (0, 0, 0, 0)


def test_auto_letterbox_crop(tmp_path, monkeypatch):
    clips = [FakeClip(3840, 2160), FakeClip(3832, 1384)]
    cfg = ScreenshotConfig(
        upscale=False,
        use_ffmpeg=False,
        add_frame_info=False,
        auto_letterbox_crop=True,
    )
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"crop": crop, "scaled": scaled_dims, "pad": pad})
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["bars.mkv", "scope.mkv"],
        [{"label": "bars"}, {"label": "scope"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert len(captured) == 2
    first_crop = captured[0]["crop"]
    assert isinstance(first_crop, tuple)
    assert first_crop[1] > 0 and first_crop[3] > 0
    assert captured[0]["scaled"] == (3840, 1384)
    assert captured[0]["pad"] == (0, 0, 0, 0)
    assert captured[1]["scaled"] == (3832, 1384)
    assert captured[1]["pad"] == (0, 0, 0, 0)


def test_pad_to_canvas_auto_handles_micro_bars(tmp_path, monkeypatch):
    clips = [FakeClip(3840, 2152), FakeClip(1920, 1080)]
    cfg = ScreenshotConfig(
        upscale=True,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=2160,
        pad_to_canvas="auto",
        letterbox_px_tolerance=8,
    )
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"scaled": scaled_dims, "pad": pad, "label": label})
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["uhd.mkv", "hd.mkv"],
        [{"label": "UHD"}, {"label": "HD"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["UHD"]["scaled"] == (3840, 2152)
    assert by_label["UHD"]["pad"] == (0, 4, 0, 4)
    assert by_label["HD"]["scaled"] == (3840, 2160)
    assert by_label["HD"]["pad"] == (0, 0, 0, 0)


def test_pad_to_canvas_auto_respects_tolerance(tmp_path, monkeypatch):
    clips = [FakeClip(3840, 2048), FakeClip(1920, 1080)]
    cfg = ScreenshotConfig(
        upscale=True,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=2160,
        pad_to_canvas="auto",
        letterbox_px_tolerance=8,
    )
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"scaled": scaled_dims, "pad": pad, "label": label})
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["scope.mkv", "hd.mkv"],
        [{"label": "scope"}, {"label": "hd"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["scope"]["pad"] == (0, 0, 0, 0)
    assert by_label["scope"]["scaled"][1] == 2048
    assert by_label["hd"]["pad"] == (0, 0, 0, 0)


def test_pad_to_canvas_on_pillarboxes_narrow_sources(tmp_path, monkeypatch):
    clips = [FakeClip(1920, 1080), FakeClip(1440, 1080)]
    cfg = ScreenshotConfig(
        upscale=False,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=1080,
        pad_to_canvas="on",
        letterbox_pillarbox_aware=False,
    )
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"scaled": scaled_dims, "pad": pad, "label": label})
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["widescreen.mkv", "academy.mkv"],
        [{"label": "ws"}, {"label": "academy"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["ws"]["pad"] == (0, 0, 0, 0)
    assert by_label["ws"]["scaled"] == (1920, 1080)
    assert by_label["academy"]["scaled"] == (1440, 1080)
    assert by_label["academy"]["pad"] == (240, 0, 240, 0)


def test_pad_to_canvas_on_without_single_res(tmp_path, monkeypatch):
    clips = [FakeClip(1920, 1080), FakeClip(1440, 1080)]
    cfg = ScreenshotConfig(
        upscale=False,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=0,
        pad_to_canvas="on",
        letterbox_pillarbox_aware=False,
    )
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"scaled": scaled_dims, "pad": pad, "label": label})
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["wide.mkv", "narrow.mkv"],
        [{"label": "wide"}, {"label": "narrow"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["wide"]["scaled"] == (1920, 1080)
    assert by_label["wide"]["pad"] == (0, 0, 0, 0)
    assert by_label["narrow"]["scaled"] == (1440, 1080)
    assert by_label["narrow"]["pad"] == (240, 0, 240, 0)


def test_pad_to_canvas_auto_zero_tolerance(tmp_path, monkeypatch):
    clips = [FakeClip(3840, 2152), FakeClip(1920, 1080)]
    cfg = ScreenshotConfig(
        upscale=True,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=2160,
        pad_to_canvas="auto",
        letterbox_px_tolerance=0,
    )
    color_cfg = ColorConfig()

    captured: list[dict[str, object]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append({"scaled": scaled_dims, "pad": pad, "label": label})
        path.write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["uhd.mkv", "hd.mkv"],
        [{"label": "UHD"}, {"label": "HD"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["UHD"]["scaled"] == (3840, 2152)
    assert by_label["UHD"]["pad"] == (0, 0, 0, 0)
    assert by_label["HD"]["scaled"] == (3840, 2160)
    assert by_label["HD"]["pad"] == (0, 0, 0, 0)


def test_ffmpeg_writer_receives_padding(tmp_path, monkeypatch):
    clips = [FakeClip(1920, 1080), FakeClip(1440, 1080)]
    cfg = ScreenshotConfig(
        use_ffmpeg=True,
        add_frame_info=False,
        single_res=1080,
        pad_to_canvas="on",
        letterbox_pillarbox_aware=False,
        mod_crop=2,
    )
    color_cfg = ColorConfig()

    calls: list[dict[str, object]] = []

    def fake_ffmpeg(
        source,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        width,
        height,
        selection_label,
        *,
        overlay_text=None,
    ):
        calls.append({"scaled": scaled, "pad": pad, "source": source})
        path.write_text("ff", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", lambda *args, **kwargs: None)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["wide.mkv", "narrow.mkv"],
        [{"label": "wide"}, {"label": "narrow"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert len(calls) == 2
    wide_call = next(call for call in calls if call["source"].endswith("wide.mkv"))
    narrow_call = next(call for call in calls if call["source"].endswith("narrow.mkv"))
    assert wide_call["scaled"] == (1920, 1080)
    assert wide_call["pad"] == (0, 0, 0, 0)
    assert narrow_call["scaled"] == (1440, 1080)
    assert narrow_call["pad"] == (240, 0, 240, 0)
def test_placeholder_logging(tmp_path, caplog, monkeypatch):
    clip = FakeClip(1280, 720)
    cfg = ScreenshotConfig(use_ffmpeg=False)
    color_cfg = ColorConfig()

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
            color_cfg,
            trim_offsets=[0],
        )

    assert "Falling back to placeholder" in caplog.text
    placeholder = Path(created[0])
    assert placeholder.read_bytes() == b"placeholder\n"
