"""Cache I/O operations for analysis metrics."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, cast

from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    MetricsMetadata,
)

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig

CACHE_FILENAME: str = "cache.compframes"
CACHE_VERSION: int = 3


class _CacheParseError(ValueError):
    """Raised when a cache file matches the key but not the schema."""


@dataclass(frozen=True, slots=True)
class _ValidatedCachePayload:
    luminance: list[float]
    motion: list[float]
    metadata: MetricsMetadata


def compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str:
    """Generate deterministic cache key from video files and analysis config."""
    h = hashlib.sha256()
    for p in sorted(video_paths, key=str):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime_ns}".encode())
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
    """Load analysis metrics when the cache file matches the expected schema.

    The `clips` parameter is reserved for future validation; currently ignored.
    """
    cache_path = cache_dir / CACHE_FILENAME
    if not cache_path.exists():
        return CacheLoadResult(success=False, reason="not_found")

    try:
        with cache_path.open("r", encoding="utf-8") as f:
            raw_data: object = json.load(f)
    except (json.JSONDecodeError, OSError):
        return CacheLoadResult(success=False, reason="corrupted")

    try:
        data = _as_mapping(raw_data)
        _validate_cache_identity(data, fingerprint)
        payload = _parse_cache_payload(data)
    except _CacheVersionMismatch:
        return CacheLoadResult(success=False, reason="version_mismatch")
    except _CacheFingerprintMismatch:
        return CacheLoadResult(success=False, reason="mismatched_inputs")
    except _CacheParseError:
        return CacheLoadResult(success=False, reason="corrupted")

    metrics = FrameMetrics(
        luminance=payload.luminance,
        motion=payload.motion,
        metadata=payload.metadata,
    )
    return CacheLoadResult(success=True, metrics=metrics)


class _CacheVersionMismatch(_CacheParseError):
    pass


class _CacheFingerprintMismatch(_CacheParseError):
    pass


def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _CacheParseError
    return cast(Mapping[str, object], value)


def _require_keys(data: Mapping[str, object], keys: set[str]) -> None:
    if not all(key in data for key in keys):
        raise _CacheParseError


def _validate_cache_identity(data: Mapping[str, object], fingerprint: str) -> None:
    _require_keys(data, {"version", "fingerprint", "luminance", "motion", "metadata"})

    if data["version"] != CACHE_VERSION:
        raise _CacheVersionMismatch
    if data["fingerprint"] != fingerprint:
        raise _CacheFingerprintMismatch


def _parse_cache_payload(data: Mapping[str, object]) -> _ValidatedCachePayload:
    metadata = _parse_metrics_metadata(_as_mapping(data["metadata"]))
    return _ValidatedCachePayload(
        luminance=_parse_numeric_series(data["luminance"]),
        motion=_parse_numeric_series(data["motion"]),
        metadata=metadata,
    )


def _parse_numeric_series(value: object) -> list[float]:
    if not isinstance(value, list):
        raise _CacheParseError

    series: list[float] = []
    for item in cast(list[object], value):
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise _CacheParseError
        series.append(float(item))
    return series


def _parse_metrics_metadata(data: Mapping[str, object]) -> MetricsMetadata:
    _require_keys(data, {"frame_count", "fps", "config_fingerprint", "clips"})

    frame_count = data["frame_count"]
    if not isinstance(frame_count, int) or isinstance(frame_count, bool) or frame_count < 0:
        raise _CacheParseError

    fps = data["fps"]
    if not isinstance(fps, str):
        raise _CacheParseError

    config_fingerprint = data["config_fingerprint"]
    if not isinstance(config_fingerprint, str):
        raise _CacheParseError

    try:
        return MetricsMetadata(
            frame_count=frame_count,
            fps=Fraction(fps),
            config_fingerprint=config_fingerprint,
            clips=_parse_clip_identities(data["clips"]),
            version=_parse_cache_version(data.get("version", CACHE_VERSION)),
        )
    except (ValueError, TypeError) as exc:
        raise _CacheParseError from exc


def _parse_clip_identities(value: object) -> list[ClipIdentity]:
    if not isinstance(value, list):
        raise _CacheParseError
    return [_parse_clip_identity(_as_mapping(entry)) for entry in cast(list[object], value)]


def _parse_clip_identity(data: Mapping[str, object]) -> ClipIdentity:
    _require_keys(data, {"path", "size", "mtime"})

    path = data["path"]
    if not isinstance(path, str):
        raise _CacheParseError

    size = data["size"]
    if not isinstance(size, int) or isinstance(size, bool):
        raise _CacheParseError

    mtime = data["mtime"]
    if not isinstance(mtime, (int, float)) or isinstance(mtime, bool):
        raise _CacheParseError

    sha1 = data.get("sha1")
    if sha1 is not None and not isinstance(sha1, str):
        raise _CacheParseError

    return ClipIdentity(path=path, size=size, mtime=float(mtime), sha1=sha1)


def _parse_cache_version(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _CacheParseError
    return value


def save_metrics_cache(metrics: FrameMetrics, cache_dir: Path) -> None:
    """Persist analysis metrics to cache file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / CACHE_FILENAME

    data: dict[str, object] = {
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
