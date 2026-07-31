"""Fastest analysis-source benchmark tests for orchestration preparation."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from frame_compare.orchestration import preparation
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.vs.types import SourceInfo
from tests.orchestration.preparation_test_support import (
    METRIC_CONFIG,
    MINIMAL_CONFIG,
)
from tests.orchestration.preparation_test_support import (
    create_config as _create_config,
)
from tests.orchestration.preparation_test_support import (
    create_video_files as _create_video_files,
)

if TYPE_CHECKING:
    import vapoursynth as vs


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


class FakeBenchmarkClip:
    def __init__(self, *, num_frames: int, delay: float, clock: list[float]) -> None:
        self.num_frames = num_frames
        self.delay = delay
        self.clock = clock

    def get_frame(self, _frame: int) -> object:
        self.clock[0] += self.delay
        return object()


class FakeBenchmarkVSLoader(FakeVSLoader):
    def __init__(
        self,
        *,
        delays_by_name: dict[str, float],
        clock: list[float],
        frames_by_name: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self._delays_by_name = delays_by_name
        self._clock = clock
        self._frames_by_name = frames_by_name or {}

    def load(self, path: Path) -> SourceInfo:
        self.loaded.append(path)
        num_frames = self._frames_by_name.get(path.name, 100)
        return SourceInfo(
            clip=cast(
                Any,
                FakeBenchmarkClip(
                    num_frames=num_frames,
                    delay=self._delays_by_name[path.name],
                    clock=self._clock,
                ),
            ),
            width=1920,
            height=1080,
            num_frames=num_frames,
            fps=Fraction(24000, 1001),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=False,
            hdr_metadata=None,
        )


def test_execute_prep_analysis_source_fastest_selects_lowest_timing_and_ties_by_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-fast.mkv", "02-tie.mkv")
    clock = [0.0]
    monkeypatch.setattr(
        "frame_compare.orchestration.analysis_source.perf_counter", lambda: clock[0]
    )
    loader = FakeBenchmarkVSLoader(
        delays_by_name={
            "00-reference.mkv": 2.0,
            "01-fast.mkv": 1.0,
            "02-tie.mkv": 1.0,
        },
        clock=clock,
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_clip is not None
    assert prep.analysis_clip.path.name == "01-fast.mkv"


def test_execute_prep_analysis_source_fastest_compares_per_sample_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-short-slow.mkv", "01-long-fast.mkv")
    clock = [0.0]
    monkeypatch.setattr(
        "frame_compare.orchestration.analysis_source.perf_counter", lambda: clock[0]
    )
    loader = FakeBenchmarkVSLoader(
        delays_by_name={
            "00-short-slow.mkv": 1.5,
            "01-long-fast.mkv": 1.0,
        },
        frames_by_name={
            "00-short-slow.mkv": 10,
            "01-long-fast.mkv": 100,
        },
        clock=clock,
    )

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_clip is not None
    assert prep.analysis_clip.path.name == "01-long-fast.mkv"


def test_execute_prep_analysis_source_fastest_cache_only_rejects_before_probe(
    tmp_path: Path,
) -> None:
    config_content = METRIC_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv")
    loader = FakeVSLoader()

    with pytest.raises(preparation.FastestAnalysisSourceCacheOnlyError):
        asyncio.run(
            preparation.execute_prep(
                RunRequest(root=tmp_path, from_cache_only=True),
                RunDependencies(vs_loader=cast(Any, loader)),
            )
        )

    assert loader.loaded == []


def test_execute_prep_analysis_source_fastest_skipped_analysis_does_not_benchmark(
    tmp_path: Path,
) -> None:
    config_content = MINIMAL_CONFIG + '\n[sources]\nanalysis_source = "fastest"\n'
    _create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "00-reference.mkv", "01-encode.mkv")
    loader = FakeVSLoader()

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, loader)),
        )
    )

    assert prep.analysis_clip is None
    assert loader.loaded == [input_dir / "00-reference.mkv", input_dir / "01-encode.mkv"]
