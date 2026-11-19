"""Cache identity and decode failure contract tests."""

import json
from pathlib import Path

import pytest

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    acquire_required_metrics,
    compute_cache_key,
    load_cached_metrics,
)
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import MetricCacheRequest
from frame_compare.config.schema import AnalysisConfig
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from tests.analysis._cache_io_test_helpers import cache_file, valid_cache_metadata_payload


def test_required_cache_load_rejects_misfiled_algorithm(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    video.write_bytes(b"video")
    quality_config = AnalysisConfig()
    performance_config = AnalysisConfig(performance_mode=AnalysisPerformanceMode.PERFORMANCE)
    request = MetricCacheRequest(analysis_source_path=video)
    fingerprint = compute_cache_key([video], quality_config, metric_request=request)
    metadata = valid_cache_metadata_payload(performance_config, frame_count=1)
    metadata["analysis_source_path"] = str(video)
    metadata["source_frame_count"] = 4
    metadata["metric_source_end_exclusive"] = 4
    payload = {
        "version": CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": [1],
        "metadata": metadata,
    }
    cache_file(tmp_path, fingerprint, video).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(MetricsCalculationError, match="mismatched_inputs"):
        acquire_required_metrics(
            request,
            video_paths=[video],
            config=quality_config,
            cache_dir=tmp_path,
            selection_domain=None,
        )


@pytest.mark.parametrize(
    "content", [pytest.param("[" * 10000, id="deep"), pytest.param("1" * 5000, id="integer-limit")]
)
def test_decode_limits_are_corrupted(tmp_path: Path, content: str) -> None:
    path = cache_file(tmp_path, "fp")
    path.write_text(content, encoding="utf-8")
    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"
