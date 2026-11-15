"""Typed filesystem contract for native VSView alignment review results."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeGuard, cast, get_args

from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES

ALIGNMENT_REVIEW_METADATA_VERSION = 6
ALIGNMENT_REVIEW_RESULT_VERSION = 1
ALIGNMENT_REVIEW_RESULT_SUFFIX = ".alignment-result.json"

ALIGNMENT_REVIEW_METADATA_VERSION_KEY = "frame_compare_contract_version"
ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY = "frame_compare_session_id"
ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY = "frame_compare_alignment_key"
ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY = "frame_compare_comparison_ordinal"
ALIGNMENT_REVIEW_METADATA_ROLE_KEY = "frame_compare_output_role"
ALIGNMENT_REVIEW_METADATA_NAME_KEY = "frame_compare_presentation_name"
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
type AlignmentReviewDecisionState = Literal["trusted_automatic", "provisional", "unavailable"]

MANUAL_AUTHORITY_ORIGINS: frozenset[_AuthorityOrigin] = frozenset(
    {
        "interactive_confirmed_this_run",
        "shared_previous_offsets",
        "preexisting_manual_override",
    }
)


@dataclass(frozen=True, slots=True)
class AlignmentReviewSession:
    script_path: Path
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
    decision_state: AlignmentReviewDecisionState | None
    candidate_offset: int | None
    summary_lines: tuple[str, ...]
    detail_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlignmentReviewComparisonMetadata:
    output_id: int
    source_frame_count: int
    session_id: str
    comparison_key: str
    comparison_ordinal: int
    presentation_name: str
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


def alignment_review_session_from_script(script_path: Path) -> AlignmentReviewSession:
    """Derive session identity and result path from a generated script name."""
    return AlignmentReviewSession(
        script_path=script_path,
        session_id=_session_id_from_filename(script_path.name),
        result_path=script_path.with_name(f"{script_path.stem}{ALIGNMENT_REVIEW_RESULT_SUFFIX}"),
    )


def write_alignment_review_result(
    session: AlignmentReviewSession,
    result: AlignmentReviewResult,
) -> None:
    """Atomically write one complete alignment review result."""
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
    try:
        raw = cast(object, json.loads(session.result_path.read_text(encoding="utf-8")))
    except FileNotFoundError as exc:
        raise AlignmentReviewContractError("alignment review result is missing") from exc
    except (OSError, *SERIALIZED_DECODE_FAILURES) as exc:
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


def _session_id_from_filename(filename: str) -> str:
    if not filename.endswith(".py"):
        raise AlignmentReviewContractError("invalid VSView session script filename")
    token = Path(filename).stem.rpartition("_")[2]
    return _validated_session_id(token)


def alignment_review_metadata_version_message(version: object) -> str:
    rendered = str(version) if _is_int(version) else "unknown"
    return (
        "Alignment review requires a newly generated session. "
        f"This session uses metadata v{rendered}; "
        f"this version requires v{ALIGNMENT_REVIEW_METADATA_VERSION}."
    )


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
        raise AlignmentReviewContractError(alignment_review_metadata_version_message(version))
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
    audio_review_raw = metadata[ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY]
    if not isinstance(comparison_key, str) or not comparison_key:
        raise AlignmentReviewContractError("alignment review output comparison key is invalid")
    if not _is_int(ordinal) or ordinal <= 0:
        raise AlignmentReviewContractError("alignment review output ordinal is invalid")
    audio_review = _parse_audio_review(audio_review_raw)
    return AlignmentReviewComparisonMetadata(
        output_id=candidate.output_id,
        source_frame_count=candidate.source_frame_count,
        session_id=session_id,
        comparison_key=comparison_key,
        comparison_ordinal=ordinal,
        presentation_name=name,
        audio_review=audio_review,
    )


_CURRENT_AUTHORITY_ORIGINS: frozenset[_AuthorityOrigin] = frozenset(
    get_args(_AuthorityOrigin.__value__)
)
_DECISION_STATES: frozenset[AlignmentReviewDecisionState] = frozenset(
    get_args(AlignmentReviewDecisionState.__value__)
)


def _is_authority_origin(value: object) -> TypeGuard[_AuthorityOrigin]:
    return isinstance(value, str) and value in _CURRENT_AUTHORITY_ORIGINS


def _is_decision_state(value: object) -> TypeGuard[AlignmentReviewDecisionState]:
    return isinstance(value, str) and value in _DECISION_STATES


def _parse_review_lines(raw: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(
        isinstance(line, str) for line in cast(list[object], raw)
    ):
        raise AlignmentReviewContractError(f"alignment review {field} must be a list of strings")
    return tuple(cast(list[str], raw))


def _parse_audio_review(raw: object) -> AlignmentReviewAudioReview:
    if not isinstance(raw, str):
        raise AlignmentReviewContractError("alignment review audio evidence is invalid")
    try:
        decoded = json.loads(raw)
    except SERIALIZED_DECODE_FAILURES as exc:
        raise AlignmentReviewContractError("alignment review audio evidence is invalid") from exc
    root = _strict_dict(
        decoded,
        {
            "current_authority",
            "decision_state",
            "candidate_offset",
            "summary_lines",
            "detail_lines",
        },
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
    decision_state = root["decision_state"]
    if decision_state is not None and not _is_decision_state(decision_state):
        raise AlignmentReviewContractError("alignment review decision state is invalid")
    candidate_offset = root["candidate_offset"]
    if candidate_offset is not None and not _is_int(candidate_offset):
        raise AlignmentReviewContractError("alignment review candidate offset is invalid")
    return AlignmentReviewAudioReview(
        current_authority=AlignmentReviewCurrentAuthority(origin=origin, frame_offset=frame_offset),
        decision_state=decision_state,
        candidate_offset=candidate_offset,
        summary_lines=_parse_review_lines(root["summary_lines"], "summary lines"),
        detail_lines=_parse_review_lines(root["detail_lines"], "detail lines"),
    )


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
