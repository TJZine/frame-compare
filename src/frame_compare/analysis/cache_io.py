"""Cache I/O operations for analysis metrics."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr

from frame_compare.analysis.errors import AnalysisCacheMissError
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
    MetricsMetadata,
)
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.cache_errors import CacheCorruptionError
from frame_compare.utils.cancellation import raise_if_cancelling

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig

CACHE_FILE_EXTENSION: str = ".compframes"
CACHE_LABEL_MAX_LENGTH: int = 80
CACHE_VERSION: int = 9
_SAFE_LABEL_CHARS = re.compile(r"[^a-z0-9._-]+")
_MULTI_SEPARATOR = re.compile(r"[-_.]{2,}")


type _FrameIndex = Annotated[StrictInt, Field(ge=0, le=2**31 - 1)]
type _PositiveFrameCount = Annotated[StrictInt, Field(ge=1, le=2**31 - 1)]
type _FiniteFloat = Annotated[StrictFloat, Field(allow_inf_nan=False)]
type _MetricScore = Annotated[StrictFloat, Field(ge=0, le=1, allow_inf_nan=False)]


class _CachedClipIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: StrictStr
    size: Annotated[StrictInt, Field(ge=0, le=2**63 - 1)]
    mtime: _FiniteFloat


class _CachedActiveRect(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x: _FrameIndex
    y: _FrameIndex
    width: _PositiveFrameCount
    height: _PositiveFrameCount

    def to_rect(self) -> MetricActiveRect:
        return MetricActiveRect(self.x, self.y, self.width, self.height)


class _CachedMetricsMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    frame_count: _PositiveFrameCount
    source_frame_count: _FrameIndex
    metric_source_start: _FrameIndex
    metric_source_end_exclusive: _FrameIndex
    fps: StrictStr
    analysis_source_path: StrictStr
    performance_mode: Literal["quality", "performance"]
    algorithm_id: StrictStr
    metric_backend: StrictStr
    algorithm_identity_json: StrictStr
    metric_active_rect: _CachedActiveRect | None
    active_rect_source: ActiveRectSource
    active_rect_detection_mode: ActiveRectDetectionMode
    active_rect_algorithm_id: ActiveRectAlgorithmId
    clips: list[_CachedClipIdentity]

    def to_metadata(self, fingerprint: str) -> MetricsMetadata:
        fps = Fraction(self.fps)
        if fps <= 0:
            raise ValueError("Cached FPS must be positive")
        return MetricsMetadata(
            frame_count=self.frame_count,
            fps=fps,
            config_fingerprint=fingerprint,
            clips=[ClipIdentity(clip.path, clip.size, clip.mtime) for clip in self.clips],
            source_frame_count=self.source_frame_count,
            metric_source_start=self.metric_source_start,
            metric_source_end_exclusive=self.metric_source_end_exclusive,
            analysis_source_path=self.analysis_source_path,
            performance_mode=self.performance_mode,
            algorithm_id=self.algorithm_id,
            metric_backend=self.metric_backend,
            algorithm_identity_json=self.algorithm_identity_json,
            metric_active_rect=(
                None if self.metric_active_rect is None else self.metric_active_rect.to_rect()
            ),
            active_rect_source=self.active_rect_source,
            active_rect_detection_mode=self.active_rect_detection_mode,
            active_rect_algorithm_id=self.active_rect_algorithm_id,
        )


class _MetricsCacheFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: StrictInt
    fingerprint: StrictStr
    luminance: list[_MetricScore]
    motion: list[_MetricScore]
    sampled_source_frames: list[_FrameIndex] | None
    metadata: _CachedMetricsMetadata


def _cache_path_sort_key(path: Path) -> str:
    return path.as_posix()


def _sorted_video_paths(video_paths: list[Path]) -> list[Path]:
    return sorted(video_paths, key=_cache_path_sort_key)


def keyed_metric_request(
    request: MetricCacheRequest, video_paths: list[Path]
) -> MetricCacheRequest:
    """Fill the source fallback without resolving optional range/FPS identity."""
    if request.analysis_source_path is None and video_paths:
        return replace(request, analysis_source_path=video_paths[0])
    return request


def acquire_required_metrics(
    request: MetricCacheRequest,
    *,
    video_paths: list[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    selection_domain: str | None,
) -> FrameMetrics:
    """Read required cache state at the caller's lifecycle boundary; never compute."""
    request = keyed_metric_request(request, video_paths)
    fingerprint = compute_cache_key(
        video_paths, config, selection_domain=selection_domain, metric_request=request
    )
    result = load_cached_metrics_for_request(cache_dir, fingerprint, request)
    if result.success and result.metrics is not None:
        if result.metrics.metadata.algorithm_identity_json == stable_metric_algorithm_identity_json(
            config
        ):
            return result.metrics
        result = CacheLoadResult(success=False, reason="mismatched_inputs")
    error_path = find_metrics_cache_file(cache_dir, fingerprint) or (
        cache_dir / metrics_cache_filename(video_paths, fingerprint)
    )
    if result.reason == "corrupted":
        raise CacheCorruptionError(error_path)
    raise AnalysisCacheMissError(f"Cached metrics missing or mismatched ({result.reason}).")


def compute_cache_key(
    video_paths: list[Path],
    config: AnalysisConfig,
    *,
    selection_domain: str | None = None,
    metric_request: MetricCacheRequest | None = None,
) -> str:
    """Generate a deterministic cache key from stat identities and analysis config.

    Source contents are intentionally not hashed: media files can be multi-gigabyte,
    and reading them solely to validate a cache lookup would defeat the cache's
    performance purpose. A same-path, same-size, same-mtime replacement is therefore
    treated as the same source by policy.
    """
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


def _sanitize_cache_label(value: str) -> str:
    label = value.lower()
    label = _SAFE_LABEL_CHARS.sub("-", label)
    label = _MULTI_SEPARATOR.sub("-", label)
    return label.strip("-_.")


def load_cached_metrics(
    cache_dir: Path,
    fingerprint: str,
) -> CacheLoadResult:
    """Load analysis metrics when the cache file matches the expected schema."""
    cache_path = find_metrics_cache_file(cache_dir, fingerprint)
    if cache_path is None:
        return CacheLoadResult(success=False, reason="not_found")
    if not cache_path.exists():
        return CacheLoadResult(success=False, reason="not_found")

    try:
        raw_data: object = json.loads(cache_path.read_text(encoding="utf-8"))
        data = _MetricsCacheFile.model_validate(raw_data)
        if data.version != CACHE_VERSION:
            return CacheLoadResult(success=False, reason="corrupted")
        if data.fingerprint != fingerprint:
            return CacheLoadResult(success=False, reason="mismatched_inputs")
        metrics = FrameMetrics(
            luminance=data.luminance,
            motion=data.motion,
            metadata=data.metadata.to_metadata(data.fingerprint),
            sampled_source_frames=(
                None if data.sampled_source_frames is None else tuple(data.sampled_source_frames)
            ),
        )
    except (OSError, ValueError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
        return CacheLoadResult(success=False, reason="corrupted")
    return CacheLoadResult(success=True, metrics=metrics)


def load_cached_metrics_for_request(
    cache_dir: Path,
    fingerprint: str,
    request: MetricCacheRequest,
) -> CacheLoadResult:
    """Load metrics only when stored metadata matches the complete request identity."""
    result = load_cached_metrics(cache_dir, fingerprint)
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
        "sampled_source_frames": (
            None if metrics.sampled_source_frames is None else list(metrics.sampled_source_frames)
        ),
        "metadata": {
            "frame_count": metrics.metadata.frame_count,
            "source_frame_count": metrics.metadata.source_frame_count,
            "metric_source_start": metrics.metadata.metric_source_start,
            "metric_source_end_exclusive": metrics.metadata.metric_source_end_exclusive,
            "fps": str(metrics.metadata.fps),
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
                }
                for c in metrics.metadata.clips
            ],
        },
    }

    write_text_atomic(
        cache_path, json.dumps(data, indent=2), encoding="utf-8", publish_guard=raise_if_cancelling
    )


def _serialize_metric_active_rect(rect: MetricActiveRect | None) -> dict[str, int] | None:
    if rect is None:
        return None
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
    }
