"""Tests for cache I/O operations."""

import json
import os
from fractions import Fraction
from pathlib import Path

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config.schema import AnalysisConfig, SelectionMode

FIXED_MTIME = 1704067200.0  # 2024-01-01 00:00:00 UTC


def create_video_file(tmp_path: Path, name: str = "video.mkv", content: bytes = b"test") -> Path:
    """Create a dummy video file with fixed mtime."""
    f = tmp_path / name
    f.write_bytes(content)
    os.utime(f, (FIXED_MTIME, FIXED_MTIME))
    return f


def test_compute_cache_key_deterministic(tmp_path: Path) -> None:
    """Same paths + config → same 64-char hex."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(frame_count=10)
    key1 = compute_cache_key([v1], config)
    key2 = compute_cache_key([v1], config)
    assert key1 == key2
    assert len(key1) == 64


def test_compute_cache_key_order_independent(tmp_path: Path) -> None:
    """[a, b] → same key as [b, a]."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    v2 = create_video_file(tmp_path, "v2.mkv")
    config = AnalysisConfig(frame_count=10)
    key1 = compute_cache_key([v1, v2], config)
    key2 = compute_cache_key([v2, v1], config)
    assert key1 == key2


def test_compute_cache_key_changes_on_frame_count(tmp_path: Path) -> None:
    """Different frame_count → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(frame_count=10))
    key2 = compute_cache_key([v1], AnalysisConfig(frame_count=20))
    assert key1 != key2


def test_compute_cache_key_changes_on_selection_mode(tmp_path: Path) -> None:
    """Different selection_mode → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(selection_mode=SelectionMode.MIXED))
    key2 = compute_cache_key([v1], AnalysisConfig(selection_mode=SelectionMode.RANDOM))
    assert key1 != key2


def test_compute_cache_key_changes_on_random_seed(tmp_path: Path) -> None:
    """Different random_seed → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(random_seed=42))
    key2 = compute_cache_key([v1], AnalysisConfig(random_seed=43))
    assert key1 != key2


def test_compute_cache_key_changes_on_dark_quantile(tmp_path: Path) -> None:
    """Different dark_quantile → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(dark_quantile=0.05))
    key2 = compute_cache_key([v1], AnalysisConfig(dark_quantile=0.10))
    assert key1 != key2


def test_compute_cache_key_changes_on_bright_quantile(tmp_path: Path) -> None:
    """Different bright_quantile → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(bright_quantile=0.95))
    key2 = compute_cache_key([v1], AnalysisConfig(bright_quantile=0.90))
    assert key1 != key2


def test_compute_cache_key_changes_on_path_change(tmp_path: Path) -> None:
    """Rename file → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(frame_count=10)
    key1 = compute_cache_key([v1], config)

    v2 = tmp_path / "v2.mkv"
    v1.rename(v2)
    key2 = compute_cache_key([v2], config)
    assert key1 != key2


def test_compute_cache_key_changes_on_size_change(tmp_path: Path) -> None:
    """Write more bytes to file → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv", content=b"test")
    key1 = compute_cache_key([v1], AnalysisConfig(frame_count=10))

    create_video_file(tmp_path, "v1.mkv", content=b"test-longer")
    key2 = compute_cache_key([v1], AnalysisConfig(frame_count=10))
    assert key1 != key2


def test_compute_cache_key_changes_on_mtime_change(tmp_path: Path) -> None:
    """os.utime(path, (new_mtime, new_mtime)) → different key."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    key1 = compute_cache_key([v1], AnalysisConfig(frame_count=10))

    os.utime(v1, (FIXED_MTIME + 1, FIXED_MTIME + 1))
    key2 = compute_cache_key([v1], AnalysisConfig(frame_count=10))
    assert key1 != key2


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """Save → load → success=True, data matches, fps == Fraction(24)."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(frame_count=10)
    fingerprint = compute_cache_key([v1], config)

    clips = [ClipIdentity(path=str(v1), size=v1.stat().st_size, mtime=v1.stat().st_mtime)]
    metadata = MetricsMetadata(
        frame_count=100,
        fps=Fraction(24, 1),
        config_fingerprint=fingerprint,
        clips=clips,
    )
    metrics = FrameMetrics(
        luminance=[0.1, 0.2, 0.3],
        motion=[0.0, 0.5, 0.1],
        metadata=metadata,
    )

    save_metrics_cache(metrics, tmp_path)
    result = load_cached_metrics(tmp_path, fingerprint, clips)

    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.luminance == [0.1, 0.2, 0.3]
    assert result.metrics.motion == [0.0, 0.5, 0.1]
    assert result.metrics.metadata.frame_count == 100
    assert result.metrics.metadata.fps == Fraction(24, 1)
    assert result.metrics.metadata.config_fingerprint == fingerprint


def test_load_not_found(tmp_path: Path) -> None:
    """Empty dir → reason="not_found"."""
    result = load_cached_metrics(tmp_path, "some-fingerprint", [])
    assert result.success is False
    assert result.reason == "not_found"


def test_load_corrupted(tmp_path: Path) -> None:
    """Invalid JSON → reason="corrupted"."""
    cache_file = tmp_path / "cache.compframes"
    cache_file.write_text("invalid json")
    result = load_cached_metrics(tmp_path, "some-fingerprint", [])
    assert result.success is False
    assert result.reason == "corrupted"


def test_load_version_mismatch(tmp_path: Path) -> None:
    """Wrong version → reason="version_mismatch"."""
    cache_file = tmp_path / "cache.compframes"
    cache_file.write_text(
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


def test_load_fingerprint_mismatch(tmp_path: Path) -> None:
    """Wrong fingerprint → reason="fingerprint_mismatch"."""
    cache_file = tmp_path / "cache.compframes"
    cache_file.write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp1",
                "luminance": [],
                "motion": [],
                "metadata": {
                    "frame_count": 0,
                    "fps": "24/1",
                    "config_fingerprint": "fp1",
                    "clips": [],
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp2", [])
    assert result.success is False
    assert result.reason == "fingerprint_mismatch"


def test_save_creates_directory(tmp_path: Path) -> None:
    """Non-existent dir → created."""
    sub_dir = tmp_path / "new_dir"
    metadata = MetricsMetadata(
        frame_count=0,
        fps=Fraction(24, 1),
        config_fingerprint="fp",
        clips=[],
    )
    metrics = FrameMetrics(luminance=[], motion=[], metadata=metadata)
    save_metrics_cache(metrics, sub_dir)
    assert sub_dir.exists()
    assert (sub_dir / "cache.compframes").exists()


def test_save_writes_required_keys(tmp_path: Path) -> None:
    """Cache file JSON has all required keys + version == CACHE_VERSION."""
    metadata = MetricsMetadata(
        frame_count=10,
        fps=Fraction(24000, 1001),
        config_fingerprint="fp",
        clips=[],
    )
    metrics = FrameMetrics(luminance=[0.5], motion=[0.1], metadata=metadata)
    save_metrics_cache(metrics, tmp_path)

    with (tmp_path / "cache.compframes").open("r") as f:
        data = json.load(f)

    assert data["version"] == CACHE_VERSION
    assert "fingerprint" in data
    assert "luminance" in data
    assert "motion" in data
    assert "metadata" in data
    assert data["metadata"]["frame_count"] == 10
    assert data["metadata"]["fps"] == "24000/1001"


def test_load_missing_key_returns_corrupted(tmp_path: Path) -> None:
    """Missing luminance key → reason="corrupted"."""
    cache_file = tmp_path / "cache.compframes"
    # Missing luminance
    cache_file.write_text(
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
                },
            }
        )
    )
    result = load_cached_metrics(tmp_path, "fp", [])
    assert result.success is False
    assert result.reason == "corrupted"
