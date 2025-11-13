import datetime as _dt
from pathlib import Path
from typing import Iterable, List, Sequence

import pytest

import src.frame_compare.analysis.cache_io as cache_io
from src.datatypes import AnalysisConfig
from src.frame_compare.analysis.cache_io import (
    ClipIdentity,
    FrameMetricsCacheInfo,
    load_selection_sidecar,
    probe_cached_metrics,
    save_selection_sidecar,
)


def _analysis_cfg() -> AnalysisConfig:
    return AnalysisConfig(
        frame_count_dark=1,
        frame_count_bright=1,
        frame_count_motion=1,
        random_frames=0,
        user_frames=[],
        downscale_height=0,
        step=1,
        analyze_in_sdr=False,
    )


def _sample_metrics() -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
    brightness = [(idx, float(idx) / 10.0) for idx in range(6)]
    motion = [(idx, float(idx) / 5.0) for idx in range(6)]
    return brightness, motion


def _capture_clips(
    root: Path,
    clip_names: Sequence[str],
    *,
    analyzed_file: str,
    sha1_overrides: Sequence[str | None] | None = None,
) -> List[ClipIdentity]:
    total = len(clip_names)
    overrides = list(sha1_overrides or [])
    entries: List[ClipIdentity] = []
    for idx, name in enumerate(clip_names):
        clip_path = (root / name).resolve()
        if not clip_path.exists():
            clip_path.write_bytes(b"data")
        stat_result = clip_path.stat()
        sha1 = overrides[idx] if idx < len(overrides) else None
        entries.append(
            ClipIdentity(
                role=cache_io.infer_clip_role(idx, name, analyzed_file, total),
                path=str(clip_path),
                name=name,
                size=int(stat_result.st_size),
                mtime=_dt.datetime.fromtimestamp(stat_result.st_mtime, tz=_dt.timezone.utc).isoformat(),
                sha1=sha1,
            )
        )
    return entries


def _make_info(cache_path: Path, clips: Sequence[ClipIdentity]) -> FrameMetricsCacheInfo:
    clip_names = [clip.name for clip in clips]
    return FrameMetricsCacheInfo(
        path=cache_path,
        files=clip_names,
        analyzed_file=clip_names[0],
        release_group="",
        trim_start=0,
        trim_end=None,
        fps_num=24,
        fps_den=1,
        clips=list(clips),
    )


def _write_files(root: Path, names_and_contents: Iterable[tuple[str, bytes]]) -> None:
    for name, content in names_and_contents:
        target = root / name
        target.write_bytes(content)


def test_v2_metrics_cache_rejects_same_names_different_paths(tmp_path: Path) -> None:
    analyzed_file = "Target.mkv"
    clip_names = ["Reference.mkv", analyzed_file]

    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    _write_files(
        dir_a,
        [("Reference.mkv", b"A-ref"), ("Target.mkv", b"A-target")],
    )
    _write_files(
        dir_b,
        [("Reference.mkv", b"B-ref"), ("Target.mkv", b"B-target")],
    )

    clips_a = _capture_clips(dir_a, clip_names, analyzed_file=analyzed_file)
    clips_b = _capture_clips(dir_b, clip_names, analyzed_file=analyzed_file)

    info_a = _make_info(dir_a / "metrics.json", clips_a)
    info_b = _make_info(dir_b / "metrics.json", clips_b)

    cfg = _analysis_cfg()
    brightness, motion = _sample_metrics()
    cache_io._save_cached_metrics(info_a, cfg, brightness, motion)

    info_b.path.write_text(info_a.path.read_text(encoding="utf-8"), encoding="utf-8")
    result = probe_cached_metrics(info_b, cfg)
    assert result.status == "stale"
    assert result.reason == "inputs_path_mismatch"

    cache_io._save_cached_metrics(info_b, cfg, brightness, motion)
    reused = probe_cached_metrics(info_b, cfg)
    assert reused.status == "reused"
    assert reused.metrics is not None


def test_v1_payload_marked_stale(tmp_path: Path) -> None:
    cache_path = tmp_path / "metrics.json"
    info = FrameMetricsCacheInfo(
        path=cache_path,
        files=["clip.mkv"],
        analyzed_file="clip.mkv",
        release_group="",
        trim_start=0,
        trim_end=None,
        fps_num=24,
        fps_den=1,
    )
    cache_path.write_text('{"version": 1}', encoding="utf-8")
    result = probe_cached_metrics(info, _analysis_cfg())
    assert result.status == "stale"
    assert result.reason == "version_mismatch"


def test_selection_sidecar_uses_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    analyzed_file = "Target.mkv"
    clip_names = ["Reference.mkv", analyzed_file]
    _write_files(
        tmp_path,
        [("Reference.mkv", b"ref"), ("Target.mkv", b"target")],
    )
    clips = _capture_clips(tmp_path, clip_names, analyzed_file=analyzed_file)

    info = _make_info(tmp_path / "metrics.json", clips)
    cfg = _analysis_cfg()
    selection_hash = "sel-hash"
    selection_frames = [0, 2, 4]

    save_selection_sidecar(
        info,
        cfg,
        selection_hash=selection_hash,
        selection_frames=selection_frames,
        selection_details={},
    )

    def _fail_stat(self: Path) -> None:  # pragma: no cover - safety net
        raise AssertionError("stat should not be called when snapshot exists")

    monkeypatch.setattr(Path, "stat", _fail_stat)
    loaded = load_selection_sidecar(info, cfg, selection_hash)
    assert loaded is not None
    frames, details = loaded
    assert frames == selection_frames
    assert isinstance(details, dict)


def test_hash_mismatch_when_opt_in_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRAME_COMPARE_CACHE_HASH", "1")
    clip_path = tmp_path / "clip.mkv"
    clip_path.write_bytes(b"content")
    analyzed_file = clip_path.name
    mtime = _dt.datetime.fromtimestamp(clip_path.stat().st_mtime, tz=_dt.timezone.utc).isoformat()
    size = int(clip_path.stat().st_size)

    clip_a = ClipIdentity(
        role="analyze",
        path=str(clip_path),
        name=analyzed_file,
        size=size,
        mtime=mtime,
        sha1="hash-a",
    )
    clip_b = ClipIdentity(
        role="analyze",
        path=str(clip_path),
        name=analyzed_file,
        size=size,
        mtime=mtime,
        sha1="hash-b",
    )

    cache_path = tmp_path / "metrics.json"
    cfg = _analysis_cfg()
    brightness, motion = _sample_metrics()
    info_a = _make_info(cache_path, [clip_a])
    cache_io._save_cached_metrics(info_a, cfg, brightness, motion)

    info_b = _make_info(cache_path, [clip_b])
    result = probe_cached_metrics(info_b, cfg)
    assert result.status == "stale"
    assert result.reason == "inputs_sha1_mismatch"
