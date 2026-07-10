from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
from typing import get_type_hints

import pytest

from frame_compare.analysis.types import (
    ClipIdentity,
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
    assert mm.version == 6


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
