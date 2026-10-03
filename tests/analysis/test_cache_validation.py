"""Malformed cache and version-rejection contract tests."""

import json
from pathlib import Path

from frame_compare.analysis.cache_io import CACHE_VERSION, load_cached_metrics
from tests.analysis._cache_io_test_helpers import cache_file


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
