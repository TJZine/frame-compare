"""Offset cache persistence for audio alignment."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import structlog
import tomli_w

from frame_compare.services.types import AlignmentAlgorithm, AlignmentConfig, AlignmentResult
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError

CACHE_VERSION = "3"
CACHE_FILE_NAME = "audio_offsets.toml"

log = structlog.get_logger()


@dataclass(frozen=True)
class _ClipFreshness:
    path: str
    size_bytes: int
    mtime_ns: int


def _cached_entry_algorithm(entry_dict: dict[str, object]) -> AlignmentAlgorithm:
    algorithm = entry_dict.get("algorithm")
    if not isinstance(algorithm, str):
        raise TypeError("algorithm must be str")
    if algorithm != "cross_correlation":
        raise ValueError("unsupported algorithm value")
    return "cross_correlation"


def _parse_cached_alignment_entry(entry_dict: dict[str, object]) -> AlignmentResult:
    algorithm = _cached_entry_algorithm(entry_dict)
    reference_clip = entry_dict["reference_clip"]
    comparison_clip = entry_dict["comparison_clip"]
    frame_offset = entry_dict["frame_offset"]
    time_offset_seconds = entry_dict["time_offset_seconds"]
    correlation_score = entry_dict["correlation_score"]

    if not isinstance(reference_clip, str):
        raise TypeError("reference_clip must be str")
    if not isinstance(comparison_clip, str):
        raise TypeError("comparison_clip must be str")
    if not isinstance(frame_offset, int):
        raise TypeError("frame_offset must be int")
    if not isinstance(time_offset_seconds, int | float):
        raise TypeError("time_offset_seconds must be number")
    if not isinstance(correlation_score, int | float):
        raise TypeError("correlation_score must be number")

    return AlignmentResult(
        reference_clip=reference_clip,
        comparison_clip=comparison_clip,
        frame_offset=frame_offset,
        time_offset_seconds=float(time_offset_seconds),
        correlation_score=float(correlation_score),
        algorithm=algorithm,
        source="cached",
    )


def _file_freshness(path: Path) -> _ClipFreshness | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None

    return _ClipFreshness(
        path=str(path.resolve()),
        size_bytes=stat_result.st_size,
        mtime_ns=stat_result.st_mtime_ns,
    )


def _parse_clip_freshness(entry_dict: dict[str, object], *, prefix: str) -> _ClipFreshness | None:
    path = entry_dict.get(f"{prefix}_path")
    size_bytes = entry_dict.get(f"{prefix}_size_bytes")
    mtime_ns = entry_dict.get(f"{prefix}_mtime_ns")

    if not isinstance(path, str):
        return None
    if not isinstance(size_bytes, int):
        return None
    if not isinstance(mtime_ns, int):
        return None

    return _ClipFreshness(
        path=path,
        size_bytes=size_bytes,
        mtime_ns=mtime_ns,
    )


def _entry_freshness_matches(
    entry_dict: dict[str, object],
    *,
    reference: Path,
    comparison: Path,
    sample_rate: int,
    max_offset_seconds: float,
    config: AlignmentConfig,
) -> bool:
    reference_freshness = _parse_clip_freshness(entry_dict, prefix="reference")
    comparison_freshness = _parse_clip_freshness(entry_dict, prefix="comparison")
    current_reference = _file_freshness(reference)
    current_comparison = _file_freshness(comparison)

    cached_sample_rate = entry_dict.get("sample_rate")
    cached_max_offset_seconds = entry_dict.get("max_offset_seconds")
    if not isinstance(cached_sample_rate, int):
        return False
    if not isinstance(cached_max_offset_seconds, int | float):
        return False
    if reference_freshness is None or comparison_freshness is None:
        return False
    if current_reference is None or current_comparison is None:
        return False

    return (
        reference_freshness == current_reference
        and comparison_freshness == current_comparison
        and cached_sample_rate == sample_rate
        and float(cached_max_offset_seconds) == max_offset_seconds
        and _entry_alignment_settings_match(entry_dict, config=config, comparison=comparison)
    )


def _effective_alignment_config(
    *,
    sample_rate: int,
    max_offset_seconds: float,
    config: AlignmentConfig | None,
) -> AlignmentConfig:
    if config is not None:
        return config
    return AlignmentConfig(sample_rate=sample_rate, max_offset_seconds=max_offset_seconds)


def _entry_alignment_settings_match(
    entry_dict: dict[str, object],
    *,
    config: AlignmentConfig,
    comparison: Path,
) -> bool:
    expected_fields: dict[str, object] = {
        "correlation_mode": config.correlation_mode,
        "preprocessing_mode": config.preprocessing_mode,
        "channel_strategy": config.channel_strategy,
        "confidence_threshold": config.confidence_threshold,
        "ambiguity_peak_ratio": config.ambiguity_peak_ratio,
        "window_length_seconds": config.window_length_seconds,
        "window_stride_seconds": config.window_stride_seconds,
        "minimum_valid_windows": config.minimum_valid_windows,
        "consensus_minimum_ratio": config.consensus_minimum_ratio,
        "refinement_mode": config.refinement_mode,
        "refinement_sample_rate": config.refinement_sample_rate,
        "reference_stream": config.reference_stream,
        "comparison_stream": config.comparison_streams.get(comparison.stem),
    }
    for field_name, expected in expected_fields.items():
        cached = entry_dict.get(field_name)
        if isinstance(expected, float):
            if not isinstance(cached, int | float) or float(cached) != expected:
                return False
            continue
        if cached != expected:
            return False
    return True


def _cache_entry_from_result(
    result: AlignmentResult,
    *,
    reference_freshness: _ClipFreshness,
    comparison_freshness: _ClipFreshness,
    sample_rate: int,
    max_offset_seconds: float,
    config: AlignmentConfig,
) -> dict[str, object]:
    comparison_stem = Path(result.comparison_clip).stem
    entry: dict[str, object] = {
        "reference_clip": result.reference_clip,
        "comparison_clip": result.comparison_clip,
        "frame_offset": result.frame_offset,
        "time_offset_seconds": result.time_offset_seconds,
        "correlation_score": result.correlation_score,
        "algorithm": result.algorithm,
        "reference_path": reference_freshness.path,
        "reference_size_bytes": reference_freshness.size_bytes,
        "reference_mtime_ns": reference_freshness.mtime_ns,
        "comparison_path": comparison_freshness.path,
        "comparison_size_bytes": comparison_freshness.size_bytes,
        "comparison_mtime_ns": comparison_freshness.mtime_ns,
        "sample_rate": sample_rate,
        "max_offset_seconds": max_offset_seconds,
        "correlation_mode": config.correlation_mode,
        "preprocessing_mode": config.preprocessing_mode,
        "channel_strategy": config.channel_strategy,
        "confidence_threshold": config.confidence_threshold,
        "ambiguity_peak_ratio": config.ambiguity_peak_ratio,
        "window_length_seconds": config.window_length_seconds,
        "window_stride_seconds": config.window_stride_seconds,
        "minimum_valid_windows": config.minimum_valid_windows,
        "consensus_minimum_ratio": config.consensus_minimum_ratio,
        "refinement_mode": config.refinement_mode,
    }
    optional_settings: dict[str, int | None] = {
        "refinement_sample_rate": config.refinement_sample_rate,
        "reference_stream": config.reference_stream,
        "comparison_stream": config.comparison_streams.get(comparison_stem),
    }
    entry.update({key: value for key, value in optional_settings.items() if value is not None})
    return entry


def _validate_existing_cache_entries(data: dict[str, object]) -> None:
    for key, entry in data.items():
        if key == "version":
            continue
        if not isinstance(entry, dict):
            raise TypeError("cache entry must be table")
        _parse_cached_alignment_entry(cast(dict[str, object], entry))


def load_cached_offsets(
    cache_dir: Path,
    reference: Path,
    comparisons: list[Path],
    *,
    sample_rate: int,
    max_offset_seconds: float,
    config: AlignmentConfig | None = None,
) -> dict[str, AlignmentResult] | None:
    """Load previously calculated offsets from cache."""
    effective_config = _effective_alignment_config(
        sample_rate=sample_rate,
        max_offset_seconds=max_offset_seconds,
        config=config,
    )
    cache_path = cache_dir / CACHE_FILE_NAME
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("rb") as f:
            data = cast(dict[str, object], tomllib.load(f))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise CacheCorruptionError(cache_path) from exc

    if data.get("version") != CACHE_VERSION:
        raise CacheVersionMismatchError(str(data.get("version")), CACHE_VERSION)

    results: dict[str, AlignmentResult] = {}
    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        if key in data:
            entry = data[key]
            if not isinstance(entry, dict):
                raise CacheCorruptionError(cache_path)
            entry_dict = cast(dict[str, object], entry)
            if not _entry_freshness_matches(
                entry_dict,
                reference=reference,
                comparison=comp,
                sample_rate=sample_rate,
                max_offset_seconds=max_offset_seconds,
                config=effective_config,
            ):
                continue
            try:
                results[key] = _parse_cached_alignment_entry(entry_dict)
            except (KeyError, TypeError, ValueError) as e:
                raise CacheCorruptionError(cache_path) from e

    return results


def save_offsets_cache(
    cache_dir: Path,
    *,
    reference: Path,
    comparisons: list[Path],
    sample_rate: int,
    max_offset_seconds: float,
    results: list[AlignmentResult],
    config: AlignmentConfig | None = None,
) -> None:
    """Persist alignment results to cache."""
    cache_path = cache_dir / CACHE_FILE_NAME
    effective_config = _effective_alignment_config(
        sample_rate=sample_rate,
        max_offset_seconds=max_offset_seconds,
        config=config,
    )

    data: dict[str, object] = {"version": CACHE_VERSION}
    reference_freshness = _file_freshness(reference)
    if reference_freshness is None:
        log.warning(
            "audio_offsets_cache_reference_missing_on_write",
            path=str(reference),
            action="alignment_results_not_cached",
        )
        return

    if cache_path.exists():
        try:
            with cache_path.open("rb") as f:
                existing_data = cast(dict[str, object], tomllib.load(f))
            if existing_data.get("version") == CACHE_VERSION:
                _validate_existing_cache_entries(existing_data)
                existing_data.pop("version", None)
                data.update(existing_data)
        except (tomllib.TOMLDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
            log.warning(
                "audio_offsets_cache_corrupt_on_write",
                path=str(cache_path),
                cache_version=CACHE_VERSION,
                action="overwrite_cache_and_discard_prior_entries",
                error=str(exc),
                exc_info=exc,
            )

    comparison_paths_by_name = {comparison.name: comparison for comparison in comparisons}
    for res in results:
        comparison_path = comparison_paths_by_name.get(res.comparison_clip)
        if comparison_path is None:
            log.warning(
                "audio_offsets_cache_unknown_comparison_on_write",
                comparison_clip=res.comparison_clip,
                action="skip_alignment_cache_entry",
            )
            continue
        comparison_freshness = _file_freshness(comparison_path)
        if comparison_freshness is None:
            log.warning(
                "audio_offsets_cache_comparison_missing_on_write",
                path=str(comparison_path),
                action="skip_alignment_cache_entry",
            )
            continue
        key = f"{Path(res.reference_clip).stem}:{Path(res.comparison_clip).stem}"
        data[key] = _cache_entry_from_result(
            res,
            reference_freshness=reference_freshness,
            comparison_freshness=comparison_freshness,
            sample_rate=sample_rate,
            max_offset_seconds=max_offset_seconds,
            config=effective_config,
        )

    try:
        write_bytes_atomic(cache_path, tomli_w.dumps(data).encode("utf-8"))
    except OSError as exc:
        log.warning(
            "audio_offsets_cache_write_failed",
            path=str(cache_path),
            error=str(exc),
            action="alignment_results_not_cached",
            exc_info=exc,
        )
