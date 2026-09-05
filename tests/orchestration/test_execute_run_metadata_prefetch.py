"""Metadata-prefetch behavior for run-folder orchestration."""

from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path
from typing import cast

import httpx
import pytest

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.config.loader import load_config
from frame_compare.orchestration import phase_post_render, preparation
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.services.errors import TmdbError
from frame_compare.services.run_folder import RunFolderReservation
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.types import MetadataConfig, TmdbMetadata
from frame_compare.utils.cache_errors import CacheCorruptionError

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    FakeVSLoader,
    analysis_selection_domain_for_cache_inputs,
    create_config,
    create_video_files,
    metric_cache_request_for_cache_inputs,
    write_probe_cache_for_inputs,
)

METADATA_CACHE_CONFIG = (
    RUN_FOLDERS_CONFIG
    + """
[analysis]
random_frame_count = 0
dark_frame_count = 1

[tmdb]
enabled = true
api_key = "test-key"
unattended = true
"""
)

METADATA_RETRY_CONFIG = (
    RUN_FOLDERS_CONFIG
    + """
[tmdb]
enabled = true
api_key = "test-key"
unattended = true
timeout_seconds = 7.5
year_tolerance = 1
category_preference = "movie"
"""
)

METADATA_UNEXPECTED_ERROR_CONFIG = (
    RUN_FOLDERS_CONFIG
    + """
[tmdb]
enabled = true
api_key = "test-key"
unattended = true
timeout_seconds = 7.5
"""
)


def test_execute_run_from_cache_only_missing_shared_cache_skips_metadata_prefetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=METADATA_CACHE_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    metadata_calls: list[list[str]] = []

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
        cache: object,
    ) -> TmdbMetadata:
        del config, client, cache
        metadata_calls.append(filenames)
        return TmdbMetadata(
            tmdb_id=123,
            title="Fight Club",
            original_title="Fight Club",
            year=1999,
            media_type="movie",
        )

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MetricsCalculationError):
        asyncio.run(execute_run(request, deps=deps))

    assert metadata_calls == []
    assert [path.name for path in input_dir.iterdir() if path.is_dir()] == []


def test_execute_run_from_cache_only_invalid_shared_cache_skips_metadata_prefetch_and_reserve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=METADATA_CACHE_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    source_path = input_dir / "source.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_request=metric_cache_request_for_cache_inputs([source_path], config),
    )
    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    cache_dir.mkdir(parents=True)
    (cache_dir / cache_io.metrics_cache_filename([source_path], fingerprint)).write_text(
        "{not-json",
        encoding="utf-8",
    )
    metadata_calls: list[list[str]] = []
    reserve_calls: list[list[str]] = []

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
        cache: object,
    ) -> TmdbMetadata:
        del config, client, cache
        metadata_calls.append(filenames)
        return TmdbMetadata(
            tmdb_id=123,
            title="Fight Club",
            original_title="Fight Club",
            year=1999,
            media_type="movie",
        )

    def _reserve_run_folder(
        generated_root: Path,
        filenames: list[str],
        tmdb_metadata: TmdbMetadata | None,
    ) -> RunFolderReservation:
        del generated_root, tmdb_metadata
        reserve_calls.append(filenames)
        return RunFolderReservation(
            path=Path("should-not-be-used"),
            folder_name="should-not-be-used",
            base_name="should-not-be-used",
            naming_source="filename_stems",
        )

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _resolve_metadata)
    monkeypatch.setattr(preparation, "reserve_run_folder", _reserve_run_folder)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(CacheCorruptionError):
        asyncio.run(execute_run(request, deps=deps))

    assert metadata_calls == []
    assert reserve_calls == []
    assert [path.name for path in input_dir.iterdir() if path.is_dir()] == []


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
    cache_paths: list[Path] = []

    def _capture_reserve_run_folder(
        generated_root: Path, filenames: list[str], tmdb_metadata: TmdbMetadata | None
    ) -> RunFolderReservation:
        del filenames
        captured_tmdb_metadata.append(tmdb_metadata)
        return RunFolderReservation(
            path=generated_root / "Fight Club (1999)",
            folder_name="Fight Club (1999)",
            base_name="Fight Club (1999)",
            naming_source="tmdb",
        )

    async def _fake_resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
        cache: object,
    ) -> TmdbMetadata | None:
        del config, client
        cache_paths.append(cast(TmdbCache, cache).path)
        resolve_calls.append(filenames)
        return expected_metadata

    monkeypatch.setattr(preparation, "reserve_run_folder", _capture_reserve_run_folder)
    monkeypatch.setattr(phase_post_render, "resolve_metadata", _fake_resolve_metadata)

    result = asyncio.run(
        execute_run(
            RunRequest(
                root=tmp_path,
                skip_analysis=True,
                skip_metadata=False,
                no_upload=True,
            ),
            deps=RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner()),
        )
    )

    assert result.success is True
    assert captured_tmdb_metadata == [expected_metadata]
    assert resolve_calls == [["source.mkv"]]
    assert cache_paths == [(tmp_path / "generated" / "cache" / "tmdb.toml").resolve()]
    assert result.screenshot_dir is not None
    assert (
        result.screenshot_dir
        == (tmp_path / "generated" / "Fight Club (1999)" / "screenshots").resolve()
    )
    run_info = tomllib.loads(
        (tmp_path / "generated" / "Fight Club (1999)" / "run_info.toml").read_text(encoding="utf-8")
    )
    assert run_info["folder_name"] == "Fight Club (1999)"
    assert run_info["naming_source"] == "tmdb"
    assert run_info["source_filenames"] == ["source.mkv"]
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": True,
        "resolved": True,
        "failed": False,
        "tmdb_id": 123,
        "title": "Fight Club",
        "year": 1999,
        "media_type": "movie",
    }


def test_execute_run_retries_metadata_phase_when_run_folder_prefetch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=METADATA_RETRY_CONFIG)
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
    warning_fields: list[dict[str, object]] = []

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
        cache: object,
    ) -> TmdbMetadata | None:
        del client, cache
        captured_configs.append(config)
        if not prefetch_calls:
            prefetch_calls.append(filenames)
            raise TmdbError("temporary metadata failure")
        phase_calls.append(filenames)
        return expected_metadata

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _resolve_metadata)
    monkeypatch.setattr(
        preparation.log,
        "warning",
        lambda event, **fields: warning_fields.append({"event": event, **fields}),
    )

    result = asyncio.run(
        execute_run(
            RunRequest(
                root=tmp_path,
                skip_analysis=True,
                skip_metadata=False,
                no_upload=True,
            ),
            deps=RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner()),
        )
    )

    assert result.success is True
    assert result.warnings == []
    assert prefetch_calls == [["source.mkv"]]
    assert phase_calls == [["source.mkv"]]
    expected_config = MetadataConfig(
        api_key="test-key",
        unattended=True,
        timeout_seconds=7.5,
        year_tolerance=1,
        category_preference="movie",
    )
    assert captured_configs == [expected_config, expected_config]
    assert warning_fields == [
        {
            "event": "metadata_prefetch_degraded",
            "filenames": ["source.mkv"],
            "error_type": "TmdbError",
            "error": "[FC-5005] TMDB error: temporary metadata failure\nHint: Check API key",
        }
    ]
    run_info = tomllib.loads(
        (tmp_path / "generated" / "source" / "run_info.toml").read_text(encoding="utf-8")
    )
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": True,
        "resolved": False,
        "failed": True,
        "error_type": "TmdbError",
    }


def test_execute_run_propagates_unexpected_run_folder_metadata_prefetch_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=METADATA_UNEXPECTED_ERROR_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
        cache: object,
    ) -> TmdbMetadata | None:
        del filenames, config, client, cache
        raise RuntimeError("unexpected metadata failure")

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _resolve_metadata)

    with pytest.raises(RuntimeError, match="unexpected metadata failure"):
        asyncio.run(
            execute_run(
                RunRequest(
                    root=tmp_path,
                    skip_analysis=True,
                    skip_metadata=False,
                    no_upload=True,
                ),
                deps=RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner()),
            )
        )
