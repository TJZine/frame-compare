import math
from dataclasses import dataclass, field
from typing import Literal

type AlignmentSource = Literal["manual", "computed", "cached"]
type AlignmentAlgorithm = Literal["cross_correlation"]
type AlignmentCorrelationMode = Literal["raw_fft", "gcc_phat"]
type AlignmentPreprocessingMode = Literal["none", "standard"]
type AlignmentChannelStrategy = Literal["mono_downmix", "best_channel"]
type AlignmentRefinementMode = Literal["disabled", "local"]
type AlignmentStabilityClassification = Literal[
    "stable",
    "possible_drift",
    "possible_discontinuity",
    "variable",
    "insufficient_evidence",
]
type PreviousOffsetReusePolicy = Literal["disabled", "prompt", "always"]
type AlignmentReuseCacheOrigin = Literal["computed", "interactive_confirmed"]
type AlignmentWriteProvenance = Literal[
    "computed_this_run",
    "interactive_confirmed_this_run",
    "shared_computed_offsets",
    "shared_previous_offsets",
    "preexisting_manual_override",
]
type AlignmentEvidenceAvailability = Literal[
    "current_attempt",
    "historical_details_unavailable",
    "not_computed",
]
type AudioDecisionState = Literal["trusted_automatic", "provisional", "unavailable"]
type AudioAttemptStatus = Literal["complete", "preanalysis_rejection", "aborted"]
type AudioSelectionMethod = Literal["explicit_override", "automatic_metadata"]
type AudioMetadataMatch = Literal["match", "mismatch", "unknown", "not_applicable"]
type AudioWindowPurpose = Literal["primary", "disputed_recheck", "zero_check"]
type AudioPeakRatio = float | Literal["unbounded"]
type AudioCollectionPhase = Literal["discovery", "verification"]
type AudioCollectionRole = Literal["reference", "comparison"]
type AudioCollectionStatus = Literal["complete", "failed"]
type AudioCollectionEnd = Literal["planned_end_reached", "observed_eof", "not_observed"]
type AudioCollectionObservation = Literal["observed", "not_observed"]
type AudioWindowCoverageState = Literal["complete", "short", "empty", "not_observed"]
type AudioWindowQualityDisposition = Literal["qualified", "rejected", "not_observed"]


def _require_int(value: object, name: str, *, minimum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


@dataclass(frozen=True, slots=True)
class SelectedAudioStreamEvidence:
    """Pathless facts for one resolved audio stream choice."""

    role: Literal["reference", "comparison"]
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
    stream_start_basis: Literal["metadata", "default_zero"]
    input_start_num: int
    input_start_den: int
    input_start_basis: Literal["metadata", "default_zero"]
    time_base_num: int | None
    time_base_den: int | None
    duration_num: int | None
    duration_den: int | None
    duration_basis: str

    def __post_init__(self) -> None:
        _require_int(self.audio_stream_index, "audio_stream_index", minimum=0)
        _require_int(self.absolute_stream_index, "absolute_stream_index", minimum=0)
        if len(self.source_identity_digest) != 64:
            raise ValueError("source_identity_digest must be a SHA-256 hex digest")
        for name in ("stream_start_den", "input_start_den"):
            _require_int(getattr(self, name), name, minimum=1)
        for name in ("sample_rate", "channels", "time_base_num", "duration_num"):
            value = getattr(self, name)
            if value is not None:
                _require_int(value, name, minimum=0)
        for name in ("time_base_den", "duration_den"):
            value = getattr(self, name)
            if value is not None:
                _require_int(value, name, minimum=1)


@dataclass(frozen=True, slots=True)
class AudioAlignmentCollectionRecord:
    """Bounded scalar facts for one continuous collection phase and role."""

    phase: AudioCollectionPhase
    role: AudioCollectionRole
    output_rate: int
    requested_horizon: int
    emitted_sample_count: int
    emitted_byte_count: int
    retained_sample_count: int
    retained_byte_count: int
    status: AudioCollectionStatus
    end_category: AudioCollectionEnd
    observed_eof_sample: int | None
    elapsed_seconds: float
    cleanup_failure_count: int
    failure_count: int

    def __post_init__(self) -> None:
        if self.phase not in {"discovery", "verification"}:
            raise ValueError("collection phase is invalid")
        if self.role not in {"reference", "comparison"}:
            raise ValueError("collection role is invalid")
        _require_int(self.output_rate, "output_rate", minimum=1)
        _require_int(self.requested_horizon, "requested_horizon", minimum=1)
        for name in (
            "emitted_sample_count",
            "emitted_byte_count",
            "retained_sample_count",
            "retained_byte_count",
            "cleanup_failure_count",
            "failure_count",
        ):
            _require_int(getattr(self, name), name, minimum=0)
        complete_bytes = self.emitted_sample_count * 4
        if not complete_bytes <= self.emitted_byte_count <= complete_bytes + 3:
            raise ValueError("emitted byte count must match complete float32 samples and carry")
        if self.status == "complete" and self.emitted_byte_count != complete_bytes:
            raise ValueError("complete collection cannot retain a partial float32 carry")
        if self.retained_byte_count != self.retained_sample_count * 4:
            raise ValueError("retained byte count must match float32 sample count")
        if self.observed_eof_sample is not None:
            _require_int(self.observed_eof_sample, "observed_eof_sample", minimum=0)
        if (
            isinstance(self.elapsed_seconds, bool)
            or not math.isfinite(self.elapsed_seconds)
            or self.elapsed_seconds < 0
        ):
            raise ValueError("collection elapsed time must be finite and non-negative")
        if self.status == "complete" and (
            self.cleanup_failure_count != 0 or self.failure_count != 0
        ):
            raise ValueError("complete collection cannot have failure counters")
        if self.status == "failed":
            if self.failure_count < 1:
                raise ValueError("failed collection must have a failure")
            if self.cleanup_failure_count > self.failure_count:
                raise ValueError("cleanup failures cannot exceed collection failures")
        if self.end_category == "planned_end_reached":
            if self.status != "complete" or self.observed_eof_sample is not None:
                raise ValueError("planned-end collection facts are inconsistent")
            if self.emitted_sample_count != self.requested_horizon:
                raise ValueError("planned-end collection must emit its requested horizon")
        elif self.end_category == "observed_eof":
            if self.status != "complete" or self.observed_eof_sample is None:
                raise ValueError("observed-EOF collection facts are inconsistent")
            if not 0 <= self.observed_eof_sample < self.requested_horizon:
                raise ValueError("observed EOF is outside the requested horizon")
            if self.emitted_sample_count != self.observed_eof_sample:
                raise ValueError("observed EOF must match emitted sample count")
        elif self.end_category == "not_observed":
            if self.status != "failed" or self.observed_eof_sample is not None:
                raise ValueError("unobserved collection facts are inconsistent")
        else:
            raise ValueError("collection end category is invalid")


@dataclass(frozen=True, slots=True)
class AudioAlignmentWindowRecord:
    """Bounded outcome for one planned alignment window."""

    logical_id: str
    purpose: AudioWindowPurpose
    attempt_number: int
    parent_id: str | None
    planned_reference_start: int
    planned_reference_count: int
    planned_comparison_start: int
    planned_comparison_count: int
    analysis_rate: int
    requested_rate: int
    actual_reference_count: int | None = None
    actual_comparison_count: int | None = None
    scoring_reference_count: int | None = None
    scoring_comparison_count: int | None = None
    discovery_reference_count: int | None = None
    discovery_comparison_count: int | None = None
    verification_reference_count: int | None = None
    verification_comparison_count: int | None = None
    continuous_sample_count: int | None = None
    continuous_sample_count_origin: Literal["discovery", "verification", "not_observed"] = (
        "not_observed"
    )
    actual_useful_reference_start: int | None = None
    actual_useful_reference_end: int | None = None
    pre_eof_expected_overlap: int | None = None
    actual_coverage: float | None = None
    coverage_state: AudioWindowCoverageState = "not_observed"
    quality_disposition: AudioWindowQualityDisposition = "not_observed"
    effective_aligned_overlap: int | None = None
    origin_basis: Literal["planned_assumption", "not_measured"] = "planned_assumption"
    local_lag: float | None = None
    global_analysis_lag: float | None = None
    requested_sample_lag: int | None = None
    requested_frame_candidate: int | None = None
    requested_score: float | None = None
    score_stage: str | None = None
    peak_ratio: AudioPeakRatio | None = None
    peak_stage: str | None = None
    peak_rate: int | None = None
    review_qualified: bool = False
    configured_quality: bool = False
    vote_disposition: Literal["voted", "abstained", "failed"] = "failed"
    terminal_stage: str = "planned"
    terminal_category: str = "planned"
    failed_role: Literal["reference", "comparison"] | None = None

    def __post_init__(self) -> None:
        _require_int(self.attempt_number, "attempt_number", minimum=1)
        for name in (
            "planned_reference_start",
            "planned_reference_count",
            "planned_comparison_start",
            "planned_comparison_count",
            "analysis_rate",
            "requested_rate",
        ):
            _require_int(
                getattr(self, name),
                name,
                minimum=1 if name in {"analysis_rate", "requested_rate"} else 0,
            )
        for name in (
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
        ):
            value = getattr(self, name)
            if value is not None:
                _require_int(value, name, minimum=0)
        for name in ("requested_sample_lag", "requested_frame_candidate"):
            value = getattr(self, name)
            if value is not None:
                _require_int(value, name)
        for value in (self.local_lag, self.global_analysis_lag, self.requested_score):
            if value is not None and not math.isfinite(value):
                raise ValueError("window numeric evidence must be finite")
        if self.actual_coverage is not None:
            if isinstance(self.actual_coverage, bool) or not math.isfinite(self.actual_coverage):
                raise ValueError("window actual coverage must be finite and numeric")
            if not 0 <= self.actual_coverage <= 1:
                raise ValueError("window actual coverage must be between zero and one")
        if (self.actual_useful_reference_start is None) != (
            self.actual_useful_reference_end is None
        ):
            raise ValueError("useful reference interval must have both endpoints")
        if (
            self.actual_useful_reference_start is not None
            and self.actual_useful_reference_end is not None
            and self.actual_useful_reference_end < self.actual_useful_reference_start
        ):
            raise ValueError("useful reference interval is reversed")
        if self.continuous_sample_count_origin not in {
            "discovery",
            "verification",
            "not_observed",
        }:
            raise ValueError("continuous sample count origin is invalid")
        if (
            self.continuous_sample_count is None
            and self.continuous_sample_count_origin != "not_observed"
        ):
            raise ValueError("missing continuous sample count must be not_observed")
        if (
            self.continuous_sample_count is not None
            and self.continuous_sample_count_origin == "not_observed"
        ):
            raise ValueError("observed continuous sample count needs an origin")
        if self.coverage_state not in {"complete", "short", "empty", "not_observed"}:
            raise ValueError("window coverage state is invalid")
        if self.coverage_state == "not_observed" and any(
            value is not None
            for value in (
                self.actual_coverage,
                self.actual_useful_reference_start,
                self.actual_useful_reference_end,
                self.pre_eof_expected_overlap,
            )
        ):
            raise ValueError("unobserved coverage cannot include observed facts")
        if self.quality_disposition not in {"qualified", "rejected", "not_observed"}:
            raise ValueError("window quality disposition is invalid")
        if isinstance(self.peak_ratio, float) and not math.isfinite(self.peak_ratio):
            raise ValueError("unbounded peak ratio must use the explicit string encoding")


@dataclass(frozen=True, slots=True)
class AudioAlignmentCandidate:
    """Observed representative for one frame-equivalent candidate group."""

    sample_offset: int
    sample_rate: int
    frame_offset: int
    supporting_window_ids: tuple[str, ...]
    median_score: float
    minimum_peak_ratio: AudioPeakRatio

    def __post_init__(self) -> None:
        _require_int(self.sample_offset, "sample_offset")
        _require_int(self.sample_rate, "sample_rate", minimum=1)
        _require_int(self.frame_offset, "frame_offset")
        if not self.supporting_window_ids:
            raise ValueError("candidate must have supporting windows")
        if not math.isfinite(self.median_score):
            raise ValueError("candidate median_score must be finite")
        if isinstance(self.minimum_peak_ratio, float) and not math.isfinite(
            self.minimum_peak_ratio
        ):
            raise ValueError("unbounded peak ratio must use the explicit string encoding")
        if len(set(self.supporting_window_ids)) != len(self.supporting_window_ids):
            raise ValueError("candidate supporting window IDs must be unique")


@dataclass(frozen=True, slots=True)
class AudioAlignmentDecision:
    """Diagnostic decision kept separate from applied alignment authority."""

    state: AudioDecisionState
    candidate: AudioAlignmentCandidate | None
    primary_reason: str
    raw_correlated_windows: int
    consensus_windows: int
    consensus_ratio: float | None
    aggregate_score: float | None
    minimum_peak_ratio: AudioPeakRatio | None
    failed_gates: tuple[str, ...] = ()
    unassessed_gates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state == "unavailable" and self.candidate is not None:
            raise ValueError("unavailable audio decision cannot have a candidate")
        if self.state != "unavailable" and self.candidate is None:
            raise ValueError(f"{self.state} audio decision requires a candidate")
        _require_int(self.raw_correlated_windows, "raw_correlated_windows", minimum=0)
        _require_int(self.consensus_windows, "consensus_windows", minimum=0)
        for value in (self.consensus_ratio, self.aggregate_score):
            if value is not None and not math.isfinite(value):
                raise ValueError("aggregate decision evidence must be finite")
        if isinstance(self.minimum_peak_ratio, float) and not math.isfinite(
            self.minimum_peak_ratio
        ):
            raise ValueError("unbounded peak ratio must use the explicit string encoding")


@dataclass(frozen=True, slots=True)
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
    sample_rate: int
    fps_num: int
    fps_den: int
    confidence_threshold: float
    ambiguity_peak_ratio: float
    minimum_valid_windows: int
    consensus_minimum_ratio: float
    selected_streams: tuple[SelectedAudioStreamEvidence, ...]
    analysis_rate: int | None
    planned_window_count: int
    peak_fft_points: int | None
    total_fft_points: int | None
    planning_reason: str | None
    windows: tuple[AudioAlignmentWindowRecord, ...]
    decision: AudioAlignmentDecision
    stability: "AlignmentStabilitySummary | None" = None
    collection_observation: AudioCollectionObservation = "not_observed"
    collection_summaries: tuple[AudioAlignmentCollectionRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_int(self.comparison_ordinal, "comparison_ordinal", minimum=1)
        _require_int(self.sample_rate, "sample_rate", minimum=1)
        _require_int(self.fps_num, "fps_num", minimum=1)
        _require_int(self.fps_den, "fps_den", minimum=1)
        _require_int(self.planned_window_count, "planned_window_count", minimum=0)
        for value in (
            self.confidence_threshold,
            self.ambiguity_peak_ratio,
            self.consensus_minimum_ratio,
        ):
            if not math.isfinite(value):
                raise ValueError("audio attempt configuration must be finite")
        _require_int(self.minimum_valid_windows, "minimum_valid_windows", minimum=1)
        for name in ("analysis_rate", "peak_fft_points", "total_fft_points"):
            value = getattr(self, name)
            if value is not None:
                _require_int(value, name, minimum=0)
        if len(self.ffmpeg_version) > 512 or len(self.ffprobe_version) > 512:
            raise ValueError("runtime version evidence exceeds its text bound")
        if len(self.extraction_recipe) > 256:
            raise ValueError("extraction recipe exceeds its text bound")
        if len(self.windows) > 18 or self.planned_window_count > 16:
            raise ValueError("audio attempt exceeds the bounded window contract")
        if self.collection_observation not in {"observed", "not_observed"}:
            raise ValueError("collection observation is invalid")
        if len(self.collection_summaries) > 4:
            raise ValueError("audio attempt exceeds the bounded collection contract")
        if self.collection_observation == "not_observed" and self.collection_summaries:
            raise ValueError("unobserved collection facts must be absent")
        if self.collection_observation == "observed" and not self.collection_summaries:
            raise ValueError("observed collection facts must not be absent")
        collection_keys = {
            (collection.phase, collection.role) for collection in self.collection_summaries
        }
        if len(collection_keys) != len(self.collection_summaries):
            raise ValueError("audio attempt collection summaries must be unique")
        if len({window.logical_id for window in self.windows}) != len(self.windows):
            raise ValueError("audio attempt window logical IDs must be unique")
        if sum(window.purpose == "primary" for window in self.windows) != self.planned_window_count:
            raise ValueError("planned_window_count must match primary window records")
        if len(self.selected_streams) != 2 or tuple(
            stream.role for stream in self.selected_streams
        ) != ("reference", "comparison"):
            raise ValueError("audio attempt requires reference and comparison stream evidence")
        if self.selected_streams[0].source_identity_digest != self.reference_identity_digest:
            raise ValueError("reference stream evidence must match the attempt identity")
        if self.selected_streams[1].source_identity_digest != self.comparison_identity_digest:
            raise ValueError("comparison stream evidence must match the attempt identity")
        window_ids = {window.logical_id for window in self.windows}
        candidate = self.decision.candidate
        if candidate is not None and not set(candidate.supporting_window_ids) <= window_ids:
            raise ValueError("candidate supporting windows must belong to the attempt")
        correlated = sum(window.terminal_category == "correlated" for window in self.windows)
        if self.decision.raw_correlated_windows != correlated:
            raise ValueError("raw correlated count must match the retained window records")


@dataclass(frozen=True)
class AlignmentWindowEvidence:
    """One bounded correlation estimate used only for stability diagnostics."""

    start_sample: int
    end_sample: int
    sample_offset: int
    score: float
    peak_ratio: float


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


@dataclass(frozen=True)
class AlignmentResult:
    """Result of an audio alignment operation."""

    reference_clip: str
    comparison_clip: str
    frame_offset: int | None
    time_offset_seconds: float | None
    correlation_score: float
    algorithm: AlignmentAlgorithm | None
    source: AlignmentSource
    applied: bool = True
    diagnostic: str | None = None
    stability: AlignmentStabilitySummary | None = None
    audio_attempt: AudioAlignmentAttempt | None = None

    def __post_init__(self) -> None:
        if self.frame_offset is not None:
            _require_int(self.frame_offset, "frame_offset")
        if self.audio_attempt is None or self.source != "computed":
            return
        decision = self.audio_attempt.decision
        if decision.state != "trusted_automatic":
            if (
                self.applied
                or self.frame_offset is not None
                or self.time_offset_seconds is not None
            ):
                raise ValueError("untrusted audio evidence cannot authorize an applied result")
            return
        candidate = decision.candidate
        if (
            not self.applied
            or candidate is None
            or self.frame_offset != candidate.frame_offset
            or self.time_offset_seconds is None
        ):
            raise ValueError("trusted automatic evidence must match the applied result")


@dataclass(frozen=True)
class AlignmentProvenance:
    """Current-run provenance used to decide shared alignment-cache write eligibility."""

    result: AlignmentResult
    comparison_cache_key: str
    provenance: AlignmentWriteProvenance
    computed_result: AlignmentResult | None = None
    evidence_availability: AlignmentEvidenceAvailability = "not_computed"


@dataclass(frozen=True)
class ReusableAlignmentEntry:
    """Shared-cache reusable alignment entry with prompt-display metadata."""

    result: AlignmentResult
    accepted_at: str
    origin: AlignmentReuseCacheOrigin
    computed_result: AlignmentResult | None = None


@dataclass(frozen=True)
class AlignmentConfig:
    """Configuration for audio alignment."""

    enable: bool = True
    sample_rate: int = 8000
    max_offset_seconds: float = 30.0
    use_vsview: bool = False
    force_interactive: bool = False
    cache_results: bool = True
    previous_offsets: PreviousOffsetReusePolicy = "disabled"
    correlation_mode: AlignmentCorrelationMode = "raw_fft"
    preprocessing_mode: AlignmentPreprocessingMode = "none"
    channel_strategy: AlignmentChannelStrategy = "mono_downmix"
    confidence_threshold: float = 0.0
    ambiguity_peak_ratio: float = 1.0
    window_length_seconds: float = 0.0
    window_stride_seconds: float = 0.0
    minimum_valid_windows: int = 1
    consensus_minimum_ratio: float = 1.0
    refinement_mode: AlignmentRefinementMode = "disabled"
    refinement_sample_rate: int | None = None
    reference_stream: int | None = None
    comparison_streams: dict[str, int] = field(default_factory=dict[str, int])
    no_color: bool = False


@dataclass(frozen=True)
class ParsedMetadata:
    """Metadata extracted from filename."""

    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None
    release_group: str | None = None
    source: str | None = None  # BluRay, WEB-DL, etc.
    resolution: str | None = None


@dataclass(frozen=True)
class TmdbMetadata:
    """Metadata from TMDB API."""

    tmdb_id: int
    title: str
    original_title: str
    year: int
    media_type: Literal["movie", "tv"]
    original_language: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None


@dataclass(frozen=True)
class SlowpicsCollectionMetadata:
    """Resolved slow.pics collection identity, independent of HTTP field names."""

    title: str
    tmdb_id: int | None = None
    tmdb_media_type: Literal["movie", "tv"] | None = None


@dataclass(frozen=True)
class MetadataConfig:
    """Configuration for metadata service."""

    api_key: str | None = None
    unattended: bool = False  # Do not prompt for unresolved matches
    timeout_seconds: float = 10.0
    year_tolerance: int = 2
    category_preference: Literal["movie", "tv"] | None = None
