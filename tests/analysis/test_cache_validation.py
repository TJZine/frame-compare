"""Malformed cache and version-rejection contract tests."""

import json
from pathlib import Path

import pytest

from frame_compare.analysis.cache_io import CACHE_VERSION, load_cached_metrics
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.config.schema import AnalysisConfig
from tests.analysis._cache_io_test_helpers import cache_file, valid_cache_metadata_payload


def test_load_corrupted(tmp_path: Path) -> None:
    """Invalid JSON → reason="corrupted"."""
    cache_file(tmp_path, "some-fingerprint").write_text("invalid json")
    result = load_cached_metrics(tmp_path, "some-fingerprint", [])
    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize("payload", ["null", "42"])
def test_load_non_mapping_root_returns_corrupted(tmp_path: Path, payload: str) -> None:
    cache_file(tmp_path, "some-fingerprint").write_text(payload, encoding="utf-8")

    result = load_cached_metrics(tmp_path, "some-fingerprint", [])

    assert result.success is False
    assert result.reason == "corrupted"


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
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "version_mismatch"


def test_load_v4_payload_returns_version_mismatch(tmp_path: Path) -> None:
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": 4,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {},
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "version_mismatch"


def test_load_v6_payload_returns_version_mismatch(tmp_path: Path) -> None:
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": 6,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

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
                    "fps": "24/1",
                    "config_fingerprint": "fp1",
                    "analysis_source_path": "",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp2", [])
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
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    "removed_key",
    [
        "performance_mode",
        "algorithm_id",
        "metric_backend",
        "algorithm_identity_json",
    ],
)
def test_load_same_version_cache_without_algorithm_metadata_is_corrupted(
    tmp_path: Path,
    removed_key: str,
) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config)
    del metadata[removed_key]
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_same_version_cache_without_metric_active_rect_metadata_is_corrupted(
    tmp_path: Path,
) -> None:
    config = AnalysisConfig()
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "source_frame_count": 0,
                    "metric_source_start": 0,
                    "metric_source_end_exclusive": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "analysis_source_path": "",
                    "clips": [],
                    "performance_mode": "quality",
                    "algorithm_id": metric_algorithm_id(config),
                    "metric_backend": metric_backend(config),
                    "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
                    "version": CACHE_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    "removed_key",
    [
        "active_rect_source",
        "active_rect_detection_mode",
        "active_rect_algorithm_id",
    ],
)
def test_load_same_version_cache_without_active_rect_provenance_is_corrupted(
    tmp_path: Path,
    removed_key: str,
) -> None:
    config = AnalysisConfig()
    metadata = {
        "frame_count": 0,
        "source_frame_count": 0,
        "metric_source_start": 0,
        "metric_source_end_exclusive": 0,
        "fps": "24/1",
        "config_fingerprint": "fp",
        "analysis_source_path": "",
        "clips": [],
        "performance_mode": "quality",
        "algorithm_id": metric_algorithm_id(config),
        "metric_backend": metric_backend(config),
        "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
        "metric_active_rect": None,
        "active_rect_source": "full-frame",
        "active_rect_detection_mode": "aspect_ratio",
        "active_rect_algorithm_id": "active_rect_resolution_v2",
        "version": CACHE_VERSION,
    }
    del metadata[removed_key]
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("active_rect_source", "unknown"),
        ("active_rect_detection_mode", "unknown"),
        ("active_rect_algorithm_id", "unknown"),
    ],
)
def test_load_same_version_cache_with_invalid_active_rect_provenance_is_corrupted(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config)
    metadata[field] = value
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("x", -1),
        ("y", -1),
        ("width", 0),
        ("height", 0),
        ("width", -1),
        ("height", -1),
    ],
)
def test_load_same_version_cache_with_invalid_metric_active_rect_is_corrupted(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    config = AnalysisConfig()
    rect = {"x": 0, "y": 0, "width": 100, "height": 100}
    rect[field] = value
    metadata = valid_cache_metadata_payload(
        config,
        metric_active_rect=rect,
        active_rect_source="explicit",
        active_rect_detection_mode="provided",
    )
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_same_version_cache_with_malformed_algorithm_identity_is_corrupted(
    tmp_path: Path,
) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config)
    metadata["algorithm_identity_json"] = "not-json"
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("algorithm_id", "wrong"),
        ("metric_backend", "wrong"),
        ("performance_mode", "performance"),
    ],
)
def test_load_same_version_cache_with_inconsistent_algorithm_metadata_is_corrupted(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config)
    metadata[field] = value
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [],
                "motion": [],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    ("luminance", "motion", "frame_count"),
    [
        ([0.1], [0.0, 0.2], 2),
        ([0.1, 0.2], [0.0], 2),
        ([0.1], [0.0], 2),
        ([0.1], [0.1], 1),
        ([float("nan")], [0.0], 1),
        ([0.1], [float("inf")], 1),
    ],
)
def test_load_metric_array_contract_violation_is_corrupted(
    tmp_path: Path,
    luminance: list[float],
    motion: list[float],
    frame_count: int,
) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(config, frame_count=frame_count)
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": luminance,
                "motion": motion,
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def test_load_missing_key_returns_corrupted(tmp_path: Path) -> None:
    """Missing luminance key → reason="corrupted"."""
    # Missing luminance
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp",
                    "clips": [],
                    "version": CACHE_VERSION,
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "corrupted"


@pytest.mark.parametrize(
    "field,value",
    [
        ("luminance", "not-a-list"),
        ("motion", [False]),
        ("metadata.fps", "not-a-fraction"),
        ("metadata.fps", "24000/0"),
        ("metadata.version", "3"),
        ("metadata.clips.0.path", 123),
        ("metadata.clips.0.size", True),
        ("metadata.clips.0.mtime", False),
        ("metadata.clips.0.sha1", 123),
    ],
)
def test_load_malformed_nested_payload_returns_corrupted(
    tmp_path: Path, field: str, value: object
) -> None:
    payload: dict[str, object] = {
        "version": CACHE_VERSION,
        "fingerprint": "fp",
        "luminance": [0.1],
        "motion": [0.0],
        "metadata": {
            "frame_count": 1,
            "source_frame_count": 1,
            "metric_source_start": 0,
            "metric_source_end_exclusive": 1,
            "fps": "24/1",
            "config_fingerprint": "fp",
            "analysis_source_path": "",
            "clips": [{"path": "video.mkv", "size": 10, "mtime": 1.0, "sha1": None}],
            "performance_mode": "quality",
            "algorithm_id": metric_algorithm_id(AnalysisConfig()),
            "metric_backend": metric_backend(AnalysisConfig()),
            "algorithm_identity_json": stable_metric_algorithm_identity_json(AnalysisConfig()),
            "metric_active_rect": None,
            "active_rect_source": "full-frame",
            "active_rect_detection_mode": "aspect_ratio",
            "active_rect_algorithm_id": "active_rect_resolution_v2",
            "version": CACHE_VERSION,
        },
    }
    _set_payload_field(payload, field, value)
    cache_file(tmp_path, "fp").write_text(json.dumps(payload), encoding="utf-8")

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is False
    assert result.reason == "corrupted"


def _set_payload_field(payload: dict[str, object], field: str, value: object) -> None:
    current: object = payload
    parts = field.split(".")
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
            continue
        if isinstance(current, list):
            current = current[int(part)]
            continue
        raise AssertionError(f"unsupported payload path: {field}")

    if isinstance(current, dict):
        current[parts[-1]] = value
        return
    if isinstance(current, list):
        current[int(parts[-1])] = value
        return
    raise AssertionError(f"unsupported payload path: {field}")
