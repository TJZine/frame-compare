"""Cache persistence contract tests."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.analysis.cache_io import (
    delete_metrics_cache_entry,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.types import FrameMetrics, MetricsMetadata
from frame_compare.config.schema import AnalysisConfig
from tests.analysis._cache_io_test_helpers import cache_file, metrics_metadata


def test_load_not_found(tmp_path: Path) -> None:
    """Empty dir → reason="not_found"."""
    result = load_cached_metrics(tmp_path, "some-fingerprint", [])
    assert result.success is False
    assert result.reason == "not_found"


def test_load_ignores_legacy_single_cache_filename(tmp_path: Path) -> None:
    """Legacy run-folder cache filename is not a shared-cache hit."""
    (tmp_path / "cache.compframes").write_text("invalid json", encoding="utf-8")

    result = load_cached_metrics(tmp_path, "some-fingerprint", [])

    assert result.success is False
    assert result.reason == "not_found"


def test_delete_metrics_cache_entry_deletes_only_matching_fingerprint(tmp_path: Path) -> None:
    matching = cache_file(tmp_path, "fp")
    matching.write_text("{}", encoding="utf-8")
    matching_sidecar = matching.with_suffix(".meta.json")
    matching_sidecar.write_text("{}", encoding="utf-8")
    other = cache_file(tmp_path, "other")
    other.write_text("{}", encoding="utf-8")

    delete_metrics_cache_entry(tmp_path, "fp")

    assert not matching.exists()
    assert not matching_sidecar.exists()
    assert other.exists()


def test_save_creates_directory(tmp_path: Path) -> None:
    """Non-existent dir → created."""
    sub_dir = tmp_path / "new_dir"
    metadata = metrics_metadata(
        frame_count=0,
        fps=Fraction(24, 1),
        config_fingerprint="fp",
        clips=[],
        config=AnalysisConfig(),
    )
    metrics = FrameMetrics(luminance=[], motion=[], metadata=metadata)
    save_metrics_cache(metrics, sub_dir)
    assert sub_dir.exists()
    assert (sub_dir / "analysis__fp.compframes").exists()


def test_save_metrics_cache_uses_atomic_text_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata = MetricsMetadata(
        frame_count=10,
        fps=Fraction(24, 1),
        config_fingerprint="fp",
        clips=[],
    )
    metrics = FrameMetrics(luminance=[0.5], motion=[0.1], metadata=metadata)
    calls: list[tuple[Path, str, str]] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append((path, content, encoding))
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.analysis.cache_io.write_text_atomic", _fake_write)

    save_metrics_cache(metrics, tmp_path)

    assert calls
    assert calls[0][0] == tmp_path / "analysis__fp.compframes"
    assert calls[0][2] == "utf-8"
    assert json.loads(calls[0][1])["fingerprint"] == "fp"
