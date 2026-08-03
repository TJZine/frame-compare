"""Cross-phase output integration contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from frame_compare.analysis.types import (
    FrameMetrics,
    MetricsMetadata,
)
from frame_compare.orchestration import phase_post_render, phase_tasks
from frame_compare.orchestration.execution_types import (
    RenderArtifacts,
)
from frame_compare.services.publishers import PublishResult
from frame_compare.services.slowpics_post_upload import (
    SlowpicsPostUploadRequest,
)
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
    _RenderRunner,
)


def test_output_phases_use_reselected_metric_metadata_after_real_initial_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 2, "bright_frame_count": 0}
    )
    luminance = [0.5 for _frame in range(100)]
    luminance[0] = 0.0
    luminance[1] = 0.01
    luminance[50] = 0.99
    luminance[60] = 1.0
    ctx.analysis_metrics = FrameMetrics(
        luminance=luminance,
        motion=[0.0 for _ in range(100)],
        metadata=MetricsMetadata(
            frame_count=100,
            fps=ctx.reference.effective_fps,
            config_fingerprint="test",
            clips=[],
        ),
    )
    initial_selection = phase_tasks.select_frames(
        metrics=ctx.analysis_metrics,
        config=ctx.config.analysis,
    )
    ctx.selection_breakdown = initial_selection.breakdown
    ctx.selection_details_by_source_frame = dict(initial_selection.selection_details)

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=98,
                time_offset_seconds=4.08,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    render_capture: dict[str, Any] = {}
    report_capture: dict[str, Any] = {}
    expected_report_path = tmp_path / "run" / "report.html"

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        render_capture.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    def _fake_generate_report(
        report_data: object, report_config: object, *, output_path: Path
    ) -> Path:
        report_capture["report_data"] = report_data
        report_capture["report_config"] = report_config
        assert output_path == expected_report_path
        return output_path

    monkeypatch.setattr(phase_tasks, "align_clips_from_request", _fake_align_clips_from_request)
    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )
    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)

    align_output = phase_tasks.run_align_phase(
        ctx,
        selected_frames=list(initial_selection.frames),
    )
    ctx.reference = align_output.reference
    ctx.comparisons = align_output.comparisons
    ctx.selection_breakdown = align_output.selection_breakdown
    ctx.selection_details_by_source_frame = align_output.selection_details_by_source_frame

    phase_tasks.run_render_phase(
        ctx,
        frames=align_output.selected_frames,
        runner=cast(Any, _RenderRunner()),
    )
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [
                tmp_path / "screenshots" / "reference_1.png",
                tmp_path / "screenshots" / "reference_2.png",
            ],
            "Encode 1": [
                tmp_path / "screenshots" / "encode_1.png",
                tmp_path / "screenshots" / "encode_2.png",
            ],
        },
        screenshot_dir=tmp_path / "screenshots",
    )
    report_output = phase_post_render.run_report_phase(
        ctx,
        frames=align_output.selected_frames,
        render=render,
        metadata=None,
        slowpics_url=None,
    )

    assert set(initial_selection.selection_details).isdisjoint({98, 99})
    assert align_output.selected_frames == [0, 1]
    assert render_capture["batch_requests"][0].selection_labels == ["Dark", "Dark"]
    assert report_output.report_path == expected_report_path
    report_data = report_capture["report_data"]
    assert [
        (detail.label, detail.detail, detail.category) for detail in report_data.frame_details
    ] == [
        ("Frame 98", "Source frame 98", "quantile_dark"),
        ("Frame 99", "Source frame 99", "quantile_dark"),
    ]


async def test_unresolved_comparison_remains_in_render_report_and_slowpics_membership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode 1")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode 2")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])
    frames = [0, 1]
    screenshots_by_label: dict[str, list[Path]] = {}
    for label in ("Reference", "Encode 1", "Encode 2"):
        label_key = label.lower().replace(" ", "-")
        screenshots_by_label[label] = []
        for frame in frames:
            screenshot = tmp_path / "screenshots" / f"{frame}-{label_key}.png"
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
            screenshots_by_label[label].append(screenshot)
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured["render_labels"] = [
            request.label for request in cast(list[Any], kwargs["batch_requests"])
        ]
        return screenshots_by_label

    def _fake_generate_report(
        report_data: object, report_config: object, *, output_path: Path
    ) -> Path:
        captured["report_clip_names"] = [clip.name for clip in cast(Any, report_data).clips]
        captured["report_config"] = report_config
        assert output_path == tmp_path / "run" / "report.html"
        return output_path

    async def _fake_publish_to_slowpics(**kwargs: object) -> PublishResult:
        upload_plan = cast(Any, kwargs["upload_plan"])
        captured["slowpics_clip_labels"] = [
            image.clip_label for image in upload_plan.rows[0].images
        ]
        return PublishResult(
            url="https://slow.pics/c/unresolved",
            screenshot_count=len(upload_plan.file_paths),
            upload_duration_seconds=0.1,
            uploaded_file_paths=tuple(upload_plan.file_paths),
        )

    async def _no_post_upload_actions(
        _request: SlowpicsPostUploadRequest,
    ) -> tuple[PostUploadActionResult, ...]:
        return ()

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )
    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)
    monkeypatch.setattr(phase_post_render, "publish_to_slowpics", _fake_publish_to_slowpics)
    monkeypatch.setattr(
        phase_post_render,
        "run_slowpics_post_upload_actions",
        _no_post_upload_actions,
    )

    render_output = phase_tasks.run_render_phase(
        ctx,
        frames=frames,
        runner=cast(Any, _RenderRunner()),
    )
    phase_post_render.run_report_phase(
        ctx,
        frames=frames,
        render=render_output.render,
        metadata=None,
        slowpics_url=None,
    )
    async with httpx.AsyncClient() as client:
        await phase_post_render.run_publish_phase(
            ctx,
            client=client,
            metadata=None,
            render=render_output.render,
            selected_frames=frames,
        )

    assert [comparison.alignment for comparison in ctx.comparisons] == [None, None]
    assert captured["render_labels"] == ["Reference", "Encode 1", "Encode 2"]
    assert captured["report_clip_names"] == ["Reference", "Encode 1", "Encode 2"]
    assert captured["slowpics_clip_labels"] == ["Reference", "Encode 1", "Encode 2"]


def test_run_report_phase_labels_skipped_analysis_alignment_fallback_random_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [0], "random_frame_count": 1, "random_seed": 42}
    )

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=80,
                time_offset_seconds=3.33,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    captured: dict[str, Any] = {}
    expected_path = tmp_path / "run" / "report.html"

    def _fake_generate_report(
        report_data: object, report_config: object, *, output_path: Path
    ) -> Path:
        captured["report_data"] = report_data
        captured["report_config"] = report_config
        assert output_path == expected_path
        return output_path

    monkeypatch.setattr(phase_tasks, "align_clips_from_request", _fake_align_clips_from_request)
    monkeypatch.setattr(phase_post_render, "generate_report", _fake_generate_report)

    align_output = phase_tasks.run_align_phase(ctx, selected_frames=[0, 66])
    ctx.reference = align_output.reference
    ctx.comparisons = align_output.comparisons
    ctx.selection_breakdown = align_output.selection_breakdown
    ctx.selection_details_by_source_frame = align_output.selection_details_by_source_frame
    render = RenderArtifacts(
        screenshots_by_label={
            "Reference": [tmp_path / "screenshots" / "reference.png"],
            "Encode 1": [tmp_path / "screenshots" / "encode.png"],
        },
        screenshot_dir=tmp_path / "screenshots",
    )

    output = phase_post_render.run_report_phase(
        ctx,
        frames=align_output.selected_frames,
        render=render,
        metadata=None,
        slowpics_url=None,
    )

    report_data = captured["report_data"]
    assert output.report_path == expected_path
    assert align_output.selected_frames == [18]
    assert [
        (detail.label, detail.detail, detail.category) for detail in report_data.frame_details
    ] == [("Frame 98", "Source frame 98", "random")]
