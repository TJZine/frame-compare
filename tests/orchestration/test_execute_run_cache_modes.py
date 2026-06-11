"""Cache-mode tests for execute_run."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path

import pytest

import frame_compare.analysis.cache_io as cache_io
import frame_compare.services.alignment_reuse_cache as alignment_reuse_cache
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricActiveRect,
    MetricsMetadata,
)
from frame_compare.config.loader import load_config
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from frame_compare.orchestration import phase_selection
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeVSLoader,
    analysis_selection_domain_for_cache_inputs,
    create_config,
    create_video_files,
    metric_active_rect_for_cache_inputs,
    write_metrics_cache,
    write_probe_cache_for_inputs,
)


def test_execute_run_no_cache_deletes_only_matching_shared_metrics_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[analysis]
random_frame_count = 0
dark_frame_count = 1

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
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
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
    )
    analysis_cache_path = cache_io.find_metrics_cache_file(analysis_cache_dir, fingerprint)
    assert analysis_cache_path is not None

    other_cache_path = analysis_cache_dir / "other__other.compframes"
    other_cache_path.write_text("{}", encoding="utf-8")

    alignment_reuse_path = (
        tmp_path / "generated" / "cache" / "alignment" / alignment_reuse_cache.CACHE_FILE_NAME
    )
    alignment_reuse_path.parent.mkdir(parents=True, exist_ok=True)
    alignment_reuse_path.write_text(
        f'version = "{alignment_reuse_cache.CACHE_VERSION}"\nsource_sets = {{}}\n',
        encoding="utf-8",
    )

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
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert not analysis_cache_path.exists()
    assert other_cache_path.exists()
    assert alignment_reuse_path.exists()


def test_execute_run_no_cache_deletes_only_current_performance_mode_metrics_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[analysis]
random_frame_count = 0
dark_frame_count = 1
performance_mode = "performance"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    config = load_config(tmp_path / "config" / "config.toml")
    quality_config = config.model_copy(
        update={
            "analysis": config.analysis.model_copy(
                update={"performance_mode": AnalysisPerformanceMode.QUALITY}
            )
        }
    )
    analysis_cache_dir = tmp_path / "generated" / "cache" / "analysis"
    source_path = input_dir / "source.mkv"
    write_metrics_cache(analysis_cache_dir, source_path=source_path, config=quality_config)
    write_metrics_cache(analysis_cache_dir, source_path=source_path, config=config)

    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    quality_fingerprint = cache_io.compute_cache_key(
        [source_path],
        quality_config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], quality_config),
    )
    performance_fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
    )
    quality_cache_path = cache_io.find_metrics_cache_file(analysis_cache_dir, quality_fingerprint)
    performance_cache_path = cache_io.find_metrics_cache_file(
        analysis_cache_dir, performance_fingerprint
    )
    assert quality_cache_path is not None
    assert performance_cache_path is not None

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
    request = RunRequest(
        root=tmp_path,
        no_cache=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert quality_cache_path.exists()
    assert not performance_cache_path.exists()


def test_execute_run_from_cache_only_fails_when_metrics_cache_missing(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[analysis]
random_frame_count = 0
dark_frame_count = 1

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

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


def test_execute_run_from_cache_only_rejects_cache_for_other_performance_mode(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[analysis]
random_frame_count = 0
dark_frame_count = 1
performance_mode = "performance"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    config = load_config(tmp_path / "config" / "config.toml")
    quality_config = config.model_copy(
        update={
            "analysis": config.analysis.model_copy(
                update={"performance_mode": AnalysisPerformanceMode.QUALITY}
            )
        }
    )
    source_path = input_dir / "source.mkv"
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=source_path,
        config=quality_config,
    )

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MetricsCalculationError, match="Cached metrics missing or mismatched"):
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
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True


def test_execute_run_from_cache_only_uses_cache_for_configured_analysis_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[sources]
reference = "reference.mkv"
analysis_source = "analysis.mkv"

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
    create_video_files(input_dir, "reference.mkv", "analysis.mkv")
    config = load_config(tmp_path / "config" / "config.toml")
    reference_path = input_dir / "reference.mkv"
    analysis_path = input_dir / "analysis.mkv"
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=reference_path,
        config=config,
        video_paths=[reference_path, analysis_path],
        analysis_source_path=analysis_path,
    )

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    diagnostics_by_stage: dict[str, list[str]] = {}

    def _record_emit(
        *,
        stage: str,
        diagnostics: list[str] | tuple[str, ...] = (),
        **_kwargs: object,
    ) -> None:
        diagnostics_by_stage[stage] = list(diagnostics)

    monkeypatch.setattr(
        "frame_compare.orchestration.coordinator.emit_consolidated_fps_report",
        _record_emit,
    )

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True
    assert diagnostics_by_stage["after_load_sources"] == [
        "Analysis source: analysis.mkv (configured)"
    ]


def test_execute_run_from_cache_only_rejects_full_frame_cache_for_active_rect_source(
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
active_rect = { x = 10, y = 20, width = 300, height = 200 }

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
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)
    full_frame_fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=selection_domain,
    )
    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    full_frame_cache_path = cache_dir / cache_io.metrics_cache_filename(
        [source_path],
        full_frame_fingerprint,
    )
    full_frame_cache_path.write_text("{}", encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(MetricsCalculationError, match="Cached metrics missing"):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_uses_active_rect_specific_cache(
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
active_rect = { x = 10, y = 20, width = 300, height = 200 }

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
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=source_path,
        config=config,
    )
    active_rect_fingerprint = cache_io.compute_cache_key(
        [source_path],
        config.analysis,
        selection_domain=analysis_selection_domain_for_cache_inputs([source_path], config),
        metric_active_rect=MetricActiveRect(x=10, y=20, width=300, height=200),
    )
    assert cache_io.find_metrics_cache_file(
        tmp_path / "generated" / "cache" / "analysis",
        active_rect_fingerprint,
    )

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.cache_hit is True


def test_execute_run_from_cache_only_fails_when_metrics_cache_invalid(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[analysis]
random_frame_count = 0
dark_frame_count = 1

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
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
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
    )
    cache_path = cache_dir / cache_io.metrics_cache_filename([source_path], fingerprint)
    cache_path.write_text("{not-json", encoding="utf-8")

    request = RunRequest(
        root=tmp_path,
        from_cache_only=True,
        skip_analysis=False,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(CacheCorruptionError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_fails_when_metrics_cache_version_mismatch(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content="""\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[analysis]
random_frame_count = 0
dark_frame_count = 1

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
""",
    )
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
        metric_active_rect=metric_active_rect_for_cache_inputs([source_path], config),
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
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader())

    with pytest.raises(CacheVersionMismatchError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_from_cache_only_requires_probe_cache_before_alignment_when_alignment_enabled(
    tmp_path: Path,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[analysis]
random_frame_count = 0
dark_frame_count = 1

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
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MetricsCalculationError, match="Cached clip probe data is required"):
        asyncio.run(execute_run(request, deps=deps))
