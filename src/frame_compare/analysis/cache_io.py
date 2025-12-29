"""Cache I/O operations for analysis metrics."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    MetricsMetadata,
)

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig

CACHE_FILENAME: str = "cache.compframes"
CACHE_VERSION: int = 2


def compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str:
    """Generate deterministic cache key from video files and analysis config.

    Args:
        video_paths: List of paths to video files involved in comparison.
        config: Analysis configuration settings.

    Returns:
        64-character SHA256 hex digest.
    """
    h = hashlib.sha256()
    for p in sorted(video_paths, key=str):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime}".encode())
    h.update(
        f"{config.frame_count}|{config.selection_mode.value}|{config.random_seed}|"
        f"{config.dark_quantile}|{config.bright_quantile}".encode()
    )
    h.update(str(CACHE_VERSION).encode("utf-8"))
    return h.hexdigest()


def load_cached_metrics(
    cache_dir: Path,
    fingerprint: str,
    clips: list[ClipIdentity],
) -> CacheLoadResult:
    """Attempt to load analysis metrics from cache file.

    Args:
        cache_dir: Directory containing the cache file.
        fingerprint: Expected cache key fingerprint.
        clips: Reserved for future validation; currently ignored.

    Returns:
        CacheLoadResult indicating success or failure reason.
    """
    cache_path = cache_dir / CACHE_FILENAME
    if not cache_path.exists():
        return CacheLoadResult(success=False, reason="not_found")

    try:
        with cache_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return CacheLoadResult(success=False, reason="corrupted")

    # Required top-level keys
    required_keys = {"version", "fingerprint", "luminance", "motion", "metadata"}
    if not all(k in data for k in required_keys):
        return CacheLoadResult(success=False, reason="corrupted")

    if data["version"] != CACHE_VERSION:
        return CacheLoadResult(success=False, reason="version_mismatch")

    if data["fingerprint"] != fingerprint:
        return CacheLoadResult(success=False, reason="fingerprint_mismatch")

    metadata_dict = data["metadata"]
    # Required metadata keys
    required_metadata_keys = {"frame_count", "fps", "config_fingerprint", "clips"}
    if not all(k in metadata_dict for k in required_metadata_keys):
        return CacheLoadResult(success=False, reason="corrupted")

    try:
        metadata = MetricsMetadata(
            frame_count=metadata_dict["frame_count"],
            fps=Fraction(metadata_dict["fps"]),
            config_fingerprint=metadata_dict["config_fingerprint"],
            clips=[
                ClipIdentity(
                    path=c["path"],
                    size=c["size"],
                    mtime=c["mtime"],
                    sha1=c.get("sha1"),
                )
                for c in metadata_dict["clips"]
            ],
            version=metadata_dict.get("version", CACHE_VERSION),
        )

        metrics = FrameMetrics(
            luminance=data["luminance"],
            motion=data["motion"],
            metadata=metadata,
        )
    except (KeyError, ValueError, TypeError):
        return CacheLoadResult(success=False, reason="corrupted")

    return CacheLoadResult(success=True, metrics=metrics)


def save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None:
    """Persist analysis metrics to cache file.

    Args:
        metrics: Metrics to save.
        cache_dir: Directory to save the cache file in.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / CACHE_FILENAME

    data: dict[str, Any] = {
        "version": CACHE_VERSION,
        "fingerprint": metrics.metadata.config_fingerprint,
        "luminance": list(metrics.luminance),
        "motion": list(metrics.motion),
        "metadata": {
            "frame_count": metrics.metadata.frame_count,
            "fps": str(metrics.metadata.fps),
            "config_fingerprint": metrics.metadata.config_fingerprint,
            "clips": [
                {
                    "path": str(c.path),
                    "size": c.size,
                    "mtime": c.mtime,
                    "sha1": c.sha1,
                }
                for c in metrics.metadata.clips
            ],
            "version": metrics.metadata.version,
        },
    }

    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
