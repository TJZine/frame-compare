"""Cache-mode tests for execute_run."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

import frame_compare.analysis.cache_io as cache_io
import frame_compare.services.alignment_reuse_cache as alignment_reuse_cache
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
)
from frame_compare.config.loader import load_config
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from frame_compare.orchestration import phase_selection
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.utils.cache_errors import CacheVersionMismatchError

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeVSLoader,
    analysis_selection_domain_for_cache_inputs,
    create_video_files,
    metric_cache_fingerprint,
    write_metrics_cache,
    write_probe_cache_for_inputs,
)
from .phase_task_helpers import _frame_metrics
from .preparation_test_support import create_config


def _cache_config(*, analysis: str, audio_alignment: str, screenshots: str, report: str) -> str:
    return f"""[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[analysis]
{analysis}

[audio_alignment]
{audio_alignment}

[screenshots]
{screenshots}

[report]
{report}
"""


@pytest.mark.parametrize("performance", [False, True], ids=["quality", "performance"])
def test_execute_run_no_cache_deletes_only_current_scoped_metrics_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    performance: bool,
) -> None:
    create_config(
        tmp_path,
        content=_cache_config(
            analysis="random_frame_count = 0\ndark_frame_count = 1",
            audio_alignment="enable = false",
            screenshots='use_ffmpeg = true\nactive_rect_detection = "aspect_ratio"',
            report="enable = false",
        ),
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")
    config = load_config(tmp_path / "config" / "config.toml")

    if performance:
        config.analysis.performance_mode = AnalysisPerformanceMode.PERFORMANCE
        config_path = tmp_path / "config" / "config.toml"
        config_path.write_text(
            config_path.read_text().replace(
                "dark_frame_count = 1", 'dark_frame_count = 1\nperformance_mode = "performance"'
            )
        )
    analysis_cache_dir = tmp_path / "generated" / "cache" / "analysis"
    source_path = input_dir / "source.mkv"
    write_metrics_cache(analysis_cache_dir, source_path=source_path, config=config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = metric_cache_fingerprint(
        video_paths=[source_path], config=config, selection_domain=selection_domain
    )
    analysis_cache_path = cast(
        Path, cache_io.find_metrics_cache_file(analysis_cache_dir, fingerprint)
    )

    if performance:
        quality_config = config.model_copy(
            update={
                "analysis": config.analysis.model_copy(
                    update={"performance_mode": AnalysisPerformanceMode.QUALITY}
                )
            }
        )
        write_metrics_cache(analysis_cache_dir, source_path=source_path, config=quality_config)
        other_fingerprint = metric_cache_fingerprint(
            video_paths=[source_path], config=quality_config, selection_domain=selection_domain
        )
        other_cache_path = cast(
            Path, cache_io.find_metrics_cache_file(analysis_cache_dir, other_fingerprint)
        )
    else:
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
        return _frame_metrics(
            luminance=[0.1] * 100,
            motion=[0.0] * 100,
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
        )

    monkeypatch.setattr(phase_selection, "calculate_metrics", _fake_calculate_metrics)
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    asyncio.run(execute_run(request, deps=deps))

    assert not analysis_cache_path.exists()
    assert other_cache_path.exists()
    assert alignment_reuse_path.exists()


def test_execute_run_from_cache_only_fails_when_probe_cache_missing(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content=_cache_config(
            analysis="random_frame_count = 0\ndark_frame_count = 1",
            audio_alignment="enable = false",
            screenshots='use_ffmpeg = true\nactive_rect_detection = "aspect_ratio"',
            report="enable = false",
        ),
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
        content=_cache_config(
            analysis='random_frame_count = 0\ndark_frame_count = 1\nperformance_mode = "performance"',
            audio_alignment="enable = false",
            screenshots='use_ffmpeg = true\nactive_rect_detection = "aspect_ratio"',
            report="enable = false",
        ),
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


@pytest.mark.parametrize(
    ("source_config", "filenames", "analysis_filename"),
    [
        pytest.param(
            '[sources.overrides."source.mkv"]\neffective_fps = "24/1"\n',
            ("source.mkv",),
            "source.mkv",
            id="effective-fps",
        ),
        pytest.param(
            '[sources]\nreference = "reference.mkv"\nanalysis_source = "analysis.mkv"\n',
            ("reference.mkv", "analysis.mkv"),
            "analysis.mkv",
            id="analysis-source",
        ),
        pytest.param(
            '[sources.overrides."source.mkv"]\nactive_rect = { x = 10, y = 20, width = 300, height = 200 }\n',
            ("source.mkv",),
            "source.mkv",
            id="active-rect",
        ),
    ],
)
def test_execute_run_from_cache_only_uses_scoped_cache(
    tmp_path: Path,
    source_config: str,
    monkeypatch: pytest.MonkeyPatch,
    filenames: tuple[str, ...],
    analysis_filename: str,
) -> None:
    config_content = (
        _cache_config(
            analysis="random_frame_count = 0\ndark_frame_count = 1",
            audio_alignment="enable = false",
            screenshots='use_ffmpeg = true\nactive_rect_detection = "aspect_ratio"',
            report="enable = false",
        )
        + source_config
    )
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, *filenames)
    config = load_config(tmp_path / "config" / "config.toml")
    paths = [input_dir / filename for filename in filenames]
    write_metrics_cache(
        tmp_path / "generated" / "cache" / "analysis",
        source_path=paths[0],
        config=config,
        video_paths=paths,
        analysis_source_path=input_dir / analysis_filename,
    )
    request = RunRequest(
        root=tmp_path, from_cache_only=True, skip_analysis=False, skip_metadata=True, no_upload=True
    )
    diagnostics_by_stage: dict[str, list[str]] = {}

    def _record_emit(
        *, stage: str, diagnostics: list[str] | tuple[str, ...] = (), **_kwargs: object
    ) -> None:
        diagnostics_by_stage[stage] = list(diagnostics)

    monkeypatch.setattr(
        "frame_compare.orchestration.coordinator.emit_consolidated_fps_report", _record_emit
    )
    result = asyncio.run(
        execute_run(
            request,
            deps=RunDependencies(
                vs_loader=FakeVSLoader(),
                ffmpeg_runner=FakeFFmpegRunner(),
            ),
        )
    )

    assert result.success is True
    assert result.cache_hit is True

    if analysis_filename == "analysis.mkv":
        assert diagnostics_by_stage["after_load_sources"] == [
            "Analysis source: Comparison 1 | selected by configured policy"
        ]


def test_execute_run_from_cache_only_rejects_full_frame_cache_for_active_rect_source(
    tmp_path: Path,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[sources.overrides."source.mkv"]
active_rect = { x = 10, y = 20, width = 300, height = 200 }

[analysis]
random_frame_count = 0
dark_frame_count = 1

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true
active_rect_detection = "aspect_ratio"

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


def test_execute_run_from_cache_only_fails_when_metrics_cache_version_mismatch(
    tmp_path: Path,
) -> None:
    create_config(
        tmp_path,
        content=_cache_config(
            analysis="random_frame_count = 0\ndark_frame_count = 1",
            audio_alignment="enable = false",
            screenshots='use_ffmpeg = true\nactive_rect_detection = "aspect_ratio"',
            report="enable = false",
        ),
    )
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    cache_dir = tmp_path / "generated" / "cache" / "analysis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(tmp_path / "config" / "config.toml")
    source_path = input_dir / "source.mkv"
    write_probe_cache_for_inputs(tmp_path / "generated" / "clip_probe.toml", [source_path], config)
    selection_domain = analysis_selection_domain_for_cache_inputs([source_path], config)
    fingerprint = metric_cache_fingerprint(
        video_paths=[source_path], config=config, selection_domain=selection_domain
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
    config_content = _cache_config(
        analysis="random_frame_count = 0\ndark_frame_count = 1",
        audio_alignment="enable = true",
        screenshots='use_ffmpeg = true\nactive_rect_detection = "aspect_ratio"',
        report="enable = false",
    )
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
