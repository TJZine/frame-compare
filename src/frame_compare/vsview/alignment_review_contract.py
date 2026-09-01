"""Typed filesystem contract for native VSView alignment review results."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeGuard, cast

from frame_compare.utils.atomic_write import write_text_atomic

ALIGNMENT_REVIEW_SCHEMA_VERSION = 1
ALIGNMENT_REVIEW_RESULT_SUFFIX = ".alignment-result.json"
VSVIEW_SESSIONS_DIR_NAME = "vsview_sessions"

ALIGNMENT_REVIEW_METADATA_VERSION_KEY = "frame_compare_contract_version"
ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY = "frame_compare_session_id"
ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY = "frame_compare_alignment_key"
ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY = "frame_compare_comparison_ordinal"
ALIGNMENT_REVIEW_METADATA_ROLE_KEY = "frame_compare_output_role"
ALIGNMENT_REVIEW_METADATA_NAME_KEY = "frame_compare_presentation_name"
ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY = "frame_compare_suggested_offset"
ALIGNMENT_REVIEW_METADATA_KEYS = frozenset(
    {
        ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
        ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
        ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
        ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
        ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
        ALIGNMENT_REVIEW_METADATA_NAME_KEY,
        ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    }
)


class AlignmentReviewContractError(ValueError):
    """Raised when an alignment review session or result is untrusted."""


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
class AlignmentReviewOutputMetadata:
    output_id: int
    source_frame_count: int
    session_id: str
    comparison_key: str
    comparison_ordinal: int
    role: Literal["reference", "comparison"]
    presentation_name: str
    suggested_offset: int | None


@dataclass(frozen=True, slots=True)
class AlignmentReviewComparisonMetadata:
    comparison_key: str
    comparison_ordinal: int
    suggested_offset: int | None
    reference: AlignmentReviewOutputMetadata
    comparison: AlignmentReviewOutputMetadata


@dataclass(frozen=True, slots=True)
class AlignmentReviewWorkspaceMetadata:
    session_id: str
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

    by_ordinal = dict[int, list[AlignmentReviewOutputMetadata]]()
    for output in outputs:
        by_ordinal.setdefault(output.comparison_ordinal, []).append(output)
    if sorted(by_ordinal) != list(range(1, len(by_ordinal) + 1)):
        raise AlignmentReviewContractError("alignment review comparison ordinals are incomplete")

    comparisons = list[AlignmentReviewComparisonMetadata]()
    keys = set[str]()
    for ordinal in sorted(by_ordinal):
        pair = by_ordinal[ordinal]
        if len(pair) != 2 or {output.role for output in pair} != {"reference", "comparison"}:
            raise AlignmentReviewContractError(
                "alignment review comparison output pair is incomplete"
            )
        reference = next(output for output in pair if output.role == "reference")
        comparison = next(output for output in pair if output.role == "comparison")
        if (
            reference.comparison_key != comparison.comparison_key
            or reference.suggested_offset != comparison.suggested_offset
        ):
            raise AlignmentReviewContractError(
                "alignment review comparison output pair is mismatched"
            )
        if reference.comparison_key in keys:
            raise AlignmentReviewContractError("alignment review comparison keys are duplicated")
        keys.add(reference.comparison_key)
        comparisons.append(
            AlignmentReviewComparisonMetadata(
                comparison_key=reference.comparison_key,
                comparison_ordinal=ordinal,
                suggested_offset=reference.suggested_offset,
                reference=reference,
                comparison=comparison,
            )
        )
    return AlignmentReviewWorkspaceMetadata(session_id=session_id, comparisons=tuple(comparisons))


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
    schema_version: Literal[1] = ALIGNMENT_REVIEW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ALIGNMENT_REVIEW_SCHEMA_VERSION:
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
) -> AlignmentReviewOutputMetadata:
    if not _is_int(candidate.output_id):
        raise AlignmentReviewContractError("alignment review output identifier must be an integer")
    if not _is_int(candidate.source_frame_count) or candidate.source_frame_count <= 0:
        raise AlignmentReviewContractError("alignment review output frame count must be positive")
    if set(candidate.metadata) != set(ALIGNMENT_REVIEW_METADATA_KEYS):
        raise AlignmentReviewContractError("alignment review output metadata fields are invalid")
    metadata = candidate.metadata
    version = metadata[ALIGNMENT_REVIEW_METADATA_VERSION_KEY]
    session_id = metadata[ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY]
    comparison_key = metadata[ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY]
    ordinal = metadata[ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY]
    role = metadata[ALIGNMENT_REVIEW_METADATA_ROLE_KEY]
    name = metadata[ALIGNMENT_REVIEW_METADATA_NAME_KEY]
    suggested_offset = metadata[ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY]
    if not _is_int(version) or version != ALIGNMENT_REVIEW_SCHEMA_VERSION:
        raise AlignmentReviewContractError("unsupported alignment review output metadata version")
    if not isinstance(session_id, str):
        raise AlignmentReviewContractError("alignment review output session identifier is invalid")
    session_id = _validated_session_id(session_id)
    if not isinstance(comparison_key, str) or not comparison_key:
        raise AlignmentReviewContractError("alignment review output comparison key is invalid")
    if not _is_int(ordinal) or ordinal <= 0:
        raise AlignmentReviewContractError("alignment review output ordinal is invalid")
    if role not in {"reference", "comparison"}:
        raise AlignmentReviewContractError("alignment review output role is invalid")
    if not isinstance(name, str) or not name:
        raise AlignmentReviewContractError("alignment review output presentation name is invalid")
    if suggested_offset is not None and not _is_int(suggested_offset):
        raise AlignmentReviewContractError("alignment review suggested offset is invalid")
    return AlignmentReviewOutputMetadata(
        output_id=candidate.output_id,
        source_frame_count=candidate.source_frame_count,
        session_id=session_id,
        comparison_key=comparison_key,
        comparison_ordinal=ordinal,
        role=cast(Literal["reference", "comparison"], role),
        presentation_name=name,
        suggested_offset=suggested_offset,
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
