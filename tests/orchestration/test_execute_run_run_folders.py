"""Run-folder behavior tests for execute_run."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

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
    MetricCacheRequest,
    MetricsMetadata,
)
from frame_compare.config.loader import load_config
from frame_compare.config.schema import AnalysisConfig
from frame_compare.orchestration import phase_selection, preparation
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.probing.probe_cache import load_clip_probe_cache
from frame_compare.services.run_folder import RunFolderReservation, derive_run_folder_name
from frame_compare.vs.types import SourceInfo
from frame_compare.vspreview.overrides import MANUAL_OVERRIDES_FILE

from .execute_run_helpers import (
    RUN_FOLDERS_CONFIG,
    FakeFFmpegRunner,
    FakeVSLoader,
    analysis_selection_domain_for_cache_inputs,
    create_config,
    create_video_files,
    metric_cache_request_for_cache_inputs,
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
    run_generated_dir = tmp_path / "generated" / run_name / "generated"

    analysis_cache_dir = tmp_path / "generated" / "cache" / "analysis"
    source_path = input_dir / "source.mkv"
    write_metrics_cache(analysis_cache_dir, source_path=source_path, config=config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_request=metric_cache_request_for_cache_inputs([source_path], config),
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
    run_dir = tmp_path / "generated" / run_name

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
    assert result.screenshot_dir == (tmp_path / "generated" / run_name / "screenshots").resolve()
    assert result.slowpics_url is None
    assert not (tmp_path / "generated" / run_name / "generated" / "cache" / "analysis").exists()
    assert (tmp_path / "generated" / run_name / "run_info.toml").exists()
    assert [path for path in input_dir.iterdir() if path.is_dir()] == []


def test_execute_prep_external_input_reserves_outputs_only_under_generated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    create_config(root, content=RUN_FOLDERS_CONFIG)
    external_input = tmp_path / "external-media"
    create_video_files(external_input, "source.mkv")

    prep = asyncio.run(
        preparation.execute_prep(
            RunRequest(
                root=root,
                input_dir=external_input,
                skip_analysis=True,
                skip_metadata=True,
                no_upload=True,
            ),
            deps=RunDependencies(
                vs_loader=FakeVSLoader(),
                ffmpeg_runner=FakeFFmpegRunner(),
            ),
        )
    )

    assert prep.workspace.input_dir == external_input.resolve()
    assert prep.workspace.run_dir is not None
    assert prep.workspace.run_dir.is_relative_to((root / "generated").resolve())
    assert prep.workspace.screenshots_dir.is_relative_to(prep.workspace.run_dir)
    assert prep.workspace.generated_dir.is_relative_to(prep.workspace.run_dir)
    assert [path for path in external_input.iterdir() if path.is_dir()] == []


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
        metric_request=metric_cache_request_for_cache_inputs([source_path], config),
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
        resolved_analysis_source_path = (
            video_paths[0] if analysis_source_path is None else analysis_source_path
        )
        cache_fingerprint = cache_io.compute_cache_key(
            video_paths,
            config,
            selection_domain=selection_domain,
            metric_request=MetricCacheRequest(
                analysis_source_path=resolved_analysis_source_path,
                effective_fps=Fraction(24, 1),
                metric_active_rect=metric_active_rect,
            ),
        )
        stats_by_path = {path: path.stat() for path in video_paths}
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
    assert second.screenshot_dir.parent.parent == tmp_path / "custom_generated"
    run_dirs = [
        path
        for path in (tmp_path / "custom_generated").iterdir()
        if (path / "run_info.toml").exists()
    ]
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
    existing_run_dir = tmp_path / "generated" / run_name
    existing_run_dir.mkdir(parents=True)
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
    assert result.screenshot_dir.parent.parent == tmp_path / "generated"
    run_dirs = [
        path
        for path in (tmp_path / "generated").iterdir()
        if path.is_dir() and (path.name == run_name or path.name.startswith(f"{run_name}_"))
    ]
    assert len(run_dirs) == 2
    assert [path for path in input_dir.iterdir() if path.is_dir()] == []


def test_execute_run_from_cache_only_ignores_old_run_folder_cache(
    tmp_path: Path,
) -> None:
    create_config(tmp_path, content=METRIC_RUN_FOLDERS_CONFIG)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    run_name = derive_run_folder_name(filenames=["source.mkv"])
    run_generated_dir = tmp_path / "generated" / run_name / "generated"
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
        metric_request=metric_cache_request_for_cache_inputs([source_path], config),
    )
    assert run_generated_dir.exists()
    assert [path for path in input_dir.iterdir() if path.is_dir()] == []
    assert (
        cache_io.find_metrics_cache_file(
            tmp_path / "generated" / "cache" / "analysis",
            fingerprint,
        )
        is None
    )
