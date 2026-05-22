"""Direct tests for orchestration preparation behavior."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.analysis import cache_io
from frame_compare.errors import AudioAlignmentError, MetricsCalculationError
from frame_compare.orchestration import preparation
from frame_compare.orchestration.probe_cache import load_clip_probe_cache
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.services.alignment import CACHE_FILE_NAME
from frame_compare.vs.types import SourceInfo

MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


ALIGNMENT_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = true

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def _create_video_files(input_dir: Path, *filenames: str) -> list[Path]:
    input_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename in filenames:
        path = input_dir / filename
        path.write_bytes(b"video")
        paths.append(path)
    return paths


class FakeVSLoader:
    def __init__(self) -> None:
        self.loaded: list[Path] = []

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24000, 1001),
            format=cast(Any, object()),
            frame_props={
                "_Transfer": 16,
                "DolbyVisionRPU": b"opaque-rpu",
                "Ignored": {"not": "toml-safe"},
            },
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> None:
        raise AssertionError("Preparation probing should not request the VS core directly")


def test_execute_prep_rejects_mutually_exclusive_cache_flags(tmp_path: Path) -> None:
    request = RunRequest(root=tmp_path, no_cache=True, from_cache_only=True)

    with pytest.raises(MetricsCalculationError, match="mutually exclusive"):
        asyncio.run(preparation.execute_prep(request, RunDependencies()))


def test_execute_prep_no_cache_removes_metrics_and_audio_offset_caches(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    metrics_path = tmp_path / "generated" / "cache" / cache_io.CACHE_FILENAME
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text("{}", encoding="utf-8")
    offsets_path = tmp_path / "generated" / CACHE_FILE_NAME
    offsets_path.parent.mkdir(parents=True, exist_ok=True)
    offsets_path.write_text('version = "1"\n', encoding="utf-8")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path, no_cache=True),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )

    assert prep.clips[0].label == "Reference"
    assert not metrics_path.exists()
    assert not offsets_path.exists()


def test_execute_prep_from_cache_only_requires_cached_alignment_offsets(tmp_path: Path) -> None:
    _create_config(tmp_path, content=ALIGNMENT_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")

    request = RunRequest(root=tmp_path, from_cache_only=True, skip_analysis=True)

    with pytest.raises(AudioAlignmentError, match="a_source:b_comp"):
        asyncio.run(
            preparation.execute_prep(request, RunDependencies(vs_loader=cast(Any, FakeVSLoader())))
        )


def test_execute_prep_from_cache_only_validates_metrics_cache_when_analysis_runs(
    tmp_path: Path,
) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    request = RunRequest(root=tmp_path, from_cache_only=True, skip_analysis=False)

    with pytest.raises(MetricsCalculationError, match="Cached metrics missing"):
        asyncio.run(
            preparation.execute_prep(request, RunDependencies(vs_loader=cast(Any, FakeVSLoader())))
        )


def test_execute_prep_probes_uncached_clips_and_persists_probe_snapshot(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    source, encode = _create_video_files(input_dir, "source.mkv", "encode.mkv")
    loader = FakeVSLoader()

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert set(loader.loaded) == {source, encode}
    assert [clip.label for clip in prep.clips] == ["Reference", "Encode 1"]
    assert [clip.probe.width for clip in prep.clips] == [1920, 1920]
    assert prep.clips[0].probe.tonemap_prop_keys == ("DolbyVisionRPU", "_Transfer")
    assert prep.clips[0].probe.preserved_frame_props == {
        "DolbyVisionRPU": 1,
        "_Transfer": 16,
    }

    probe_cache = load_clip_probe_cache(tmp_path / "generated" / "clip_probe.toml")
    assert len(probe_cache) == 2
    assert {snapshot.fingerprint.path for snapshot in probe_cache.values()} == {source, encode}


def test_execute_prep_reuses_probe_cache_without_vs_loader(tmp_path: Path) -> None:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")

    first = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    second = asyncio.run(preparation.execute_prep(RunRequest(root=tmp_path), RunDependencies()))

    assert second.clips[0].label == "Reference"
    assert second.clips[0].probe == first.clips[0].probe
