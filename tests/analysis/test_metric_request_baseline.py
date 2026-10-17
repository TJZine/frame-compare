"""Literal keys/tokens/v8 bytes captured from b2dcd6aa before the P7 migration."""

import json
import os
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest

from frame_compare.analysis import cache_io, metric_identity, metrics
from frame_compare.analysis.metric_strategies import MetricComputationResult
from frame_compare.analysis.sampling import PERFORMANCE_BURST_COUNT, PERFORMANCE_SAMPLING_FRACTION
from frame_compare.analysis.types import MetricCacheRequest, MetricFrameRange
from frame_compare.config.schema import AnalysisConfig
from frame_compare.vs.types import SourceInfo

BASELINE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures/metric_request_baseline.json").read_text()
)


@pytest.mark.parametrize("case", list(BASELINE["vectors"]))
def test_request_identity_and_persisted_bytes_match_pre_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = [Path("reference.mkv"), Path("comparison.mkv")]
    for path, data in zip(paths, [b"reference", b"comparison"], strict=True):
        path.write_bytes(data)
        os.utime(path, ns=(BASELINE["mtime_ns"], BASELINE["mtime_ns"]))
    requests = {
        "absent_range_fps": MetricCacheRequest(paths[0]),
        "explicit_full_range": MetricCacheRequest(paths[0], MetricFrameRange(4, 0, 4)),
        "explicit_source_fps": MetricCacheRequest(paths[0], effective_fps=Fraction(24)),
        "absent_source": MetricCacheRequest(None),
        "explicit_range_fps": MetricCacheRequest(paths[0], MetricFrameRange(4, 0, 4), Fraction(24)),
    }
    request = requests[case]
    expected = BASELINE["vectors"][case]
    config = AnalysisConfig(ignore_lead_seconds=0, ignore_trail_seconds=0, min_window_seconds=0)
    monkeypatch.setattr(
        metric_identity, "media_runtime_identity", lambda _scope: BASELINE["runtime"]
    )
    assert cache_io._metric_cache_request_token(request) == expected["token"]
    assert (
        cache_io.compute_cache_key(
            paths, config, selection_domain="fixed-domain", metric_request=request
        )
        == expected["raw_key"]
    )
    assert (
        cache_io._metric_cache_request_token(cache_io.keyed_metric_request(request, paths))
        == expected["keyed_token"]
    )
    strategy_result = MetricComputationResult(
        [0.1, 0.2, 0.3, 0.4],
        [0.0, 0.1, 0.2, 0.3],
        "quality",
        metric_identity.metric_algorithm_id(config),
        "vapoursynth_planestats",
        metric_identity.stable_metric_algorithm_identity_json(config),
    )
    source = cast(SourceInfo, SimpleNamespace(clip=SimpleNamespace(num_frames=4), fps=Fraction(24)))
    with (
        patch.object(metrics, "_load_analysis_source", return_value=source),
        patch.object(metrics, "calculate_metric_strategy", return_value=strategy_result),
    ):
        acquisition = metrics.calculate_metrics(
            request,
            video_paths=paths,
            config=config,
            cache_dir=tmp_path / "cache",
            selection_domain="fixed-domain",
        )
    assert acquisition.metrics.metadata.config_fingerprint == expected["calculation_key"]
    cache_file = next((tmp_path / "cache").glob("*.compframes"))
    assert cache_file.read_text() == expected["cache_bytes"]
    required = cache_io.acquire_required_metrics(
        request,
        video_paths=paths,
        config=config,
        cache_dir=tmp_path / "cache",
        selection_domain="fixed-domain",
    )
    assert required == acquisition.metrics


def test_sampling_constants_require_a_deliberate_algorithm_version_decision() -> None:
    assert metric_identity._ALGORITHM_VERSION == "analysis_metrics_v7"
    assert Fraction(1, 4) == PERFORMANCE_SAMPLING_FRACTION
    assert PERFORMANCE_BURST_COUNT == 8
