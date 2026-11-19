"""Shared alignment reuse cache owner."""

from __future__ import annotations

import hashlib
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Self, cast

import structlog
import tomli_w
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from frame_compare.services.alignment_decision import ALIGNMENT_ESTIMATOR_POLICY
from frame_compare.services.alignment_evidence import (
    AlignmentStabilityClassification,
    AlignmentStabilitySummary,
)
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.types import (
    AlignmentAlgorithm,
    AlignmentResult,
    AlignmentReuseCacheOrigin,
    ComparisonResolution,
    ReusableAlignmentEntry,
)
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

CACHE_VERSION = "3"
CACHE_FILE_NAME = "alignment_reuse.toml"
_ACTIVE_RECT_IDENTITY_VERSION = "1"

log = structlog.get_logger()


type _TomlValue = str | int | float | bool | None


def _clip_identity_dict(clip: AlignmentClipRequest) -> dict[str, _TomlValue]:
    data: dict[str, _TomlValue] = {
        "path": str(clip.identity.path.resolve()),
        "size_bytes": clip.identity.size_bytes,
        "mtime_ns": clip.identity.mtime_ns,
        "trim_start_frames": clip.trim_start_frames,
        "effective_fps_num": clip.effective_fps_num,
        "effective_fps_den": clip.effective_fps_den,
        "active_rect_identity_version": _ACTIVE_RECT_IDENTITY_VERSION,
        "active_rect": "absent" if clip.active_rect_x is None else "resolved",
    }
    if clip.active_rect_x is not None:
        data.update(
            {
                "active_rect_x": clip.active_rect_x,
                "active_rect_y": clip.active_rect_y,
                "active_rect_width": clip.active_rect_width,
                "active_rect_height": clip.active_rect_height,
            }
        )
    if clip.trim_end_frame_inclusive is not None:
        data["trim_end_frame_inclusive"] = clip.trim_end_frame_inclusive
    if clip.selected_audio_stream is not None:
        data["selected_audio_stream"] = clip.selected_audio_stream
    return data


def _settings_identity_dict(request: AlignmentRequest) -> dict[str, _TomlValue]:
    settings = request.settings
    return {
        "estimator_policy": ALIGNMENT_ESTIMATOR_POLICY,
        "max_offset_seconds": settings.max_offset_seconds,
        "channel_strategy": settings.channel_strategy,
    }


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
    return _source_set_identity_key(_source_set_identity(request))


def _source_set_identity_key(identity: dict[str, object]) -> str:
    payload = tomli_w.dumps(identity).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def comparison_cache_key(clip: AlignmentClipRequest) -> str:
    payload = tomli_w.dumps(_clip_identity_dict(clip)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _has_duplicate_comparison_keys(request: AlignmentRequest) -> bool:
    return len({comparison_cache_key(clip) for clip in request.comparisons}) != len(
        request.comparisons
    )


def _cache_path(request: AlignmentRequest) -> Path:
    return request.shared_alignment_cache_dir / CACHE_FILE_NAME


def _cache_lock_path(cache_path: Path) -> Path:
    return cache_path.with_name(f"{cache_path.name}.lock")


def _load_cache_data(cache_path: Path) -> dict[str, object] | None:
    try:
        handle = cache_path.open("rb")
    except FileNotFoundError:
        return None
    try:
        with handle:
            data = cast(dict[str, object], tomllib.load(handle))
    except SERIALIZED_DECODE_FAILURES as exc:
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


type _FiniteFloat = Annotated[StrictFloat, Field(allow_inf_nan=False)]
type _FrameOffset = Annotated[StrictInt, Field(ge=-(2**31), le=2**31 - 1)]


class _StoredStability(BaseModel):
    model_config = ConfigDict(extra="ignore")

    classification: AlignmentStabilityClassification
    valid_windows: Annotated[StrictInt, Field(ge=0)]
    offset_min_frames: _FrameOffset | None = None
    offset_max_frames: _FrameOffset | None = None
    first_offset_frames: _FrameOffset | None = None
    last_offset_frames: _FrameOffset | None = None
    largest_adjacent_jump_frames: Annotated[StrictInt, Field(ge=0)] | None = None
    change_position_seconds: Annotated[_FiniteFloat, Field(ge=0)] | None = None

    def to_summary(self) -> AlignmentStabilitySummary:
        return AlignmentStabilitySummary(
            classification=self.classification,
            valid_windows=self.valid_windows,
            offset_min_frames=self.offset_min_frames,
            offset_max_frames=self.offset_max_frames,
            first_offset_frames=self.first_offset_frames,
            last_offset_frames=self.last_offset_frames,
            largest_adjacent_jump_frames=self.largest_adjacent_jump_frames,
            change_position_seconds=self.change_position_seconds,
        )


class _StoredComputed(BaseModel):
    model_config = ConfigDict(extra="ignore")

    frame_offset: _FrameOffset
    time_offset_seconds: _FiniteFloat
    correlation_score: _FiniteFloat
    stability: _StoredStability

    def to_result(self, reference_name: str, comparison_name: str) -> AlignmentResult:
        return AlignmentResult(
            reference_clip=reference_name,
            comparison_clip=comparison_name,
            frame_offset=self.frame_offset,
            time_offset_seconds=self.time_offset_seconds,
            correlation_score=self.correlation_score,
            algorithm="cross_correlation",
            source="cached",
            stability=self.stability.to_summary(),
        )


class _StoredEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    origin: AlignmentReuseCacheOrigin
    frame_offset: _FrameOffset
    time_offset_seconds: _FiniteFloat
    accepted_at: AwareDatetime
    correlation_score: _FiniteFloat | None = None
    stability: _StoredStability | None = None
    computed_result: _StoredComputed | None = None

    @field_validator("accepted_at", mode="before")
    @classmethod
    def parse_accepted_at(cls, value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError("accepted_at must be an ISO datetime string")
        return datetime.fromisoformat(value)

    @model_validator(mode="after")
    def require_computed_evidence(self) -> Self:
        if self.origin == "computed" and (self.correlation_score is None or self.stability is None):
            raise ValueError("computed entries require correlation_score and stability")
        return self

    def to_entry(self, reference_name: str, comparison_name: str) -> ReusableAlignmentEntry:
        accepted_at = self.accepted_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        fallback = None
        algorithm: AlignmentAlgorithm | None
        if self.origin == "computed":
            assert self.correlation_score is not None and self.stability is not None
            score = self.correlation_score
            stability = self.stability.to_summary()
            algorithm = "cross_correlation"
        else:
            if self.computed_result is not None:
                fallback = self.computed_result.to_result(reference_name, comparison_name)
            score = 1.0
            stability = fallback.stability if fallback is not None else None
            algorithm = None
        result = AlignmentResult(
            reference_clip=reference_name,
            comparison_clip=comparison_name,
            frame_offset=self.frame_offset,
            time_offset_seconds=self.time_offset_seconds,
            correlation_score=score,
            algorithm=algorithm,
            source="cached",
            stability=stability,
        )
        return ReusableAlignmentEntry(
            result=result,
            accepted_at=accepted_at,
            origin=self.origin,
            computed_result=result if self.origin == "computed" else fallback,
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
    warning_event = "alignment_reuse_cache_unreadable"
    try:
        if _has_duplicate_comparison_keys(request):
            return None
        data = _load_cache_data(cache_path)
        if data is None:
            return None

        source_set_key = source_set_cache_key(request)
        warning_event = "alignment_reuse_cache_corrupt_source_set"
        try:
            source_sets = cast(Mapping[str, object], data["source_sets"])
            source_set = cast(Mapping[str, object], source_sets[source_set_key])
            entries = cast(Mapping[str, object], source_set["entries"])
        except KeyError:
            return None

        requested_comparisons = request.comparisons if comparisons is None else comparisons
        results: dict[str, ReusableAlignmentEntry] = {}
        for comparison in requested_comparisons:
            comparison_key = comparison_cache_key(comparison)
            try:
                raw_entry = entries[comparison_key]
            except KeyError:
                return None
            warning_event = "alignment_reuse_cache_invalid_entry"
            results[comparison_key] = _StoredEntry.model_validate(raw_entry).to_entry(
                request.reference.path.name, comparison.path.name
            )
        return results
    except Exception:
        log.warning(
            warning_event,
            path=str(cache_path),
            action="ignore_shared_alignment_cache",
        )
        return None


def _cache_origin(resolution: ComparisonResolution) -> AlignmentReuseCacheOrigin | None:
    if resolution.origin in {"computed_this_run", "shared_computed_offsets"}:
        return "computed"
    if resolution.origin == "interactive_confirmed_this_run":
        return "interactive_confirmed"
    return None


@dataclass(frozen=True, slots=True)
class ReusableSourceSetCandidate:
    """Complete publication admitted for one exact requested source set."""

    source_set_key: str
    resolutions: tuple[ComparisonResolution, ...]


def prepare_reusable_source_set(
    request: AlignmentRequest, resolutions: Mapping[str, ComparisonResolution]
) -> ReusableSourceSetCandidate | None:
    if not request.comparisons or _has_duplicate_comparison_keys(request):
        return None
    prepared: list[ComparisonResolution] = []
    for comparison in request.comparisons:
        item = resolutions.get(alignment_key(request.reference.path, comparison.path))
        if item is None or item.comparison_cache_key != comparison_cache_key(comparison):
            return None
        result = item.result
        if _cache_origin(item) is None or not result.applied:
            return None
        if item.origin == "computed_this_run":
            attempt = result.audio_attempt
            if (
                attempt is None
                or attempt.decision.state != "trusted_automatic"
                or result.stability is None
            ):
                return None
        elif item.origin == "shared_computed_offsets":
            if result.stability is None:
                return None
        elif item.computed_fallback is not None and item.computed_fallback.stability is None:
            return None
        prepared.append(item)
    if not any(
        item.origin in {"computed_this_run", "interactive_confirmed_this_run"} for item in prepared
    ):
        return None
    return ReusableSourceSetCandidate(source_set_cache_key(request), tuple(prepared))


def _entry_from_resolution(
    resolution: ComparisonResolution,
    *,
    accepted_at: str,
) -> dict[str, object]:
    origin = _cache_origin(resolution)
    if origin is None:
        raise ValueError("ineligible shared alignment resolution")
    result = resolution.result
    entry: dict[str, object] = {
        "frame_offset": result.frame_offset,
        "time_offset_seconds": result.time_offset_seconds,
        "origin": origin,
        "accepted_at": accepted_at,
    }
    if origin == "computed":
        if result.stability is None:
            raise ValueError("computed stability is required")
        entry["correlation_score"] = result.correlation_score
        entry["stability"] = _stability_dict(result.stability)
    elif resolution.computed_fallback is not None:
        computed = resolution.computed_fallback
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
    candidate: ReusableSourceSetCandidate,
    *,
    accepted_at: str | None = None,
) -> bool:
    """Persist reusable offsets for the prepared source set."""
    if candidate.source_set_key != source_set_cache_key(request):
        raise ValueError("alignment candidate belongs to a different source set")

    cache_path = _cache_path(request)
    source_set_key = source_set_cache_key(request)
    accepted_at_value = accepted_at if accepted_at is not None else _accepted_at_now()
    entries: dict[str, object] = {}
    for comparison, resolution in zip(request.comparisons, candidate.resolutions, strict=True):
        comparison_key = comparison_cache_key(comparison)
        entries[comparison_key] = _entry_from_resolution(
            resolution,
            accepted_at=accepted_at_value,
        )

    def guard_publication() -> None:
        raise_if_cancelling()

    try:
        with exclusive_file_lock(_cache_lock_path(cache_path), abort_check=raise_if_cancelling):
            data = _initial_write_data(cache_path)
            source_sets = cast(dict[str, object], data["source_sets"])
            source_sets[source_set_key] = {"entries": entries}
            try:
                content = tomli_w.dumps(data).encode("utf-8")
            except (RecursionError, TypeError, ValueError) as exc:
                log.warning(
                    "alignment_reuse_cache_serialization_failed",
                    path=str(cache_path),
                    action="shared_alignment_offsets_not_cached",
                    error=str(exc),
                )
                return False
            write_bytes_atomic(cache_path, content, publish_guard=guard_publication)
    except OSError as exc:
        log.warning(
            "alignment_reuse_cache_write_failed",
            path=str(cache_path),
            action="shared_alignment_offsets_not_cached",
            error=str(exc),
            exc_info=exc,
        )
        return False
    return True
