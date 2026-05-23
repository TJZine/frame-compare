"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from frame_compare.analysis.types import (
    CacheLoadResult,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)
from frame_compare.config import ConfigSchema, SelectionMode, load_config
from frame_compare.errors import AudioAlignmentError
from frame_compare.orchestration import phase_tasks
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.types import RunArtifacts
from frame_compare.services.publishers import PublishResult
from frame_compare.services.types import AlignmentResult, MetadataConfig, TmdbMetadata
from frame_compare.utils.types import WorkspacePaths

MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[analysis]
frame_count = 3
random_seed = 7

[audio_alignment]
enable = true
sample_rate = 12000
max_offset_seconds = 4.5
use_vspreview = true
force_interactive = false
cache_results = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> ConfigSchema:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return load_config(config_path)


def _workspace(tmp_path: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )


def _clip(path: Path, *, label: str, num_frames: int = 100) -> ClipState:
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=path, size_bytes=0, mtime_ns=0),
        width=1920,
        height=1080,
        num_frames=num_frames,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    return ClipState(
        path=path,
        label=label,
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
    )


def _context(tmp_path: Path, *, comparisons: list[ClipState] | None = None) -> RunContext:
    config = _create_config(tmp_path)
    reference_path = tmp_path / "comparison_videos" / "reference.mkv"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(b"reference")
    reference = _clip(reference_path, label="Reference")
    return RunContext(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[] if comparisons is None else comparisons,
    )


def test_resolve_run_metadata_builds_metadata_config_and_delegates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = (
        MINIMAL_CONFIG
        + """\

[tmdb]
api_key = "test-key"
enabled = true
unattended = true
timeout_seconds = 3.5
"""
    )
    config = _create_config(tmp_path, content=config_content)
    expected = TmdbMetadata(
        tmdb_id=1,
        title="Heat",
        original_title="Heat",
        year=1995,
        media_type="movie",
    )
    captured: dict[str, Any] = {}

    async def _fake_resolve_metadata(
        *,
        filenames: list[str],
        config: MetadataConfig,
        client: httpx.AsyncClient,
    ) -> TmdbMetadata:
        captured["filenames"] = filenames
        captured["config"] = config
        captured["client"] = client
        return expected

    monkeypatch.setattr(phase_tasks, "resolve_metadata", _fake_resolve_metadata)

    async def _run() -> TmdbMetadata | None:
        async with httpx.AsyncClient() as client:
            result = await phase_tasks.resolve_run_metadata(
                filenames=["Heat.1995.mkv"],
                config=config,
                client=client,
            )
            assert captured["client"] is client
            return result

    assert asyncio.run(_run()) == expected
    assert captured["filenames"] == ["Heat.1995.mkv"]
    assert captured["config"] == MetadataConfig(
        api_key="test-key",
        unattended=True,
        timeout_seconds=3.5,
    )


def test_select_initial_frame_plan_uses_effective_reference_domain(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=19)
    selected_frames: list[int] = []

    phase_tasks.select_initial_frame_plan(ctx, selected_frames=selected_frames)

    assert len(selected_frames) == 3
    assert all(0 <= frame < 10 for frame in selected_frames)


def test_run_analyze_phase_records_cache_hit_and_selection_breakdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    input_videos = [ctx.reference.path]
    metrics = FrameMetrics(
        luminance=[0.1, 0.9],
        motion=[0.2, 0.8],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24, 1),
            config_fingerprint="fingerprint",
            clips=[],
        ),
    )
    breakdown = SelectionBreakdown(quantile_dark=[1], quantile_bright=[8], motion=[13])
    selection = FrameSelection(
        frames=[1, 8, 13],
        mode=SelectionMode.MIXED,
        seed=ctx.config.analysis.random_seed,
        breakdown=breakdown,
    )
    calls: dict[str, Any] = {}

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=True, metrics=metrics)

    def _fake_calculate_metrics(**kwargs: object) -> FrameMetrics:
        calls["calculate"] = kwargs
        return metrics

    def _fake_select_frames(**kwargs: object) -> FrameSelection:
        calls["select"] = kwargs
        return selection

    monkeypatch.setattr(phase_tasks.cache_io, "load_cached_metrics", _fake_load_cached_metrics)
    monkeypatch.setattr(phase_tasks, "calculate_metrics", _fake_calculate_metrics)
    monkeypatch.setattr(phase_tasks, "select_frames", _fake_select_frames)
    artifacts = RunArtifacts()
    selected_frames: list[int] = []

    phase_tasks.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
        selected_frames=selected_frames,
        artifacts=artifacts,
    )

    assert artifacts.metrics_cache_hit is True
    assert selected_frames == [1, 8, 13]
    assert ctx.selection_breakdown == breakdown
    assert calls["calculate"]["video_paths"] == input_videos
    assert calls["calculate"]["cache_dir"] == ctx.workspace.cache_dir
    assert calls["select"] == {"metrics": metrics, "config": ctx.config.analysis}


def test_run_artifacts_legacy_render_accessors_keep_mutations() -> None:
    artifacts = RunArtifacts()
    screenshot = Path("screenshots/reference_1.png")

    artifacts.screenshots_by_label["Reference"] = [screenshot]
    artifacts.screenshot_dir = Path("screenshots")

    assert artifacts.screenshots_by_label == {"Reference": [screenshot]}
    assert artifacts.screenshot_dir == Path("screenshots")
    assert artifacts.render is not None
    assert artifacts.render.screenshots_by_label == {"Reference": [screenshot]}
    assert artifacts.render.screenshot_dir == Path("screenshots")


def test_run_align_phase_no_comparisons_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    selected_frames = [2, 4]

    def _unexpected_align(**_kwargs: object) -> list[AlignmentResult]:
        raise AssertionError("No comparisons should skip alignment work")

    monkeypatch.setattr(phase_tasks, "align_clips", _unexpected_align)

    phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert selected_frames == [2, 4]
    assert ctx.comparisons == []


def test_run_align_phase_applies_offsets_and_normalizes_selected_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    selected_frames = [0, 2, 50, 99]
    captured: dict[str, Any] = {}

    def _fake_align_clips(**kwargs: object) -> list[AlignmentResult]:
        captured.update(kwargs)
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=2,
                time_offset_seconds=0.08,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert captured["reference"] == ctx.reference.path
    assert captured["comparisons"] == [comparison.path]
    assert captured["cache_dir"] == ctx.workspace.generated_dir
    assert captured["config"].sample_rate == 12000
    assert captured["config"].max_offset_seconds == 4.5
    assert captured["config"].use_vspreview is True
    assert captured["config"].cache_results is False
    assert ctx.reference.trim.trim_start_frames == 2
    assert ctx.comparisons[0].trim.trim_start_frames == 0
    assert ctx.comparisons[0].alignment is not None
    assert ctx.comparisons[0].alignment.relative_offset_frames == 2
    assert selected_frames == [0, 48, 97]


def test_run_align_phase_raises_when_alignment_leaves_no_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv",
        label="Encode 1",
        num_frames=2,
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    selected_frames = [0, 1]

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=100,
                time_offset_seconds=4.0,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    with pytest.raises(AudioAlignmentError, match="No overlapping frames"):
        phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)


async def test_run_metadata_phase_resolves_when_enabled_and_client_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    expected = TmdbMetadata(
        tmdb_id=2,
        title="Thief",
        original_title="Thief",
        year=1981,
        media_type="movie",
    )
    captured: dict[str, Any] = {}

    async def _fake_resolve_run_metadata(**kwargs: object) -> TmdbMetadata:
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(phase_tasks, "resolve_run_metadata", _fake_resolve_run_metadata)
    artifacts = RunArtifacts()

    async with httpx.AsyncClient() as client:
        await phase_tasks.run_metadata_phase(
            ctx,
            client=client,
            prefetched_metadata=None,
            metadata_prefetched=False,
            artifacts=artifacts,
        )
        assert captured["client"] is client

    assert captured["filenames"] == ["reference.mkv"]
    assert captured["config"] == ctx.config
    assert artifacts.resolved_metadata == expected


async def test_run_publish_phase_sets_url_from_publish_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    metadata = TmdbMetadata(
        tmdb_id=3,
        title="Collateral",
        original_title="Collateral",
        year=2004,
        media_type="movie",
    )
    artifacts = RunArtifacts(resolved_metadata=metadata)
    captured: dict[str, Any] = {}

    async def _fake_publish_to_slowpics(**kwargs: object) -> PublishResult:
        captured.update(kwargs)
        return PublishResult(
            url="https://slow.pics/c/collateral",
            screenshot_count=2,
            upload_duration_seconds=0.1,
        )

    monkeypatch.setattr(phase_tasks, "publish_to_slowpics", _fake_publish_to_slowpics)

    async with httpx.AsyncClient() as client:
        await phase_tasks.run_publish_phase(ctx, client=client, artifacts=artifacts)
        assert captured["client"] is client

    assert captured["screenshot_dir"] == ctx.workspace.screenshots_dir
    assert captured["config"] == ctx.config.slowpics
    assert captured["metadata"] == metadata
    assert artifacts.slowpics_url == "https://slow.pics/c/collateral"


def test_run_report_phase_builds_report_data_and_records_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    artifacts = RunArtifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "reference_1.png"],
            "Encode 1": [tmp_path / "screenshots" / "encode_1.png"],
        },
        slowpics_url="https://slow.pics/c/example",
    )
    captured: dict[str, Any] = {}
    expected_path = tmp_path / "report.html"

    def _fake_generate_report(report_data: object, report_config: object) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        return expected_path

    monkeypatch.setattr(phase_tasks, "generate_report", _fake_generate_report)

    phase_tasks.run_report_phase(ctx, frames=[5], artifacts=artifacts)

    report_data = captured["report_data"]
    assert artifacts.report_path == expected_path
    assert report_data.frames == [5]
    assert report_data.clips[0].screenshots == artifacts.screenshots_by_label["Reference"]
    assert report_data.clips[1].screenshots == artifacts.screenshots_by_label["Encode 1"]
    assert report_data.slowpics_url == "https://slow.pics/c/example"
    assert [(clip.name, clip.resolution, clip.fps) for clip in report_data.clips] == [
        ("Reference", (1920, 1080), 24.0),
        ("Encode 1", (1920, 1080), 24.0),
    ]
    assert captured["report_config"] == ctx.config.report


def test_run_report_phase_without_screenshots_clears_existing_report_path(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    artifacts = RunArtifacts(report_path=tmp_path / "stale.html")

    phase_tasks.run_report_phase(ctx, frames=[1], artifacts=artifacts)

    assert artifacts.report_path is None


@dataclass(frozen=True)
class _RenderRunner:
    pass


def test_run_render_phase_maps_aligned_frames_to_source_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18)]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[4])
    artifacts = RunArtifacts()
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    phase_tasks.run_render_phase(
        ctx,
        frames=[1],
        runner=cast(Any, _RenderRunner()),
        artifacts=artifacts,
    )

    requests = captured["batch_requests"]
    assert requests[0].source_frames == [4]
    assert requests[0].display_frames == [1]
    assert requests[0].selection_labels == ["Dark"]
    assert requests[1].source_frames == [2]
    assert captured["output_dir"] == ctx.workspace.screenshots_dir
    assert artifacts.screenshots_by_label == {"Reference": [tmp_path / "reference.png"]}
    assert artifacts.screenshot_dir == ctx.workspace.screenshots_dir
