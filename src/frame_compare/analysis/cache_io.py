"""Cache I/O operations for analysis metrics."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, cast

from frame_compare.analysis.metric_identity import stable_metric_algorithm_identity_json
from frame_compare.analysis.types import (
    ActiveRectAlgorithmId,
    ActiveRectDetectionMode,
    ActiveRectSource,
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    MetricActiveRect,
    MetricCacheRequest,
    MetricFrameRange,
    MetricsMetadata,
)
from frame_compare.utils.atomic_write import write_text_atomic

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig

CACHE_FILE_EXTENSION: str = ".compframes"
CACHE_LABEL_MAX_LENGTH: int = 80
CACHE_VERSION: int = 7
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


def compute_cache_key(
    video_paths: list[Path],
    config: AnalysisConfig,
    *,
    selection_domain: str | None = None,
    metric_request: MetricCacheRequest | None = None,
) -> str:
    """Generate deterministic cache key from video files and analysis config."""
    h = hashlib.sha256()
    if video_paths:
        reference_path = video_paths[0]
        stat = reference_path.stat()
        h.update(f"reference|{reference_path}|{stat.st_size}|{stat.st_mtime_ns}".encode())
    if selection_domain is not None:
        h.update(f"selection_domain|{selection_domain}".encode())
    for p in _sorted_video_paths(video_paths):
        stat = p.stat()
        h.update(f"{p}|{stat.st_size}|{stat.st_mtime_ns}".encode())
    h.update(
        f"{config.ignore_lead_seconds}|{config.ignore_trail_seconds}|"
        f"{config.min_window_seconds}".encode()
    )
    request = metric_request or MetricCacheRequest(
        analysis_source_path=video_paths[0] if video_paths else None
    )
    h.update(f"metric_request|{_metric_cache_request_token(request)}".encode())
    h.update(f"metric_algorithm|{stable_metric_algorithm_identity_json(config)}".encode())
    h.update(str(CACHE_VERSION).encode("utf-8"))
    return h.hexdigest()


def _metric_active_rect_token(rect: MetricActiveRect | None) -> str:
    if rect is None:
        return "full_frame"
    return f"rect:{rect.x},{rect.y},{rect.width},{rect.height}"


def _metric_cache_request_token(request: MetricCacheRequest) -> str:
    effective_fps = (
        "source"
        if request.effective_fps is None
        else f"{request.effective_fps.numerator}/{request.effective_fps.denominator}"
    )
    source_path = "" if request.analysis_source_path is None else str(request.analysis_source_path)
    frame_range = request.metric_frame_range
    frame_range_token = (
        "full_source"
        if frame_range is None
        else (f"{frame_range.source_frame_count}:{frame_range.start}:{frame_range.end_exclusive}")
    )
    return "|".join(
        (
            f"source:{source_path}",
            f"frame_range:{frame_range_token}",
            f"effective_fps:{effective_fps}",
            f"rect:{_metric_active_rect_token(request.metric_active_rect)}",
            f"rect_source:{request.active_rect_source}",
            f"detection:{request.active_rect_detection_mode}",
            f"algorithm:{request.active_rect_algorithm_id}",
        )
    )


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


def load_cached_metrics_for_request(
    cache_dir: Path,
    fingerprint: str,
    clips: list[ClipIdentity],
    request: MetricCacheRequest,
) -> CacheLoadResult:
    """Load metrics only when stored metadata matches the complete request identity."""
    result = load_cached_metrics(cache_dir, fingerprint, clips)
    if not (result.success and result.metrics is not None):
        return result
    if not _metrics_metadata_matches_request(result.metrics.metadata, request):
        return CacheLoadResult(success=False, reason="mismatched_inputs")
    return result


def _metrics_metadata_matches_request(
    metadata: MetricsMetadata,
    request: MetricCacheRequest,
) -> bool:
    expected_source = (
        "" if request.analysis_source_path is None else str(request.analysis_source_path)
    )
    frame_range_matches = (
        metadata.metric_source_start == 0
        and metadata.metric_source_end_exclusive == metadata.source_frame_count
        if request.metric_frame_range is None
        else (
            metadata.source_frame_count == request.metric_frame_range.source_frame_count
            and metadata.metric_source_start == request.metric_frame_range.start
            and metadata.metric_source_end_exclusive == request.metric_frame_range.end_exclusive
        )
    )
    return (
        metadata.analysis_source_path == expected_source
        and frame_range_matches
        and metadata.metric_active_rect == request.metric_active_rect
        and metadata.active_rect_source == request.active_rect_source
        and metadata.active_rect_detection_mode == request.active_rect_detection_mode
        and metadata.active_rect_algorithm_id == request.active_rect_algorithm_id
        and (request.effective_fps is None or metadata.fps == request.effective_fps)
    )


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
    luminance = _parse_numeric_series(data["luminance"])
    motion = _parse_numeric_series(data["motion"])
    _validate_metric_arrays(
        luminance=luminance,
        motion=motion,
        frame_count=metadata.frame_count,
        metric_source_start=metadata.metric_source_start,
    )
    return _ValidatedCachePayload(
        luminance=luminance,
        motion=motion,
        metadata=metadata,
    )


def _parse_numeric_series(value: object) -> list[float]:
    if not isinstance(value, list):
        raise _CacheParseError

    series: list[float] = []
    for item in cast(list[object], value):
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise _CacheParseError
        value = float(item)
        if not math.isfinite(value):
            raise _CacheParseError
        series.append(value)
    return series


def _validate_metric_arrays(
    *,
    luminance: list[float],
    motion: list[float],
    frame_count: int,
    metric_source_start: int,
) -> None:
    if len(luminance) != frame_count or len(motion) != frame_count:
        raise _CacheParseError
    if motion and metric_source_start == 0 and motion[0] != 0.0:
        raise _CacheParseError


def _parse_metrics_metadata(data: Mapping[str, object]) -> MetricsMetadata:
    _require_keys(
        data,
        {
            "frame_count",
            "fps",
            "config_fingerprint",
            "clips",
            "source_frame_count",
            "metric_source_start",
            "metric_source_end_exclusive",
            "analysis_source_path",
            "performance_mode",
            "algorithm_id",
            "metric_backend",
            "algorithm_identity_json",
            "metric_active_rect",
            "active_rect_source",
            "active_rect_detection_mode",
            "active_rect_algorithm_id",
        },
    )

    frame_count = data["frame_count"]
    if not isinstance(frame_count, int) or isinstance(frame_count, bool) or frame_count < 0:
        raise _CacheParseError

    source_frame_count = _parse_nonnegative_int(data["source_frame_count"])
    metric_source_start = _parse_nonnegative_int(data["metric_source_start"])
    metric_source_end_exclusive = _parse_nonnegative_int(data["metric_source_end_exclusive"])
    try:
        MetricFrameRange(
            source_frame_count=source_frame_count,
            start=metric_source_start,
            end_exclusive=metric_source_end_exclusive,
        )
    except ValueError as exc:
        raise _CacheParseError from exc
    if metric_source_end_exclusive - metric_source_start != frame_count:
        raise _CacheParseError

    fps = data["fps"]
    if not isinstance(fps, str):
        raise _CacheParseError

    config_fingerprint = data["config_fingerprint"]
    if not isinstance(config_fingerprint, str):
        raise _CacheParseError

    analysis_source_path = data["analysis_source_path"]
    if not isinstance(analysis_source_path, str):
        raise _CacheParseError

    performance_mode = data["performance_mode"]
    if not isinstance(performance_mode, str):
        raise _CacheParseError

    algorithm_id = data["algorithm_id"]
    if not isinstance(algorithm_id, str):
        raise _CacheParseError

    metric_backend = data["metric_backend"]
    if not isinstance(metric_backend, str):
        raise _CacheParseError

    algorithm_identity_json = data["algorithm_identity_json"]
    if not isinstance(algorithm_identity_json, str):
        raise _CacheParseError
    algorithm_identity = _parse_algorithm_identity_json(algorithm_identity_json)
    _validate_algorithm_metadata_fields(
        algorithm_id=algorithm_id,
        metric_backend=metric_backend,
        performance_mode=performance_mode,
        algorithm_identity_json=algorithm_identity_json,
        algorithm_identity=algorithm_identity,
    )

    active_rect_source = _parse_active_rect_source(data["active_rect_source"])
    active_rect_detection_mode = _parse_active_rect_detection_mode(
        data["active_rect_detection_mode"]
    )
    active_rect_algorithm_id = _parse_active_rect_algorithm_id(data["active_rect_algorithm_id"])

    try:
        return MetricsMetadata(
            frame_count=frame_count,
            fps=Fraction(fps),
            config_fingerprint=config_fingerprint,
            clips=_parse_clip_identities(data["clips"]),
            source_frame_count=source_frame_count,
            metric_source_start=metric_source_start,
            metric_source_end_exclusive=metric_source_end_exclusive,
            analysis_source_path=analysis_source_path,
            performance_mode=performance_mode,
            algorithm_id=algorithm_id,
            metric_backend=metric_backend,
            algorithm_identity_json=algorithm_identity_json,
            metric_active_rect=_parse_metric_active_rect(data["metric_active_rect"]),
            active_rect_source=active_rect_source,
            active_rect_detection_mode=active_rect_detection_mode,
            active_rect_algorithm_id=active_rect_algorithm_id,
            version=_parse_cache_version(data.get("version", CACHE_VERSION)),
        )
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise _CacheParseError from exc


def _parse_clip_identities(value: object) -> list[ClipIdentity]:
    if not isinstance(value, list):
        raise _CacheParseError
    return [_parse_clip_identity(_as_mapping(entry)) for entry in cast(list[object], value)]


def _parse_metric_active_rect(value: object) -> MetricActiveRect | None:
    if value is None:
        return None
    data = _as_mapping(value)
    _require_keys(data, {"x", "y", "width", "height"})
    fields: dict[str, int] = {}
    for key in ("x", "y", "width", "height"):
        item = data[key]
        if not isinstance(item, int) or isinstance(item, bool):
            raise _CacheParseError
        fields[key] = item
    if fields["x"] < 0 or fields["y"] < 0 or fields["width"] <= 0 or fields["height"] <= 0:
        raise _CacheParseError
    try:
        return MetricActiveRect(
            x=fields["x"],
            y=fields["y"],
            width=fields["width"],
            height=fields["height"],
        )
    except TypeError as exc:
        raise _CacheParseError from exc


def _parse_active_rect_source(value: object) -> ActiveRectSource:
    if value not in {
        "explicit",
        "metadata",
        "dimension-derived",
        "aspect-ratio-derived",
        "content-derived",
        "full-frame",
    }:
        raise _CacheParseError
    return cast(ActiveRectSource, value)


def _parse_active_rect_detection_mode(value: object) -> ActiveRectDetectionMode:
    if value not in {"provided", "dimension", "aspect_ratio", "auto"}:
        raise _CacheParseError
    return cast(ActiveRectDetectionMode, value)


def _parse_active_rect_algorithm_id(value: object) -> ActiveRectAlgorithmId:
    if value != "active_rect_resolution_v2":
        raise _CacheParseError
    return cast(ActiveRectAlgorithmId, value)


def _parse_algorithm_identity_json(value: str) -> Mapping[str, object]:
    try:
        raw_data: object = json.loads(value)
    except json.JSONDecodeError as exc:
        raise _CacheParseError from exc
    return _as_mapping(raw_data)


def _validate_algorithm_metadata_fields(
    *,
    algorithm_id: str,
    metric_backend: str,
    performance_mode: str,
    algorithm_identity_json: str,
    algorithm_identity: Mapping[str, object],
) -> None:
    expected_algorithm_id = hashlib.sha256(algorithm_identity_json.encode("utf-8")).hexdigest()
    if algorithm_id != expected_algorithm_id:
        raise _CacheParseError

    identity_backend = algorithm_identity.get("backend")
    if not isinstance(identity_backend, str) or metric_backend != identity_backend:
        raise _CacheParseError

    identity_performance_mode = algorithm_identity.get("performance_mode")
    if (
        not isinstance(identity_performance_mode, str)
        or performance_mode != identity_performance_mode
    ):
        raise _CacheParseError


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


def _parse_nonnegative_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
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
            "source_frame_count": metrics.metadata.source_frame_count,
            "metric_source_start": metrics.metadata.metric_source_start,
            "metric_source_end_exclusive": metrics.metadata.metric_source_end_exclusive,
            "fps": str(metrics.metadata.fps),
            "config_fingerprint": metrics.metadata.config_fingerprint,
            "analysis_source_path": metrics.metadata.analysis_source_path,
            "performance_mode": metrics.metadata.performance_mode,
            "algorithm_id": metrics.metadata.algorithm_id,
            "metric_backend": metrics.metadata.metric_backend,
            "algorithm_identity_json": metrics.metadata.algorithm_identity_json,
            "metric_active_rect": _serialize_metric_active_rect(
                metrics.metadata.metric_active_rect
            ),
            "active_rect_source": metrics.metadata.active_rect_source,
            "active_rect_detection_mode": metrics.metadata.active_rect_detection_mode,
            "active_rect_algorithm_id": metrics.metadata.active_rect_algorithm_id,
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


def _serialize_metric_active_rect(rect: MetricActiveRect | None) -> dict[str, int] | None:
    if rect is None:
        return None
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
    }
