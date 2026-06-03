"""Cache-mode tests for execute_run."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.loader import load_config
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.services.alignment import CACHE_FILE_NAME
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeVSLoader,
    analysis_selection_domain_for_cache_inputs,
    create_config,
    create_video_files,
    write_metrics_cache,
    write_probe_cache_for_inputs,
)


def test_execute_run_no_cache_deletes_only_matching_shared_metrics_cache(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    config = load_config(tmp_path / "config" / "config.toml")

    analysis_cache_dir = tmp_path / "generated" / "cache" / "analysis"
    source_path = input_dir / "source.mkv"
    write_metrics_cache(analysis_cache_dir, source_path=source_path, config=config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
    )
    analysis_cache_path = cache_io.find_metrics_cache_file(analysis_cache_dir, fingerprint)
    assert analysis_cache_path is not None

    other_cache_path = analysis_cache_dir / "other__other.compframes"
    other_cache_path.write_text("{}", encoding="utf-8")

    offsets_path = tmp_path / "generated" / CACHE_FILE_NAME
    offsets_path.parent.mkdir(parents=True, exist_ok=True)
    offsets_path.write_text('version = "1"\n', encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        no_cache=True,
        skip_analysis=True,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert not analysis_cache_path.exists()
    assert other_cache_path.exists()
    assert offsets_path.exists()


def test_execute_run_from_cache_only_fails_when_metrics_cache_missing(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(MetricsCalculationError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_uses_cache_for_explicit_reference_effective_fps_equal_to_source(
    tmp_path: Path,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[sources.overrides."source.mkv"]
effective_fps = "24/1"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=source_path,
        config=config,
    )

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True


def test_execute_run_from_cache_only_fails_when_metrics_cache_invalid(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
    )
    cache_path = cache_dir / cache_io.metrics_cache_filename([source_path], fingerprint)
    cache_path.write_text("{not-json", encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(CacheCorruptionError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_fails_when_metrics_cache_version_mismatch(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
    )
    cache_path = cache_dir / cache_io.metrics_cache_filename([source_path], fingerprint)
    cache_payload = {
        "version": cache_io.CACHE_VERSION + 1,
        "fingerprint": fingerprint,
        "luminance": [0.1],
        "motion": [0.2],
        "metadata": {
            "frame_count": 1,
            "fps": "24",
            "config_fingerprint": "test",
            "clips": [
                {
                    "path": str(input_dir / "source.mkv"),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(CacheVersionMismatchError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_requires_probe_cache_before_audio_offsets_when_alignment_enabled(
    tmp_path: Path,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = true

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_source.mkv", "b_comp.mkv")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MetricsCalculationError, match="Cached clip probe data is required"):
        asyncio.run(execute_run(request, deps=deps))
