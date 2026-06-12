"""Run-folder behavior tests for execute_run."""

from __future__ import annotations

import asyncio
import tomllib
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

import httpx
import pytest

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricActiveRect,
    MetricsMetadata,
)
from frame_compare.config.loader import load_config
from frame_compare.config.schema import AnalysisConfig
from frame_compare.orchestration import phase_post_render, phase_selection, preparation
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.probing.probe_cache import load_clip_probe_cache
from frame_compare.services.errors import TmdbError
from frame_compare.services.run_folder import RunFolderReservation, derive_run_folder_name
from frame_compare.services.types import MetadataConfig, TmdbMetadata
from frame_compare.utils.cache_errors import CacheCorruptionError
from frame_compare.vs.types import SourceInfo
from frame_compare.vspreview.overrides import MANUAL_OVERRIDES_FILE

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    FakeVSLoader,
    analysis_selection_domain_for_cache_inputs,
    create_config,
    create_video_files,
    metric_active_rect_for_cache_inputs,
    write_metrics_cache,
    write_probe_cache_for_inputs,
)

if TYPE_CHECKING:
    import vapoursynth as vs


METRIC_RUN_FOLDERS_CONFIG = (
    RUN_FOLDERS_CONFIG
    + """
[analysis]
random_frame_count = 0
dark_frame_count = 1
"""
)


class ClipStub:
    num_frames = 100


class FormatStub:
    pass


class AnalysisCapableVSLoader:
    def load(self, path: Path) -> SourceInfo:
        del path
        return SourceInfo(
            clip=cast("vs.VideoNode", ClipStub()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast("vs.VideoFormat", FormatStub()),
            frame_props={},
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> object:
        raise RuntimeError("ensure_core should not be called in this test")


class NoProbeVSLoader:
    def load(self, path: Path) -> SourceInfo:
        del path
        raise AssertionError("run_info write failure should happen before probing")

    def ensure_core(self) -> object:
        raise AssertionError("run_info write failure should happen before VS core access")


def test_execute_run_no_cache_deletes_shared_cache_when_run_folders_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    config = load_config(tmp_path / "config" / "config.toml")

    run_name = "Movie (2024)"
    monkeypatch.setattr(
        preparation,
        "reserve_run_folder",
        lambda input_dir, **_kwargs: RunFolderReservation(
            path=input_dir / run_name,
            folder_name=run_name,
            base_name=run_name,
            naming_source="parsed_metadata",
        ),
    )
    run_generated_dir = input_dir / run_name / "generated"

    analysis_cache_dir = tmp_path / "generated" / "cache" / "analysis"
    source_path = input_dir / "source.mkv"
    write_metrics_cache(analysis_cache_dir, source_path=source_path, config=config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
    )
    analysis_cache_path = cache_io.find_metrics_cache_file(analysis_cache_dir, fingerprint)
    assert analysis_cache_path is not None

    run_generated_dir.mkdir(parents=True, exist_ok=True)
    manual_overrides_path = run_generated_dir / MANUAL_OVERRIDES_FILE
    manual_overrides_path.write_text('version = "1"\n', encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        no_cache=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )

    def _fake_calculate_metrics(**_kwargs: object) -> FrameMetrics:
        return FrameMetrics(
            luminance=[0.1] * 100,
            motion=[0.0] * 100,
            metadata=MetricsMetadata(
                frame_count=100,
                fps=Fraction(24, 1),
                config_fingerprint="fingerprint",
                clips=[
                    ClipIdentity(
                        path=str(source_path),
                        size=source_path.stat().st_size,
                        mtime=source_path.stat().st_mtime,
                        sha1=None,
                    )
                ],
            ),
        )

    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)
    deps = RunDependencies(vs_loader=AnalysisCapableVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert not analysis_cache_path.exists()
    assert manual_overrides_path.exists()


def test_execute_run_from_cache_only_does_not_reserve_run_folder_when_metrics_cache_missing(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_dir = input_dir / run_name

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(MetricsCalculationError):
        asyncio.run(execute_run(request, deps=deps))

    assert not run_dir.exists()


def test_execute_run_from_cache_only_uses_shared_cache_when_run_folders_enabled(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    write_metrics_cache(cache_dir, source_path=source_path, config=config)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    assert result.success is True
    assert result.cache_hit is True
    assert result.warnings == []
    assert result.screenshot_dir == (input_dir / run_name / "screenshots").resolve()
    assert result.slowpics_url is None
    assert not (input_dir / run_name / "generated" / "cache" / "analysis").exists()
    assert (input_dir / run_name / "run_info.toml").exists()


def test_execute_run_custom_generated_dir_run_folders_saves_and_loads_shared_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "custom_generated"
config_dir = "config"
use_run_folders = true

[analysis]
random_frame_count = 0
dark_frame_count = 1

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
    source_path = input_dir / "source.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
    )

    def _fake_calculate_metrics(
        *,
        video_paths: list[Path],
        config: AnalysisConfig,
        cache_dir: Path,
        analysis_source_path: Path | None = None,
        metric_active_rect: MetricActiveRect | None = None,
        selection_domain: str | None = None,
        **_kwargs: object,
    ) -> FrameMetrics:
        cache_fingerprint = cache_io.compute_cache_key(
            video_paths,
            config,
            selection_domain=selection_domain,
            metric_active_rect=metric_active_rect,
        )
        stats_by_path = {path: path.stat() for path in video_paths}
        resolved_analysis_source_path = (
            video_paths[0] if analysis_source_path is None else analysis_source_path
        )
        metrics = FrameMetrics(
            luminance=[0.1] * 100,
            motion=[0.0] * 100,
            metadata=MetricsMetadata(
                frame_count=100,
                fps=Fraction(24, 1),
                config_fingerprint=cache_fingerprint,
                clips=[
                    ClipIdentity(
                        path=str(path),
                        size=stats_by_path[path].st_size,
                        mtime=stats_by_path[path].st_mtime,
                    )
                    for path in video_paths
                ],
                analysis_source_path=str(resolved_analysis_source_path),
                performance_mode=config.performance_mode.value,
                algorithm_id=metric_algorithm_id(config),
                metric_backend=metric_backend(config),
                algorithm_identity_json=stable_metric_algorithm_identity_json(config),
                metric_active_rect=metric_active_rect,
                version=cache_io.CACHE_VERSION,
            ),
        )
        cache_io.save_metrics_cache(metrics, cache_dir)
        return metrics

    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)

    first = asyncio.run(
        execute_run(
            RunRequest(
                root=tmp_path,
                skip_analysis=False,
                skip_metadata=True,
                no_upload=True,
            ),
            deps=RunDependencies(
                vs_loader=AnalysisCapableVSLoader(),
                ffmpeg_runner=FakeFFmpegRunner(),
            ),
        )
    )

    shared_cache_dir = tmp_path / "custom_generated" / "cache" / "analysis"
    shared_cache_path = cache_io.find_metrics_cache_file(shared_cache_dir, fingerprint)
    assert first.success is True
    assert first.cache_hit is False
    assert shared_cache_path is not None
    assert (tmp_path / "custom_generated" / "clip_probe.toml").exists()
    assert not any(input_dir.glob("*/generated/cache/analysis/*.compframes"))

    def _fail_calculate_metrics(**_kwargs: object) -> NoReturn:
        raise AssertionError("from-cache-only should load the shared analysis cache")

    monkeypatch.setattr(phase_selection, "calculate_metrics", _fail_calculate_metrics)

    second = asyncio.run(
        execute_run(
            RunRequest(
                root=tmp_path,
                from_cache_only=True,
                skip_analysis=False,
                skip_metadata=True,
                no_upload=True,
            ),
            deps=RunDependencies(
                vs_loader=AnalysisCapableVSLoader(),
                ffmpeg_runner=FakeFFmpegRunner(),
            ),
        )
    )

    assert second.success is True
    assert second.cache_hit is True
    assert second.screenshot_dir is not None
    assert second.screenshot_dir.parent.parent == input_dir
    run_dirs = [path for path in input_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 2
    assert all((run_dir / "generated" / "clip_probe.toml").exists() for run_dir in run_dirs)


def test_execute_run_cache_only_run_folder_probe_snapshot_excludes_unrelated_shared_entries(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "unrelated.mkv")
    source_path = input_dir / "source.mkv"
    unrelated_path = input_dir / "unrelated.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    write_probe_cache_for_inputs(
        tmp_path / "generated" / "clip_probe.toml",
        [source_path, unrelated_path],
        config,
    )
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=source_path,
        config=config,
    )
    unrelated_path.unlink()

    result = asyncio.run(
        execute_run(
            RunRequest(
                root=tmp_path,
                from_cache_only=True,
                skip_analysis=False,
                skip_metadata=True,
                no_upload=True,
            ),
            deps=RunDependencies(
                vs_loader=AnalysisCapableVSLoader(),
                ffmpeg_runner=FakeFFmpegRunner(),
            ),
        )
    )

    assert result.success is True
    assert result.cache_hit is True
    assert result.screenshot_dir is not None
    run_probe_cache = load_clip_probe_cache(
        result.screenshot_dir.parent / "generated" / "clip_probe.toml"
    )
    assert {snapshot.fingerprint.path for snapshot in run_probe_cache.values()} == {source_path}


def test_execute_run_normal_rerun_creates_fresh_run_folder_and_uses_shared_cache(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    existing_run_dir = input_dir / run_name
    existing_run_dir.mkdir()
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=source_path,
        config=config,
    )

    request = RunRequest(
        root=tmp_path,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert result.screenshot_dir != (existing_run_dir / "screenshots").resolve()
    assert result.screenshot_dir is not None
    assert result.screenshot_dir.parent.parent == input_dir
    assert len([path for path in input_dir.iterdir() if path.is_dir()]) == 2


def test_execute_run_from_cache_only_ignores_old_run_folder_cache(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_generated_dir = input_dir / run_name / "generated"
    source_path = input_dir / "source.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    write_metrics_cache(run_generated_dir / "cache", source_path=source_path, config=config)

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MetricsCalculationError):
        asyncio.run(execute_run(request, deps=deps))

    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
    )
    assert sorted(path.name for path in input_dir.iterdir() if path.is_dir()) == [run_name]
    assert (
        cache_io.find_metrics_cache_file(
            tmp_path / "generated" / "cache" / "analysis",
            fingerprint,
        )
        is None
    )


def test_execute_run_from_cache_only_missing_shared_cache_skips_metadata_prefetch(
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

[analysis]
random_frame_count = 0
dark_frame_count = 1

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
    metadata_calls: list[list[str]] = []

    async def _resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata:
        del config, client
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
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[analysis]
random_frame_count = 0
dark_frame_count = 1

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
    source_path = input_dir / "source.mkv"
    config = load_config(tmp_path / "config" / "config.toml")
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
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
    ) -> TmdbMetadata:
        del config, client
        metadata_calls.append(filenames)
        return TmdbMetadata(
            tmdb_id=123,
            title="Fight Club",
            original_title="Fight Club",
            year=1999,
            media_type="movie",
        )

    def _reserve_run_folder(
        input_dir: Path,
        filenames: list[str],
        tmdb_metadata: TmdbMetadata | None,
    ) -> RunFolderReservation:
        del input_dir, tmdb_metadata
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

    def _capture_reserve_run_folder(
        input_dir: Path, filenames: list[str], tmdb_metadata: TmdbMetadata | None
    ) -> RunFolderReservation:
        del filenames
        captured_tmdb_metadata.append(tmdb_metadata)
        return RunFolderReservation(
            path=input_dir / "Fight Club (1999)",
            folder_name="Fight Club (1999)",
            base_name="Fight Club (1999)",
            naming_source="tmdb",
        )

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
    monkeypatch.setattr(phase_post_render, "resolve_metadata", _fake_resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert captured_tmdb_metadata == [expected_metadata]
    assert resolve_calls == [["source.mkv"]]
    assert result.screenshot_dir is not None
    assert result.screenshot_dir == (input_dir / "Fight Club (1999)" / "screenshots").resolve()
    run_info = tomllib.loads(
        (input_dir / "Fight Club (1999)" / "run_info.toml").read_text(encoding="utf-8")
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
year_tolerance = 1
category_preference = "movie"
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

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.warnings == []
    assert prefetch_calls == [["source.mkv"]]
    assert phase_calls == [["source.mkv"]]
    assert captured_configs == [
        MetadataConfig(
            api_key="test-key",
            unattended=True,
            timeout_seconds=7.5,
            year_tolerance=1,
            category_preference="movie",
        ),
        MetadataConfig(
            api_key="test-key",
            unattended=True,
            timeout_seconds=7.5,
            year_tolerance=1,
            category_preference="movie",
        ),
    ]
    run_info_path = input_dir / "source" / "run_info.toml"
    run_info = tomllib.loads(run_info_path.read_text(encoding="utf-8"))
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": True,
        "resolved": False,
        "failed": True,
        "error_type": "TmdbError",
    }


def test_execute_prep_writes_run_info_with_clock_and_no_http_client_skip(
    tmp_path: Path,
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
    create_video_files(input_dir, "source.mkv", "encode.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
        clock=lambda: datetime(2026, 6, 8, 15, 30, 45, tzinfo=UTC),
    )

    result = asyncio.run(preparation.execute_prep(request, deps=deps))

    assert result.workspace.run_dir is not None
    run_info_path = result.workspace.run_dir / "run_info.toml"
    run_info = tomllib.loads(run_info_path.read_text(encoding="utf-8"))
    assert run_info["created_at"] == "2026-06-08T15:30:45Z"
    assert run_info["source_filenames"] == ["encode.mkv", "source.mkv"]
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": False,
        "resolved": False,
        "failed": False,
        "skip_reason": "no_http_client",
    }


def test_execute_run_writes_run_info_with_skip_metadata_facts(
    tmp_path: Path,
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

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.screenshot_dir is not None
    run_info = tomllib.loads(
        (result.screenshot_dir.parent / "run_info.toml").read_text(encoding="utf-8")
    )
    assert run_info["tmdb"] == {
        "enabled": True,
        "attempted": False,
        "resolved": False,
        "failed": False,
        "skip_reason": "skip_metadata",
    }


def test_execute_run_run_info_write_failure_happens_before_probing_and_cleans_empty_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(tmp_path, content=RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    def _fail_write_run_info(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(preparation, "write_run_info", _fail_write_run_info)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=NoProbeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(OSError, match="disk full"):
        asyncio.run(execute_run(request, deps=deps))

    assert [path.name for path in input_dir.iterdir() if path.is_dir()] == []


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

    monkeypatch.setattr(phase_post_render, "resolve_metadata", _resolve_metadata)

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=False,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(RuntimeError, match="unexpected metadata failure"):
        asyncio.run(execute_run(request, deps=deps))
