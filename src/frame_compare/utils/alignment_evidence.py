"""Whole-track audio alignment evidence (schema v4).

This module is the single definition of the audio-evidence schema. Services
import these frozen dataclasses from here; the diagnostics writer serializes
them with ``dataclasses.asdict``; the VSView review contract validates an
embedded attempt by calling :func:`evidence_from_payload` and
translating ``ValueError`` into its contract error.

Standard library only: this module must stay importable from the VSView panel
process without NumPy.

Every Literal vocabulary is defined once as a type alias below and enforced
through :func:`typing.get_args`, never repeated. Parsing is one generic
dataclass parser; every invariant lives in ``__post_init__`` so services
constructing an invalid attempt fail at construction with ``ValueError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass
from statistics import median
from types import UnionType
from typing import (
    Any,
    Literal,
    TypeAliasType,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

type AudioDecisionState = Literal["trusted_automatic", "provisional", "unavailable"]
type AudioAttemptStatus = Literal["complete", "preanalysis_rejection", "aborted"]
type AudioSelectionMethod = Literal["explicit_override", "automatic_metadata"]
type AudioMetadataMatch = Literal["match", "mismatch", "unknown", "not_applicable"]
type AudioPeakRatio = float | Literal["unbounded"]
type AudioStartBasis = Literal["metadata", "default_zero"]
type AudioDurationBasis = Literal["duration_ts", "stream_duration", "stream_tag", "unavailable"]
type AudioOutcomeStatus = Literal["agreed", "no_single_offset", "search_edge", "no_usable_audio"]
type AudioCollectionObservation = Literal["observed", "not_observed"]
type AudioCandidateBasis = Literal["audio_only"]
type VideoCheckObservationState = Literal["observed", "not_observed"]
type AlignmentStabilityClassification = Literal[
    "stable",
    "possible_drift",
    "possible_discontinuity",
    "variable",
    "insufficient_evidence",
]
type CollectionFailureCategory = Literal[
    "spawn_failed",
    "reader_start_failed",
    "stdout_reader_failed",
    "stderr_reader_failed",
    "timeout",
    "stalled",
    "cancelled",
    "partial_float32_sample",
    "output_exceeded",
    "nonfinite_output",
    "nonzero_exit",
    "consumer_failed",
    "cleanup_failed",
]
type AudioPairSide = Literal["reference", "comparison"]
type EvidenceRowStyle = Literal["value", "warn", "muted"]
type VideoTargetKind = Literal["chunk", "run"]
type VideoTargetResolution = Literal[
    "resolved",
    "unresolved",
    "unexamined",
    "alternative_confirmed",
]
type VideoTargetWinner = Literal["confirmed", "alternative", "neither"]

_AUDIO_REVIEW_REGION_REASONS = frozenset(
    {
        "competing_offset_confirmed_by_video",
        "competing_offset",
        "unresolved_audio_disagreement",
    }
)
type _AudioReviewTargetKey = tuple[VideoTargetKind, int, int]
type _AudioReviewTargetProjection = tuple[_AudioReviewTargetKey, VideoTargetResolution]

AUDIO_ANALYSIS_SAMPLE_RATE = 8000
MAX_AUDIO_CHUNKS = 4096
_MAX_TEXT = 256
_MAX_VERSION_TEXT = 512
MAX_VIDEO_POSITIONS = 12
MAX_VIDEO_TARGET_POSITIONS = 12
MAX_VIDEO_TARGETS = 12
MAX_VIDEO_ALTERNATIVE_OFFSETS = 3
MAX_VIDEO_CHECK_POINTS = 5

#: Plain-words reason phrases for unavailable audio states (m4). Both the
#: terminal presentation and the VSView panel render these; collection failure
#: categories share one generic phrase.
AUDIO_UNAVAILABLE_REASON_PHRASES: dict[str, str] = {
    "no_single_offset": "no single offset across the track",
    "search_edge": "best offset at the search edge",
    "no_usable_audio": "no usable audio signal",
    "selected_audio_timeline_unavailable": "selected audio timeline unavailable",
    "analysis_budget_exceeded": "analysis budget exceeded",
    "source_identity_changed": "source changed during analysis",
}
AUDIO_COLLECTION_FAILURE_PHRASE = "audio collection failed"


def audio_unavailable_phrase(reason: str) -> str:
    """Return the plain-words phrase for an unavailable primary reason."""
    phrase = AUDIO_UNAVAILABLE_REASON_PHRASES.get(reason)
    if phrase is not None:
        return phrase
    if reason in get_args(CollectionFailureCategory.__value__):
        return AUDIO_COLLECTION_FAILURE_PHRASE
    return reason


_NONE_TYPE = type(None)


def _unwrap(annotation: object) -> object:
    while isinstance(annotation, TypeAliasType):
        annotation = annotation.__value__
    return annotation


def _walk_value(annotation: object, value: Any, what: str, *, parse: bool) -> Any:
    """Check or parse one value using the same type-driven walk."""
    annotation = _unwrap(annotation)
    if annotation is None or annotation is _NONE_TYPE:
        if value is None:
            return None
        raise ValueError(f"{what} must be null")
    origin = get_origin(annotation)
    if origin is Literal:
        if value not in get_args(annotation):
            raise ValueError(f"{what} must be one of {sorted(get_args(annotation))}")
        return value
    if origin is Union or isinstance(annotation, UnionType):
        args = get_args(annotation)
        if value is None:
            if _NONE_TYPE in args:
                return None
            raise ValueError(f"{what} must not be null")
        errors: list[str] = []
        for member in args:
            if member is _NONE_TYPE:
                continue
            try:
                return _walk_value(member, value, what, parse=parse)
            except ValueError as exc:
                errors.append(str(exc))
                continue
        raise ValueError(f"{what} is invalid: {value!r} ({'; '.join(errors)})")
    if annotation is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{what} must be a boolean")
        return value
    if annotation is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{what} must be an integer")
        return value
    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{what} must be a finite number")
        if not math.isfinite(float(value)):
            raise ValueError(f"{what} must be a finite number")
        return float(value) if parse else value
    if annotation is str:
        if not isinstance(value, str):
            raise ValueError(f"{what} must be a string")
        return value
    if origin is tuple:
        args: tuple[Any, ...] = get_args(annotation)
        if parse:
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"{what} must be an array")
            entries: tuple[Any, ...] = tuple(cast(list[Any] | tuple[Any, ...], value))
        else:
            if not isinstance(value, tuple):
                raise ValueError(f"{what} must be a tuple")
            entries = cast(tuple[Any, ...], value)
        if len(args) == 2 and args[1] is Ellipsis:
            if parse:
                checked: tuple[Any, ...] = tuple(
                    _walk_value(args[0], item, f"{what}[{index}]", parse=True)
                    for index, item in enumerate(entries)
                )
                return checked
            for index, item in enumerate(entries):
                _walk_value(args[0], item, f"{what}[{index}]", parse=False)
            return cast(Any, value)
        if args:
            if len(entries) != len(args):
                raise ValueError(f"{what} must hold {len(args)} entries")
            if parse:
                checked = tuple(
                    _walk_value(member, item, f"{what}[{index}]", parse=True)
                    for index, (member, item) in enumerate(zip(args, entries, strict=True))
                )
                return checked
            for index, (member, item) in enumerate(zip(args, entries, strict=True)):
                _walk_value(member, item, f"{what}[{index}]", parse=False)
            return cast(Any, value)
        return tuple(entries) if parse else cast(Any, value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if parse:
            return evidence_from_payload(annotation, value)
        if not isinstance(value, annotation):
            raise ValueError(f"{what} must be {annotation.__name__}")
        return value
    raise TypeError(f"unsupported evidence type for {what}: {annotation!r}")


def _check_value(annotation: object, value: Any, what: str) -> None:
    """Strictly check one constructed value against a field annotation."""
    _walk_value(annotation, value, what, parse=False)


def _check_shallow(obj: object) -> None:
    """Run the strict type check over every field of one evidence object."""
    hints: dict[str, Any] = get_type_hints(type(obj))
    for field in fields(cast(Any, obj)):
        _check_value(hints[field.name], getattr(obj, field.name), field.name)


def _check_text(name: str, value: object, *, maximum: int = _MAX_TEXT) -> None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{name} must be 1..{maximum} characters")


def _check_optional_text(name: str, value: object, *, maximum: int = _MAX_TEXT) -> None:
    if value is None:
        return
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{name} must be a string of at most {maximum} characters")


def _check_int(name: str, value: object, *, minimum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _check_digest(name: str, value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in value)
    ):
        raise ValueError(f"{name} must be a SHA-256 hex digest")


def _parse_value(annotation: object, value: Any, what: str) -> Any:
    """Parse one JSON value against a resolved dataclass field annotation."""
    return _walk_value(annotation, value, what, parse=True)


def evidence_from_payload[T](cls: type[T], data: object) -> T:
    """Rebuild one frozen evidence dataclass from its JSON payload.

    This is the single parser entry point: no per-class ``from_payload``
    exists. Requires the payload key set to equal the dataclass field names:
    no unknown or missing keys. Field shapes come from
    :func:`typing.get_type_hints`; value invariants run in ``__post_init__``.
    """
    what = cls.__name__
    if not isinstance(data, dict):
        raise ValueError(f"{what} must be a JSON object")
    raw: dict[Any, Any] = cast(dict[Any, Any], data)
    names = {field.name for field in fields(cast(Any, cls))}
    unknown = sorted(key for key in raw if key not in names)
    if unknown:
        raise ValueError(f"{what} has unknown keys: {unknown}")
    missing = sorted(names - {key for key in raw if isinstance(key, str)})
    if missing:
        raise ValueError(f"{what} is missing keys: {missing}")
    hints: dict[str, Any] = get_type_hints(cls)
    parsed: dict[str, Any] = {
        name: _parse_value(hints[name], raw[name], f"{what}.{name}") for name in names
    }
    return cls(**parsed)  # type: ignore[call-arg]


@dataclass(frozen=True, slots=True)
class SelectedAudioStreamEvidence:
    """Pathless facts for one resolved audio stream choice plus its video start."""

    role: AudioPairSide
    source_identity_digest: str
    audio_stream_index: int
    absolute_stream_index: int
    selection_method: AudioSelectionMethod
    selection_rank: tuple[int, ...]
    codec_name: str | None
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    language: str | None
    is_default: bool
    is_original: bool
    is_commentary: bool
    language_match: AudioMetadataMatch
    commentary_match: AudioMetadataMatch
    stream_start_num: int
    stream_start_den: int
    stream_start_basis: AudioStartBasis
    input_start_num: int
    input_start_den: int
    input_start_basis: AudioStartBasis
    time_base_num: int | None
    time_base_den: int | None
    duration_num: int | None
    duration_den: int | None
    duration_basis: AudioDurationBasis
    video_start_num: int
    video_start_den: int
    video_start_basis: AudioStartBasis

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_digest("source_identity_digest", self.source_identity_digest)
        _check_int("audio_stream_index", self.audio_stream_index, minimum=0)
        _check_int("absolute_stream_index", self.absolute_stream_index, minimum=0)
        _check_optional_text("codec_name", self.codec_name)
        if self.sample_rate is not None:
            _check_int("sample_rate", self.sample_rate, minimum=0)
        if self.channels is not None:
            _check_int("channels", self.channels, minimum=0)
        _check_optional_text("channel_layout", self.channel_layout)
        _check_optional_text("language", self.language)
        _check_int("stream_start_den", self.stream_start_den, minimum=1)
        _check_int("input_start_den", self.input_start_den, minimum=1)
        if self.time_base_num is not None:
            _check_int("time_base_num", self.time_base_num, minimum=0)
        if self.time_base_den is not None:
            _check_int("time_base_den", self.time_base_den, minimum=1)
        if self.duration_num is not None:
            _check_int("duration_num", self.duration_num, minimum=0)
        if self.duration_den is not None:
            _check_int("duration_den", self.duration_den, minimum=1)
        _check_int("video_start_den", self.video_start_den, minimum=1)


@dataclass(frozen=True, slots=True)
class AudioAnalysisFacts:
    """Whole-track chunk plan facts: fixed 8 kHz rate, search radius, tiling."""

    analysis_rate: int
    max_offset_seconds: float
    chunk_samples: int
    lag_samples: int
    planned_chunk_count: int

    def __post_init__(self) -> None:
        _check_shallow(self)
        if self.analysis_rate != AUDIO_ANALYSIS_SAMPLE_RATE:
            raise ValueError("analysis rate must be 8000")
        if self.max_offset_seconds < 1:
            raise ValueError("max_offset_seconds must be finite and >= 1")
        _check_int("chunk_samples", self.chunk_samples, minimum=0)
        _check_int("lag_samples", self.lag_samples, minimum=0)
        _check_int("planned_chunk_count", self.planned_chunk_count, minimum=0)
        if self.planned_chunk_count > MAX_AUDIO_CHUNKS:
            raise ValueError("planned chunk count is out of bounds")


@dataclass(frozen=True, slots=True)
class AudioChunkColumns:
    """Compact columnar per-chunk rows over the planned chunks.

    Empty columns mean chunk rows were omitted for the native projection
    (``rows_omitted``) or were never observed (a rejection or an aborted
    collection); otherwise every column has one entry per planned chunk.
    ``total_samples`` is status-qualified: completed attempts retain the
    analyzed 8 kHz reference span, aborted attempts retain the planned span,
    and attempts without a plan (including preanalysis rejections) retain zero.
    """

    starts: tuple[int, ...]
    counts: tuple[int, ...]
    active: tuple[bool, ...]
    lags: tuple[int | None, ...]
    psrs: tuple[AudioPeakRatio | None, ...]
    credible: tuple[bool, ...]
    agrees: tuple[bool, ...]
    total_samples: int
    rows_omitted: bool = False

    def __post_init__(self) -> None:
        _check_shallow(self)
        columns = (
            self.starts,
            self.counts,
            self.active,
            self.lags,
            self.psrs,
            self.credible,
            self.agrees,
        )
        if any(len(column) != len(self.starts) for column in columns):
            raise ValueError("chunk columns must share one length")
        if self.rows_omitted and self.starts:
            raise ValueError("omitted chunk rows must be empty")
        _check_int("total_samples", self.total_samples, minimum=0)
        for item in self.starts:
            _check_int("starts", item, minimum=0)
        for item in self.counts:
            _check_int("counts", item, minimum=1)
        previous_start: int | None = None
        for index in range(len(self.starts)):
            start = self.starts[index]
            if previous_start is not None and start <= previous_start:
                raise ValueError("chunk starts must increase")
            previous_start = start
            if not self.active[index] and (
                self.lags[index] is not None
                or self.psrs[index] is not None
                or self.credible[index]
                or self.agrees[index]
            ):
                raise ValueError("inactive chunks cannot carry lag evidence")
            if self.active[index] and (self.lags[index] is None or self.psrs[index] is None):
                raise ValueError("active chunks require a lag and PSR")
            if self.credible[index] and not self.active[index]:
                raise ValueError("credible chunks must be active")
            if self.agrees[index] and not self.credible[index]:
                raise ValueError("agreeing chunks must be credible")


@dataclass(frozen=True, slots=True)
class AudioChunkRun:
    """Credible chunks sharing one lag, in index order (edit or drift diagnosis).

    Non-credible chunks between members neither end nor join a run, so
    ``chunk_count`` can be smaller than the index span.
    """

    first_index: int
    last_index: int
    lag: int
    chunk_count: int

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("first_index", self.first_index, minimum=0)
        _check_int("last_index", self.last_index, minimum=0)
        _check_int("chunk_count", self.chunk_count, minimum=1)
        if self.last_index < self.first_index:
            raise ValueError("chunk run ends before it starts")
        if self.chunk_count > self.last_index - self.first_index + 1:
            raise ValueError("chunk run count exceeds its index span")


@dataclass(frozen=True, slots=True)
class AudioStageOutcome:
    """Chunked-estimator outcome with the A5 compensation and A6 sub-frame estimate."""

    status: AudioOutcomeStatus
    global_lag: int | None
    active_chunks: int
    credible_chunks: int
    agreeing_chunks: int
    compensation_seconds: float | None
    subframe_estimate: float | None
    rounded_frame: int | None

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("active_chunks", self.active_chunks, minimum=0)
        _check_int("credible_chunks", self.credible_chunks, minimum=0)
        _check_int("agreeing_chunks", self.agreeing_chunks, minimum=0)
        if not self.agreeing_chunks <= self.credible_chunks <= self.active_chunks:
            raise ValueError("chunk counts must nest: agreeing <= credible <= active")
        if (self.status == "no_usable_audio") == (self.global_lag is not None):
            raise ValueError("global lag must be absent exactly for unusable audio")
        if self.global_lag is None:
            if self.subframe_estimate is not None or self.rounded_frame is not None:
                raise ValueError("sub-frame evidence needs a global lag")
        elif self.subframe_estimate is None or self.rounded_frame is None:
            raise ValueError("a global lag needs its sub-frame estimate")


@dataclass(frozen=True, slots=True)
class AudioCollectionFacts:
    """Bounded scalar transport facts for one paired side (no PCM, no stderr text)."""

    role: AudioPairSide
    emitted_samples: int
    eof_sample: int | None
    elapsed_seconds: float
    returncode: int | None
    stderr_bytes: int
    stderr_truncated: bool
    cleanup_completed: bool

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("emitted_samples", self.emitted_samples, minimum=0)
        if self.eof_sample is not None:
            _check_int("eof_sample", self.eof_sample, minimum=0)
        if self.elapsed_seconds < 0:
            raise ValueError("collection elapsed time must be non-negative")
        _check_int("stderr_bytes", self.stderr_bytes, minimum=0)


@dataclass(frozen=True, slots=True)
class AudioCollectionFailure:
    """One pair-level collection failure (m14): the category plus its side, if any."""

    category: CollectionFailureCategory
    side: AudioPairSide | None

    def __post_init__(self) -> None:
        _check_shallow(self)


@dataclass(frozen=True, slots=True)
class VideoPositionDifference:
    """Per-position rank-normalized luma differences for each scored offset."""

    position_index: int
    reference_frame: int
    score_by_offset: tuple[float, ...]

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("position_index", self.position_index, minimum=0)
        _check_int("reference_frame", self.reference_frame, minimum=0)
        if any(score < 0 for score in self.score_by_offset):
            raise ValueError("video position scores must be non-negative")


@dataclass(frozen=True, slots=True)
class VideoTargetPosition:
    """One V3a position's relative two-hypothesis result."""

    position_index: int
    reference_frame: int
    confirmed_score: float
    alternative_score: float
    winner: VideoTargetWinner

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("position_index", self.position_index, minimum=0)
        _check_int("reference_frame", self.reference_frame, minimum=0)
        if self.confirmed_score < 0 or self.alternative_score < 0:
            raise ValueError("target hypothesis scores must be non-negative")


@dataclass(frozen=True, slots=True)
class VideoTargetEvidence:
    """A chunk or competing run, its half-open 8 kHz bounds, and V3a positions."""

    kind: VideoTargetKind
    first_chunk_index: int
    last_chunk_index: int
    credible: bool
    start_sample: int
    end_sample: int
    target_offset: int
    alternative_offsets: tuple[int, ...]
    resolution: VideoTargetResolution
    positions: tuple[VideoTargetPosition, ...]

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("first_chunk_index", self.first_chunk_index, minimum=0)
        _check_int("last_chunk_index", self.last_chunk_index, minimum=0)
        _check_int("start_sample", self.start_sample, minimum=0)
        _check_int("end_sample", self.end_sample, minimum=0)
        _check_int("target_offset", self.target_offset)
        if self.last_chunk_index < self.first_chunk_index:
            raise ValueError("video target ends before it starts")
        if self.end_sample <= self.start_sample:
            raise ValueError("video target sample interval must be non-empty")
        if self.kind == "chunk" and self.first_chunk_index != self.last_chunk_index:
            raise ValueError("chunk targets must name one chunk")
        if self.kind == "run":
            if self.first_chunk_index == self.last_chunk_index:
                raise ValueError("run targets must name at least two chunks")
            if not self.credible:
                raise ValueError("run targets must be credible")
        if not 1 <= len(self.alternative_offsets) <= MAX_VIDEO_ALTERNATIVE_OFFSETS:
            raise ValueError("video targets must have 1..3 alternative offsets")
        if len(set(self.alternative_offsets)) != len(self.alternative_offsets):
            raise ValueError("video target alternative offsets must be unique")
        if len(self.positions) > 4:
            raise ValueError("video targets have at most four positions")
        if self.resolution == "unexamined":
            if self.positions:
                raise ValueError("unexamined video targets must have no positions")
            return
        if not self.positions:
            raise ValueError("examined video targets need a position")
        winners = [position.winner for position in self.positions]
        if self.resolution == "alternative_confirmed":
            if "alternative" not in winners:
                raise ValueError("alternative-confirmed targets need an alternative winner")
        elif "alternative" in winners:
            raise ValueError("only alternative-confirmed targets may have an alternative winner")
        elif self.resolution == "resolved":
            required = 2 if self.kind == "run" else 1
            if winners.count("confirmed") < required:
                raise ValueError("resolved targets need enough confirmed positions")
        elif "confirmed" not in winners and "neither" not in winners:
            raise ValueError("unresolved targets need an observed position")


@dataclass(frozen=True, slots=True)
class AudioSameFrameContext:
    """A credible audio disagreement that rounds to the confirmed frame."""

    chunk_index: int
    lag_samples: int
    subframe_estimate: float
    rounded_frame: int

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("chunk_index", self.chunk_index, minimum=0)


@dataclass(frozen=True, slots=True)
class AudioAuthorityRecount:
    """The A4b frame-level recount alongside the untouched U1 outcome."""

    raw_status: AudioOutcomeStatus
    raw_agreeing_chunks: int
    authority_status: AudioOutcomeStatus
    authority_agreeing_chunks: int
    passed: bool

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("raw_agreeing_chunks", self.raw_agreeing_chunks, minimum=0)
        _check_int("authority_agreeing_chunks", self.authority_agreeing_chunks, minimum=0)


@dataclass(frozen=True, slots=True)
class VideoCheckPoint:
    """A bounded P4a frame pair for quick manual review."""

    timestamp_seconds: float
    reference_frame: int
    suggested_comparison_frame: int

    def __post_init__(self) -> None:
        _check_shallow(self)
        if self.timestamp_seconds < 0:
            raise ValueError("video check-point timestamp must be non-negative")
        _check_int("reference_frame", self.reference_frame, minimum=0)
        _check_int("suggested_comparison_frame", self.suggested_comparison_frame, minimum=0)


@dataclass(frozen=True, slots=True)
class VideoCheckObservation:
    """Video frame-check evidence; ``not_observed`` until the video stage fills it."""

    observation: VideoCheckObservationState
    scored_offsets: tuple[int, ...]
    confirmed_offset: int | None
    index_build_seconds: float | None
    positions: tuple[VideoPositionDifference, ...]
    targets: tuple[VideoTargetEvidence, ...] = ()
    same_frame_context: tuple[AudioSameFrameContext, ...] = ()
    check_points: tuple[VideoCheckPoint, ...] = ()

    def __post_init__(self) -> None:
        _check_shallow(self)
        if self.index_build_seconds is not None and self.index_build_seconds < 0:
            raise ValueError("video index build time must be non-negative")
        if self.observation == "not_observed":
            if (
                self.scored_offsets
                or self.confirmed_offset is not None
                or self.index_build_seconds is not None
                or self.positions
                or self.targets
                or self.same_frame_context
                or self.check_points
            ):
                raise ValueError("an unobserved video check must not carry evidence")
            return
        if len(self.scored_offsets) != 5:
            raise ValueError("an observed video check scores five offsets")
        if len(self.positions) > MAX_VIDEO_POSITIONS:
            raise ValueError("video check has too many confirmation positions")
        if self.confirmed_offset is not None and self.confirmed_offset not in self.scored_offsets:
            raise ValueError("a confirmed video offset must be a scored offset")
        if self.index_build_seconds is None:
            raise ValueError("an observed video check needs index-build time")
        for position in self.positions:
            if len(position.score_by_offset) != len(self.scored_offsets):
                raise ValueError("video position scores must cover every scored offset")
        indexes = [position.position_index for position in self.positions]
        if len(set(indexes)) != len(indexes):
            raise ValueError("video position indexes must be unique")
        if len(self.targets) > MAX_VIDEO_TARGETS:
            raise ValueError("video check has too many targets")
        target_position_count = sum(len(target.positions) for target in self.targets)
        if target_position_count > MAX_VIDEO_TARGET_POSITIONS:
            raise ValueError("video check has too many targeted positions")
        if self.targets and self.confirmed_offset is None:
            raise ValueError("targeted video evidence needs a confirmed offset")
        if self.same_frame_context and self.confirmed_offset is None:
            raise ValueError("same-frame context needs a confirmed offset")
        if self.same_frame_context and any(
            item.rounded_frame != self.confirmed_offset for item in self.same_frame_context
        ):
            raise ValueError("same-frame context must round to the confirmed offset")
        for target in self.targets:
            if target.target_offset == self.confirmed_offset:
                raise ValueError("video target offset must differ from the confirmed offset")
            expected = tuple(
                offset
                for offset in range(target.target_offset - 1, target.target_offset + 2)
                if offset != self.confirmed_offset
            )
            if target.alternative_offsets != expected:
                raise ValueError(
                    "target alternatives must be the ordered target-offset neighbourhood "
                    "and exclude the confirmed offset"
                )
        target_indexes = [
            position.position_index for target in self.targets for position in target.positions
        ]
        if len(set(target_indexes)) != len(target_indexes):
            raise ValueError("targeted video position indexes must be unique")
        if len(self.same_frame_context) > MAX_VIDEO_TARGET_POSITIONS:
            raise ValueError("video check has too much same-frame context")
        if len(self.check_points) > MAX_VIDEO_CHECK_POINTS:
            raise ValueError("video check has too many check points")


@dataclass(frozen=True, slots=True)
class AudioDecisionCandidate:
    """Observed frame candidate with the sub-frame estimate it came from."""

    frame_offset: int
    time_offset_seconds: float
    subframe_estimate: float
    basis: AudioCandidateBasis

    def __post_init__(self) -> None:
        _check_shallow(self)


@dataclass(frozen=True, slots=True)
class AudioAlignmentDecision:
    """Diagnostic decision kept separate from applied alignment authority."""

    state: AudioDecisionState
    candidate: AudioDecisionCandidate | None
    primary_reason: str
    failed_gates: tuple[str, ...]

    def __post_init__(self) -> None:
        _check_shallow(self)
        if (self.state == "unavailable") == (self.candidate is not None):
            raise ValueError("only an unavailable decision lacks a candidate")
        _check_text("primary_reason", self.primary_reason)
        if any(not item for item in self.failed_gates):
            raise ValueError("audio decision.failed_gates must hold non-empty strings")


@dataclass(frozen=True)
class AlignmentStabilitySummary:
    """Compact diagnostic classification of offset variation over time."""

    classification: AlignmentStabilityClassification
    valid_windows: int
    offset_min_frames: int | None
    offset_max_frames: int | None
    first_offset_frames: int | None
    last_offset_frames: int | None
    largest_adjacent_jump_frames: int | None
    change_position_seconds: float | None

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_int("valid_windows", self.valid_windows, minimum=0)
        if self.largest_adjacent_jump_frames is not None:
            _check_int("largest_adjacent_jump_frames", self.largest_adjacent_jump_frames, minimum=0)
        if self.change_position_seconds is not None and self.change_position_seconds < 0:
            raise ValueError("stability change position must be non-negative")


@dataclass(frozen=True)
class AudioAlignmentAttempt:
    """Complete immutable evidence for one current-run audio attempt."""

    reference_identity_digest: str
    comparison_identity_digest: str
    comparison_ordinal: int
    status: AudioAttemptStatus
    estimator_policy: str
    diagnostic_policy: str
    media_runtime_fingerprint: str
    ffmpeg_version: str
    ffprobe_version: str
    extraction_recipe: str
    fps_num: int
    fps_den: int
    selected_streams: tuple[SelectedAudioStreamEvidence, SelectedAudioStreamEvidence]
    analysis: AudioAnalysisFacts
    chunks: AudioChunkColumns
    runs: tuple[AudioChunkRun, ...]
    audio: AudioStageOutcome
    collection_observation: AudioCollectionObservation
    collection: tuple[AudioCollectionFacts, ...]
    video_check: VideoCheckObservation
    decision: AudioAlignmentDecision
    stability: AlignmentStabilitySummary
    collection_failure: AudioCollectionFailure | None = None
    authority_recount: AudioAuthorityRecount | None = None

    def __post_init__(self) -> None:
        _check_shallow(self)
        _check_digest("reference_identity_digest", self.reference_identity_digest)
        _check_digest("comparison_identity_digest", self.comparison_identity_digest)
        _check_int("comparison_ordinal", self.comparison_ordinal, minimum=1)
        _check_text("estimator_policy", self.estimator_policy)
        _check_text("diagnostic_policy", self.diagnostic_policy)
        _check_text(
            "media_runtime_fingerprint", self.media_runtime_fingerprint, maximum=_MAX_VERSION_TEXT
        )
        _check_text("ffmpeg_version", self.ffmpeg_version, maximum=_MAX_VERSION_TEXT)
        _check_text("ffprobe_version", self.ffprobe_version, maximum=_MAX_VERSION_TEXT)
        _check_text("extraction_recipe", self.extraction_recipe)
        _check_int("fps_num", self.fps_num, minimum=1)
        _check_int("fps_den", self.fps_den, minimum=1)
        if tuple(stream.role for stream in self.selected_streams) != ("reference", "comparison"):
            raise ValueError("audio attempt requires reference and comparison stream evidence")
        if self.status != "complete" and self.decision.state != "unavailable":
            raise ValueError("non-complete audio attempts require an unavailable decision")
        if self.selected_streams[0].source_identity_digest != self.reference_identity_digest:
            raise ValueError("reference stream evidence must match the attempt identity")
        if self.selected_streams[1].source_identity_digest != self.comparison_identity_digest:
            raise ValueError("comparison stream evidence must match the attempt identity")
        if self.collection_observation == "not_observed":
            if self.collection or self.collection_failure is not None:
                raise ValueError("unobserved collection facts must be absent")
        elif tuple(fact.role for fact in self.collection) != ("reference", "comparison"):
            raise ValueError("observed collection facts need both paired sides in order")
        planned = self.analysis.planned_chunk_count
        lag_radius = self.analysis.lag_samples
        # The span is analyzed for complete attempts, planned for aborted
        # attempts, and zero when no plan exists.
        total_samples = self.chunks.total_samples
        if planned == 0:
            if total_samples != 0:
                raise ValueError("zero planned chunks require zero total samples")
        elif not (
            (planned - 1) * self.analysis.chunk_samples
            < total_samples
            <= planned * self.analysis.chunk_samples
        ):
            raise ValueError("total samples must cover every planned chunk")
        if not self.chunks.rows_omitted:
            if self.status == "complete":
                if len(self.chunks.starts) != planned:
                    raise ValueError("chunk columns must be empty or cover every planned chunk")
            elif self.chunks.starts and len(self.chunks.starts) != planned:
                raise ValueError("chunk columns must be empty or cover every planned chunk")
            if self.chunks.starts:
                for index, (start, count) in enumerate(
                    zip(self.chunks.starts, self.chunks.counts, strict=True)
                ):
                    if start != index * self.analysis.chunk_samples:
                        raise ValueError("chunk starts must follow the nominal tiling")
                    expected_count = (
                        total_samples - start
                        if index == planned - 1
                        else self.analysis.chunk_samples
                    )
                    if count != expected_count:
                        raise ValueError("chunk counts must match the total sample span")
                if sum(self.chunks.counts) != total_samples:
                    raise ValueError("chunk counts must sum to total samples")
        for lag in self.chunks.lags:
            if lag is not None and abs(lag) > lag_radius:
                raise ValueError("chunk lag exceeds the search radius")
        for run in self.runs:
            if run.last_index >= planned:
                raise ValueError("chunk run exceeds the planned chunks")
            if abs(run.lag) > lag_radius:
                raise ValueError("chunk run lag exceeds the search radius")
        if self.audio.global_lag is not None and abs(self.audio.global_lag) > lag_radius:
            raise ValueError("global lag exceeds the search radius")
        if self.audio.active_chunks > planned:
            raise ValueError("active chunks exceed the planned chunks")
        if any(item.chunk_index >= planned for item in self.video_check.same_frame_context):
            raise ValueError("same-frame context exceeds the planned chunks")
        for target in self.video_check.targets:
            if target.last_chunk_index >= planned:
                raise ValueError("video target exceeds the planned chunks")
            expected_start = target.first_chunk_index * self.analysis.chunk_samples
            expected_end = min(
                (target.last_chunk_index + 1) * self.analysis.chunk_samples,
                total_samples,
            )
            if target.start_sample != expected_start:
                raise ValueError("video target start does not match its first chunk")
            if target.end_sample != expected_end:
                raise ValueError("video target end does not match its last chunk")
            if not self.chunks.rows_omitted:
                for index in range(target.first_chunk_index, target.last_chunk_index + 1):
                    member_start = self.chunks.starts[index]
                    member_end = member_start + self.chunks.counts[index]
                    nominal_start = index * self.analysis.chunk_samples
                    nominal_end = (index + 1) * self.analysis.chunk_samples
                    if member_start != nominal_start:
                        raise ValueError("video target member start does not match its chunk")
                    if member_end != nominal_end and not (
                        index == planned - 1 and nominal_start < member_end < nominal_end
                    ):
                        raise ValueError("video target member end does not match its chunk")
                expected_end = (
                    self.chunks.starts[target.last_chunk_index]
                    + self.chunks.counts[target.last_chunk_index]
                )
                if target.end_sample != expected_end:
                    raise ValueError("video target end does not match chunk evidence")
                if target.kind == "chunk" and (
                    target.credible != self.chunks.credible[target.first_chunk_index]
                ):
                    raise ValueError("video target credibility does not match chunk evidence")
                if target.kind == "run" and not all(
                    self.chunks.credible[target.first_chunk_index : target.last_chunk_index + 1]
                ):
                    raise ValueError("credible run targets require credible member chunks")
        if self.authority_recount is not None:
            if self.video_check.confirmed_offset is None:
                raise ValueError("authority recount needs a confirmed video offset")
            if self.authority_recount.raw_status != self.audio.status:
                raise ValueError("authority recount must retain the raw audio outcome")
            if self.authority_recount.raw_agreeing_chunks != self.audio.agreeing_chunks:
                raise ValueError("authority recount must retain raw agreeing chunks")
            if self.authority_recount.authority_agreeing_chunks > self.audio.credible_chunks:
                raise ValueError("authority recount exceeds credible chunks")
            if self.authority_recount.passed != (
                self.authority_recount.authority_status == "agreed"
            ):
                raise ValueError("authority recount pass flag is inconsistent")


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    """One structured evidence row: a display key, its value, and a style token."""

    key: str
    value: str
    style: EvidenceRowStyle


def _format_compensation(compensation: float | None) -> str:
    if compensation is None:
        return "compensation=unknown"
    return f"compensation={compensation:+.3f}s"


def audio_evidence_rows(attempt: AudioAlignmentAttempt) -> tuple[EvidenceRow, ...]:
    """Return the shared verbose evidence rows for one audio attempt (m2).

    Both the terminal verbose output and the VSView panel details render
    these rows; neither rebuilds them from formatted strings.
    """
    decision = attempt.decision
    analysis = attempt.analysis
    audio = attempt.audio
    rows: list[EvidenceRow] = [
        EvidenceRow(
            key="Runtime/policy",
            value=(
                f"{attempt.media_runtime_fingerprint}; {attempt.estimator_policy}; "
                f"diagnostic={attempt.diagnostic_policy}"
            ),
            style="value",
        ),
        EvidenceRow(
            key="Decision",
            value=(
                f"state={decision.state}; reason={decision.primary_reason}; "
                f"failed={','.join(decision.failed_gates) or 'none'}"
            ),
            style="warn" if decision.state == "unavailable" else "value",
        ),
    ]
    parts = [
        f"active={audio.active_chunks}",
        f"credible={audio.credible_chunks}",
        f"agreeing={audio.agreeing_chunks}",
    ]
    if audio.global_lag is not None:
        lag_ms = audio.global_lag / analysis.analysis_rate * 1000
        parts.append(f"lag={audio.global_lag:+d} samples ({lag_ms:+.2f}ms)")
    parts.append(_format_compensation(audio.compensation_seconds))
    if audio.subframe_estimate is not None:
        parts.append(f"sub-frame=audio {audio.subframe_estimate:+.2f}f")
    if audio.rounded_frame is not None:
        parts.append(f"rounded={audio.rounded_frame:+d}f")
    rows.append(EvidenceRow(key="Evidence", value="; ".join(parts), style="value"))
    rows.append(
        EvidenceRow(
            key="Analysis",
            value=(
                f"rate={analysis.analysis_rate}; max_offset={analysis.max_offset_seconds}s; "
                f"chunk={analysis.chunk_samples}; lag_radius={analysis.lag_samples}; "
                f"planned={analysis.planned_chunk_count}"
            ),
            style="value",
        )
    )
    stability = attempt.stability
    planned = analysis.planned_chunk_count
    scope = f"{stability.valid_windows}/{planned} credible chunks"
    if stability.valid_windows < planned:
        scope += "; chunks without credible evidence are not assessed"
    rows.append(
        EvidenceRow(
            key="Stability",
            value=f"{stability.classification.replace('_', ' ')}; scoped to {scope} (diagnostic only).",
            style="value",
        )
    )
    if audio.status != "agreed":
        for run in attempt.runs:
            rows.append(
                EvidenceRow(
                    key=f"Run {run.first_index}-{run.last_index}",
                    value=f"lag={run.lag:+d} x{run.chunk_count} chunks",
                    style="value",
                )
            )
    for stream in attempt.selected_streams:
        rows.append(
            EvidenceRow(
                key=f"Stream {stream.role}",
                value=(
                    f"a:{stream.audio_stream_index} (absolute {stream.absolute_stream_index}), "
                    f"codec={stream.codec_name or 'unknown'}, "
                    f"language={stream.language or 'unknown'}, "
                    f"channels={stream.channels or 'unknown'}/{stream.channel_layout or 'unknown'}, "
                    f"rate={stream.sample_rate or 'unknown'}, selection={stream.selection_method}, "
                    f"rank={stream.selection_rank}, start={stream.stream_start_num}/"
                    f"{stream.stream_start_den} ({stream.stream_start_basis}), "
                    f"input={stream.input_start_num}/{stream.input_start_den} "
                    f"({stream.input_start_basis}), duration={stream.duration_num}/"
                    f"{stream.duration_den} ({stream.duration_basis}), "
                    f"video-start={stream.video_start_num}/"
                    f"{stream.video_start_den} ({stream.video_start_basis}), "
                    f"language-match={stream.language_match}, "
                    f"commentary-match={stream.commentary_match}"
                ),
                style="value",
            )
        )
    rows.append(EvidenceRow(key="Collection", value=attempt.collection_observation, style="value"))
    for facts in attempt.collection:
        rows.append(
            EvidenceRow(
                key="Collection side",
                value=(
                    f"{facts.role}: emitted={facts.emitted_samples} samples; "
                    f"EOF={facts.eof_sample}; elapsed={facts.elapsed_seconds:.1f}s; "
                    f"exit={facts.returncode}; stderr={facts.stderr_bytes} bytes "
                    f"(truncated={facts.stderr_truncated}); "
                    f"cleanup={'complete' if facts.cleanup_completed else 'incomplete'}"
                ),
                style="value",
            )
        )
    if attempt.collection_failure is not None:
        failure = attempt.collection_failure
        rows.append(
            EvidenceRow(
                key="Collection failure",
                value=f"failure={failure.category} (side={failure.side})",
                style="warn",
            )
        )
    return tuple(rows)


type AudioReviewRegionStatus = Literal["confirmed by video", "not settled", "not checked"]


@dataclass(frozen=True, slots=True)
class AudioReviewRegion:
    """One non-overlapping review region in track order."""

    offset: int
    start_seconds: float
    end_seconds: float
    status: AudioReviewRegionStatus
    target_resolution: VideoTargetResolution | None = None
    target_key: _AudioReviewTargetKey | None = None
    target_projections: tuple[_AudioReviewTargetProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class AudioReviewPresentation:
    """Shared P4/P4a policy consumed by terminal and VSView renderers."""

    attempt: AudioAlignmentAttempt
    suggested_offset: int | None
    reasons: tuple[str, ...]
    regions: tuple[AudioReviewRegion, ...]
    check_points: tuple[VideoCheckPoint, ...]
    same_frame_regions: tuple[AudioReviewRegion, ...]
    resolved_regions: tuple[AudioReviewRegion, ...]
    video_wins: int
    video_informative: int
    video_margin: float | None

    def reason_lines(self, *, panel: bool = False) -> tuple[str, ...]:
        lines: list[str] = []
        for reason in self.reasons:
            region = _review_reason_region(self.regions, self.suggested_offset, reason)
            if reason == "competing_offset_confirmed_by_video" and region is not None:
                lines.append(
                    f"The video confirms {region.offset:+d}f in {_review_region_text(region, panel=panel)}, "
                    "so the sources likely differ by an edit there."
                )
            elif reason == "competing_offset" and region is not None:
                lines.append(
                    f"Audio in {_review_region_text(region, panel=panel)} points to {region.offset:+d}f, "
                    "and the video could not settle which offset is right there."
                )
            elif reason == "unresolved_audio_disagreement":
                if region is not None:
                    lines.append(
                        f"Audio in {_review_region_text(region, panel=panel)} points to {region.offset:+d}f, "
                        "and the video could not rule that out."
                    )
                unexamined = sum(
                    max(1, target.last_chunk_index - target.first_chunk_index + 1)
                    for target in self.attempt.video_check.targets
                    if target.resolution == "unexamined"
                )
                if unexamined:
                    lines.append(
                        f"Audio in {unexamined} more section{'' if unexamined == 1 else 's'} points "
                        "elsewhere; they were not checked, so the offset is not applied."
                    )
            elif reason == "video_check_inconclusive" and self.suggested_offset is not None:
                lines.append(
                    f"The audio points to {self.suggested_offset:+d}f, but the video could not confirm "
                    "the exact frame (little motion or different framing at the checked points)."
                )
            elif reason == "video_check_unavailable" and self.suggested_offset is not None:
                lines.append(
                    f"The audio points to {self.suggested_offset:+d}f, but the video could not be read "
                    "to confirm the exact frame."
                )
            elif reason == "video_check_pending":
                lines.append("Video confirmation pending; not applied.")
            elif (
                reason == "no_single_offset"
                and self.attempt.video_check.confirmed_offset is not None
            ):
                lines.append(
                    "The audio does not agree on one offset across the track; the video suggests "
                    f"{self.attempt.video_check.confirmed_offset:+d}f at the checked points."
                )
        return tuple(dict.fromkeys(lines))

    def region_lines(self, *, panel: bool = False, limit: int | None = None) -> tuple[str, ...]:
        regions = self.regions if limit is None else self.regions[:limit]
        return tuple(
            f"{region.offset:+d}f  {_review_region_text(region, panel=panel)}  {region.status}"
            for region in regions
        )

    def check_point_lines(
        self,
        *,
        panel: bool = False,
        limit: int | None = None,
        include_label: bool = True,
    ) -> tuple[str, ...]:
        points = self.check_points if limit is None else self.check_points[:limit]
        separator = "↔" if panel else "<->"
        dash = " — " if panel else "  "
        return tuple(
            f"{'Check ' if include_label else ''}{_review_time(point.timestamp_seconds)}{dash}reference "
            f"{point.reference_frame:,} {separator} comparison "
            f"{point.suggested_comparison_frame:,} "
            f"({point.reference_frame - point.suggested_comparison_frame:+d}f)"
            for point in points
        )

    def established_audio_line(self) -> str:
        authority = self.attempt.authority_recount
        agreeing = (
            authority.authority_agreeing_chunks
            if authority is not None
            else self.attempt.audio.agreeing_chunks
        )
        offset = self.suggested_offset
        if offset is None:
            offset = self.attempt.audio.rounded_frame or 0
        weak = max(0, self.attempt.audio.active_chunks - self.attempt.audio.credible_chunks)
        inactive = max(
            0,
            self.attempt.analysis.planned_chunk_count - self.attempt.audio.active_chunks,
        )
        return (
            f"Audio: {agreeing} of {self.attempt.audio.credible_chunks} credible sections agree on "
            f"{offset:+d}f ({max(0, self.attempt.audio.credible_chunks - agreeing)} differ; "
            f"{weak} active with weak evidence; {inactive} inactive)."
        )

    def established_video_line(self) -> str:
        video = self.attempt.video_check
        if video.observation != "observed":
            return "Video: not observed."
        if video.confirmed_offset is None:
            return f"Video: did not confirm an offset at {len(video.positions)} check points."
        margin = "n/a" if self.video_margin is None else f"{self.video_margin:.1f}×"
        if self.video_margin is not None and math.isinf(self.video_margin):
            margin = "∞"
        return (
            f"Video: confirmed {video.confirmed_offset:+d}f at {self.video_wins} of "
            f"{len(video.positions)} check points (median margin {margin})."
        )

    def context_lines(self, *, panel: bool = False) -> tuple[str, ...]:
        lines: list[str] = []
        recount = self.attempt.authority_recount
        if recount is not None and recount.raw_agreeing_chunks != recount.authority_agreeing_chunks:
            lines.append(
                f"Audio (raw): {recount.raw_agreeing_chunks} of {self.attempt.audio.credible_chunks} "
                "sections agree; "
                f"{recount.authority_agreeing_chunks - recount.raw_agreeing_chunks} more are within "
                "the same frame, so "
                f"{recount.authority_agreeing_chunks} of {self.attempt.audio.credible_chunks} agree "
                "for this offset."
            )
        if self.same_frame_regions:
            lines.append(
                f"{len(self.same_frame_regions)} section{'' if len(self.same_frame_regions) == 1 else 's'} "
                "differ by less than a frame (sub-frame); not a disagreement."
            )
        if self.resolved_regions:
            lines.append(
                f"Audio differed in {_review_region_text(self.resolved_regions[0], panel=panel)}; "
                "the video confirmed the offset there."
            )
        return tuple(lines)

    def noted_line(self, *, panel: bool = False) -> str | None:
        if self.same_frame_regions:
            ranges = ", ".join(
                _review_region_text(region, panel=panel) for region in self.same_frame_regions
            )
            return (
                f"Noted: audio differed in {len(self.same_frame_regions)} section"
                f"{'s' if len(self.same_frame_regions) != 1 else ''} ({ranges}); the video "
                f"confirmed {self.suggested_offset:+d}f there."
                if self.suggested_offset is not None
                else None
            )
        if self.resolved_regions and self.suggested_offset is not None:
            ranges = ", ".join(
                _review_region_text(region, panel=panel) for region in self.resolved_regions
            )
            count = sum(
                max(1, target.last_chunk_index - target.first_chunk_index + 1)
                for target in self.attempt.video_check.targets
                if target.resolution == "resolved" and target.kind == "chunk"
            )
            return (
                f"Noted: audio differed in {count or len(self.resolved_regions)} section"
                f"{'s' if (count or len(self.resolved_regions)) != 1 else ''} ({ranges}); "
                f"the video confirmed {self.suggested_offset:+d}f there."
            )
        return None

    def normal_review_rows(self, *, panel: bool, action_line: str) -> tuple[EvidenceRow, ...]:
        """Return the shared normal P4 block after its surface-specific outcome."""
        if self.attempt.decision.primary_reason == "video_check_pending":
            return (
                EvidenceRow(
                    key="",
                    value="Video confirmation pending; not applied.",
                    style="warn",
                ),
            )

        rows = [
            EvidenceRow(key="", value=line, style="warn") for line in self.reason_lines(panel=panel)
        ]
        if _AUDIO_REVIEW_REGION_REASONS.intersection(self.reasons):
            rows.extend(
                EvidenceRow(key="", value=f"  {line}", style="muted")
                for line in self.region_lines(panel=panel, limit=3)
            )
            if len(self.regions) > 3:
                rows.append(
                    EvidenceRow(
                        key="",
                        value=f"and {len(self.regions) - 3} more regions",
                        style="muted",
                    )
                )
        rows.extend(
            EvidenceRow(key="", value=line, style="muted")
            for line in self.check_point_lines(panel=panel, limit=2)
        )
        rows.append(EvidenceRow(key="", value=action_line, style="muted"))
        return tuple(rows)

    def verbose_rows(self, *, panel: bool = False) -> tuple[EvidenceRow, ...]:
        rows: list[EvidenceRow] = [
            EvidenceRow(key="Established", value=self.established_audio_line(), style="value"),
            EvidenceRow(key="", value=self.established_video_line(), style="value"),
        ]
        for index, line in enumerate(self.region_lines(panel=panel)):
            rows.append(EvidenceRow(key="Regions" if index == 0 else "", value=line, style="muted"))
        for index, line in enumerate(self.context_lines(panel=panel)):
            rows.append(EvidenceRow(key="Context" if index == 0 else "", value=line, style="muted"))
        for index, line in enumerate(self.check_point_lines(panel=panel, include_label=False)):
            rows.append(
                EvidenceRow(key="Check points" if index == 0 else "", value=line, style="muted")
            )
        decision = self.attempt.decision
        rows.append(
            EvidenceRow(
                key="Decision",
                value=(
                    f"state={decision.state}; reason={decision.primary_reason}; "
                    f"also={','.join(decision.failed_gates[1:]) or 'none'}"
                ),
                style="value",
            )
        )
        return tuple(rows)

    def verbose_lines(self, *, panel: bool = False) -> tuple[str, ...]:
        lines: list[str] = []
        continuation_key = ""
        for row in self.verbose_rows(panel=panel):
            if row.key:
                lines.append(f"{row.key}: {row.value}")
                continuation_key = row.key
            else:
                lines.append(f"{' ' * (len(continuation_key) + 2)}{row.value}")
        return tuple(lines)


def _review_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _review_region_text(region: AudioReviewRegion, *, panel: bool) -> str:
    separator = "–" if panel else "-"
    return f"{_review_time(region.start_seconds)}{separator}{_review_time(region.end_seconds)}"


def _review_frame_for_lag(attempt: AudioAlignmentAttempt, lag: int) -> int:
    compensation = attempt.audio.compensation_seconds or 0.0
    seconds = lag / attempt.analysis.analysis_rate + compensation
    return math.floor(seconds * attempt.fps_num / attempt.fps_den + 0.5)


def _review_chunk_bounds(
    attempt: AudioAlignmentAttempt, first: int, last: int
) -> tuple[float, float]:
    starts = attempt.chunks.starts
    counts = attempt.chunks.counts
    rate = attempt.analysis.analysis_rate
    if starts and 0 <= first < len(starts) and 0 <= last < len(starts):
        return starts[first] / rate, (starts[last] + counts[last]) / rate
    chunk_samples = attempt.analysis.chunk_samples
    return first * chunk_samples / rate, min(
        (last + 1) * chunk_samples, attempt.chunks.total_samples
    ) / rate


def _review_target_bounds(
    attempt: AudioAlignmentAttempt, target: VideoTargetEvidence
) -> tuple[float, float]:
    rate = attempt.analysis.analysis_rate
    return target.start_sample / rate, target.end_sample / rate


def _review_target_map(
    video: VideoCheckObservation,
) -> dict[_AudioReviewTargetKey, VideoTargetEvidence]:
    return {
        (target.kind, target.first_chunk_index, target.last_chunk_index): target
        for target in video.targets
    }


def _review_target_status(target: VideoTargetEvidence | None) -> AudioReviewRegionStatus:
    if target is None:
        return "not settled"
    if target.resolution in {"resolved", "alternative_confirmed"}:
        return "confirmed by video"
    return "not checked" if target.resolution == "unexamined" else "not settled"


def _review_target_offset(video: VideoCheckObservation, target: VideoTargetEvidence) -> int:
    if target.resolution == "resolved" and video.confirmed_offset is not None:
        return video.confirmed_offset
    return target.target_offset


def _review_target_candidates(
    attempt: AudioAlignmentAttempt,
    targets: tuple[VideoTargetEvidence, ...],
) -> tuple[AudioReviewRegion, ...]:
    regions: list[AudioReviewRegion] = []
    for target in targets:
        start, end = _review_target_bounds(attempt, target)
        regions.append(
            AudioReviewRegion(
                _review_target_offset(attempt.video_check, target),
                start,
                end,
                _review_target_status(target),
                target.resolution,
                (target.kind, target.first_chunk_index, target.last_chunk_index),
            )
        )
    return tuple(regions)


def _review_region_target_projections(
    region: AudioReviewRegion,
) -> tuple[_AudioReviewTargetProjection, ...]:
    if region.target_projections:
        return region.target_projections
    if region.target_key is None or region.target_resolution is None:
        return ()
    return ((region.target_key, region.target_resolution),)


def _review_merge_target_projections(
    first: AudioReviewRegion, second: AudioReviewRegion
) -> tuple[_AudioReviewTargetProjection, ...]:
    return tuple(
        dict.fromkeys(
            (
                *_review_region_target_projections(first),
                *_review_region_target_projections(second),
            )
        )
    )


def _review_merge_status(
    first: AudioReviewRegionStatus, second: AudioReviewRegionStatus
) -> AudioReviewRegionStatus:
    if "not checked" in {first, second}:
        return "not checked"
    if "not settled" in {first, second}:
        return "not settled"
    return "confirmed by video"


def _review_track_bounds(attempt: AudioAlignmentAttempt) -> tuple[float, float]:
    planned = attempt.analysis.planned_chunk_count
    if planned:
        return _review_chunk_bounds(attempt, 0, planned - 1)
    return 0.0, 0.0


def _review_non_overlapping(
    regions: tuple[AudioReviewRegion, ...],
) -> tuple[AudioReviewRegion, ...]:
    ordered = sorted(regions, key=lambda region: (region.start_seconds, region.end_seconds))
    clipped: list[AudioReviewRegion] = []
    cursor = 0.0
    for region in ordered:
        if (
            clipped
            and region.start_seconds == clipped[-1].start_seconds
            and region.end_seconds == clipped[-1].end_seconds
            and region.offset == clipped[-1].offset
        ):
            previous = clipped[-1]
            primary = previous if previous.target_key is not None else region
            clipped[-1] = AudioReviewRegion(
                previous.offset,
                previous.start_seconds,
                previous.end_seconds,
                (
                    primary.status
                    if primary.target_key is not None
                    else _review_merge_status(previous.status, region.status)
                ),
                primary.target_resolution,
                primary.target_key,
                _review_merge_target_projections(previous, region),
            )
            continue
        start = max(region.start_seconds, cursor)
        if region.end_seconds <= start:
            continue
        candidate = AudioReviewRegion(
            region.offset,
            start,
            region.end_seconds,
            region.status,
            region.target_resolution,
            region.target_key,
            _review_region_target_projections(region),
        )
        if (
            clipped
            and clipped[-1].offset == candidate.offset
            and clipped[-1].status == candidate.status
            and clipped[-1].target_resolution == candidate.target_resolution
            and clipped[-1].target_key == candidate.target_key
            and clipped[-1].target_projections == candidate.target_projections
        ):
            previous = clipped[-1]
            clipped[-1] = AudioReviewRegion(
                previous.offset,
                previous.start_seconds,
                max(previous.end_seconds, candidate.end_seconds),
                previous.status,
                previous.target_resolution,
                previous.target_key,
                previous.target_projections,
            )
        else:
            clipped.append(candidate)
        cursor = max(cursor, candidate.end_seconds)
    return tuple(clipped)


def _review_overlay_regions(
    base_regions: tuple[AudioReviewRegion, ...],
    target_regions: tuple[AudioReviewRegion, ...],
) -> tuple[AudioReviewRegion, ...]:
    all_regions = (*base_regions, *target_regions)
    boundaries = tuple(
        sorted(
            {
                boundary
                for region in all_regions
                for boundary in (region.start_seconds, region.end_seconds)
                if region.end_seconds > region.start_seconds
            }
        )
    )
    segments: list[AudioReviewRegion] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        if end <= start:
            continue
        active_base = tuple(
            region
            for region in base_regions
            if region.start_seconds < end and region.end_seconds > start
        )
        active_targets = tuple(
            region
            for region in target_regions
            if region.start_seconds < end and region.end_seconds > start
        )
        if not active_base and not active_targets:
            continue
        if active_targets:
            selected_target = min(
                active_targets,
                key=lambda region: (
                    region.end_seconds - region.start_seconds,
                    region.start_seconds,
                ),
            )
            active = (selected_target,) + tuple(
                region
                for region in (*active_targets, *active_base)
                if region is not selected_target
            )
            offset = selected_target.offset
        else:
            active = active_base
            offset = active_base[0].offset
        primary = next((region for region in active if region.target_key is not None), active[0])
        status = active[0].status
        projections = _review_region_target_projections(active[0])
        for region in active[1:]:
            if not active_targets:
                status = _review_merge_status(status, region.status)
            projections = tuple(
                dict.fromkeys((*projections, *_review_region_target_projections(region)))
            )
        segments.append(
            AudioReviewRegion(
                offset,
                start,
                end,
                status,
                primary.target_resolution,
                primary.target_key,
                projections,
            )
        )
    return _review_non_overlapping(tuple(segments))


def _review_regions(
    attempt: AudioAlignmentAttempt, suggested: int | None
) -> tuple[AudioReviewRegion, ...]:
    video = attempt.video_check
    targets = _review_target_map(video)
    runs: list[AudioReviewRegion] = []
    for run in attempt.runs:
        target = targets.get(("run", run.first_index, run.last_index))
        converted = _review_frame_for_lag(attempt, run.lag)
        offset = (
            _review_target_offset(video, target)
            if target is not None
            else (
                suggested
                if suggested is not None
                and (run.lag == attempt.audio.global_lag or converted == suggested)
                else converted
            )
        )
        start, end = (
            _review_target_bounds(attempt, target)
            if target is not None
            else _review_chunk_bounds(attempt, run.first_index, run.last_index)
        )
        status: AudioReviewRegionStatus = (
            "confirmed by video"
            if video.confirmed_offset is not None and offset == video.confirmed_offset
            else _review_target_status(target)
        )
        runs.append(
            AudioReviewRegion(
                offset,
                start,
                end,
                status,
                target.resolution if target is not None else None,
                ("run", run.first_index, run.last_index) if target is not None else None,
            )
        )

    majority = tuple(
        region for region in runs if suggested is not None and region.offset == suggested
    )
    if majority:
        regions = runs
    elif suggested is not None:
        start, end = _review_track_bounds(attempt)
        competing = _review_non_overlapping(tuple(runs))
        majority_regions: list[AudioReviewRegion] = []
        cursor = start
        majority_status = (
            "confirmed by video" if video.confirmed_offset == suggested else "not settled"
        )
        for region in competing:
            if region.start_seconds > cursor:
                majority_regions.append(
                    AudioReviewRegion(suggested, cursor, region.start_seconds, majority_status)
                )
            cursor = max(cursor, region.end_seconds)
        if cursor < end:
            majority_regions.append(AudioReviewRegion(suggested, cursor, end, majority_status))
        regions = (*majority_regions, *competing)
    else:
        regions = tuple(runs)

    chronological = _review_overlay_regions(
        _review_non_overlapping(tuple(regions)),
        _review_target_candidates(attempt, video.targets),
    )
    if suggested is None:
        return chronological
    return tuple(
        [region for region in chronological if region.offset == suggested]
        + [region for region in chronological if region.offset != suggested]
    )


def _review_reason_region(
    regions: tuple[AudioReviewRegion, ...], suggested: int | None, reason: str
) -> AudioReviewRegion | None:
    candidates = tuple(region for region in regions if region.offset != suggested)
    target_candidates = candidates

    def target_regions(
        kind: VideoTargetKind,
        resolutions: frozenset[VideoTargetResolution],
    ) -> tuple[AudioReviewRegion, ...]:
        return tuple(
            region
            for region in target_candidates
            if any(
                target_key[0] == kind and resolution in resolutions
                for target_key, resolution in _review_region_target_projections(region)
            )
        )

    if reason == "competing_offset_confirmed_by_video":
        candidates = tuple(
            region
            for region in candidates
            if any(
                resolution == "alternative_confirmed"
                for _target_key, resolution in _review_region_target_projections(region)
            )
        )
        return candidates[0] if candidates else None
    if reason == "competing_offset":
        candidates = target_regions("run", frozenset({"unresolved", "unexamined"}))
        return candidates[0] if candidates else None
    if reason == "unresolved_audio_disagreement":
        candidates = target_regions("chunk", frozenset({"unresolved"}))
        if not candidates:
            candidates = target_regions("run", frozenset({"unresolved"}))
        return candidates[0] if candidates else None
    return candidates[0] if candidates else (regions[0] if regions else None)


def _review_video_vote(
    video: VideoCheckObservation,
) -> tuple[int, int, float | None]:
    if video.observation != "observed" or video.confirmed_offset is None:
        return 0, 0, None
    informative: list[tuple[int, float]] = []
    for position in video.positions:
        scores = position.score_by_offset
        best_index = min(range(len(scores)), key=scores.__getitem__)
        if best_index == 0 or best_index == len(scores) - 1:
            continue
        best = scores[best_index]
        if not best < scores[best_index - 1] or not best < scores[best_index + 1]:
            continue
        runner = min(score for index, score in enumerate(scores) if index != best_index)
        if best == 0.0:
            if runner == 0.0:
                continue
            margin = math.inf
        else:
            margin = runner / best
            if margin < 1.1:
                continue
        informative.append((video.scored_offsets[best_index], margin))
    wins = sum(winner == video.confirmed_offset for winner, _margin in informative)
    winning_margins = [margin for winner, margin in informative if winner == video.confirmed_offset]
    return wins, len(informative), (median(winning_margins) if winning_margins else None)


def build_audio_review_presentation(attempt: AudioAlignmentAttempt) -> AudioReviewPresentation:
    """Build the shared P4/P4a presentation policy for one audio attempt."""
    video = attempt.video_check
    suggested = video.confirmed_offset
    if suggested is None and attempt.decision.candidate is not None:
        suggested = attempt.decision.candidate.frame_offset
    reasons = tuple(
        dict.fromkeys(attempt.decision.failed_gates or (attempt.decision.primary_reason,))
    )
    regions = _review_regions(attempt, suggested)
    same_frame_regions = tuple(
        AudioReviewRegion(
            (video.confirmed_offset if video.confirmed_offset is not None else item.rounded_frame),
            *_review_chunk_bounds(attempt, item.chunk_index, item.chunk_index),
            "confirmed by video",
        )
        for item in video.same_frame_context
    )
    resolved_regions: list[AudioReviewRegion] = []
    for target in video.targets:
        if target.kind != "chunk":
            continue
        start, end = _review_target_bounds(attempt, target)
        target_region = AudioReviewRegion(
            (video.confirmed_offset if video.confirmed_offset is not None else suggested or 0),
            start,
            end,
            _review_target_status(target),
        )
        if target.resolution == "resolved" and target.credible:
            resolved_regions.append(target_region)
    wins, informative, margin = _review_video_vote(video)
    return AudioReviewPresentation(
        attempt=attempt,
        suggested_offset=suggested,
        reasons=reasons,
        regions=regions,
        check_points=video.check_points[:5],
        same_frame_regions=tuple(same_frame_regions),
        resolved_regions=tuple(resolved_regions),
        video_wins=wins,
        video_informative=informative,
        video_margin=margin,
    )


__all__ = [
    "AUDIO_ANALYSIS_SAMPLE_RATE",
    "AUDIO_COLLECTION_FAILURE_PHRASE",
    "AUDIO_UNAVAILABLE_REASON_PHRASES",
    "AlignmentStabilityClassification",
    "AlignmentStabilitySummary",
    "AudioAlignmentAttempt",
    "AudioAlignmentDecision",
    "AudioAuthorityRecount",
    "AudioAnalysisFacts",
    "AudioAttemptStatus",
    "AudioCandidateBasis",
    "AudioChunkColumns",
    "AudioChunkRun",
    "AudioCollectionFacts",
    "AudioCollectionFailure",
    "AudioCollectionObservation",
    "AudioDecisionCandidate",
    "AudioDecisionState",
    "AudioDurationBasis",
    "AudioMetadataMatch",
    "AudioOutcomeStatus",
    "AudioPairSide",
    "AudioPeakRatio",
    "AudioReviewPresentation",
    "AudioReviewRegion",
    "AudioReviewRegionStatus",
    "AudioSelectionMethod",
    "AudioStageOutcome",
    "AudioStartBasis",
    "CollectionFailureCategory",
    "EvidenceRow",
    "EvidenceRowStyle",
    "MAX_VIDEO_ALTERNATIVE_OFFSETS",
    "MAX_VIDEO_CHECK_POINTS",
    "MAX_VIDEO_POSITIONS",
    "MAX_VIDEO_TARGET_POSITIONS",
    "MAX_VIDEO_TARGETS",
    "MAX_AUDIO_CHUNKS",
    "SelectedAudioStreamEvidence",
    "AudioSameFrameContext",
    "VideoCheckPoint",
    "VideoCheckObservation",
    "VideoCheckObservationState",
    "VideoPositionDifference",
    "VideoTargetEvidence",
    "VideoTargetKind",
    "VideoTargetPosition",
    "VideoTargetResolution",
    "VideoTargetWinner",
    "audio_evidence_rows",
    "audio_unavailable_phrase",
    "build_audio_review_presentation",
    "evidence_from_payload",
]
