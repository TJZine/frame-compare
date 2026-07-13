"""Stable algorithm identity for analysis metric caches."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from frame_compare.config.schema_enums import AnalysisPerformanceMode

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig

type MetricAlgorithmIdentity = Mapping[str, object]

_ALGORITHM_VERSION = "analysis_metrics_v5"


def build_metric_algorithm_identity(config: AnalysisConfig) -> MetricAlgorithmIdentity:
    """Build the cache identity payload for the configured analysis metric algorithm."""
    if config.performance_mode == AnalysisPerformanceMode.QUALITY:
        return _quality_identity()
    if config.performance_mode == AnalysisPerformanceMode.PERFORMANCE:
        return _performance_identity()
    raise ValueError(f"Unsupported analysis performance mode: {config.performance_mode}")


def stable_metric_algorithm_identity_json(config: AnalysisConfig) -> str:
    """Serialize the algorithm identity with stable key ordering for hashing/storage."""
    return _stable_json(build_metric_algorithm_identity(config))


def metric_algorithm_id(config: AnalysisConfig) -> str:
    """Return a compact stable hash for the configured metric algorithm identity."""
    identity_json = stable_metric_algorithm_identity_json(config)
    return hashlib.sha256(identity_json.encode("utf-8")).hexdigest()


def metric_backend(config: AnalysisConfig) -> str:
    """Return the backend label from the configured metric algorithm identity."""
    backend = build_metric_algorithm_identity(config).get("backend")
    if not isinstance(backend, str):
        raise ValueError("Metric algorithm identity is missing a string backend")
    return backend


def _stable_json(payload: MetricAlgorithmIdentity) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _quality_identity() -> dict[str, object]:
    return {
        "algorithm_version": _ALGORITHM_VERSION,
        "backend": "vapoursynth_planestats",
        "performance_mode": "quality",
        "luminance": {
            "temporal": "requested_contiguous_window_frames",
            "spatial": "active_rect_aware_full_resolution_luma",
            "operation": "planestats_average",
        },
        "motion": {
            "temporal": "requested_window_pairs_with_source_lookbehind",
            "spatial": "active_rect_aware_full_resolution_luma",
            "operation": "planestats_diff",
        },
    }


def _performance_identity() -> dict[str, object]:
    return {
        "algorithm_version": _ALGORITHM_VERSION,
        "backend": "vapoursynth_planestats",
        "performance_mode": "performance",
        "luminance": {
            "temporal": "requested_contiguous_window_frames",
            "spatial": "active_rect_aware_luma_resize",
            "target_max_width": 320,
            "resize": "bicubic",
            "upscale": False,
            "operation": "planestats_average",
        },
        "motion": {
            "temporal": "requested_window_pairs_with_source_lookbehind",
            "spatial": "active_rect_aware_luma_resize",
            "target_max_width": 320,
            "resize": "bicubic",
            "upscale": False,
            "operation": "planestats_diff",
        },
    }


__all__ = [
    "MetricAlgorithmIdentity",
    "build_metric_algorithm_identity",
    "metric_algorithm_id",
    "metric_backend",
    "stable_metric_algorithm_identity_json",
]
