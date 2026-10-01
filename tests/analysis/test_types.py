from fractions import Fraction

import pytest

from frame_compare.analysis.types import (
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
    SelectionDetail,
)


def test_metrics_metadata_default_schema_version() -> None:
    mm = MetricsMetadata(frame_count=100, fps=Fraction(24), config_fingerprint="fp", clips=[])
    assert mm.version == 8


def test_performance_metrics_require_a_sorted_explicit_source_map() -> None:
    metadata = MetricsMetadata(
        frame_count=2,
        fps=Fraction(24),
        config_fingerprint="fp",
        clips=[],
        source_frame_count=20,
        metric_source_start=5,
        metric_source_end_exclusive=15,
        performance_mode="performance",
    )

    with pytest.raises(ValueError, match="require an explicit"):
        FrameMetrics(luminance=[0.1, 0.2], motion=[0.0, 0.1], metadata=metadata)
    with pytest.raises(ValueError, match="sorted and unique"):
        FrameMetrics(
            luminance=[0.1, 0.2],
            motion=[0.0, 0.1],
            metadata=metadata,
            sampled_source_frames=(10, 9),
        )


def test_selection_default_factories_are_isolated() -> None:
    first_breakdown = SelectionBreakdown()
    second_breakdown = SelectionBreakdown()
    first_breakdown.user.append(1)

    first_selection = FrameSelection(frames=[], seed=1, breakdown=first_breakdown)
    second_selection = FrameSelection(frames=[], seed=2, breakdown=second_breakdown)
    first_selection.selection_details[1] = SelectionDetail(
        frame_index=1,
        label="User",
        source="user",
    )

    assert second_breakdown.user == []
    assert second_selection.selection_details == {}
