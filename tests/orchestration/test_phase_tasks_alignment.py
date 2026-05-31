"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config.schema import SelectionMode
from frame_compare.orchestration import phase_tasks
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentResult
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
)


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

    output = phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert captured["reference"] == ctx.reference.path
    assert captured["comparisons"] == [comparison.path]
    assert captured["cache_dir"] == ctx.workspace.generated_dir
    assert captured["config"].sample_rate == 12000
    assert captured["config"].max_offset_seconds == 4.5
    assert captured["config"].use_vspreview is True
    assert captured["config"].cache_results is False
    assert captured["config"].correlation_mode == "gcc_phat"
    assert captured["config"].preprocessing_mode == "standard"
    assert captured["config"].channel_strategy == "best_channel"
    assert captured["config"].confidence_threshold == 0.25
    assert captured["config"].ambiguity_peak_ratio == 1.5
    assert captured["config"].window_length_seconds == 8.0
    assert captured["config"].window_stride_seconds == 2.0
    assert captured["config"].minimum_valid_windows == 2
    assert captured["config"].consensus_minimum_ratio == 0.75
    assert captured["config"].refinement_mode == "local"
    assert captured["config"].refinement_sample_rate == 16000
    assert captured["config"].reference_stream == 1
    assert captured["config"].comparison_streams == {"encode": 2}
    assert output.reference.trim.trim_start_frames == 2
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].alignment is not None
    assert output.comparisons[0].alignment.relative_offset_frames == 2
    assert output.selected_frames == [0, 48, 97]
    assert ctx.reference.trim.trim_start_frames == 0
    assert ctx.comparisons[0].alignment is None
    assert selected_frames == [0, 2, 50, 99]
    assert output.selection_breakdown is None
    assert output.selection_details_by_source_frame is None


def test_run_align_phase_reselects_trimmed_overlap_when_fallback_plan_would_drop_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220)
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"selection_mode": SelectionMode.QUANTILE, "frame_count": 4}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[float(frame) / 219.0 for frame in range(220)],
        motion=[0.0 for _ in range(220)],
        metadata=MetricsMetadata(
            frame_count=220,
            fps=Fraction(24, 1),
            config_fingerprint="test",
            clips=[ClipIdentity(path="reference.mkv", size=1, mtime=1.0)],
        ),
    )
    selected_frames = [0, 1, 2, 3]

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=60,
                time_offset_seconds=2.5,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)
    overlap_start = output.reference.trim.trim_start_frames
    overlap_length = output.reference.effective_num_frames()

    expected_selection = phase_tasks.select_frames(
        metrics=FrameMetrics(
            luminance=ctx.analysis_metrics.luminance[overlap_start : overlap_start + overlap_length],
            motion=ctx.analysis_metrics.motion[overlap_start : overlap_start + overlap_length],
            metadata=replace(ctx.analysis_metrics.metadata, frame_count=overlap_length),
        ),
        config=ctx.config.analysis,
    )

    assert output.selected_frames == list(expected_selection.frames)
    assert output.selection_breakdown is not None
    assert output.selection_details_by_source_frame is not None
    expected_source_frames = {overlap_start + frame for frame in expected_selection.frames}
    assert set(output.selection_details_by_source_frame) == expected_source_frames
    assert all(
        detail.label in {"Dark", "Bright"}
        for detail in output.selection_details_by_source_frame.values()
    )


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


def test_run_align_phase_degrades_whole_set_when_any_result_is_not_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])
    selected_frames = [0, 2, 50, 99]

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_a.mkv",
                frame_offset=2,
                time_offset_seconds=0.08,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_b.mkv",
                frame_offset=None,
                time_offset_seconds=None,
                correlation_score=0.1,
                algorithm="cross_correlation",
                source="computed",
                applied=False,
                diagnostic="low_confidence",
            ),
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert output.reference.trim.trim_start_frames == 0
    assert output.reference.trim.trim_end_frame_inclusive == ctx.reference.probe.num_frames - 1
    assert [comparison.alignment for comparison in output.comparisons] == [None, None]
    assert [comparison.trim.trim_start_frames for comparison in output.comparisons] == [0, 0]
    assert output.selected_frames == [0, 2, 50]


def test_run_align_phase_no_comparisons_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    selected_frames = [2, 4]

    def _unexpected_align(**_kwargs: object) -> list[AlignmentResult]:
        raise AssertionError("No comparisons should skip alignment work")

    monkeypatch.setattr(phase_tasks, "align_clips", _unexpected_align)

    output = phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert output.selected_frames == [2, 4]
    assert output.comparisons == []
    assert selected_frames == [2, 4]
    assert ctx.comparisons == []
