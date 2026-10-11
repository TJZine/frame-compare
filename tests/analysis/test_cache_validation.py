"""Malformed cache and version-rejection contract tests."""

import json
from pathlib import Path

import pytest

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    load_cached_metrics,
    read_cache_version,
)
from frame_compare.config.schema import AnalysisConfig
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
                    "fps": "24/1",
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
                    "fps": "24/1",
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
