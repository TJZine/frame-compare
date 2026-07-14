from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
from typing import get_type_hints

import pytest

from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricCacheRequest,
    MetricsMetadata,
    SelectionBreakdown,
    SelectionDetail,
)


def test_metric_cache_request_runtime_annotations_resolve() -> None:
    hints = get_type_hints(MetricCacheRequest)

    assert hints["analysis_source_path"] == Path | None


def test_clip_identity_is_frozen() -> None:
    ci = ClipIdentity(path="a.mkv", size=100, mtime=1.0)
    with pytest.raises(FrozenInstanceError):
        ci.path = "x"


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


def test_quality_metrics_forbid_sparse_source_map() -> None:
    metadata = MetricsMetadata(
        frame_count=1,
        fps=Fraction(24),
        config_fingerprint="fp",
        clips=[],
    )

    with pytest.raises(ValueError, match="Only performance"):
        FrameMetrics(
            luminance=[0.1],
            motion=[0.0],
            metadata=metadata,
            sampled_source_frames=(0,),
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
