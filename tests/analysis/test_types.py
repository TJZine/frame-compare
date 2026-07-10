from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
from typing import get_type_hints

import pytest

from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricActiveRect,
    MetricCacheRequest,
    MetricsMetadata,
    SelectionBreakdown,
    SelectionDetail,
)


def test_metric_cache_request_runtime_annotations_resolve() -> None:
    hints = get_type_hints(MetricCacheRequest)

    assert hints["analysis_source_path"] == Path | None


def test_clip_identity_creation():
    ci = ClipIdentity(path="a.mkv", size=100, mtime=1.0, sha1="abc")
    assert ci.path == "a.mkv"
    assert ci.size == 100
    assert ci.mtime == 1.0
    assert ci.sha1 == "abc"


def test_clip_identity_optional_sha1():
    ci = ClipIdentity(path="a.mkv", size=100, mtime=1.0)
    assert ci.sha1 is None


def test_clip_identity_frozen():
    ci = ClipIdentity(path="a.mkv", size=100, mtime=1.0)
    with pytest.raises(FrozenInstanceError):
        ci.path = "x"


def test_metrics_metadata_creation():
    mm = MetricsMetadata(frame_count=100, fps=Fraction(24), config_fingerprint="fp", clips=[])
    assert mm.frame_count == 100
    assert mm.fps == Fraction(24)
    assert mm.config_fingerprint == "fp"
    assert mm.clips == []
    assert mm.performance_mode == "quality"
    assert mm.algorithm_identity_json == "{}"
    assert mm.metric_active_rect is None


def test_metrics_metadata_default_version():
    mm = MetricsMetadata(frame_count=100, fps=Fraction(24), config_fingerprint="fp", clips=[])
    assert mm.version == 6


def test_metric_active_rect_creation():
    rect = MetricActiveRect(x=10, y=20, width=300, height=200)
    assert rect.x == 10
    assert rect.y == 20
    assert rect.width == 300
    assert rect.height == 200


def test_frame_metrics_creation():
    mm = MetricsMetadata(frame_count=100, fps=Fraction(24), config_fingerprint="fp", clips=[])
    fm = FrameMetrics(luminance=[0.5], motion=[0.1], metadata=mm)
    assert fm.luminance == [0.5]
    assert fm.motion == [0.1]
    assert fm.metadata is mm


def test_selection_breakdown_creation():
    sb = SelectionBreakdown(quantile_dark=[1], quantile_bright=[2], motion=[3], random=[4])
    assert sb.quantile_dark == [1]
    assert sb.quantile_bright == [2]
    assert sb.motion == [3]
    assert sb.random == [4]


def test_frame_selection_creation():
    sb = SelectionBreakdown()
    detail = SelectionDetail(
        frame_index=1,
        label="Dark",
        source="analysis",
        timecode="00:00:00.042",
        score=0.1,
        clip_role="analyze",
        notes="quantile_dark",
    )
    fs = FrameSelection(
        frames=[1, 2],
        seed=42,
        breakdown=sb,
        selection_details={1: detail},
    )
    assert fs.frames == [1, 2]
    assert fs.seed == 42
    assert fs.breakdown is sb
    assert fs.selection_details == {1: detail}


def test_cache_load_result_success():
    mm = MetricsMetadata(frame_count=100, fps=Fraction(24), config_fingerprint="fp", clips=[])
    fm = FrameMetrics(luminance=[], motion=[], metadata=mm)
    clr = CacheLoadResult(success=True, metrics=fm)
    assert clr.success is True
    assert clr.metrics is fm
    assert clr.reason is None


def test_cache_load_result_failure():
    clr = CacheLoadResult(success=False, reason="not_found")
    assert clr.success is False
    assert clr.metrics is None
    assert clr.reason == "not_found"
