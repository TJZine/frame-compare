"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.analysis.window import SelectionWindow
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
    assert captured["reference_fps"] == ctx.reference.effective_fps
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


def test_run_align_phase_normalizes_analyze_selected_base_domain_frames_with_base_trims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=80)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=7, trim_end_frame_inclusive=90)]

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
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

    output = phase_tasks.run_align_phase(ctx, selected_frames=[2, 4, 52])

    assert output.reference.trim.trim_start_frames == 5
    assert output.reference.trim.trim_end_frame_inclusive == 80
    assert output.comparisons[0].trim.trim_start_frames == 7
    assert output.comparisons[0].trim.trim_end_frame_inclusive == 82
    assert output.reference.effective_num_frames() == 76
    assert output.comparisons[0].effective_num_frames() == 76
    assert output.selected_frames == [0, 2, 50]


def test_run_align_phase_reselects_trimmed_overlap_when_fallback_plan_would_drop_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
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
            luminance=ctx.analysis_metrics.luminance[
                overlap_start : overlap_start + overlap_length
            ],
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


def test_run_align_phase_fallback_reselects_only_inside_global_selection_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.selection_window = SelectionWindow(start_frame=80, end_frame_exclusive=140)
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

    output = phase_tasks.run_align_phase(ctx, selected_frames=[0, 1, 2, 3])

    assert output.selection_details_by_source_frame is not None
    selected_source_frames = {
        output.reference.trim.trim_start_frames + frame for frame in output.selected_frames
    }
    assert selected_source_frames == set(output.selection_details_by_source_frame)
    assert selected_source_frames
    assert all(80 <= frame < 140 for frame in selected_source_frames)


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


def test_run_align_phase_preserves_accepted_alignment_when_another_result_is_rejected(
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

    assert output.reference.trim.trim_start_frames == 2
    assert output.reference.trim.trim_end_frame_inclusive == 99
    assert output.comparisons[0].alignment is not None
    assert output.comparisons[0].alignment.relative_offset_frames == 2
    assert output.comparisons[1].alignment is None
    assert [comparison.trim.trim_start_frames for comparison in output.comparisons] == [0, 2]
    assert output.selected_frames == [0, 48, 97]
    assert len(output.warnings) == 1
    warning = output.warnings[0]
    normalized_warning = warning.replace("_", " ").lower()
    assert "align:" in warning.lower()
    assert "encode_b" in warning.lower()
    assert "low confidence" in normalized_warning
    assert "unapplied" in normalized_warning
    assert "best-effort reference-frame domain" in warning
    assert "without accepted alignment" in warning


def test_run_align_phase_normalizes_three_comparisons_with_rejected_zero_offset_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    comp_c = _clip(tmp_path / "comparison_videos" / "encode_c.mkv", label="Encode C")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b, comp_c])

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
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_c.mkv",
                frame_offset=-3,
                time_offset_seconds=-0.125,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            ),
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=[2, 50, 96])

    assert output.reference.alignment is None
    assert [
        None if comparison.alignment is None else comparison.alignment.relative_offset_frames
        for comparison in output.comparisons
    ] == [2, None, -3]
    assert output.reference.trim.trim_start_frames == 2
    assert [comparison.trim.trim_start_frames for comparison in output.comparisons] == [0, 2, 5]
    assert output.selected_frames == [0, 48, 94]
    assert len(output.warnings) == 1
    assert "encode_b" in output.warnings[0].lower()


def test_run_align_phase_legacy_normalizes_positive_negative_and_zero_offsets_with_base_trims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    comp_c = _clip(tmp_path / "comparison_videos" / "encode_c.mkv", label="Encode C")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b, comp_c])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=90)
    ctx.comparisons = [
        comp_a.with_trim(trim_start_frames=7, trim_end_frame_inclusive=95),
        comp_b.with_trim(trim_start_frames=11, trim_end_frame_inclusive=99),
        comp_c.with_trim(trim_start_frames=13, trim_end_frame_inclusive=97),
    ]

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_a.mkv",
                frame_offset=10,
                time_offset_seconds=0.417,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_b.mkv",
                frame_offset=-5,
                time_offset_seconds=-0.208,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_c.mkv",
                frame_offset=0,
                time_offset_seconds=0.0,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            ),
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=[10, 57, 81])

    assert output.reference.trim.trim_start_frames == 13
    assert [comparison.trim.trim_start_frames for comparison in output.comparisons] == [
        7,
        26,
        23,
    ]
    assert output.reference.trim.trim_end_frame_inclusive == 86
    assert [comparison.trim.trim_end_frame_inclusive for comparison in output.comparisons] == [
        80,
        99,
        96,
    ]
    assert [
        output.reference.effective_num_frames(),
        *[comparison.effective_num_frames() for comparison in output.comparisons],
    ] == [74, 74, 74, 74]
    assert output.selected_frames == [0, 47, 71]


def test_run_align_phase_normalizes_manual_source_frame_pair_offsets_globally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_a.mkv",
                # Equivalent to user entering source-frame pair 120 108.
                frame_offset=12,
                time_offset_seconds=0.5,
                correlation_score=1.0,
                algorithm=None,
                source="manual",
            ),
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_b.mkv",
                # Equivalent to user entering source-frame pair 120 124.
                frame_offset=-4,
                time_offset_seconds=-0.167,
                correlation_score=1.0,
                algorithm=None,
                source="manual",
            ),
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=[12, 40, 95])

    assert [
        comparison.alignment.relative_offset_frames if comparison.alignment is not None else None
        for comparison in output.comparisons
    ] == [12, -4]
    assert output.reference.trim.trim_start_frames == 12
    assert [comparison.trim.trim_start_frames for comparison in output.comparisons] == [0, 16]
    assert output.selected_frames == [0, 28, 83]


@pytest.mark.parametrize(
    ("frame_offset", "expected_reference_source_frame", "expected_comparison_source_frame"),
    [
        (7, 7, 0),
        (-5, 0, 5),
        (0, 0, 0),
    ],
)
def test_map_aligned_to_source_frame_after_positive_negative_and_zero_offsets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    frame_offset: int,
    expected_reference_source_frame: int,
    expected_comparison_source_frame: int,
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=frame_offset,
                time_offset_seconds=frame_offset / 24,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=[0, 20, 40])

    assert (
        phase_tasks._map_aligned_to_source_frame(
            clip=output.reference,
            aligned_frame=0,
        )
        == expected_reference_source_frame
    )
    assert (
        phase_tasks._map_aligned_to_source_frame(
            clip=output.comparisons[0],
            aligned_frame=0,
        )
        == expected_comparison_source_frame
    )


def test_run_align_phase_rejects_applied_result_without_frame_offset_even_when_mixed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode_a.mkv",
                frame_offset=None,
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

    with pytest.raises(
        AudioAlignmentError, match="Applied alignment result is missing frame offset."
    ):
        phase_tasks.run_align_phase(ctx, selected_frames=[0, 2, 50, 99])


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
