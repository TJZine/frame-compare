"""Malformed cache and version-rejection contract tests."""

import json
from pathlib import Path

import pytest

from frame_compare.analysis import cache_io
from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    acquire_required_metrics,
    compute_cache_key,
    load_cached_metrics,
    read_cache_version,
)
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import MetricCacheRequest
from frame_compare.config.schema import AnalysisConfig
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from tests.analysis._cache_io_test_helpers import cache_file, valid_cache_metadata_payload


def test_load_version_mismatch(tmp_path: Path) -> None:
    """Wrong version → reason="version_mismatch"."""
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": 1,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {},
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp")
    assert result.success is False
    assert result.reason == "version_mismatch"


def test_load_mismatched_inputs(tmp_path: Path) -> None:
    """Wrong fingerprint → reason="mismatched_inputs"."""
    cache_file(tmp_path, "fp2").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp1",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "source_frame_count": 0,
                    "metric_source_start": 0,
                    "metric_source_end_exclusive": 0,
                    "fps": "24",
                    "config_fingerprint": "fp1",
                    "analysis_source_path": "",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp2")
    assert result.success is False
    assert result.reason == "mismatched_inputs"


def test_load_same_version_cache_without_analysis_source_path_is_corrupted(
    tmp_path: Path,
) -> None:
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24",
                    "config_fingerprint": "fp",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp")

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_invalid_utf8_cache_is_corrupted_and_has_no_version(tmp_path: Path) -> None:
    path = cache_file(tmp_path, "fp")
    path.write_bytes(b"\xff")

    result = load_cached_metrics(tmp_path, "fp")

    assert result.success is False
    assert result.reason == "corrupted"
    assert read_cache_version(path) is None


@pytest.mark.parametrize("field", ["luminance", "motion", "mtime"])
def test_load_oversized_numeric_cache_entry_is_corrupted(tmp_path: Path, field: str) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config, frame_count=1)
    payload: dict[str, object] = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": None,
        "metadata": metadata,
    }
    if field == "mtime":
        metadata["clips"] = [{"path": "fixture.mkv", "size": 1, "mtime": 10**400}]
    else:
        payload[field] = [10**400]
    cache_file(tmp_path, "fp").write_text(json.dumps(payload), encoding="utf-8")

    result = load_cached_metrics(tmp_path, "fp")

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize("field", ["luminance", "motion", "mtime"])
def test_load_numeric_cache_boolean_is_corrupted(tmp_path: Path, field: str) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config, frame_count=1)
    payload: dict[str, object] = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": None,
        "metadata": metadata,
    }
    if field == "mtime":
        metadata["clips"] = [{"path": "fixture.mkv", "size": 1, "mtime": True}]
    else:
        payload[field] = [True]
    cache_file(tmp_path, "fp").write_text(json.dumps(payload), encoding="utf-8")

    result = load_cached_metrics(tmp_path, "fp")

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_empty_metric_range_is_corrupted(tmp_path: Path) -> None:
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=0)
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "sampled_source_frames": None,
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"


def test_load_performance_cache_rejects_oversized_declared_range_before_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _UnmaterializedBurst:
        frame_count = 4_000_000

        @property
        def start(self) -> int:
            raise AssertionError("expected source map was materialized")

        @property
        def end_exclusive(self) -> int:
            raise AssertionError("expected source map was materialized")

    config = AnalysisConfig(performance_mode=AnalysisPerformanceMode.PERFORMANCE)
    metadata = valid_cache_metadata_payload(config, frame_count=1)
    metadata["source_frame_count"] = 4_000_000
    metadata["metric_source_end_exclusive"] = 4_000_000
    payload = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": [1],
        "metadata": metadata,
    }
    path = cache_file(tmp_path, "fp")
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        cache_io,
        "plan_performance_bursts",
        lambda **_: (_UnmaterializedBurst(),),
    )

    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"


@pytest.mark.parametrize("fps", ["24.0", "24/1", "48/2", "1e50"])
def test_load_cache_requires_writer_fps_format(tmp_path: Path, fps: str) -> None:
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=1)
    metadata["fps"] = fps
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [0.5],
                "motion": [0.0],
                "sampled_source_frames": None,
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"


@pytest.mark.parametrize(
    ("field", "values"),
    [("luminance", [1.1]), ("motion", [0.0, -0.1])],
)
def test_load_cache_rejects_out_of_range_metric_scores(
    tmp_path: Path, field: str, values: list[float]
) -> None:
    frame_count = len(values)
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=frame_count)
    payload: dict[str, object] = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5] * frame_count,
        "motion": [0.0] * frame_count,
        "sampled_source_frames": None,
        "metadata": metadata,
    }
    payload[field] = values
    cache_file(tmp_path, "fp").write_text(json.dumps(payload), encoding="utf-8")

    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"


def test_load_cache_rejects_nested_fingerprint_mismatch(tmp_path: Path) -> None:
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=1)
    payload = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": None,
        "metadata": metadata,
    }
    path = cache_file(tmp_path, "fp")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_cached_metrics(tmp_path, "fp").success is True

    metadata["config_fingerprint"] = "other"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_cached_metrics(tmp_path, "fp").reason == "mismatched_inputs"


def test_required_cache_load_rejects_misfiled_algorithm(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    video.write_bytes(b"video")
    quality_config = AnalysisConfig()
    performance_config = AnalysisConfig(performance_mode=AnalysisPerformanceMode.PERFORMANCE)
    request = MetricCacheRequest(analysis_source_path=video)
    fingerprint = compute_cache_key([video], quality_config, metric_request=request)
    metadata = valid_cache_metadata_payload(performance_config, frame_count=1)
    metadata["config_fingerprint"] = fingerprint
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


def test_load_cache_with_unencodable_algorithm_identity_is_corrupted(tmp_path: Path) -> None:
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=1)
    metadata["algorithm_identity_json"] = (
        '{"backend":"vapoursynth_planestats","performance_mode":"quality","bad":"\ud800"}'
    )
    payload = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": None,
        "metadata": metadata,
    }
    cache_file(tmp_path, "fp").write_text(json.dumps(payload), encoding="utf-8")

    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"


@pytest.mark.parametrize(
    "content", [pytest.param("[" * 10000, id="deep"), pytest.param("1" * 5000, id="integer-limit")]
)
def test_decode_limits_are_corrupted_with_unknown_version(tmp_path: Path, content: str) -> None:
    path = cache_file(tmp_path, "fp")
    path.write_text(content, encoding="utf-8")
    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"
    assert read_cache_version(path) is None


@pytest.mark.parametrize(
    "field", ["active_rect_source", "active_rect_detection_mode", "algorithm_identity_json"]
)
@pytest.mark.parametrize("value", [[], {}, "[" * 10000, "1" * 5000])
def test_cache_metadata_corruption_recovers(tmp_path: Path, field: str, value: object) -> None:
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=1)
    payload = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.5],
        "motion": [0.0],
        "sampled_source_frames": None,
        "metadata": metadata,
    }
    path = cache_file(tmp_path, "fp")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_cached_metrics(tmp_path, "fp").success
    metadata[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_cached_metrics(tmp_path, "fp").reason == "corrupted"
