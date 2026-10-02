"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from frame_compare.analysis.errors import ExclusionRecoverySelectionError, SelectionError
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.analysis.window import SelectionWindow
from frame_compare.orchestration import phase_alignment, phase_selection
from frame_compare.orchestration.full_window_retry import FullWindowRetryOverride
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.alignment_evidence import AlignmentStabilitySummary
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
    _run_align_phase,
)


def test_run_align_phase_applies_offsets_and_normalizes_selected_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    comparison = replace(
        comparison,
        probe=replace(
            comparison.probe,
            preserved_frame_props={"_Matrix": 1, "_Transfer": 16, "_Primaries": 9},
        ),
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = replace(
        ctx.reference,
        probe=replace(
            ctx.reference.probe,
            preserved_frame_props={"_Matrix": 1, "_Transfer": 1, "_Primaries": 1},
        ),
    )
    selected_frames = [0, 2, 50, 99]
    captured: dict[str, Any] = {}

    def _fake_align_clips_from_request(*args: object, **kwargs: object) -> list[AlignmentResult]:
        captured["request"] = args[0]
        captured["config"] = args[1]
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=selected_frames)

    assert output.reference.trim.trim_start_frames == 2
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.selected_frames == [0, 48, 97]


def test_run_align_phase_retains_material_variable_alignment_without_phase_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    summary = AlignmentStabilitySummary(
        classification="variable",
        valid_windows=4,
        offset_min_frames=-3,
        offset_max_frames=4,
        first_offset_frames=0,
        last_offset_frames=2,
        largest_adjacent_jump_frames=3,
        change_position_seconds=None,
    )
    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: [
            AlignmentResult(
                "reference.mkv",
                "encode.mkv",
                2,
                0.08,
                0.9,
                "cross_correlation",
                "computed",
                stability=summary,
            )
        ],
    )

    output = _run_align_phase(ctx, selected_frames=[2, 50])

    assert output.comparisons[0].alignment is not None
    assert output.comparisons[0].alignment.relative_offset_frames == 2
    assert output.comparisons[0].alignment.stability == summary
    # U3 surfaces variability in the Frame Alignment report stability row,
    # not as a phase warning; the applied constant offset is retained as-is.
    assert output.warnings == []


def test_alignment_request_records_configured_reference_relationship(tmp_path: Path) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config = ctx.config.model_copy(
        update={"sources": ctx.config.sources.model_copy(update={"reference": "encode.mkv"})}
    )

    alignment_request = phase_alignment._alignment_request_from_context(ctx)

    assert alignment_request.selected_reference_relationship == "configured"
    assert alignment_request.reference.path == ctx.reference.path
    assert [comparison_request.path for comparison_request in alignment_request.comparisons] == [
        comparison.path
    ]


@pytest.mark.parametrize(
    (
        "reference_trim",
        "comparison_specs",
        "alignments",
        "selected_frames",
        "expected_trims",
        "expected_frames",
        "warns",
    ),
    [
        pytest.param(
            (3, 80),
            [("encode.mkv", "Encode 1", 7, 90)],
            [
                AlignmentResult(
                    reference_clip="reference.mkv",
                    comparison_clip="encode.mkv",
                    frame_offset=2,
                    time_offset_seconds=0.08,
                    correlation_score=0.9,
                    algorithm="cross_correlation",
                    source="computed",
                )
            ],
            [10, 20, 52],
            (9, [7], 80, [78]),
            [4, 14, 46],
            False,
            id="base-trims",
        ),
        pytest.param(
            (3, 99),
            [
                ("encode_a.mkv", "Encode A", 7, 99),
                ("encode_b.mkv", "Encode B", 11, 99),
                ("encode_c.mkv", "Encode C", 13, 99),
            ],
            [
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
            ],
            [20, 50, 80],
            (10, [8, 18, 13], None, None),
            [13, 43, 73],
            True,
            id="mixed-authority",
        ),
        pytest.param(
            (3, 90),
            [
                ("encode_a.mkv", "Encode A", 7, 95),
                ("encode_b.mkv", "Encode B", 11, 99),
                ("encode_c.mkv", "Encode C", 13, 97),
            ],
            [
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
            ],
            [20, 57, 81],
            (17, [7, 22, 17], 90, [80, 95, 90]),
            [6, 43, 67],
            False,
            id="unequal-trims",
        ),
        pytest.param(
            (0, None),
            [("encode_a.mkv", "Encode A", 0, None), ("encode_b.mkv", "Encode B", 0, None)],
            [
                AlignmentResult(
                    reference_clip="reference.mkv",
                    comparison_clip="encode_a.mkv",
                    frame_offset=12,
                    time_offset_seconds=0.5,
                    correlation_score=1.0,
                    algorithm=None,
                    source="cached",
                ),
                AlignmentResult(
                    reference_clip="reference.mkv",
                    comparison_clip="encode_b.mkv",
                    frame_offset=-4,
                    time_offset_seconds=-0.167,
                    correlation_score=1.0,
                    algorithm=None,
                    source="manual",
                ),
            ],
            [12, 40, 95],
            (12, [0, 16], None, None),
            [0, 28, 83],
            False,
            id="preclassified-manual-cached",
        ),
    ],
)
def test_run_align_phase_composes_global_source_trims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference_trim: tuple[int, int | None],
    comparison_specs: list[tuple[str, str, int, int | None]],
    alignments: list[AlignmentResult],
    selected_frames: list[int],
    expected_trims: tuple[int, list[int], int | None, list[int] | None],
    expected_frames: list[int],
    warns: bool,
) -> None:
    comparisons = [
        _clip(tmp_path / "comparison_videos" / filename, label=label).with_trim(
            trim_start_frames=start,
            trim_end_frame_inclusive=end,
        )
        for filename, label, start, end in comparison_specs
    ]
    ctx = _context(tmp_path, comparisons=comparisons)
    ctx.reference = ctx.reference.with_trim(
        trim_start_frames=reference_trim[0],
        trim_end_frame_inclusive=reference_trim[1],
    )
    monkeypatch.setattr(
        phase_alignment, "align_clips_from_request", lambda *_args, **_kwargs: alignments
    )
    output = _run_align_phase(ctx, selected_frames=selected_frames)

    assert output.reference.trim.trim_start_frames == expected_trims[0]
    assert [clip.trim.trim_start_frames for clip in output.comparisons] == expected_trims[1]
    if expected_trims[2] is not None:
        assert output.reference.trim.trim_end_frame_inclusive == expected_trims[2]
        assert [
            clip.trim.trim_end_frame_inclusive for clip in output.comparisons
        ] == expected_trims[3]
    assert output.selected_frames == expected_frames
    if warns:
        assert len(output.warnings) == 1
        assert "align: Encode B alignment" in output.warnings[0]
        assert "encode_b" not in output.warnings[0]


def test_run_align_phase_does_not_backfill_dropped_user_frames_with_random(
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
                frame_offset=2,
                time_offset_seconds=0.08,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=[0, 50])

    assert output.reference.trim.trim_start_frames == 2
    assert output.selected_frames == [48]
    assert output.warnings == [
        "frame selection: dropped user frame(s) outside aligned renderable range: 0"
    ]


def test_run_align_phase_does_not_substitute_after_full_window_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [0], "random_frame_count": 1, "random_seed": 42}
    )
    ctx.full_window_retry_override = FullWindowRetryOverride(
        ignore_lead_seconds=2.0,
        ignore_trail_seconds=2.0,
    )

    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=80,
                time_offset_seconds=3.33,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )

    with pytest.raises(ExclusionRecoverySelectionError, match="full-window retry"):
        _run_align_phase(ctx, selected_frames=[0, 66])


def test_run_align_phase_reselects_trimmed_overlap_when_fallback_plan_would_drop_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = replace(
        ctx.reference,
        probe=replace(ctx.reference.probe, num_frames=220),
    )
    ctx.selection_window = SelectionWindow(start_frame=0, end_frame_exclusive=220)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={
            "random_frame_count": 0,
            "dark_frame_count": 2,
            "bright_frame_count": 0,
            "dark_quantile": 0.2,
        }
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[float(frame) / 219.0 for frame in range(220)],
        motion=[0.0 for _ in range(220)],
        metadata=MetricsMetadata(
            frame_count=220,
            fps=Fraction(60, 1),
            config_fingerprint="test",
            clips=[ClipIdentity(path="reference.mkv", size=1, mtime=1.0)],
        ),
    )
    selected_frames = [0, 1, 2, 3]

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=selected_frames)

    assert output.selected_frames == [0, 12]
    assert output.selection_breakdown.quantile_dark == [60, 72]
    assert set(output.selection_details_by_source_frame) == {60, 72}
    assert all(
        detail.label in {"Dark", "Bright"}
        for detail in output.selection_details_by_source_frame.values()
    )


def test_run_align_phase_filters_and_rebases_sparse_metrics_for_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 2}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[0.9, 0.8, 0.4, 0.1, 0.2],
        motion=[0.1, 0.1, 0.2, 0.3, 0.4],
        metadata=MetricsMetadata(
            frame_count=5,
            fps=Fraction(24),
            config_fingerprint="test",
            clips=[],
            source_frame_count=220,
            metric_source_start=0,
            metric_source_end_exclusive=220,
            performance_mode="performance",
        ),
        sampled_source_frames=(10, 20, 65, 75, 90),
    )

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=[0, 1])

    assert output.reference.trim.trim_start_frames == 60
    assert output.selected_frames == [15, 30]
    assert output.selection_breakdown.quantile_dark == [75, 90]
    assert set(output.selection_details_by_source_frame) == {75, 90}


def test_run_align_phase_sparse_overlap_reports_metric_candidate_underfill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 2}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[0.1, 0.2],
        motion=[0.1, 0.2],
        metadata=MetricsMetadata(
            frame_count=2,
            fps=Fraction(24),
            config_fingerprint="test",
            clips=[],
            source_frame_count=220,
            metric_source_start=0,
            metric_source_end_exclusive=220,
            performance_mode="performance",
        ),
        sampled_source_frames=(10, 100),
    )

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    with pytest.raises(SelectionError) as exc_info:
        _run_align_phase(ctx, selected_frames=[0, 1])

    assert exc_info.value.context.details == {
        "reason": "insufficient_candidates",
        "requested": 2,
        "found": 0,
    }


def test_run_align_phase_raises_when_overlap_is_smaller_than_generated_counts(
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
            fps=Fraction(24, 1),
            config_fingerprint="test",
            clips=[ClipIdentity(path="reference.mkv", size=1, mtime=1.0)],
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    with pytest.raises(SelectionError) as exc_info:
        _run_align_phase(ctx, selected_frames=[0, 1, 2, 3])

    assert exc_info.value.context.details == {
        "reason": "insufficient generated candidates after alignment",
        "requested": 4,
        "found": 2,
    }


def test_run_align_phase_preserves_surviving_user_label_when_metrics_reselect_same_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"user_frames": [98], "random_frame_count": 0, "dark_frame_count": 1}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[float(frame) / 99.0 for frame in range(100)],
        motion=[0.0 for _ in range(100)],
        metadata=MetricsMetadata(
            frame_count=100,
            fps=Fraction(24, 1),
            config_fingerprint="test",
            clips=[ClipIdentity(path="reference.mkv", size=1, mtime=1.0)],
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=[98, 0])

    assert output.selected_frames == [0, 1]
    assert output.selection_breakdown.user == [98]
    assert output.selection_details_by_source_frame[98].label == "User"
    assert output.selection_details_by_source_frame[99].label == "Dark"


def test_run_align_phase_fallback_reselects_only_inside_global_selection_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1", num_frames=220
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.selection_window = SelectionWindow(start_frame=80, end_frame_exclusive=140)
    ctx.analysis_clip = _clip(
        tmp_path / "comparison_videos" / "analysis.mkv",
        label="Analysis",
        num_frames=220,
    ).with_trim(trim_start_frames=20, trim_end_frame_inclusive=219)
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 2, "bright_frame_count": 2}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[float(frame) / 219.0 for frame in range(100, 160)],
        motion=[0.0 for _ in range(60)],
        metadata=MetricsMetadata(
            frame_count=60,
            fps=Fraction(24, 1),
            config_fingerprint="test",
            clips=[ClipIdentity(path="reference.mkv", size=1, mtime=1.0)],
            source_frame_count=220,
            metric_source_start=100,
            metric_source_end_exclusive=160,
        ),
    )

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=[0, 1, 2, 3])

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

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    with pytest.raises(AudioAlignmentError, match="No overlapping frames"):
        _run_align_phase(ctx, selected_frames=selected_frames)


def test_run_align_phase_preserves_accepted_alignment_when_another_result_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])
    selected_frames = [0, 2, 50, 99]

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=selected_frames)

    assert output.reference.trim.trim_start_frames == 2
    assert output.reference.trim.trim_end_frame_inclusive == 99
    assert [comparison.trim.trim_start_frames for comparison in output.comparisons] == [0, 2]
    assert output.selected_frames == [0, 48, 97]
    assert len(output.warnings) == 1
    warning = output.warnings[0]
    normalized_warning = warning.replace("_", " ").lower()
    assert "align:" in warning.lower()
    assert "align: Encode B alignment" in warning
    assert "encode_b" not in warning
    assert "low confidence" in normalized_warning
    assert "unapplied" in normalized_warning
    assert "best-effort reference-frame domain" in warning
    assert "without accepted alignment" in warning


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

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    output = _run_align_phase(ctx, selected_frames=[0, 20, 40])

    assert (
        phase_selection.map_aligned_to_source_frame(
            clip=output.reference,
            aligned_frame=0,
        )
        == expected_reference_source_frame
    )
    assert (
        phase_selection.map_aligned_to_source_frame(
            clip=output.comparisons[0],
            aligned_frame=0,
        )
        == expected_comparison_source_frame
    )


def test_map_aligned_to_source_frame_rejects_negative_aligned_frame(tmp_path: Path) -> None:
    ctx = _context(tmp_path)

    with pytest.raises(AudioAlignmentError, match="is before trimmed domain"):
        phase_selection.map_aligned_to_source_frame(
            clip=ctx.reference,
            aligned_frame=-1,
        )


def test_run_align_phase_rejects_applied_result_without_frame_offset_even_when_mixed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "encode_a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "encode_b.mkv", label="Encode B")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])

    def _fake_align_clips_from_request(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
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

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _fake_align_clips_from_request)

    with pytest.raises(
        AudioAlignmentError, match="Applied alignment result is missing frame offset."
    ):
        _run_align_phase(ctx, selected_frames=[0, 2, 50, 99])


def test_run_align_phase_no_comparisons_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    selected_frames = [2, 4]

    def _unexpected_align(*_args: object, **_kwargs: object) -> list[AlignmentResult]:
        raise AssertionError("No comparisons should skip alignment work")

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", _unexpected_align)

    output = _run_align_phase(ctx, selected_frames=selected_frames)

    assert output.selected_frames == [2, 4]
    assert output.comparisons == []
    assert selected_frames == [2, 4]
    assert ctx.comparisons == []
