from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Literal, cast, get_args

type AudioDecisionState = Literal["trusted_automatic", "provisional", "unavailable"]
type AudioAttemptStatus = Literal["complete", "preanalysis_rejection", "aborted"]
type AudioSelectionMethod = Literal["explicit_override", "automatic_metadata"]
type AudioMetadataMatch = Literal["match", "mismatch", "unknown", "not_applicable"]
type AudioPeakRatio = float | Literal["unbounded"]
type AudioStartBasis = Literal["metadata", "default_zero"]
type AudioDurationBasis = Literal[
    "duration_ts", "stream_duration", "stream_tag", "packet_tail", "unavailable"
]
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
type VideoTargetKind = Literal["chunk", "run"]
type VideoTargetResolution = Literal[
    "resolved",
    "unresolved",
    "unexamined",
    "alternative_confirmed",
    "local_video_inconclusive",
]
type VideoTargetWinner = Literal["confirmed", "alternative", "neither"]

AUDIO_ANALYSIS_SAMPLE_RATE = 8000
MAX_AUDIO_CHUNKS = 4096
MAX_VIDEO_TARGET_POSITIONS = 12

AUDIO_UNAVAILABLE_REASON_PHRASES: dict[str, str] = {
    "no_single_offset": "no single offset across the track",
    "search_edge": "best offset at the search edge",
    "no_usable_audio": "no usable audio signal",
    "selected_audio_timeline_unavailable": "selected audio timeline unavailable",
    "retime_rate_unsupported": "retimed audio rate unsupported",
    "analysis_budget_exceeded": "analysis budget exceeded",
    "source_identity_changed": "source changed during analysis",
}
AUDIO_COLLECTION_FAILURE_PHRASE = "audio collection failed"


def audio_unavailable_phrase(reason: str) -> str:
    phrase = AUDIO_UNAVAILABLE_REASON_PHRASES.get(reason)
    if phrase is not None:
        return phrase
    if reason in get_args(CollectionFailureCategory.__value__):
        return AUDIO_COLLECTION_FAILURE_PHRASE
    return reason


def analysis_stream_start(start: Fraction, timeline_scale: Fraction) -> Fraction:
    return start * timeline_scale


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
    timeline_scale_num: int
    timeline_scale_den: int

    @property
    def timeline_scale(self) -> Fraction:
        return Fraction(self.timeline_scale_num, self.timeline_scale_den)

    @property
    def analysis_audio_start(self) -> Fraction:
        return analysis_stream_start(
            Fraction(self.stream_start_num, self.stream_start_den), self.timeline_scale
        )

    @property
    def analysis_video_start(self) -> Fraction:
        return analysis_stream_start(
            Fraction(self.video_start_num, self.video_start_den), self.timeline_scale
        )


@dataclass(frozen=True, slots=True)
class AudioAnalysisFacts:
    analysis_rate: int
    max_offset_seconds: float
    chunk_samples: int
    lag_samples: int
    planned_chunk_count: int


@dataclass(frozen=True, slots=True)
class AudioChunkColumns:
    """Compact columnar per-chunk rows over the planned chunks.

    Empty columns mean chunk rows were never observed (a rejection or an
    aborted collection). Otherwise every column has one entry per planned chunk.
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


@dataclass(frozen=True, slots=True)
class AudioStageOutcome:
    status: AudioOutcomeStatus
    global_lag: int | None
    active_chunks: int
    credible_chunks: int
    agreeing_chunks: int
    compensation_seconds: float | None
    subframe_estimate: float | None
    rounded_frame: int | None


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


@dataclass(frozen=True, slots=True)
class AudioCollectionFailure:
    category: CollectionFailureCategory
    side: AudioPairSide | None


@dataclass(frozen=True, slots=True)
class VideoPositionDifference:
    """Per-position rank-normalized luma differences for each scored offset."""

    position_index: int
    reference_frame: int
    score_by_offset: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class VideoTargetPosition:
    position_index: int
    reference_frame: int
    confirmed_score: float
    alternative_score: float
    winner: VideoTargetWinner
    alternative_offset: int | None = None


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

    def representative_offset(self) -> int:
        if self.resolution == "alternative_confirmed":
            return next(
                position.alternative_offset
                for position in self.positions
                if position.winner == "alternative" and position.alternative_offset is not None
            )
        return self.target_offset


@dataclass(frozen=True, slots=True)
class AudioSameFrameContext:
    """A credible audio disagreement that rounds to the confirmed frame."""

    chunk_index: int
    lag_samples: int
    subframe_estimate: float
    rounded_frame: int


@dataclass(frozen=True, slots=True)
class AudioAuthorityRecount:
    """The A4b frame-level recount alongside the untouched U1 outcome."""

    raw_status: AudioOutcomeStatus
    raw_agreeing_chunks: int
    authority_status: AudioOutcomeStatus
    authority_agreeing_chunks: int
    passed: bool


@dataclass(frozen=True, slots=True)
class VideoCheckPoint:
    timestamp_seconds: float
    reference_frame: int
    suggested_comparison_frame: int


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


@dataclass(frozen=True, slots=True)
class AudioDecisionCandidate:
    frame_offset: int
    time_offset_seconds: float
    subframe_estimate: float
    basis: AudioCandidateBasis


@dataclass(frozen=True, slots=True)
class AudioAlignmentDecision:
    """Diagnostic decision kept separate from applied alignment authority."""

    state: AudioDecisionState
    candidate: AudioDecisionCandidate | None
    primary_reason: str
    failed_gates: tuple[str, ...]


@dataclass(frozen=True)
class AlignmentStabilitySummary:
    classification: AlignmentStabilityClassification
    valid_windows: int
    offset_min_frames: int | None
    offset_max_frames: int | None
    first_offset_frames: int | None
    last_offset_frames: int | None
    largest_adjacent_jump_frames: int | None
    change_position_seconds: float | None


@dataclass(frozen=True)
class AudioAlignmentAttempt:
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


def audio_attempt_payload(attempt: AudioAlignmentAttempt) -> dict[str, object]:
    return cast(dict[str, object], asdict(attempt))


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
    "AudioSelectionMethod",
    "AudioStageOutcome",
    "AudioStartBasis",
    "CollectionFailureCategory",
    "MAX_VIDEO_TARGET_POSITIONS",
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
    "analysis_stream_start",
    "audio_unavailable_phrase",
    "audio_attempt_payload",
]
