"""Offset cache persistence for audio alignment."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import structlog
import tomli_w

from frame_compare.services.types import AlignmentAlgorithm, AlignmentResult
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError

CACHE_VERSION = "1"
CACHE_FILE_NAME = "audio_offsets.toml"

log = structlog.get_logger()


def _cached_entry_algorithm(entry_dict: dict[str, object]) -> AlignmentAlgorithm:
    algorithm = entry_dict.get("algorithm")
    if algorithm is None and "method" in entry_dict:
        algorithm = entry_dict["method"]

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


def _cache_entry_from_result(result: AlignmentResult) -> dict[str, object]:
    return {
        "reference_clip": result.reference_clip,
        "comparison_clip": result.comparison_clip,
        "frame_offset": result.frame_offset,
        "time_offset_seconds": result.time_offset_seconds,
        "correlation_score": result.correlation_score,
        "algorithm": result.algorithm,
    }


def _normalize_legacy_cache_entries(data: dict[str, object]) -> None:
    """Rewrite legacy cache keys to the current schema before saving."""
    for key, entry in data.items():
        if key == "version" or not isinstance(entry, dict):
            continue
        data[key] = _cache_entry_from_result(
            _parse_cached_alignment_entry(cast(dict[str, object], entry))
        )


def load_cached_offsets(
    cache_dir: Path,
    clips: list[Path],
) -> dict[str, AlignmentResult] | None:
    """Load previously calculated offsets from cache."""
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

    reference = clips[0]
    comparisons = clips[1:]

    results: dict[str, AlignmentResult] = {}
    for comp in comparisons:
        key = f"{reference.stem}:{comp.stem}"
        if key in data:
            entry = data[key]
            if not isinstance(entry, dict):
                raise CacheCorruptionError(cache_path)
            entry_dict = cast(dict[str, object], entry)
            try:
                results[key] = _parse_cached_alignment_entry(entry_dict)
            except (KeyError, TypeError, ValueError) as e:
                raise CacheCorruptionError(cache_path) from e

    return results


def save_offsets_cache(
    cache_dir: Path,
    results: list[AlignmentResult],
) -> None:
    """Persist alignment results to cache."""
    cache_path = cache_dir / CACHE_FILE_NAME

    data: dict[str, object] = {"version": CACHE_VERSION}
    if cache_path.exists():
        try:
            with cache_path.open("rb") as f:
                existing_data = cast(dict[str, object], tomllib.load(f))
            _normalize_legacy_cache_entries(existing_data)
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

    for res in results:
        key = f"{Path(res.reference_clip).stem}:{Path(res.comparison_clip).stem}"
        data[key] = _cache_entry_from_result(res)

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
