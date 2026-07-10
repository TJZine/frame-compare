"""Probe persistence and reuse tests for orchestration preparation."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from frame_compare.orchestration import preparation
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.vs.types import SourceInfo
from tests.orchestration.preparation_test_support import (
    create_config as _create_config,
)
from tests.orchestration.preparation_test_support import (
    create_video_files as _create_video_files,
)

if TYPE_CHECKING:
    import vapoursynth as vs
from frame_compare.orchestration.probing.probe_cache import load_clip_probe_cache


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

    def ensure_core(self) -> vs.Core:
        raise AssertionError("Preparation probing should not request the VS core directly")


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
    assert [clip.label for clip in prep.clips] == ["encode", "source"]
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

    assert second.clips[0].label == "source"
    assert second.clips[0].probe == first.clips[0].probe
