"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from frame_compare.analysis.types import (
    SelectionBreakdown,
)
from frame_compare.orchestration import phase_tasks
from frame_compare.orchestration.types import MetadataPrefetch, RenderArtifacts, RunArtifacts
from frame_compare.services.publishers import PublishResult
from frame_compare.services.types import TmdbMetadata
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
    _RenderRunner,
)


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

    async with httpx.AsyncClient() as client:
        output = await phase_tasks.run_metadata_phase(
            ctx,
            client=client,
            metadata_prefetch=MetadataPrefetch(None, False),
        )
        assert captured["client"] is client

    assert captured["filenames"] == ["reference.mkv"]
    assert captured["config"] == ctx.config
    assert output.resolved_metadata == expected


def test_run_report_phase_builds_report_data_and_records_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "reference_1.png"],
            "Encode 1": [tmp_path / "screenshots" / "encode_1.png"],
        },
        screenshot_dir=tmp_path / "screenshots",
    )
    artifacts = RunArtifacts(
        render=render,
        slowpics_url="https://slow.pics/c/example",
    )
    captured: dict[str, Any] = {}
    expected_path = tmp_path / "report.html"

    def _fake_generate_report(report_data: object, report_config: object) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        return expected_path

    monkeypatch.setattr(phase_tasks, "generate_report", _fake_generate_report)

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[5],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_path
    assert artifacts.report_path is None
    assert report_data.frames == [5]
    assert report_data.clips[0].screenshots == render.screenshots_by_label["Reference"]
    assert report_data.clips[1].screenshots == render.screenshots_by_label["Encode 1"]
    assert report_data.slowpics_url == "https://slow.pics/c/example"
    assert [(clip.name, clip.resolution, clip.fps) for clip in report_data.clips] == [
        ("Reference", (1920, 1080), 24.0),
        ("Encode 1", (1920, 1080), 24.0),
    ]
    assert captured["report_config"] == ctx.config.report


def test_run_render_phase_maps_aligned_frames_to_source_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18)]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[4])
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    runner = cast(Any, _RenderRunner())
    output = phase_tasks.run_render_phase(
        ctx,
        frames=[1],
        runner=runner,
    )

    requests = captured["batch_requests"]
    assert requests[0].source_frames == [4]
    assert requests[0].display_frames == [1]
    assert requests[0].selection_labels == ["Dark"]
    assert requests[1].source_frames == [2]
    assert captured["output_dir"] == ctx.workspace.screenshots_dir
    options = captured["options"]
    assert options.overlay_mode == ctx.config.screenshots.overlay_mode
    assert options.ffmpeg_runner is runner
    assert options.reporter is ctx.reporter
    assert output.render == RenderArtifacts(
        screenshots_by_label={"Reference": [tmp_path / "reference.png"]},
        screenshot_dir=ctx.workspace.screenshots_dir,
    )


def test_run_report_phase_without_screenshots_clears_existing_report_path(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    artifacts = RunArtifacts(report_path=tmp_path / "stale.html")

    output = phase_tasks.run_report_phase(
        ctx,
        frames=[1],
        render=artifacts.render,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )

    assert output.report_path is None
    assert artifacts.report_path == tmp_path / "stale.html"


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
        output = await phase_tasks.run_publish_phase(ctx, client=client, metadata=metadata)
        assert captured["client"] is client

    assert captured["screenshot_dir"] == ctx.workspace.screenshots_dir
    assert captured["config"] == ctx.config.slowpics
    assert captured["metadata"] == metadata
    assert output.slowpics_url == "https://slow.pics/c/collateral"
