import pytest

from src.analysis import (
    FrameMetricsCacheInfo,
    _quantile,
    compute_selection_window,
    dedupe,
    select_frames,
)
from src.datatypes import AnalysisConfig, TonemapConfig


class FakeClip:
    def __init__(self, num_frames: int, brightness, motion):
        self.num_frames = num_frames
        self.fps_num = 24
        self.fps_den = 1
        self.analysis_brightness = brightness
        self.analysis_motion = motion


def test_quantile_basic():
    data = [0, 1, 2, 3, 4]
    assert _quantile(data, 0.0) == 0
    assert _quantile(data, 1.0) == 4
    assert _quantile(data, 0.5) == 2
    assert pytest.approx(_quantile(data, 0.25)) == 1.0
    with pytest.raises(ValueError):
        _quantile([], 0.5)


def test_dedupe_separation():
    frames = [0, 10, 20, 30, 100]
    deduped = dedupe(frames, min_separation_sec=1.0, fps=24.0)
    assert deduped == [0, 30, 100]


def test_compute_selection_window_basic():
    spec = compute_selection_window(2400, 24.0, ignore_lead_seconds=10.0, ignore_trail_seconds=5.0, min_window_seconds=1.0)
    assert spec.start_frame == 240
    assert spec.end_frame == 2280
    assert pytest.approx(spec.start_seconds, rel=1e-6) == 10.0
    assert pytest.approx(spec.end_seconds, rel=1e-6) == 95.0
    assert pytest.approx(spec.applied_lead_seconds, rel=1e-6) == 10.0
    assert pytest.approx(spec.applied_trail_seconds, rel=1e-6) == 5.0
    assert not spec.warnings


def test_compute_selection_window_clamps_to_clip():
    spec = compute_selection_window(60, 30.0, ignore_lead_seconds=2.0, ignore_trail_seconds=2.0, min_window_seconds=5.0)
    assert spec.start_frame == 0
    assert spec.end_frame == 60
    assert pytest.approx(spec.start_seconds, rel=1e-6) == 0.0
    assert pytest.approx(spec.end_seconds, rel=1e-6) == 2.0
    assert pytest.approx(spec.applied_lead_seconds, rel=1e-6) == 0.0
    assert pytest.approx(spec.applied_trail_seconds, rel=1e-6) == 0.0
    assert spec.warnings


def test_select_frames_deterministic(monkeypatch):
    clip = FakeClip(
        num_frames=300,
        brightness=[i / 300 for i in range(300)],
        motion=[(300 - i) / 300 for i in range(300)],
    )

    calls = []

    def fake_process(target_clip, file_name, cfg):
        calls.append(file_name)
        return target_clip

    monkeypatch.setattr(
        "src.analysis.vs_core.process_clip_for_screenshot",
        fake_process,
    )

    cfg = AnalysisConfig(
        frame_count_dark=3,
        frame_count_bright=3,
        frame_count_motion=2,
        random_frames=0,
        user_frames=[],
        downscale_height=0,
        step=10,
        analyze_in_sdr=True,
        use_quantiles=True,
    )

    files = ["a.mkv", "b.mkv"]
    first = select_frames(clip, cfg, files, file_under_analysis="a.mkv")
    second = select_frames(clip, cfg, files, file_under_analysis="a.mkv")

    assert first == second
    assert sorted(first) == first
    assert len(calls) == 2


def test_user_and_random_frames(monkeypatch):
    clip = FakeClip(
        num_frames=200,
        brightness=[(i % 50) / 50 for i in range(200)],
        motion=[(i % 30) / 30 for i in range(200)],
    )

    monkeypatch.setattr(
        "src.analysis.vs_core.process_clip_for_screenshot",
        lambda clip, file_name, cfg: clip,
    )

    cfg = AnalysisConfig(
        frame_count_dark=0,
        frame_count_bright=0,
        frame_count_motion=0,
        random_frames=3,
        user_frames=[5, 10, 150],
        screen_separation_sec=0,
        step=5,
        analyze_in_sdr=False,
    )

    frames = select_frames(clip, cfg, files=["x.mkv"], file_under_analysis="x.mkv")
    assert frames == sorted(frames)
    for user_frame in cfg.user_frames:
        assert user_frame in frames
    extras = [f for f in frames if f not in set(cfg.user_frames)]
    assert len(extras) == cfg.random_frames


def test_select_frames_respects_window(monkeypatch, caplog):
    clip = FakeClip(
        num_frames=220,
        brightness=[i / 220 for i in range(220)],
        motion=[(220 - i) / 220 for i in range(220)],
    )

    monkeypatch.setattr(
        "src.analysis.vs_core.process_clip_for_screenshot",
        lambda clip, file_name, cfg: clip,
    )

    cfg = AnalysisConfig(
        frame_count_dark=2,
        frame_count_bright=0,
        frame_count_motion=0,
        random_frames=0,
        user_frames=[10, 75, 180],
        screen_separation_sec=0,
        step=1,
    )

    caplog.set_level("WARNING")
    frames = select_frames(
        clip,
        cfg,
        files=["clip.mkv"],
        file_under_analysis="clip.mkv",
        frame_window=(50, 150),
    )

    assert frames
    assert all(50 <= frame < 150 for frame in frames)
    assert 75 in frames
    assert 10 not in frames
    assert 180 not in frames
    assert any("Dropped" in record.message for record in caplog.records)


def test_select_frames_uses_cache(monkeypatch, tmp_path):
    clip = FakeClip(
        num_frames=120,
        brightness=[i / 120 for i in range(120)],
        motion=[(120 - i) / 120 for i in range(120)],
    )

    monkeypatch.setattr(
        "src.analysis.vs_core.process_clip_for_screenshot",
        lambda clip, file_name, cfg: clip,
    )

    calls = {"count": 0}

    def fake_collect(analysis_clip, cfg, indices, progress=None):
        calls["count"] += 1
        return ([(idx, float(idx)) for idx in indices], [(idx, float(idx)) for idx in indices])

    monkeypatch.setattr("src.analysis._collect_metrics_vapoursynth", fake_collect)

    cfg = AnalysisConfig(
        frame_count_dark=1,
        frame_count_bright=1,
        frame_count_motion=1,
        random_frames=0,
        user_frames=[],
        downscale_height=0,
        analyze_in_sdr=False,
        use_quantiles=True,
    )

    cache_info = FrameMetricsCacheInfo(
        path=tmp_path / "metrics.json",
        files=["a.mkv"],
        analyzed_file="a.mkv",
        release_group="",
        trim_start=0,
        trim_end=None,
        fps_num=24,
        fps_den=1,
    )

    frames_first = select_frames(clip, cfg, ["a.mkv"], "a.mkv", cache_info=cache_info)
    assert cache_info.path.exists()
    assert calls["count"] == 1

    calls["count"] = 0
    frames_second = select_frames(clip, cfg, ["a.mkv"], "a.mkv", cache_info=cache_info)
    assert calls["count"] == 0
    assert frames_first == frames_second


def test_tonemap_config_invalidates_cache(monkeypatch, tmp_path):
    clip = FakeClip(
        num_frames=90,
        brightness=[i / 90 for i in range(90)],
        motion=[0.0 for _ in range(90)],
    )

    monkeypatch.setattr(
        "src.analysis.vs_core.process_clip_for_screenshot",
        lambda clip, file_name, cfg: clip,
    )

    calls = {"count": 0}

    def fake_collect(analysis_clip, cfg, indices, progress=None):
        calls["count"] += 1
        values = [(idx, float(idx)) for idx in indices]
        return values, values

    monkeypatch.setattr("src.analysis._collect_metrics_vapoursynth", fake_collect)

    cfg = AnalysisConfig(
        frame_count_dark=1,
        frame_count_bright=1,
        frame_count_motion=0,
        random_frames=0,
        user_frames=[],
        analyze_in_sdr=True,
        use_quantiles=True,
        downscale_height=0,
    )

    cache_info = FrameMetricsCacheInfo(
        path=tmp_path / "metrics.json",
        files=["clip.mkv"],
        analyzed_file="clip.mkv",
        release_group="",
        trim_start=0,
        trim_end=None,
        fps_num=24,
        fps_den=1,
    )

    tonemap_one = TonemapConfig(target_nits=120.0)
    tonemap_two = TonemapConfig(target_nits=160.0)

    first = select_frames(
        clip,
        cfg,
        ["clip.mkv"],
        "clip.mkv",
        cache_info=cache_info,
        tonemap_cfg=tonemap_one,
    )
    assert first
    assert calls["count"] == 1

    second = select_frames(
        clip,
        cfg,
        ["clip.mkv"],
        "clip.mkv",
        cache_info=cache_info,
        tonemap_cfg=tonemap_one,
    )
    assert second == first
    assert calls["count"] == 1

    third = select_frames(
        clip,
        cfg,
        ["clip.mkv"],
        "clip.mkv",
        cache_info=cache_info,
        tonemap_cfg=tonemap_two,
    )
    assert third
    assert calls["count"] == 2


def test_motion_quarter_gap(monkeypatch):
    clip = FakeClip(
        num_frames=240,
        brightness=[0.5 for _ in range(240)],
        motion=[0.0 for _ in range(240)],
    )

    def fake_collect(analysis_clip, cfg, indices, progress=None):
        brightness = [(idx, 0.0) for idx in indices]
        motion = [(idx, float(idx)) for idx in indices]
        return brightness, motion

    monkeypatch.setattr("src.analysis._collect_metrics_vapoursynth", fake_collect)
    monkeypatch.setattr(
        "src.analysis.vs_core.process_clip_for_screenshot",
        lambda clip, file_name, cfg: clip,
    )

    cfg = AnalysisConfig(
        frame_count_dark=0,
        frame_count_bright=0,
        frame_count_motion=4,
        random_frames=0,
        user_frames=[],
        screen_separation_sec=8,
        motion_diff_radius=0,
        analyze_in_sdr=False,
        step=1,
    )

    frames = select_frames(clip, cfg, files=["file.mkv"], file_under_analysis="file.mkv")
    assert len(frames) == 4
    diffs = [b - a for a, b in zip(frames, frames[1:])]
    assert all(diff >= 48 for diff in diffs)
    assert any(diff < 192 for diff in diffs)
