"""Render phase output contracts owned by orchestration phase tasks."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.types import (
    FrameMetrics,
    MetricsMetadata,
    SelectionBreakdown,
    SelectionDetail,
)
from frame_compare.config.schema import OverlayMode
from frame_compare.orchestration import phase_tasks
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.orchestration.execution_types import (
    RenderArtifacts,
)
from frame_compare.services.types import AlignmentResult
from frame_compare.vs.types import HDRMetadata
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
    _RenderRunner,
)


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
        options = cast(Any, kwargs["options"])
        assert options.warnings is not None
        options.warnings.append("render: geometry alignment skipped")
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
    assert requests[0].label == "Reference"
    assert requests[0].filename_label == "reference"
    assert requests[0].display_frames == [1]
    assert requests[0].selection_labels == ["Dark"]
    assert requests[1].source_frames == [2]
    assert requests[1].label == "Encode 1"
    assert requests[1].filename_label == "encode"
    assert captured["output_dir"] == ctx.workspace.screenshots_dir
    options = captured["options"]
    assert options.overlay_mode == ctx.config.screenshots.overlay_mode
    assert options.ffmpeg_runner is runner
    assert options.reporter is ctx.reporter
    assert output.render == RenderArtifacts(
        screenshots_by_label={"Reference": [tmp_path / "reference.png"]},
        screenshot_dir=ctx.workspace.screenshots_dir,
        warnings=["render: geometry alignment skipped"],
    )


def test_run_render_phase_maps_three_clip_aligned_frames_to_source_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode 1")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode 2")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [
        comp_a.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18),
        comp_b.with_trim(trim_start_frames=5, trim_end_frame_inclusive=30),
    ]
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {
            "Reference": [tmp_path / "reference-1.png", tmp_path / "reference-2.png"],
            "Encode 1": [tmp_path / "encode-a-1.png", tmp_path / "encode-a-2.png"],
            "Encode 2": [tmp_path / "encode-b-1.png", tmp_path / "encode-b-2.png"],
        }

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    phase_tasks.run_render_phase(
        ctx,
        frames=[1, 2],
        runner=cast(Any, _RenderRunner()),
    )

    requests = captured["batch_requests"]
    assert [(request.label, request.source_frames) for request in requests] == [
        ("Reference", [4, 5]),
        ("Encode 1", [2, 3]),
        ("Encode 2", [6, 7]),
    ]
    assert [request.display_frames for request in requests] == [[1, 2], [1, 2], [1, 2]]


def test_run_align_then_render_phase_maps_four_clip_aligned_frames_in_clip_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(
        tmp_path / "comparison_videos" / "encode_a.mkv",
        label="Encode 1",
        num_frames=120,
    )
    comp_b = _clip(
        tmp_path / "comparison_videos" / "encode_b.mkv",
        label="Encode 2",
        num_frames=105,
    )
    comp_c = _clip(
        tmp_path / "comparison_videos" / "encode_c.mkv",
        label="Encode 3",
        num_frames=140,
    )
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b, comp_c])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=90)
    ctx.comparisons = [
        comp_a.with_trim(trim_start_frames=7, trim_end_frame_inclusive=95),
        comp_b.with_trim(trim_start_frames=11, trim_end_frame_inclusive=99),
        comp_c.with_trim(trim_start_frames=13, trim_end_frame_inclusive=120),
    ]

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_a.mkv",
                frame_offset=10,
                time_offset_seconds=10 / 24,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_b.mkv",
                frame_offset=-5,
                time_offset_seconds=-5 / 24,
                correlation_score=0.92,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_c.mkv",
                frame_offset=0,
                time_offset_seconds=0.0,
                correlation_score=0.98,
                algorithm="cross_correlation",
                source="computed",
            ),
        ]

    monkeypatch.setattr(phase_tasks, "align_clips_from_request", _fake_align_clips_from_request)
    align_output = phase_tasks.run_align_phase(ctx, selected_frames=[10, 57, 81])
    ctx.reference = align_output.reference
    ctx.comparisons = align_output.comparisons
    ctx.selection_breakdown = SelectionBreakdown(
        quantile_dark=[13],
        quantile_bright=[60],
        motion=[84],
    )
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {
            "Reference": [tmp_path / "reference-1.png"],
            "Encode 1": [tmp_path / "encode-a-1.png"],
            "Encode 2": [tmp_path / "encode-b-1.png"],
            "Encode 3": [tmp_path / "encode-c-1.png"],
        }

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    phase_tasks.run_render_phase(
        ctx,
        frames=align_output.selected_frames,
        runner=cast(Any, _RenderRunner()),
    )

    requests = captured["batch_requests"]
    assert [
        (
            request.label,
            request.source_frames,
            request.display_frames,
            request.selection_labels,
            request.probe_num_frames,
        )
        for request in requests
    ] == [
        ("Reference", [13, 60, 84], [0, 47, 71], ["Dark", "Bright", "Motion"], 100),
        ("Encode 1", [7, 54, 78], [0, 47, 71], ["Dark", "Bright", "Motion"], 120),
        ("Encode 2", [26, 73, 97], [0, 47, 71], ["Dark", "Bright", "Motion"], 105),
        ("Encode 3", [23, 70, 94], [0, 47, 71], ["Dark", "Bright", "Motion"], 140),
    ]


def test_run_render_phase_passes_clip_active_rect_to_batch_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = replace(
        ctx.reference,
        active_rect=ClipActiveRect(
            x=240,
            y=140,
            width=1440,
            height=800,
            source="explicit",
            detection_mode="aspect_ratio",
        ),
    )
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
    )

    requests = captured["batch_requests"]
    assert requests[0].diagnostic_metadata_trusted_for_geometry is False
    assert requests[0].active_rect is not None
    assert (
        requests[0].active_rect.x,
        requests[0].active_rect.y,
        requests[0].active_rect.width,
        requests[0].active_rect.height,
    ) == (240, 140, 1440, 800)
    assert requests[0].active_rect_source == "explicit"
    assert requests[0].active_rect_detection_mode == "aspect_ratio"
    assert requests[1].active_rect is not None
    assert (
        requests[1].active_rect.x,
        requests[1].active_rect.y,
        requests[1].active_rect.width,
        requests[1].active_rect.height,
    ) == (0, 0, comparison.probe.width, comparison.probe.height)
    assert requests[1].active_rect_source == "full-frame"


def test_run_render_phase_prefers_typed_selection_details_in_reference_source_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.screenshots.overlay_mode = OverlayMode.DIAGNOSTIC
    ctx.config.diagnostics.per_frame_nits = True
    ctx.config.color.target_nits = 200
    ctx.reference = replace(
        ctx.reference,
        probe=replace(
            ctx.reference.probe,
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)",
                max_cll=1000,
                max_fall=400,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
            preserved_frame_props={
                "DolbyVisionRPU": 1,
                "_Range": 0,
                "DolbyVision_L1_Average": 12.5,
                "DolbyVision_L1_Maximum": 450.0,
                "DolbyVision_L6_MaxCLL": 900.0,
                "DolbyVision_L6_MaxFALL": 300.0,
            },
        ),
    )
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [
        replace(
            comparison.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18),
            probe=replace(
                comparison.probe,
                is_hdr=True,
                hdr_metadata=HDRMetadata(
                    mastering_display=None,
                    max_cll=600,
                    max_fall=200,
                    color_primaries=9,
                    transfer=16,
                    matrix=9,
                ),
                preserved_frame_props={"_ColorRange": 0},
            ),
        )
    ]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[4])
    ctx.selection_details_by_source_frame = {
        4: SelectionDetail(
            frame_index=4,
            label="User",
            source="analysis",
            timecode="00:00:00.167",
            score=0.5,
            clip_role="analyze",
            notes="user_override",
        )
    }
    captured: dict[str, Any] = {}

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    runner = cast(Any, _RenderRunner())
    phase_tasks.run_render_phase(
        ctx,
        frames=[1],
        runner=runner,
    )

    requests = captured["batch_requests"]
    assert requests[0].selection_labels == ["User"]
    assert requests[0].selection_details is not None
    assert requests[0].selection_details[0] is not None
    assert requests[0].selection_details[0].label == "User"
    assert requests[0].diagnostic_metadata is not None
    assert requests[0].diagnostic_metadata[0] is not None
    assert requests[0].diagnostic_metadata[0].max_cll == 1000
    assert requests[0].diagnostic_metadata[0].color_range == "limited"
    assert requests[0].diagnostic_metadata[0].dolby_vision is not None
    assert requests[0].diagnostic_metadata[0].measurement is not None
    assert requests[0].diagnostic_metadata[0].measurement.avg_nits == pytest.approx(100.0)
    assert requests[1].selection_details is not None
    assert requests[1].selection_details[0] is not None
    assert requests[1].selection_details[0].frame_index == 4
    assert requests[1].diagnostic_metadata is not None
    assert requests[1].diagnostic_metadata[0] is not None
    assert requests[1].diagnostic_metadata[0].max_cll == 600
    assert requests[1].diagnostic_metadata[0].color_range == "full"


def test_run_render_phase_uses_alignment_reselected_source_domain_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=60, trim_end_frame_inclusive=219)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=0, trim_end_frame_inclusive=159)]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[60], quantile_bright=[219])
    ctx.selection_details_by_source_frame = {
        60: SelectionDetail(
            frame_index=60,
            label="Dark",
            source="analysis",
            timecode="00:00:02.500",
            clip_role="analyze",
            notes="quantile_dark",
        ),
        219: SelectionDetail(
            frame_index=219,
            label="Bright",
            source="analysis",
            timecode="00:00:09.125",
            clip_role="analyze",
            notes="quantile_bright",
        ),
    }
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
        frames=[0, 159],
        runner=cast(Any, _RenderRunner()),
    )

    requests = captured["batch_requests"]
    assert requests[0].selection_labels == ["Dark", "Bright"]
    assert requests[0].selection_details is not None
    assert [
        detail.label if detail is not None else None for detail in requests[0].selection_details
    ] == [
        "Dark",
        "Bright",
    ]


def test_run_render_phase_labels_skipped_analysis_alignment_fallback_random_frame(
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

    def _fake_render_screenshots_from_batch(**kwargs: object) -> dict[str, list[Path]]:
        captured.update(kwargs)
        return {"Reference": [tmp_path / "reference.png"]}

    monkeypatch.setattr(phase_tasks, "align_clips_from_request", _fake_align_clips_from_request)
    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        _fake_render_screenshots_from_batch,
    )

    align_output = phase_tasks.run_align_phase(ctx, selected_frames=[0, 66])
    ctx.reference = align_output.reference
    ctx.comparisons = align_output.comparisons
    ctx.selection_breakdown = align_output.selection_breakdown
    ctx.selection_details_by_source_frame = align_output.selection_details_by_source_frame

    phase_tasks.run_render_phase(
        ctx,
        frames=align_output.selected_frames,
        runner=cast(Any, _RenderRunner()),
    )

    requests = captured["batch_requests"]
    assert align_output.selected_frames == [18]
    assert requests[0].selection_labels == ["Random"]
    assert requests[0].selection_details is not None
    assert requests[0].selection_details[0] is not None
    assert requests[0].selection_details[0].frame_index == 98
    assert requests[0].selection_details[0].label == "Random"


def test_run_render_phase_rejects_analysis_fallback_when_overlap_is_smaller_than_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 2, "bright_frame_count": 2}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[float(frame) / 99.0 for frame in range(100)],
        motion=[0.0 for _ in range(100)],
        metadata=MetricsMetadata(
            frame_count=100,
            fps=ctx.reference.effective_fps,
            config_fingerprint="test",
            clips=[],
        ),
    )

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

    monkeypatch.setattr(phase_tasks, "align_clips_from_request", _fake_align_clips_from_request)

    with pytest.raises(SelectionError) as exc_info:
        phase_tasks.run_align_phase(ctx, selected_frames=[0, 1, 2, 3])

    assert exc_info.value.context.details == {
        "reason": "insufficient generated candidates after alignment",
        "requested": 4,
        "found": 2,
    }
