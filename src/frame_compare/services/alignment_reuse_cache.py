"""Shared alignment reuse cache owner."""

from __future__ import annotations

import hashlib
import math
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeGuard, cast

import structlog
import tomli_w

from frame_compare.services.types import (
    AlignmentProvenance,
    AlignmentResult,
    AlignmentReuseCacheOrigin,
    AlignmentStabilityClassification,
    AlignmentStabilitySummary,
    ReusableAlignmentEntry,
)
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

CACHE_VERSION = "2"
CACHE_FILE_NAME = "alignment_reuse.toml"

log = structlog.get_logger()


type _TomlValue = str | int | float | bool | None


def _is_finite_number(value: object) -> TypeGuard[int | float]:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _float_matches(value: object, expected: float) -> bool:
    return _is_finite_number(value) and float(value) == expected


def _int_matches(value: object, expected: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == expected


def _clip_identity_dict(clip: AlignmentClipRequest) -> dict[str, _TomlValue]:
    data: dict[str, _TomlValue] = {
        "path": str(clip.identity.path.resolve()),
        "size_bytes": clip.identity.size_bytes,
        "mtime_ns": clip.identity.mtime_ns,
        "trim_start_frames": clip.trim_start_frames,
        "effective_fps_num": clip.effective_fps_num,
        "effective_fps_den": clip.effective_fps_den,
    }
    if clip.trim_end_frame_inclusive is not None:
        data["trim_end_frame_inclusive"] = clip.trim_end_frame_inclusive
    if clip.selected_audio_stream is not None:
        data["selected_audio_stream"] = clip.selected_audio_stream
    return data


def _settings_identity_dict(request: AlignmentRequest) -> dict[str, _TomlValue]:
    settings = request.settings
    data: dict[str, _TomlValue] = {
        "sample_rate": settings.sample_rate,
        "max_offset_seconds": settings.max_offset_seconds,
        "correlation_mode": settings.correlation_mode,
        "preprocessing_mode": settings.preprocessing_mode,
        "channel_strategy": settings.channel_strategy,
        "confidence_threshold": settings.confidence_threshold,
        "ambiguity_peak_ratio": settings.ambiguity_peak_ratio,
        "window_length_seconds": settings.window_length_seconds,
        "window_stride_seconds": settings.window_stride_seconds,
        "minimum_valid_windows": settings.minimum_valid_windows,
        "consensus_minimum_ratio": settings.consensus_minimum_ratio,
        "refinement_mode": settings.refinement_mode,
    }
    if settings.refinement_sample_rate is not None:
        data["refinement_sample_rate"] = settings.refinement_sample_rate
    return data


def _comparison_identity_dict(clip: AlignmentClipRequest) -> dict[str, _TomlValue]:
    data = _clip_identity_dict(clip)
    data["key"] = comparison_cache_key(clip)
    return data


def _source_set_identity(request: AlignmentRequest) -> dict[str, object]:
    return {
        "selected_reference_relationship": request.selected_reference_relationship,
        "reference": _clip_identity_dict(request.reference),
        "comparisons": [_comparison_identity_dict(clip) for clip in request.comparisons],
        "settings": _settings_identity_dict(request),
        "media_runtime_fingerprint": media_runtime_fingerprint("alignment"),
    }


def source_set_cache_key(request: AlignmentRequest) -> str:
    """Return the deterministic shared-cache key for an alignment source set."""
    payload = tomli_w.dumps(_source_set_identity(request)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def comparison_cache_key(clip: AlignmentClipRequest) -> str:
    payload = tomli_w.dumps(_clip_identity_dict(clip)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_path(request: AlignmentRequest) -> Path:
    return request.shared_alignment_cache_dir / CACHE_FILE_NAME


def _cache_lock_path(cache_path: Path) -> Path:
    return cache_path.with_name(f"{cache_path.name}.lock")


def _load_cache_data(cache_path: Path) -> dict[str, object] | None:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("rb") as handle:
            data = cast(dict[str, object], tomllib.load(handle))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        log.warning(
            "alignment_reuse_cache_unreadable",
            path=str(cache_path),
            action="ignore_shared_alignment_cache",
            error=str(exc),
            exc_info=exc,
        )
        return None
    if data.get("version") != CACHE_VERSION:
        log.warning(
            "alignment_reuse_cache_version_mismatch",
            path=str(cache_path),
            expected_version=CACHE_VERSION,
            found_version=data.get("version"),
            action="ignore_shared_alignment_cache",
        )
        return None
    return data


def _source_sets_table(data: dict[str, object], *, cache_path: Path) -> dict[str, object] | None:
    source_sets = data.get("source_sets")
    if source_sets is None:
        log.warning(
            "alignment_reuse_cache_missing_source_sets",
            path=str(cache_path),
            action="ignore_shared_alignment_cache",
        )
        return None
    if not isinstance(source_sets, dict):
        log.warning(
            "alignment_reuse_cache_malformed_source_sets",
            path=str(cache_path),
            action="ignore_shared_alignment_cache",
        )
        return None
    return cast(dict[str, object], source_sets)


def _entry_origin(entry: dict[str, object]) -> AlignmentReuseCacheOrigin:
    origin = entry.get("origin")
    if origin == "computed":
        return "computed"
    if origin == "vspreview_confirmed":
        return "vspreview_confirmed"
    raise ValueError("unsupported shared alignment cache origin")


def _optional_identity_fields_for_table(table_name: str) -> set[str]:
    if table_name in {"reference", "comparison"}:
        return {"trim_end_frame_inclusive", "selected_audio_stream"}
    if table_name == "settings":
        return {"refinement_sample_rate"}
    return set()


def _table_matches_expected_identity(
    cached_dict: dict[str, object],
    expected: dict[str, _TomlValue],
    *,
    table_name: str,
) -> bool:
    for field_name, expected_value in expected.items():
        cached_value = cached_dict.get(field_name)
        if isinstance(expected_value, float):
            if not _float_matches(cached_value, expected_value):
                return False
            continue
        if isinstance(expected_value, int):
            if not _int_matches(cached_value, expected_value):
                return False
            continue
        if cached_value != expected_value:
            return False

    for optional_field in _optional_identity_fields_for_table(table_name):
        expected_has_field = optional_field in expected
        cached_has_field = optional_field in cached_dict
        if expected_has_field != cached_has_field:
            return False

    return True


def _entry_matches_request(
    entry: dict[str, object],
    *,
    request: AlignmentRequest,
    comparison: AlignmentClipRequest,
) -> bool:
    expected_fields = {
        "reference": _clip_identity_dict(request.reference),
        "comparison": _clip_identity_dict(comparison),
        "settings": _settings_identity_dict(request),
    }
    for table_name, expected in expected_fields.items():
        cached = entry.get(table_name)
        if not isinstance(cached, dict):
            return False
        cached_dict = cast(dict[str, object], cached)
        if not _table_matches_expected_identity(cached_dict, expected, table_name=table_name):
            return False
    return entry.get("selected_reference_relationship") == request.selected_reference_relationship


def _parse_entry(
    entry: dict[str, object],
    *,
    request: AlignmentRequest,
    comparison: AlignmentClipRequest,
) -> ReusableAlignmentEntry:
    origin = _entry_origin(entry)
    reference_clip = entry.get("reference_clip")
    comparison_clip = entry.get("comparison_clip")
    frame_offset = entry.get("frame_offset")
    time_offset_seconds = entry.get("time_offset_seconds")
    correlation_score = entry.get("correlation_score")
    accepted_at = entry.get("accepted_at")

    if not isinstance(reference_clip, str):
        raise TypeError("reference_clip must be str")
    if not isinstance(comparison_clip, str):
        raise TypeError("comparison_clip must be str")
    if not isinstance(frame_offset, int) or isinstance(frame_offset, bool):
        raise TypeError("frame_offset must be int")
    if not _is_finite_number(time_offset_seconds):
        raise TypeError("time_offset_seconds must be finite number")
    if not isinstance(accepted_at, str) or not accepted_at:
        raise TypeError("accepted_at must be non-empty str")
    if origin == "computed":
        if not _is_finite_number(correlation_score):
            raise TypeError("computed correlation_score must be finite number")
        replay_correlation_score = float(correlation_score)
    else:
        replay_correlation_score = 1.0
    if not _entry_matches_request(entry, request=request, comparison=comparison):
        raise ValueError("shared alignment cache entry identity mismatch")

    computed_result = _parse_cached_computed_result(entry.get("computed_result"), entry=entry)
    if origin == "computed":
        stability = _parse_stability(entry.get("stability"))
        if stability is None:
            raise ValueError("computed stability is required")
    else:
        stability = computed_result.stability if computed_result is not None else None

    result = AlignmentResult(
        reference_clip=reference_clip,
        comparison_clip=comparison_clip,
        frame_offset=frame_offset,
        time_offset_seconds=float(time_offset_seconds),
        correlation_score=replay_correlation_score,
        algorithm="cross_correlation" if origin == "computed" else None,
        source="cached",
        stability=stability,
    )
    return ReusableAlignmentEntry(
        result=result,
        accepted_at=accepted_at,
        origin=origin,
        computed_result=result if origin == "computed" else computed_result,
    )


def _parse_cached_computed_result(
    value: object,
    *,
    entry: dict[str, object],
) -> AlignmentResult | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("computed_result must be table")
    computed = cast(dict[str, object], value)
    frame_offset = computed.get("frame_offset")
    time_offset_seconds = computed.get("time_offset_seconds")
    correlation_score = computed.get("correlation_score")
    if not isinstance(frame_offset, int) or isinstance(frame_offset, bool):
        raise TypeError("computed_result.frame_offset must be int")
    if not _is_finite_number(time_offset_seconds):
        raise TypeError("computed_result.time_offset_seconds must be finite number")
    if not _is_finite_number(correlation_score):
        raise TypeError("computed_result.correlation_score must be finite number")
    reference_clip = entry.get("reference_clip")
    comparison_clip = entry.get("comparison_clip")
    if not isinstance(reference_clip, str):
        raise TypeError("reference_clip must be str")
    if not isinstance(comparison_clip, str):
        raise TypeError("comparison_clip must be str")
    stability = _parse_stability(computed.get("stability"))
    if stability is None:
        raise ValueError("computed_result.stability is required")
    return AlignmentResult(
        reference_clip=reference_clip,
        comparison_clip=comparison_clip,
        frame_offset=frame_offset,
        time_offset_seconds=float(time_offset_seconds),
        correlation_score=float(correlation_score),
        algorithm="cross_correlation",
        source="cached",
        stability=stability,
    )


def _parse_stability(value: object) -> AlignmentStabilitySummary | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("stability must be table")
    data = cast(dict[str, object], value)
    allowed_fields = {
        "classification",
        "valid_windows",
        "offset_min_frames",
        "offset_max_frames",
        "first_offset_frames",
        "last_offset_frames",
        "largest_adjacent_jump_frames",
        "change_position_seconds",
    }
    if unknown_fields := data.keys() - allowed_fields:
        raise ValueError(f"unsupported stability fields: {sorted(unknown_fields)}")
    classification = data.get("classification")
    if classification not in {
        "stable",
        "possible_drift",
        "possible_discontinuity",
        "variable",
        "insufficient_evidence",
    }:
        raise ValueError("unsupported stability classification")
    valid_windows = data.get("valid_windows")
    if not isinstance(valid_windows, int) or isinstance(valid_windows, bool) or valid_windows < 0:
        raise TypeError("stability.valid_windows must be non-negative int")

    def optional_int(name: str) -> int | None:
        field = data.get(name)
        if field is None:
            return None
        if not isinstance(field, int) or isinstance(field, bool):
            raise TypeError(f"stability.{name} must be int or absent")
        return field

    position = data.get("change_position_seconds")
    if position is not None and (not _is_finite_number(position) or position < 0):
        raise TypeError(
            "stability.change_position_seconds must be finite non-negative number or absent"
        )
    return AlignmentStabilitySummary(
        classification=cast(AlignmentStabilityClassification, classification),
        valid_windows=valid_windows,
        offset_min_frames=optional_int("offset_min_frames"),
        offset_max_frames=optional_int("offset_max_frames"),
        first_offset_frames=optional_int("first_offset_frames"),
        last_offset_frames=optional_int("last_offset_frames"),
        largest_adjacent_jump_frames=optional_int("largest_adjacent_jump_frames"),
        change_position_seconds=None if position is None else float(position),
    )


def _stability_dict(summary: AlignmentStabilitySummary) -> dict[str, object]:
    data: dict[str, object] = {
        "classification": summary.classification,
        "valid_windows": summary.valid_windows,
    }
    for name in (
        "offset_min_frames",
        "offset_max_frames",
        "first_offset_frames",
        "last_offset_frames",
        "largest_adjacent_jump_frames",
        "change_position_seconds",
    ):
        value = getattr(summary, name)
        if value is not None:
            data[name] = value
    return data


def load_reusable_offset_entries(
    request: AlignmentRequest,
    *,
    comparisons: list[AlignmentClipRequest] | None = None,
) -> dict[str, ReusableAlignmentEntry] | None:
    """Load complete reusable previous-offset entries, or return ``None``."""
    cache_path = _cache_path(request)
    data = _load_cache_data(cache_path)
    if data is None:
        return None

    source_set_key = source_set_cache_key(request)
    source_sets = _source_sets_table(data, cache_path=cache_path)
    if source_sets is None:
        return None
    source_set = source_sets.get(source_set_key)
    if not isinstance(source_set, dict):
        return None
    source_set_dict = cast(dict[str, object], source_set)
    entries = source_set_dict.get("entries")
    if not isinstance(entries, dict):
        log.warning(
            "alignment_reuse_cache_corrupt_source_set",
            path=str(cache_path),
            source_set_key=source_set_key,
            action="ignore_shared_alignment_cache",
        )
        return None
    entry_table = cast(dict[str, object], entries)

    requested_comparisons = request.comparisons if comparisons is None else comparisons

    results: dict[str, ReusableAlignmentEntry] = {}
    for comparison in requested_comparisons:
        comparison_key = comparison_cache_key(comparison)
        entry = entry_table.get(comparison_key)
        if not isinstance(entry, dict):
            return None
        try:
            results[comparison_key] = _parse_entry(
                cast(dict[str, object], entry),
                request=request,
                comparison=comparison,
            )
        except (KeyError, TypeError, ValueError) as exc:
            log.warning(
                "alignment_reuse_cache_invalid_entry",
                path=str(cache_path),
                source_set_key=source_set_key,
                comparison_key=comparison_key,
                action="ignore_shared_alignment_cache",
                error=str(exc),
                exc_info=exc,
            )
            return None
    return results


def _origin_for_provenance(provenance: AlignmentProvenance) -> AlignmentReuseCacheOrigin | None:
    if provenance.provenance in {"computed_this_run", "shared_computed_offsets"}:
        return "computed"
    if provenance.provenance == "vspreview_confirmed_this_run":
        return "vspreview_confirmed"
    return None


def _is_write_eligible(provenance: AlignmentProvenance) -> bool:
    result = provenance.result
    origin = _origin_for_provenance(provenance)
    return (
        origin is not None
        and result.applied
        and result.frame_offset is not None
        and result.time_offset_seconds is not None
        and (origin != "computed" or result.stability is not None)
        and (provenance.computed_result is None or provenance.computed_result.stability is not None)
    )


def _entry_from_provenance(
    provenance: AlignmentProvenance,
    *,
    request: AlignmentRequest,
    comparison: AlignmentClipRequest,
    accepted_at: str,
) -> dict[str, object]:
    origin = _origin_for_provenance(provenance)
    if origin is None:
        raise ValueError("ineligible shared alignment provenance")
    result = provenance.result
    entry: dict[str, object] = {
        "reference_clip": request.reference.path.name,
        "comparison_clip": comparison.path.name,
        "frame_offset": result.frame_offset,
        "time_offset_seconds": result.time_offset_seconds,
        "origin": origin,
        "accepted_at": accepted_at,
        "selected_reference_relationship": request.selected_reference_relationship,
        "reference": _clip_identity_dict(request.reference),
        "comparison": _clip_identity_dict(comparison),
        "settings": _settings_identity_dict(request),
    }
    if origin == "computed":
        if result.stability is None:
            raise ValueError("computed stability is required")
        entry["correlation_score"] = result.correlation_score
        entry["stability"] = _stability_dict(result.stability)
    elif provenance.computed_result is not None:
        computed = provenance.computed_result
        if computed.frame_offset is not None and computed.time_offset_seconds is not None:
            if computed.stability is None:
                raise ValueError("computed_result.stability is required")
            entry["computed_result"] = {
                "frame_offset": computed.frame_offset,
                "time_offset_seconds": computed.time_offset_seconds,
                "correlation_score": computed.correlation_score,
                "stability": _stability_dict(computed.stability),
            }
    return entry


def _initial_write_data(cache_path: Path) -> dict[str, object]:
    data = _load_cache_data(cache_path)
    if data is None:
        return {"version": CACHE_VERSION, "source_sets": {}}
    source_sets = _source_sets_table(data, cache_path=cache_path)
    if source_sets is None:
        return {"version": CACHE_VERSION, "source_sets": {}}
    return {"version": CACHE_VERSION, "source_sets": source_sets}


def _accepted_at_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def save_reusable_offsets(
    request: AlignmentRequest,
    provenances: list[AlignmentProvenance],
    *,
    accepted_at: str | None = None,
) -> None:
    """Persist a complete current-run accepted source set to the shared cache.

    If any requested comparison is missing or has ineligible provenance, nothing is written.
    """
    if not request.comparisons:
        return
    by_comparison_key = {item.comparison_cache_key: item for item in provenances}
    request_comparison_keys = [
        comparison_cache_key(comparison) for comparison in request.comparisons
    ]
    if any(comparison_key not in by_comparison_key for comparison_key in request_comparison_keys):
        return
    if any(
        not _is_write_eligible(by_comparison_key[comparison_key])
        for comparison_key in request_comparison_keys
    ):
        return

    cache_path = _cache_path(request)
    source_set_key = source_set_cache_key(request)
    accepted_at_value = accepted_at if accepted_at is not None else _accepted_at_now()
    entries: dict[str, object] = {}
    for comparison in request.comparisons:
        comparison_key = comparison_cache_key(comparison)
        provenance = by_comparison_key[comparison_key]
        entries[comparison_key] = _entry_from_provenance(
            provenance,
            request=request,
            comparison=comparison,
            accepted_at=accepted_at_value,
        )

    source_set: dict[str, object] = {
        "identity": _source_set_identity(request),
        "entries": entries,
    }

    try:
        with exclusive_file_lock(_cache_lock_path(cache_path)):
            data = _initial_write_data(cache_path)
            source_sets = cast(dict[str, object], data["source_sets"])
            source_sets[source_set_key] = source_set
            write_bytes_atomic(cache_path, tomli_w.dumps(data).encode("utf-8"))
    except OSError as exc:
        log.warning(
            "alignment_reuse_cache_write_failed",
            path=str(cache_path),
            action="shared_alignment_offsets_not_cached",
            error=str(exc),
            exc_info=exc,
        )
