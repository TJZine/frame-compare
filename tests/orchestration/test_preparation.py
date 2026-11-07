"""Probe persistence and reuse tests for orchestration preparation."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from frame_compare.orchestration import phase_alignment, preparation
from frame_compare.orchestration.types import RunDependencies
from frame_compare.vs.types import SourceInfo
from tests.orchestration.preparation_test_support import (
    create_config as _create_config,
)
from tests.orchestration.preparation_test_support import (
    create_video_files as _create_video_files,
)
from tests.run_request_support import make_run_request

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
            make_run_request(root=tmp_path),
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
            make_run_request(root=tmp_path),
            RunDependencies(vs_loader=cast(Any, FakeVSLoader())),
        )
    )
    second = asyncio.run(
        preparation.execute_prep(make_run_request(root=tmp_path), RunDependencies())
    )

    assert second.clips[0].label == "source"
    assert second.clips[0].probe == first.clips[0].probe


def _symlinked_input(tmp_path: Path) -> tuple[Path, Path, Path]:
    _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    input_dir.mkdir()
    original_target = tmp_path / "first.mkv"
    replacement_target = tmp_path / "second.mkv"
    original_target.write_bytes(b"first")
    replacement_target.write_bytes(b"other")
    original_stat = original_target.stat()
    os.utime(replacement_target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    alias = input_dir / "comparison.mkv"
    alias.symlink_to(original_target)
    return alias, original_target, replacement_target


def test_cold_probe_caches_facts_from_the_frozen_symlink_target(tmp_path: Path) -> None:
    alias, original_target, replacement_target = _symlinked_input(tmp_path)

    class RetargetingVSLoader(FakeVSLoader):
        def load(self, path: Path) -> SourceInfo:
            # Retarget after fingerprinting and restore before preparation can recheck the alias.
            alias.unlink()
            alias.symlink_to(replacement_target)
            try:
                info = super().load(path)
                if path.read_bytes() == b"other":
                    return replace(info, width=1280, fps=Fraction(25))
                return info
            finally:
                alias.unlink()
                alias.symlink_to(original_target)

    run = make_run_request(root=tmp_path)
    cold = asyncio.run(
        preparation.execute_prep(run, RunDependencies(vs_loader=RetargetingVSLoader()))
    )
    warm = asyncio.run(preparation.execute_prep(run, RunDependencies()))

    (cold_clip,) = cold.clips
    (warm_clip,) = warm.clips
    assert warm_clip.path == cold_clip.path == alias
    assert (warm_clip.probe.width, warm_clip.probe.fps) == (1920, Fraction(24000, 1001))
    assert warm_clip.probe == cold_clip.probe
    assert warm_clip.probe.fingerprint.path == original_target


def test_prepared_alignment_rejects_retargeted_symlink_with_matching_stat(tmp_path: Path) -> None:
    alias, _, replacement_target = _symlinked_input(tmp_path)

    run = make_run_request(root=tmp_path)
    cold = asyncio.run(preparation.execute_prep(run, RunDependencies(vs_loader=FakeVSLoader())))
    warm = asyncio.run(preparation.execute_prep(run, RunDependencies()))
    clips = [
        phase_alignment._alignment_clip_request(prep.clips[0], selected_audio_stream=None)
        for prep in (cold, warm)
    ]
    assert all(clip.path == alias and clip.identity_is_current() for clip in clips)

    alias.unlink()
    alias.symlink_to(replacement_target)

    assert all(not clip.identity_is_current() for clip in clips)


def test_execute_prep_uses_one_acquisition_and_discovers_sources_at_use(tmp_path: Path) -> None:
    import pytest

    from frame_compare.config.loader import load_config
    from frame_compare.orchestration.errors import NoVideosFoundError
    from frame_compare.orchestration.run_inputs import acquire_run_config
    from frame_compare.orchestration.types import RunRequest

    config_file = _create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    _create_video_files(input_dir, "source.mkv")
    calls = 0

    def load(config_path=None, overrides=None):
        nonlocal calls
        calls += 1
        assert calls == 1, "execution must never reacquire configuration"
        return load_config(config_path, overrides)

    inputs = acquire_run_config(root=tmp_path, load_config_fn=load)
    config_file.write_text("[runtime]\nmemory_limit_mb = 1\n")
    request = RunRequest(inputs=inputs, skip_metadata=True, skip_analysis=True)
    prep = asyncio.run(preparation.execute_prep(request, RunDependencies(vs_loader=FakeVSLoader())))
    assert prep.config is inputs.config
    assert prep.config.runtime.memory_limit_mb is None
    assert calls == 1
    (input_dir / "source.mkv").unlink()
    with pytest.raises(NoVideosFoundError):
        asyncio.run(preparation.execute_prep(request, RunDependencies(vs_loader=FakeVSLoader())))
    assert calls == 1
