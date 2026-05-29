"""Cache I/O operations for analysis metrics."""

from __future__ import annotations

import hashlib
import json
import re
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
from frame_compare.utils.atomic_write import write_text_atomic

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig

CACHE_FILE_EXTENSION: str = ".compframes"
CACHE_LABEL_MAX_LENGTH: int = 80
CACHE_VERSION: int = 3
_SAFE_LABEL_CHARS = re.compile(r"[^a-z0-9._-]+")
_MULTI_SEPARATOR = re.compile(r"[-_.]{2,}")


class _CacheParseError(ValueError):
    """Raised when a cache file matches the key but not the schema."""


@dataclass(frozen=True, slots=True)
class _ValidatedCachePayload:
    luminance: list[float]
    motion: list[float]
    metadata: MetricsMetadata


def _cache_path_sort_key(path: Path) -> str:
    return path.as_posix()


def _sorted_video_paths(video_paths: list[Path]) -> list[Path]:
    return sorted(video_paths, key=_cache_path_sort_key)


def compute_cache_key(video_paths: list[Path], config: AnalysisConfig) -> str:
    """Generate deterministic cache key from video files and analysis config."""
    h = hashlib.sha256()
    for p in _sorted_video_paths(video_paths):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime_ns}".encode())
    h.update(
        f"{config.frame_count}|{config.selection_mode.value}|{config.random_seed}|"
        f"{config.dark_quantile}|{config.bright_quantile}".encode()
    )
    h.update(str(CACHE_VERSION).encode("utf-8"))
    return h.hexdigest()


def build_cache_label(video_paths: list[Path]) -> str:
    """Build a filesystem-safe human label from input filename stems."""
    parts: list[str] = []
    for path in _sorted_video_paths(video_paths):
        label = _sanitize_cache_label(path.stem)
        if label:
            parts.append(label)
    if not parts:
        return "analysis"

    label = "__".join(parts)
    if len(label) > CACHE_LABEL_MAX_LENGTH:
        label = label[:CACHE_LABEL_MAX_LENGTH].rstrip("-_.")
    return label or "analysis"


def metrics_cache_filename(video_paths: list[Path], fingerprint: str) -> str:
    """Return the labeled filename for an analysis cache entry."""
    return f"{build_cache_label(video_paths)}__{fingerprint}{CACHE_FILE_EXTENSION}"


def find_metrics_cache_file(cache_dir: Path, fingerprint: str) -> Path | None:
    """Find the shared analysis cache file for a full fingerprint."""
    fingerprint_suffix = f"__{fingerprint}{CACHE_FILE_EXTENSION}"
    try:
        entries = sorted(cache_dir.iterdir(), key=lambda path: path.name)
    except OSError:
        return None
    for path in entries:
        if path.is_file() and path.name.endswith(fingerprint_suffix):
            return path
    return None


def delete_metrics_cache_entry(cache_dir: Path, fingerprint: str) -> None:
    """Delete shared analysis cache files matching a full fingerprint."""
    fingerprint_suffix = f"__{fingerprint}{CACHE_FILE_EXTENSION}"
    try:
        entries = list(cache_dir.iterdir())
    except OSError:
        return
    for path in entries:
        if not path.is_file() or not path.name.endswith(fingerprint_suffix):
            continue
        path.unlink()
        sidecar_path = path.with_suffix(".meta.json")
        if sidecar_path.exists():
            sidecar_path.unlink()


def read_cache_version(cache_path: Path) -> str | None:
    """Read the top-level version from a cache payload for error reporting."""
    try:
        raw_data: object = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw_data, Mapping):
        return None
    data = cast(Mapping[str, object], raw_data)
    version = data.get("version")
    return str(version) if version is not None else None


def _sanitize_cache_label(value: str) -> str:
    label = value.lower()
    label = _SAFE_LABEL_CHARS.sub("-", label)
    label = _MULTI_SEPARATOR.sub("-", label)
    return label.strip("-_.")


def load_cached_metrics(
    cache_dir: Path,
    fingerprint: str,
    clips: list[ClipIdentity],
) -> CacheLoadResult:
    """Load analysis metrics when the cache file matches the expected schema.

    The `clips` parameter is reserved for future validation; currently ignored.
    """
    cache_path = find_metrics_cache_file(cache_dir, fingerprint)
    if cache_path is None:
        return CacheLoadResult(success=False, reason="not_found")
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
    except (ValueError, TypeError, ZeroDivisionError) as exc:
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
    cache_path = cache_dir / metrics_cache_filename(
        [Path(clip.path) for clip in metrics.metadata.clips],
        metrics.metadata.config_fingerprint,
    )

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

    write_text_atomic(cache_path, json.dumps(data, indent=2), encoding="utf-8")
