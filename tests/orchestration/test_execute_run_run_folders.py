"""Run-folder behavior tests for execute_run."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.loader import load_config
from frame_compare.orchestration import phase_tasks, preparation
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.services.alignment import CACHE_FILE_NAME
from frame_compare.services.errors import TmdbError
from frame_compare.services.run_folder import derive_run_folder_name
from frame_compare.services.types import MetadataConfig, TmdbMetadata

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    FakeVSLoader,
    create_config,
    create_video_files,
    write_metrics_cache,
)


def test_execute_run_no_cache_deletes_run_folder_cache_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "comp.mkv")

    run_name = "Movie (2024)"
    monkeypatch.setattr(
        preparation, "reserve_run_folder", lambda input_dir, **_kwargs: input_dir / run_name
    )
    run_generated_dir = input_dir / run_name / "generated"

    analysis_cache_dir = run_generated_dir / "cache"
    analysis_cache_dir.mkdir(parents=True, exist_ok=True)
    analysis_cache_path = analysis_cache_dir / cache_io.CACHE_FILENAME
    analysis_cache_path.write_text("{}", encoding="utf-8")

    offsets_path = run_generated_dir / CACHE_FILE_NAME
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
    assert not offsets_path.exists()


def test_execute_run_from_cache_only_does_not_reserve_run_folder_when_metrics_cache_missing(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_dir = input_dir / run_name

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

    assert not run_dir.exists()


def test_execute_run_from_cache_only_uses_run_folder_cache_when_enabled(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_generated_dir = input_dir / run_name / "generated"
    cache_dir = run_generated_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_io.CACHE_FILENAME

    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    fingerprint = cache_io.compute_cache_key([source_path], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.1] * 100,
        "motion": [0.2] * 100,
        "metadata": {
            "frame_count": 100,
            "fps": "24",
            "config_fingerprint": fingerprint,
            "clips": [
                {
                    "path": str(source_path),
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
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert result.warnings == []
    assert result.screenshot_dir == (run_generated_dir.parent / "screenshots").resolve()
    assert result.slowpics_url is None


def test_execute_run_from_cache_only_preserves_existing_run_folder_casing(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    existing_run_name = run_name.upper()
    run_generated_dir = input_dir / existing_run_name / "generated"
    source_path = input_dir / "source.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    write_metrics_cache(run_generated_dir / "cache", source_path=source_path, config=config)

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
    assert result.screenshot_dir == (input_dir / existing_run_name / "screenshots").resolve()


def test_execute_run_from_cache_only_ignores_prefetched_tmdb_run_folder_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_generated_dir = input_dir / run_name / "generated"
    cache_dir = run_generated_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    fingerprint = cache_io.compute_cache_key([source_path], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.1] * 100,
        "motion": [0.2] * 100,
        "metadata": {
            "frame_count": 100,
            "fps": "24",
            "config_fingerprint": fingerprint,
            "clips": [
                {
                    "path": str(source_path),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    (cache_dir / cache_io.CACHE_FILENAME).write_text(json.dumps(cache_payload), encoding="utf-8")

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata:
        del filenames, config, client
        return TmdbMetadata(
            tmdb_id=123,
            title="Fight Club",
            original_title="Fight Club",
            year=1999,
            media_type="movie",
        )

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert result.screenshot_dir == (input_dir / run_name / "screenshots").resolve()


def test_execute_run_passes_prefetched_tmdb_metadata_to_run_folder_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    expected_metadata = TmdbMetadata(
        tmdb_id=123,
        title="Fight Club",
        original_title="Fight Club",
        year=1999,
        media_type="movie",
    )

    captured_tmdb_metadata: list[TmdbMetadata | None] = []
    resolve_calls: list[list[str]] = []

    def _capture_reserve_run_folder(
        input_dir: Path, filenames: list[str], tmdb_metadata: TmdbMetadata | None
    ) -> Path:
        del filenames
        captured_tmdb_metadata.append(tmdb_metadata)
        return input_dir / "Fight Club (1999)"

    async def _fake_resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata | None:
        del config, client
        resolve_calls.append(filenames)
        return expected_metadata

    monkeypatch.setattr(preparation, "reserve_run_folder", _capture_reserve_run_folder)
    monkeypatch.setattr(phase_tasks, "resolve_metadata", _fake_resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert captured_tmdb_metadata == [expected_metadata]
    assert resolve_calls == [["source.mkv"]]
    assert result.screenshot_dir is not None
    assert result.screenshot_dir == (input_dir / "Fight Club (1999)" / "screenshots").resolve()


def test_execute_run_retries_metadata_phase_when_run_folder_prefetch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
timeout_seconds = 7.5
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    expected_metadata = TmdbMetadata(
        tmdb_id=456,
        title="Heat",
        original_title="Heat",
        year=1995,
        media_type="movie",
    )

    prefetch_calls: list[list[str]] = []
    phase_calls: list[list[str]] = []
    captured_configs: list[MetadataConfig] = []

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata | None:
        del client
        captured_configs.append(config)
        if not prefetch_calls:
            prefetch_calls.append(filenames)
            raise TmdbError("temporary metadata failure")
        phase_calls.append(filenames)
        return expected_metadata

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.warnings == []
    assert prefetch_calls == [["source.mkv"]]
    assert phase_calls == [["source.mkv"]]
    assert captured_configs == [
        MetadataConfig(api_key="test-key", unattended=True, timeout_seconds=7.5),
        MetadataConfig(api_key="test-key", unattended=True, timeout_seconds=7.5),
    ]


def test_execute_run_propagates_unexpected_run_folder_metadata_prefetch_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
timeout_seconds = 7.5
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata | None:
        del filenames, config, client
        raise RuntimeError("unexpected metadata failure")

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        skip_dovi=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(RuntimeError, match="unexpected metadata failure"):
        asyncio.run(execute_run(request, deps=deps))
