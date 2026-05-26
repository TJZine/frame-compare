"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import Any

import httpx
import pytest

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import (
    CacheLoadResult,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)
from frame_compare.config.schema import SelectionMode
from frame_compare.orchestration import phase_tasks
from frame_compare.orchestration.types import RenderArtifacts, RunArtifacts
from frame_compare.services.types import MetadataConfig, TmdbMetadata
from tests.orchestration.phase_task_helpers import (
    MINIMAL_CONFIG,
    _context,
    _create_config,
)


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
    selected_frames: list[int] = []

    output = phase_tasks.run_analyze_phase(
        ctx,
        input_videos=input_videos,
        workspace=ctx.workspace,
    )

    assert output.metrics_cache_hit is True
    assert output.selected_frames == [1, 8, 13]
    assert output.selection_breakdown == breakdown
    assert selected_frames == []
    assert ctx.selection_breakdown is None
    assert calls["calculate"]["video_paths"] == input_videos
    assert calls["calculate"]["cache_dir"] == ctx.workspace.cache_dir
    assert calls["select"] == {"metrics": metrics, "config": ctx.config.analysis}


def test_run_analyze_phase_cache_only_missing_cache_does_not_recompute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    input_videos = [ctx.reference.path]

    def _fake_load_cached_metrics(*_args: object, **_kwargs: object) -> CacheLoadResult:
        return CacheLoadResult(success=False, reason="not_found")

    def _fake_calculate_metrics(**_kwargs: object) -> FrameMetrics:
        raise AssertionError("cache-only analyze phase must not recompute metrics")

    monkeypatch.setattr(phase_tasks.cache_io, "load_cached_metrics", _fake_load_cached_metrics)
    monkeypatch.setattr(phase_tasks, "calculate_metrics", _fake_calculate_metrics)

    with pytest.raises(MetricsCalculationError, match="Cached metrics missing"):
        phase_tasks.run_analyze_phase(
            ctx,
            input_videos=input_videos,
            workspace=ctx.workspace,
            require_cache_only=True,
        )


def test_select_initial_frame_plan_uses_effective_reference_domain(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=19)
    selected_frames: list[int] = []

    output = phase_tasks.select_initial_frame_plan(ctx)

    assert selected_frames == []
    assert len(output.selected_frames) == 3
    assert all(0 <= frame < 10 for frame in output.selected_frames)


def test_run_artifacts_uses_render_artifacts_carrier() -> None:
    artifacts = RunArtifacts()
    assert artifacts.render is None

    screenshot = Path("screenshots/reference_1.png")
    artifacts.render = RenderArtifacts(
        screenshots_by_label={"Reference": [screenshot]},
        screenshot_dir=Path("screenshots"),
    )

    assert artifacts.render.screenshots_by_label == {"Reference": [screenshot]}
    assert artifacts.render.screenshot_dir == Path("screenshots")


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
