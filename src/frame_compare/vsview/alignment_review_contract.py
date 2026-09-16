"""Typed filesystem contract for native VSView alignment review results."""

from __future__ import annotations

import json
import math
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeGuard, cast, get_args

from frame_compare.utils.atomic_write import write_text_atomic

ALIGNMENT_REVIEW_METADATA_VERSION = 3
ALIGNMENT_REVIEW_RESULT_VERSION = 1
ALIGNMENT_REVIEW_RESULT_SUFFIX = ".alignment-result.json"
VSVIEW_SESSIONS_DIR_NAME = "vsview_sessions"

ALIGNMENT_REVIEW_METADATA_VERSION_KEY = "frame_compare_contract_version"
ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY = "frame_compare_session_id"
ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY = "frame_compare_alignment_key"
ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY = "frame_compare_comparison_ordinal"
ALIGNMENT_REVIEW_METADATA_ROLE_KEY = "frame_compare_output_role"
ALIGNMENT_REVIEW_METADATA_NAME_KEY = "frame_compare_presentation_name"
ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY = "frame_compare_suggested_offset"
ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY = "frame_compare_audio_review"
ALIGNMENT_REVIEW_REFERENCE_METADATA_KEYS = frozenset(
    {
        ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
        ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
        ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
        ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    }
)
ALIGNMENT_REVIEW_COMPARISON_METADATA_KEYS = frozenset(
    {
        ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
        ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
        ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
        ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
        ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
        ALIGNMENT_REVIEW_METADATA_NAME_KEY,
        ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
        ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY,
    }
)


class AlignmentReviewContractError(ValueError):
    """Raised when an alignment review session or result is untrusted."""


type _AuthorityOrigin = Literal[
    "computed_this_run",
    "shared_computed_offsets",
    "interactive_confirmed_this_run",
    "shared_previous_offsets",
    "preexisting_manual_override",
    "none",
]
type _EvidenceAvailabilityLiteral = Literal[
    "current_attempt", "historical_details_unavailable", "not_computed"
]


@dataclass(frozen=True, slots=True)
class AlignmentReviewSession:
    script_path: Path
    sessions_dir: Path
    session_id: str
    result_path: Path


@dataclass(frozen=True, slots=True)
class AlignmentReviewExpectedComparison:
    comparison_key: str
    reference_source_frame_count: int
    comparison_source_frame_count: int

    def __post_init__(self) -> None:
        if not self.comparison_key:
            raise ValueError("comparison_key must not be empty")
        for name, value in (
            ("reference_source_frame_count", self.reference_source_frame_count),
            ("comparison_source_frame_count", self.comparison_source_frame_count),
        ):
            if not _is_int(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class AlignmentReviewOutputCandidate:
    """Untrusted VSView output facts used to discover an alignment workspace."""

    output_id: int
    source_frame_count: int
    metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class AlignmentReviewReferenceMetadata:
    output_id: int
    source_frame_count: int
    session_id: str
    presentation_name: str


@dataclass(frozen=True, slots=True)
class AlignmentReviewCurrentAuthority:
    origin: _AuthorityOrigin
    frame_offset: int | None


@dataclass(frozen=True, slots=True)
class AlignmentReviewAudioReview:
    current_authority: AlignmentReviewCurrentAuthority
    evidence_availability: _EvidenceAvailabilityLiteral
    audio_attempt: Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class AlignmentReviewComparisonMetadata:
    output_id: int
    source_frame_count: int
    session_id: str
    comparison_key: str
    comparison_ordinal: int
    presentation_name: str
    suggested_offset: int | None
    audio_review: AlignmentReviewAudioReview


@dataclass(frozen=True, slots=True)
class AlignmentReviewWorkspaceMetadata:
    session_id: str
    reference: AlignmentReviewReferenceMetadata
    comparisons: tuple[AlignmentReviewComparisonMetadata, ...]


def parse_alignment_review_workspace_metadata(
    candidates: tuple[AlignmentReviewOutputCandidate, ...],
) -> AlignmentReviewWorkspaceMetadata:
    """Strictly parse one complete Frame Compare VSView output workspace."""
    if not candidates:
        raise AlignmentReviewContractError("alignment review workspace has no outputs")
    outputs = tuple(_parse_output_metadata(candidate) for candidate in candidates)
    session_id = outputs[0].session_id
    if any(output.session_id != session_id for output in outputs):
        raise AlignmentReviewContractError("alignment review workspace mixes sessions")
    if len({output.output_id for output in outputs}) != len(outputs):
        raise AlignmentReviewContractError("alignment review output identifiers are duplicated")

    references = tuple(
        output for output in outputs if isinstance(output, AlignmentReviewReferenceMetadata)
    )
    if len(references) != 1:
        raise AlignmentReviewContractError(
            "alignment review workspace must contain exactly one reference"
        )
    comparisons = tuple(
        output for output in outputs if isinstance(output, AlignmentReviewComparisonMetadata)
    )
    if not comparisons:
        raise AlignmentReviewContractError(
            "alignment review workspace must contain at least one comparison"
        )
    ordinals = sorted(comparison.comparison_ordinal for comparison in comparisons)
    if ordinals != list(range(1, len(comparisons) + 1)):
        raise AlignmentReviewContractError("alignment review comparison ordinals are incomplete")
    if len({comparison.comparison_key for comparison in comparisons}) != len(comparisons):
        raise AlignmentReviewContractError("alignment review comparison keys are duplicated")
    return AlignmentReviewWorkspaceMetadata(
        session_id=session_id,
        reference=references[0],
        comparisons=tuple(
            sorted(comparisons, key=lambda comparison: comparison.comparison_ordinal)
        ),
    )


@dataclass(frozen=True, slots=True)
class ConfirmedAlignmentReviewDecision:
    comparison_key: str
    reference_source_frame: int
    comparison_source_frame: int
    action: Literal["confirmed"] = "confirmed"

    def __post_init__(self) -> None:
        if not self.comparison_key:
            raise ValueError("comparison_key must not be empty")
        for name, value in (
            ("reference_source_frame", self.reference_source_frame),
            ("comparison_source_frame", self.comparison_source_frame),
        ):
            if not _is_int(value) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class KeepCurrentAlignmentReviewDecision:
    comparison_key: str
    action: Literal["keep_current"] = "keep_current"

    def __post_init__(self) -> None:
        if not self.comparison_key:
            raise ValueError("comparison_key must not be empty")


type AlignmentReviewDecision = ConfirmedAlignmentReviewDecision | KeepCurrentAlignmentReviewDecision


@dataclass(frozen=True, slots=True)
class AlignmentReviewResult:
    session_id: str
    decisions: tuple[AlignmentReviewDecision, ...]
    schema_version: Literal[1] = ALIGNMENT_REVIEW_RESULT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ALIGNMENT_REVIEW_RESULT_VERSION:
            raise ValueError("unsupported alignment review result schema")
        _validated_session_id(self.session_id)


def alignment_review_session_from_script(
    script_path: Path,
    *,
    sessions_dir: Path | None = None,
    require_result_absent: bool = False,
) -> AlignmentReviewSession:
    """Derive trusted session identity and result path from a generated script."""
    owner = script_path.parent if sessions_dir is None else sessions_dir
    if owner.name != VSVIEW_SESSIONS_DIR_NAME or owner.is_symlink() or not owner.is_dir():
        raise AlignmentReviewContractError("invalid VSView sessions directory")
    if script_path.parent.resolve() != owner.resolve():
        raise AlignmentReviewContractError(
            "VSView session script is outside its sessions directory"
        )
    if script_path.is_symlink() or not script_path.is_file():
        raise AlignmentReviewContractError("VSView session script is not a regular file")

    session_id = _session_id_from_filename(script_path.name)
    result_path = script_path.with_name(f"{script_path.stem}{ALIGNMENT_REVIEW_RESULT_SUFFIX}")
    if result_path.parent.resolve() != owner.resolve():
        raise AlignmentReviewContractError(
            "alignment review result path escaped its sessions directory"
        )
    if require_result_absent and os.path.lexists(result_path):
        raise AlignmentReviewContractError("alignment review result already exists")
    return AlignmentReviewSession(
        script_path=script_path,
        sessions_dir=owner,
        session_id=session_id,
        result_path=result_path,
    )


def write_alignment_review_result(
    session: AlignmentReviewSession,
    result: AlignmentReviewResult,
) -> None:
    """Atomically write one complete alignment review result."""
    _validate_session_paths(session, result_file_must_exist=False)
    if result.session_id != session.session_id:
        raise AlignmentReviewContractError("alignment review result session mismatch")
    payload = {
        "schema_version": result.schema_version,
        "session_id": result.session_id,
        "decisions": [_decision_payload(decision) for decision in result.decisions],
    }
    write_text_atomic(
        session.result_path,
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def read_alignment_review_result(
    session: AlignmentReviewSession,
    expected_comparisons: tuple[AlignmentReviewExpectedComparison, ...],
) -> AlignmentReviewResult:
    """Read and strictly validate the exact trusted result sidecar."""
    _validate_session_paths(session, result_file_must_exist=True)
    try:
        raw = cast(
            object,
            json.loads(
                session.result_path.read_text(encoding="utf-8"),
                object_pairs_hook=_json_object_without_duplicates,
            ),
        )
    except FileNotFoundError as exc:
        raise AlignmentReviewContractError("alignment review result is missing") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AlignmentReviewContractError("alignment review result is unreadable") from exc
    result = _parse_result(raw)
    validate_alignment_review_result(result, session, expected_comparisons)
    return result


def validate_alignment_review_result(
    result: AlignmentReviewResult,
    session: AlignmentReviewSession,
    expected_comparisons: tuple[AlignmentReviewExpectedComparison, ...],
) -> None:
    """Validate session identity, complete order, actions, and raw frame bounds."""
    if result.session_id != session.session_id:
        raise AlignmentReviewContractError("alignment review result session mismatch")
    expected_keys = tuple(expected.comparison_key for expected in expected_comparisons)
    if len(set(expected_keys)) != len(expected_keys):
        raise AlignmentReviewContractError("expected alignment review comparison keys are invalid")
    if len(result.decisions) != len(expected_comparisons):
        raise AlignmentReviewContractError("alignment review result is incomplete")
    for decision, expected in zip(result.decisions, expected_comparisons, strict=True):
        if decision.comparison_key != expected.comparison_key:
            raise AlignmentReviewContractError("alignment review comparison order mismatch")
        if isinstance(decision, ConfirmedAlignmentReviewDecision):
            if decision.reference_source_frame >= expected.reference_source_frame_count:
                raise AlignmentReviewContractError("reference source frame is out of bounds")
            if decision.comparison_source_frame >= expected.comparison_source_frame_count:
                raise AlignmentReviewContractError("comparison source frame is out of bounds")


def _validate_session_paths(
    session: AlignmentReviewSession, *, result_file_must_exist: bool
) -> None:
    trusted = alignment_review_session_from_script(
        session.script_path,
        sessions_dir=session.sessions_dir,
    )
    if trusted != session:
        raise AlignmentReviewContractError("alignment review session paths are inconsistent")
    if os.path.lexists(session.result_path):
        if session.result_path.is_symlink() or not session.result_path.is_file():
            raise AlignmentReviewContractError("alignment review result is not a regular file")
        if session.result_path.resolve().parent != session.sessions_dir.resolve():
            raise AlignmentReviewContractError(
                "alignment review result escaped its sessions directory"
            )
    elif result_file_must_exist:
        raise AlignmentReviewContractError("alignment review result is missing")


def _session_id_from_filename(filename: str) -> str:
    if not filename.endswith(".py"):
        raise AlignmentReviewContractError("invalid VSView session script filename")
    token = Path(filename).stem.rpartition("_")[2]
    return _validated_session_id(token)


def _parse_output_metadata(
    candidate: AlignmentReviewOutputCandidate,
) -> AlignmentReviewReferenceMetadata | AlignmentReviewComparisonMetadata:
    if not _is_int(candidate.output_id):
        raise AlignmentReviewContractError("alignment review output identifier must be an integer")
    if not _is_int(candidate.source_frame_count) or candidate.source_frame_count <= 0:
        raise AlignmentReviewContractError("alignment review output frame count must be positive")
    metadata = candidate.metadata
    version = metadata.get(ALIGNMENT_REVIEW_METADATA_VERSION_KEY)
    if not _is_int(version) or version != ALIGNMENT_REVIEW_METADATA_VERSION:
        rendered = str(version) if _is_int(version) else "unknown"
        raise AlignmentReviewContractError(
            "Alignment review requires a newly generated session. "
            f"This session uses metadata v{rendered}; this version requires v3."
        )
    role = metadata.get(ALIGNMENT_REVIEW_METADATA_ROLE_KEY)
    if role == "reference":
        expected_keys = ALIGNMENT_REVIEW_REFERENCE_METADATA_KEYS
    elif role == "comparison":
        expected_keys = ALIGNMENT_REVIEW_COMPARISON_METADATA_KEYS
    else:
        raise AlignmentReviewContractError("alignment review output role is invalid")
    if set(metadata) != set(expected_keys):
        raise AlignmentReviewContractError("alignment review output metadata fields are invalid")
    session_id = metadata[ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY]
    name = metadata[ALIGNMENT_REVIEW_METADATA_NAME_KEY]
    if not isinstance(session_id, str):
        raise AlignmentReviewContractError("alignment review output session identifier is invalid")
    session_id = _validated_session_id(session_id)
    if not isinstance(name, str) or not name:
        raise AlignmentReviewContractError("alignment review output presentation name is invalid")
    if role == "reference":
        return AlignmentReviewReferenceMetadata(
            output_id=candidate.output_id,
            source_frame_count=candidate.source_frame_count,
            session_id=session_id,
            presentation_name=name,
        )
    comparison_key = metadata[ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY]
    ordinal = metadata[ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY]
    suggested_offset = metadata[ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY]
    audio_review_raw = metadata[ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY]
    if not isinstance(comparison_key, str) or not comparison_key:
        raise AlignmentReviewContractError("alignment review output comparison key is invalid")
    if not _is_int(ordinal) or ordinal <= 0:
        raise AlignmentReviewContractError("alignment review output ordinal is invalid")
    if suggested_offset is not None and not _is_int(suggested_offset):
        raise AlignmentReviewContractError("alignment review suggested offset is invalid")
    audio_review = _parse_audio_review(
        audio_review_raw,
        suggested_offset=suggested_offset,
        comparison_ordinal=ordinal,
    )
    return AlignmentReviewComparisonMetadata(
        output_id=candidate.output_id,
        source_frame_count=candidate.source_frame_count,
        session_id=session_id,
        comparison_key=comparison_key,
        comparison_ordinal=ordinal,
        presentation_name=name,
        suggested_offset=suggested_offset,
        audio_review=audio_review,
    )


_CURRENT_AUTHORITY_ORIGINS: frozenset[_AuthorityOrigin] = frozenset(
    get_args(_AuthorityOrigin.__value__)
)
_EVIDENCE_AVAILABILITY: frozenset[_EvidenceAvailabilityLiteral] = frozenset(
    get_args(_EvidenceAvailabilityLiteral.__value__)
)
_ATTEMPT_KEYS = {
    "reference_identity_digest",
    "comparison_identity_digest",
    "comparison_ordinal",
    "status",
    "estimator_policy",
    "diagnostic_policy",
    "media_runtime_fingerprint",
    "ffmpeg_version",
    "ffprobe_version",
    "extraction_recipe",
    "sample_rate",
    "fps_num",
    "fps_den",
    "confidence_threshold",
    "ambiguity_peak_ratio",
    "minimum_valid_windows",
    "consensus_minimum_ratio",
    "selected_streams",
    "analysis_rate",
    "planned_window_count",
    "peak_fft_points",
    "total_fft_points",
    "planning_reason",
    "windows",
    "decision",
    "stability",
    "collection_observation",
    "collection_summaries",
}
_STREAM_KEYS = {
    "role",
    "source_identity_digest",
    "audio_stream_index",
    "absolute_stream_index",
    "selection_method",
    "selection_rank",
    "codec_name",
    "sample_rate",
    "channels",
    "channel_layout",
    "language",
    "is_default",
    "is_original",
    "is_commentary",
    "language_match",
    "commentary_match",
    "stream_start_num",
    "stream_start_den",
    "stream_start_basis",
    "input_start_num",
    "input_start_den",
    "input_start_basis",
    "time_base_num",
    "time_base_den",
    "duration_num",
    "duration_den",
    "duration_basis",
}
_WINDOW_KEYS = {
    "logical_id",
    "purpose",
    "attempt_number",
    "parent_id",
    "planned_reference_start",
    "planned_reference_count",
    "planned_comparison_start",
    "planned_comparison_count",
    "analysis_rate",
    "requested_rate",
    "actual_reference_count",
    "actual_comparison_count",
    "scoring_reference_count",
    "scoring_comparison_count",
    "discovery_reference_count",
    "discovery_comparison_count",
    "verification_reference_count",
    "verification_comparison_count",
    "continuous_sample_count",
    "continuous_sample_count_origin",
    "actual_useful_reference_start",
    "actual_useful_reference_end",
    "pre_eof_expected_overlap",
    "actual_coverage",
    "coverage_state",
    "quality_disposition",
    "effective_aligned_overlap",
    "origin_basis",
    "local_lag",
    "global_analysis_lag",
    "requested_sample_lag",
    "requested_frame_candidate",
    "requested_score",
    "score_stage",
    "peak_ratio",
    "peak_stage",
    "peak_rate",
    "review_qualified",
    "configured_quality",
    "vote_disposition",
    "terminal_stage",
    "terminal_category",
    "failed_role",
}
_DECISION_KEYS = {
    "state",
    "candidate",
    "primary_reason",
    "raw_correlated_windows",
    "consensus_windows",
    "consensus_ratio",
    "aggregate_score",
    "minimum_peak_ratio",
    "failed_gates",
    "unassessed_gates",
}
_CANDIDATE_KEYS = {
    "sample_offset",
    "sample_rate",
    "frame_offset",
    "supporting_window_ids",
    "median_score",
    "minimum_peak_ratio",
}
_STABILITY_KEYS = {
    "classification",
    "valid_windows",
    "offset_min_frames",
    "offset_max_frames",
    "first_offset_frames",
    "last_offset_frames",
    "largest_adjacent_jump_frames",
    "change_position_seconds",
}
_COLLECTION_KEYS = {
    "phase",
    "role",
    "output_rate",
    "requested_horizon",
    "emitted_sample_count",
    "emitted_byte_count",
    "retained_sample_count",
    "retained_byte_count",
    "status",
    "end_category",
    "observed_eof_sample",
    "elapsed_seconds",
    "cleanup_failure_count",
    "failure_count",
}


def _is_authority_origin(value: object) -> TypeGuard[_AuthorityOrigin]:
    return isinstance(value, str) and value in _CURRENT_AUTHORITY_ORIGINS


def _is_evidence_availability(value: object) -> TypeGuard[_EvidenceAvailabilityLiteral]:
    return isinstance(value, str) and value in _EVIDENCE_AVAILABILITY


def _parse_audio_review(
    raw: object, *, suggested_offset: int | None, comparison_ordinal: int
) -> AlignmentReviewAudioReview:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 128 * 1024:
        raise AlignmentReviewContractError("alignment review audio evidence is invalid")
    try:
        decoded = json.loads(raw, object_pairs_hook=_json_object_without_duplicates)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AlignmentReviewContractError("alignment review audio evidence is invalid") from exc
    root = _strict_dict(
        decoded,
        {"current_authority", "evidence_availability", "audio_attempt"},
        "audio evidence",
    )
    authority_raw = _strict_dict(
        root["current_authority"], {"origin", "frame_offset"}, "current authority"
    )
    origin = authority_raw["origin"]
    frame_offset = authority_raw["frame_offset"]
    if not _is_authority_origin(origin):
        raise AlignmentReviewContractError("alignment review current authority origin is invalid")
    if frame_offset is not None and not _is_int(frame_offset):
        raise AlignmentReviewContractError("alignment review current authority offset is invalid")
    if (origin == "none") != (frame_offset is None):
        raise AlignmentReviewContractError("alignment review current authority is inconsistent")
    if suggested_offset != frame_offset:
        raise AlignmentReviewContractError("alignment review trusted offset is inconsistent")
    availability = root["evidence_availability"]
    if not _is_evidence_availability(availability):
        raise AlignmentReviewContractError("alignment review evidence availability is invalid")
    attempt = root["audio_attempt"]
    if availability == "current_attempt":
        _validate_audio_attempt(
            attempt,
            suggested_offset=suggested_offset,
            authority_origin=origin,
            comparison_ordinal=comparison_ordinal,
        )
    elif attempt is not None:
        raise AlignmentReviewContractError(
            "historical alignment evidence must not invent an attempt"
        )
    return AlignmentReviewAudioReview(
        current_authority=AlignmentReviewCurrentAuthority(origin=origin, frame_offset=frame_offset),
        evidence_availability=availability,
        audio_attempt=cast(Mapping[str, object] | None, attempt),
    )


def _validate_audio_attempt(
    raw: object,
    *,
    suggested_offset: int | None,
    authority_origin: _AuthorityOrigin,
    comparison_ordinal: int,
) -> None:
    attempt = _strict_dict(raw, _ATTEMPT_KEYS, "audio attempt")
    _bounded_text_fields(
        attempt,
        (
            "estimator_policy",
            "diagnostic_policy",
            "media_runtime_fingerprint",
            "ffmpeg_version",
            "ffprobe_version",
            "extraction_recipe",
        ),
    )
    _require_int_fields(
        attempt,
        (
            "comparison_ordinal",
            "sample_rate",
            "fps_num",
            "fps_den",
            "minimum_valid_windows",
            "planned_window_count",
        ),
    )
    if attempt["comparison_ordinal"] != comparison_ordinal:
        raise AlignmentReviewContractError("alignment review attempt ordinal is inconsistent")
    for digest_name in ("reference_identity_digest", "comparison_identity_digest"):
        digest = attempt[digest_name]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise AlignmentReviewContractError("alignment review source identity is invalid")
    if attempt["status"] not in {"complete", "preanalysis_rejection", "aborted"}:
        raise AlignmentReviewContractError("alignment review attempt status is invalid")
    if (
        cast(int, attempt["sample_rate"]) <= 0
        or cast(int, attempt["fps_num"]) <= 0
        or cast(int, attempt["fps_den"]) <= 0
        or cast(int, attempt["minimum_valid_windows"]) <= 0
        or not 0 <= cast(int, attempt["planned_window_count"]) <= 16
    ):
        raise AlignmentReviewContractError("alignment review attempt bounds are invalid")
    _require_number_fields(
        attempt,
        ("confidence_threshold", "ambiguity_peak_ratio", "consensus_minimum_ratio"),
    )
    _require_nullable_int_fields(attempt, ("analysis_rate", "peak_fft_points", "total_fft_points"))
    observation = attempt["collection_observation"]
    if observation not in {"observed", "not_observed"}:
        raise AlignmentReviewContractError("alignment review collection observation is invalid")
    collections = attempt["collection_summaries"]
    if not isinstance(collections, list):
        raise AlignmentReviewContractError("alignment review collection summaries are invalid")
    typed_collections = cast(list[object], collections)
    if len(typed_collections) > 4:
        raise AlignmentReviewContractError("alignment review collection summaries are invalid")
    if observation == "not_observed" and typed_collections:
        raise AlignmentReviewContractError("unobserved alignment collection facts must be absent")
    collection_keys: set[tuple[object, object]] = set()
    for collection in typed_collections:
        data = _strict_dict(collection, _COLLECTION_KEYS, "collection summary")
        _validate_collection_summary(data, collection_keys)
    if observation == "observed" and not typed_collections:
        raise AlignmentReviewContractError("observed alignment collection facts are absent")
    streams = attempt["selected_streams"]
    windows = attempt["windows"]
    if not isinstance(streams, list):
        raise AlignmentReviewContractError("alignment review selected streams are invalid")
    typed_streams = cast(list[object], streams)
    if len(typed_streams) != 2:
        raise AlignmentReviewContractError("alignment review selected streams are invalid")
    typed_stream_data: list[dict[str, object]] = []
    for stream in typed_streams:
        data = _strict_dict(stream, _STREAM_KEYS, "selected stream")
        typed_stream_data.append(data)
        _require_int_fields(
            data,
            (
                "audio_stream_index",
                "absolute_stream_index",
                "stream_start_num",
                "stream_start_den",
                "input_start_num",
                "input_start_den",
            ),
        )
        _require_nullable_int_fields(
            data,
            (
                "sample_rate",
                "channels",
                "time_base_num",
                "time_base_den",
                "duration_num",
                "duration_den",
            ),
        )
        _require_bool_fields(data, ("is_default", "is_original", "is_commentary"))
        if (
            cast(int, data["audio_stream_index"]) < 0
            or cast(int, data["absolute_stream_index"]) < 0
            or cast(int, data["stream_start_den"]) <= 0
            or cast(int, data["input_start_den"]) <= 0
        ):
            raise AlignmentReviewContractError(
                "alignment review selected stream bounds are invalid"
            )
        if data["selection_method"] not in {"explicit_override", "automatic_metadata"}:
            raise AlignmentReviewContractError("alignment review stream selection is invalid")
        if data["stream_start_basis"] not in {"metadata", "default_zero"} or data[
            "input_start_basis"
        ] not in {"metadata", "default_zero"}:
            raise AlignmentReviewContractError("alignment review stream timing basis is invalid")
        for match_name in ("language_match", "commentary_match"):
            if data[match_name] not in {"match", "mismatch", "unknown", "not_applicable"}:
                raise AlignmentReviewContractError("alignment review stream match is invalid")
        _validate_scalar_tree(data)
    if tuple(stream["role"] for stream in typed_stream_data) != ("reference", "comparison"):
        raise AlignmentReviewContractError("alignment review selected stream roles are invalid")
    if (
        typed_stream_data[0]["source_identity_digest"] != attempt["reference_identity_digest"]
        or typed_stream_data[1]["source_identity_digest"] != attempt["comparison_identity_digest"]
    ):
        raise AlignmentReviewContractError("alignment review selected stream identity is invalid")
    if not isinstance(windows, list):
        raise AlignmentReviewContractError("alignment review windows are invalid")
    typed_windows = cast(list[object], windows)
    if len(typed_windows) > 18:
        raise AlignmentReviewContractError("alignment review windows are invalid")
    window_ids: list[str] = []
    primary_count = 0
    correlated_count = 0
    for window in typed_windows:
        data = _strict_dict(window, _WINDOW_KEYS, "window")
        logical_id = data["logical_id"]
        if not isinstance(logical_id, str) or not logical_id:
            raise AlignmentReviewContractError("alignment review window identifier is invalid")
        window_ids.append(logical_id)
        if data["purpose"] == "primary":
            primary_count += 1
        elif data["purpose"] not in {"disputed_recheck", "zero_check"}:
            raise AlignmentReviewContractError("alignment review window purpose is invalid")
        if data["terminal_category"] == "correlated":
            correlated_count += 1
        _require_int_fields(
            data,
            (
                "attempt_number",
                "planned_reference_start",
                "planned_reference_count",
                "planned_comparison_start",
                "planned_comparison_count",
                "analysis_rate",
                "requested_rate",
            ),
        )
        _require_nullable_int_fields(
            data,
            (
                "actual_reference_count",
                "actual_comparison_count",
                "scoring_reference_count",
                "scoring_comparison_count",
                "discovery_reference_count",
                "discovery_comparison_count",
                "verification_reference_count",
                "verification_comparison_count",
                "continuous_sample_count",
                "actual_useful_reference_start",
                "actual_useful_reference_end",
                "pre_eof_expected_overlap",
                "effective_aligned_overlap",
                "peak_rate",
            ),
            minimum=0,
        )
        _require_nullable_int_fields(data, ("requested_sample_lag", "requested_frame_candidate"))
        _require_bool_fields(data, ("review_qualified", "configured_quality"))
        if (
            cast(int, data["attempt_number"]) <= 0
            or cast(int, data["planned_reference_start"]) < 0
            or cast(int, data["planned_reference_count"]) < 0
            or cast(int, data["planned_comparison_start"]) < 0
            or cast(int, data["planned_comparison_count"]) < 0
            or cast(int, data["analysis_rate"]) <= 0
            or cast(int, data["requested_rate"]) <= 0
        ):
            raise AlignmentReviewContractError("alignment review window bounds are invalid")
        if data["origin_basis"] not in {"planned_assumption", "not_measured"}:
            raise AlignmentReviewContractError("alignment review window origin is invalid")
        if data["continuous_sample_count_origin"] not in {
            "discovery",
            "verification",
            "not_observed",
        }:
            raise AlignmentReviewContractError(
                "alignment review continuous sample origin is invalid"
            )
        continuous_count = data["continuous_sample_count"]
        if continuous_count is None and data["continuous_sample_count_origin"] != "not_observed":
            raise AlignmentReviewContractError(
                "alignment review continuous sample origin is inconsistent"
            )
        if (
            continuous_count is not None
            and data["continuous_sample_count_origin"] == "not_observed"
        ):
            raise AlignmentReviewContractError(
                "alignment review continuous sample origin is inconsistent"
            )
        useful_start = data["actual_useful_reference_start"]
        useful_end = data["actual_useful_reference_end"]
        if (useful_start is None) != (useful_end is None):
            raise AlignmentReviewContractError(
                "alignment review useful reference interval is inconsistent"
            )
        if (
            useful_start is not None
            and useful_end is not None
            and cast(int, useful_end) < cast(int, useful_start)
        ):
            raise AlignmentReviewContractError(
                "alignment review useful reference interval is invalid"
            )
        _require_nullable_number_fields(data, ("actual_coverage",))
        coverage = data["actual_coverage"]
        if coverage is not None and not 0 <= cast(float, coverage) <= 1:
            raise AlignmentReviewContractError("alignment review actual coverage is invalid")
        if data["coverage_state"] not in {"complete", "short", "empty", "not_observed"}:
            raise AlignmentReviewContractError("alignment review coverage state is invalid")
        if data["coverage_state"] == "not_observed" and any(
            value is not None
            for value in (
                coverage,
                data["actual_useful_reference_start"],
                data["actual_useful_reference_end"],
                data["pre_eof_expected_overlap"],
            )
        ):
            raise AlignmentReviewContractError(
                "alignment review unobserved coverage includes observed facts"
            )
        if data["quality_disposition"] not in {"qualified", "rejected", "not_observed"}:
            raise AlignmentReviewContractError("alignment review quality disposition is invalid")
        if data["vote_disposition"] not in {"voted", "abstained", "failed"}:
            raise AlignmentReviewContractError("alignment review window vote is invalid")
        _require_nullable_number_fields(
            data,
            ("local_lag", "global_analysis_lag", "requested_score", "peak_ratio"),
        )
        _validate_scalar_tree(data)
    if len(set(window_ids)) != len(window_ids):
        raise AlignmentReviewContractError("alignment review window identifiers are duplicated")
    if primary_count != attempt["planned_window_count"]:
        raise AlignmentReviewContractError("alignment review planned window count is inconsistent")
    decision = _strict_dict(attempt["decision"], _DECISION_KEYS, "audio decision")
    _validate_scalar_tree(decision, skip=("candidate",))
    state = decision["state"]
    candidate = decision["candidate"]
    if state not in {"trusted_automatic", "provisional", "unavailable"}:
        raise AlignmentReviewContractError("alignment review audio decision is invalid")
    _require_int_fields(decision, ("raw_correlated_windows", "consensus_windows"))
    if decision["raw_correlated_windows"] != correlated_count:
        raise AlignmentReviewContractError(
            "alignment review correlated window count is inconsistent"
        )
    if not 0 <= cast(int, decision["consensus_windows"]) <= correlated_count:
        raise AlignmentReviewContractError("alignment review consensus window count is invalid")
    _require_nullable_number_fields(
        decision, ("consensus_ratio", "aggregate_score", "minimum_peak_ratio")
    )
    if state == "unavailable":
        if candidate is not None:
            raise AlignmentReviewContractError("unavailable audio evidence has a candidate")
    else:
        candidate_data = _strict_dict(candidate, _CANDIDATE_KEYS, "audio candidate")
        _require_int_fields(candidate_data, ("sample_offset", "sample_rate", "frame_offset"))
        _require_number_fields(candidate_data, ("median_score",))
        _require_peak_ratio(candidate_data, "minimum_peak_ratio", nullable=False)
        _validate_scalar_tree(candidate_data)
        supporting = candidate_data["supporting_window_ids"]
        if not isinstance(supporting, list):
            raise AlignmentReviewContractError("alignment review candidate support is invalid")
        typed_supporting = cast(list[object], supporting)
        if not typed_supporting or any(not isinstance(item, str) for item in typed_supporting):
            raise AlignmentReviewContractError("alignment review candidate support is invalid")
        supporting_ids = cast(list[str], typed_supporting)
        if len(set(supporting_ids)) != len(supporting_ids) or not set(supporting_ids) <= set(
            window_ids
        ):
            raise AlignmentReviewContractError("alignment review candidate support is invalid")
        candidate_offset = candidate_data["frame_offset"]
        if not _is_int(candidate_offset):
            raise AlignmentReviewContractError("alignment review candidate offset is invalid")
        if state == "trusted_automatic":
            if authority_origin != "computed_this_run" or suggested_offset != candidate_offset:
                raise AlignmentReviewContractError("accepted audio evidence is inconsistent")
        elif authority_origin in {"computed_this_run", "shared_computed_offsets"}:
            raise AlignmentReviewContractError("provisional audio evidence became authoritative")
    stability = attempt["stability"]
    if stability is not None:
        stability_data = _strict_dict(stability, _STABILITY_KEYS, "stability")
        _require_int_fields(stability_data, ("valid_windows",))
        _require_nullable_int_fields(
            stability_data,
            (
                "offset_min_frames",
                "offset_max_frames",
                "first_offset_frames",
                "last_offset_frames",
                "largest_adjacent_jump_frames",
            ),
        )
        _require_nullable_number_fields(stability_data, ("change_position_seconds",))
        _validate_scalar_tree(stability_data)
    _validate_scalar_tree(
        attempt,
        skip=(
            "selected_streams",
            "windows",
            "decision",
            "stability",
            "collection_summaries",
        ),
    )


def _bounded_text_fields(data: Mapping[str, object], names: tuple[str, ...]) -> None:
    for name in names:
        value = data[name]
        if not isinstance(value, str) or len(value) > 512:
            raise AlignmentReviewContractError(f"alignment review {name} is invalid")


def _validate_collection_summary(
    data: Mapping[str, object], collection_keys: set[tuple[object, object]]
) -> None:
    _require_int_fields(
        data,
        (
            "output_rate",
            "requested_horizon",
            "emitted_sample_count",
            "emitted_byte_count",
            "retained_sample_count",
            "retained_byte_count",
            "cleanup_failure_count",
            "failure_count",
        ),
    )
    _require_nullable_int_fields(data, ("observed_eof_sample",), minimum=0)
    _require_number_fields(data, ("elapsed_seconds",))
    if data["phase"] not in {"discovery", "verification"}:
        raise AlignmentReviewContractError("alignment review collection phase is invalid")
    if data["role"] not in {"reference", "comparison"}:
        raise AlignmentReviewContractError("alignment review collection role is invalid")
    collection_key = (data["phase"], data["role"])
    if collection_key in collection_keys:
        raise AlignmentReviewContractError("alignment review collection summaries are duplicated")
    collection_keys.add(collection_key)
    if (
        cast(int, data["output_rate"]) <= 0
        or cast(int, data["requested_horizon"]) <= 0
        or cast(int, data["emitted_sample_count"]) < 0
        or cast(int, data["emitted_byte_count"]) < 0
        or cast(int, data["retained_sample_count"]) < 0
        or cast(int, data["retained_byte_count"]) < 0
        or cast(int, data["cleanup_failure_count"]) < 0
        or cast(int, data["failure_count"]) < 0
        or cast(float, data["elapsed_seconds"]) < 0
    ):
        raise AlignmentReviewContractError("alignment review collection bounds are invalid")
    complete_bytes = cast(int, data["emitted_sample_count"]) * 4
    emitted_bytes = cast(int, data["emitted_byte_count"])
    if not complete_bytes <= emitted_bytes <= complete_bytes + 3:
        raise AlignmentReviewContractError("alignment review emitted byte count is inconsistent")
    if cast(int, data["retained_byte_count"]) != cast(int, data["retained_sample_count"]) * 4:
        raise AlignmentReviewContractError("alignment review retained byte count is inconsistent")
    status = data["status"]
    end_category = data["end_category"]
    observed_eof = data["observed_eof_sample"]
    if status not in {"complete", "failed"}:
        raise AlignmentReviewContractError("alignment review collection status is invalid")
    if status == "complete" and emitted_bytes != complete_bytes:
        raise AlignmentReviewContractError("alignment review complete collection has byte carry")
    if status == "complete" and (data["cleanup_failure_count"] != 0 or data["failure_count"] != 0):
        raise AlignmentReviewContractError("alignment review complete collection has failures")
    if status == "failed":
        if cast(int, data["failure_count"]) < 1:
            raise AlignmentReviewContractError("alignment review failed collection has no failure")
        if cast(int, data["cleanup_failure_count"]) > cast(int, data["failure_count"]):
            raise AlignmentReviewContractError(
                "alignment review cleanup failures exceed collection failures"
            )
    if end_category not in {"planned_end_reached", "observed_eof", "not_observed"}:
        raise AlignmentReviewContractError("alignment review collection end is invalid")
    if end_category == "planned_end_reached":
        if (
            status != "complete"
            or observed_eof is not None
            or data["emitted_sample_count"] != data["requested_horizon"]
        ):
            raise AlignmentReviewContractError(
                "alignment review planned-end facts are inconsistent"
            )
    elif end_category == "observed_eof":
        if status != "complete" or observed_eof is None:
            raise AlignmentReviewContractError(
                "alignment review observed-EOF facts are inconsistent"
            )
        if not 0 <= cast(int, observed_eof) < cast(int, data["requested_horizon"]):
            raise AlignmentReviewContractError("alignment review observed EOF is out of bounds")
        if data["emitted_sample_count"] != observed_eof:
            raise AlignmentReviewContractError("alignment review observed EOF is inconsistent")
    elif status != "failed" or observed_eof is not None:
        raise AlignmentReviewContractError("alignment review unobserved collection is inconsistent")
    _validate_scalar_tree(data)


def _require_int_fields(data: Mapping[str, object], names: tuple[str, ...]) -> None:
    for name in names:
        if not _is_int(data[name]):
            raise AlignmentReviewContractError(f"alignment review {name} is invalid")


def _require_nullable_int_fields(
    data: Mapping[str, object], names: tuple[str, ...], *, minimum: int | None = None
) -> None:
    for name in names:
        value = data[name]
        if value is None:
            continue
        if not _is_int(value) or (minimum is not None and value < minimum):
            raise AlignmentReviewContractError(f"alignment review {name} is invalid")


def _require_bool_fields(data: Mapping[str, object], names: tuple[str, ...]) -> None:
    for name in names:
        if not isinstance(data[name], bool):
            raise AlignmentReviewContractError(f"alignment review {name} is invalid")


def _require_number_fields(data: Mapping[str, object], names: tuple[str, ...]) -> None:
    for name in names:
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise AlignmentReviewContractError(f"alignment review {name} is invalid")
        if not math.isfinite(value):
            raise AlignmentReviewContractError(f"alignment review {name} is invalid")


def _require_nullable_number_fields(data: Mapping[str, object], names: tuple[str, ...]) -> None:
    for name in names:
        value = data[name]
        if value is None:
            continue
        if name in {"peak_ratio", "minimum_peak_ratio"}:
            _require_peak_ratio(data, name, nullable=True)
        else:
            _require_number_fields(data, (name,))


def _require_peak_ratio(data: Mapping[str, object], name: str, *, nullable: bool) -> None:
    value = data[name]
    if nullable and value is None:
        return
    if value == "unbounded":
        return
    _require_number_fields(data, (name,))


def _validate_scalar_tree(data: Mapping[str, object], *, skip: tuple[str, ...] = ()) -> None:
    for key, value in data.items():
        if key in skip or value is None or isinstance(value, bool):
            continue
        if isinstance(value, str):
            if len(value) > 512 or any(ord(char) < 32 for char in value):
                raise AlignmentReviewContractError("alignment review text evidence is invalid")
            continue
        if _is_int(value):
            continue
        if isinstance(value, float):
            if not math.isfinite(value):
                raise AlignmentReviewContractError("alignment review numeric evidence is invalid")
            continue
        if isinstance(value, list) and all(
            isinstance(item, str) or _is_int(item) for item in cast(list[object], value)
        ):
            continue
        raise AlignmentReviewContractError(f"alignment review {key} is invalid")


def _validated_session_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError) as exc:
        raise AlignmentReviewContractError("invalid alignment review session identifier") from exc
    if value != parsed.hex:
        raise AlignmentReviewContractError("invalid alignment review session identifier")
    return parsed.hex


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _json_object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AlignmentReviewContractError("alignment review JSON contains duplicate fields")
        result[key] = value
    return result


def _parse_result(raw: object) -> AlignmentReviewResult:
    root = _strict_dict(raw, {"schema_version", "session_id", "decisions"}, "result")
    if not _is_int(root["schema_version"]) or root["schema_version"] != 1:
        raise AlignmentReviewContractError("unsupported alignment review result schema")
    session_id = root["session_id"]
    if not isinstance(session_id, str):
        raise AlignmentReviewContractError("alignment review session identifier must be a string")
    raw_decisions = root["decisions"]
    if not isinstance(raw_decisions, list):
        raise AlignmentReviewContractError("alignment review decisions must be a list")
    decisions = tuple(_parse_decision(item) for item in cast(list[object], raw_decisions))
    return AlignmentReviewResult(session_id=session_id, decisions=decisions)


def _parse_decision(raw: object) -> AlignmentReviewDecision:
    if not isinstance(raw, dict):
        raise AlignmentReviewContractError("alignment review decision must be an object")
    data = cast(dict[object, object], raw)
    action = data.get("action")
    if action == "keep_current":
        strict = _strict_dict(data, {"comparison_key", "action"}, "keep_current decision")
        key = strict["comparison_key"]
        if not isinstance(key, str):
            raise AlignmentReviewContractError("comparison key must be a string")
        try:
            return KeepCurrentAlignmentReviewDecision(comparison_key=key)
        except ValueError as exc:
            raise AlignmentReviewContractError(str(exc)) from exc
    if action == "confirmed":
        strict = _strict_dict(
            data,
            {
                "comparison_key",
                "action",
                "reference_source_frame",
                "comparison_source_frame",
            },
            "confirmed decision",
        )
        key = strict["comparison_key"]
        reference_frame = strict["reference_source_frame"]
        comparison_frame = strict["comparison_source_frame"]
        if not isinstance(key, str):
            raise AlignmentReviewContractError("comparison key must be a string")
        if not _is_int(reference_frame) or not _is_int(comparison_frame):
            raise AlignmentReviewContractError("confirmed source frames must be integers")
        try:
            return ConfirmedAlignmentReviewDecision(
                comparison_key=key,
                reference_source_frame=reference_frame,
                comparison_source_frame=comparison_frame,
            )
        except ValueError as exc:
            raise AlignmentReviewContractError(str(exc)) from exc
    raise AlignmentReviewContractError("unsupported alignment review decision action")


def _strict_dict(raw: object, keys: set[str], description: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise AlignmentReviewContractError(f"alignment review {description} must be an object")
    untyped = cast(dict[object, object], raw)
    if any(not isinstance(key, str) for key in untyped):
        raise AlignmentReviewContractError(f"alignment review {description} must be an object")
    data = cast(dict[str, object], untyped)
    if set(data) != keys:
        raise AlignmentReviewContractError(f"alignment review {description} fields are invalid")
    return data


def _decision_payload(decision: AlignmentReviewDecision) -> dict[str, object]:
    payload: dict[str, object] = {
        "comparison_key": decision.comparison_key,
        "action": decision.action,
    }
    if isinstance(decision, ConfirmedAlignmentReviewDecision):
        payload["reference_source_frame"] = decision.reference_source_frame
        payload["comparison_source_frame"] = decision.comparison_source_frame
    return payload
