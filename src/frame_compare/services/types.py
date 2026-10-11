import math
from dataclasses import dataclass
from typing import Literal

from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
)

type AlignmentSource = Literal["manual", "computed", "cached"]
type AlignmentAlgorithm = Literal["cross_correlation"]
type AlignmentChannelStrategy = Literal["mono_downmix", "best_channel"]
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


def _require_int(name: str, value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


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
        _require_int("frame_offset", self.frame_offset)
        if self.applied:
            if self.frame_offset is None or self.time_offset_seconds is None:
                raise ValueError("applied alignment requires frame and time offsets")
            if isinstance(self.time_offset_seconds, bool) or not math.isfinite(
                self.time_offset_seconds
            ):
                raise ValueError("applied alignment requires a finite time offset")
        elif self.frame_offset is not None or self.time_offset_seconds is not None:
            raise ValueError("unapplied alignment cannot carry offsets")
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
            or self.time_offset_seconds != candidate.time_offset_seconds
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


@dataclass
class AlignmentReviewSummary:
    """Aggregate native-review outcome for human summaries (memory only).

    This carrier is filled during alignment review and read back by the
    orchestration layer for terminal summaries. It is never persisted to the
    run record, ``phase_timings``, or JSON output.
    """

    review_ran: bool = False
    pairs_confirmed: int = 0
    comparisons_kept: int = 0
    review_seconds: float = 0.0
    # Set when review was pending but VSView never ran, so the durable Align
    # line warns instead of showing success.
    review_unresolved: bool = False


@dataclass(frozen=True)
class AlignmentConfig:
    """Configuration for audio alignment."""

    enable: bool = True
    use_vsview: bool = False
    force_interactive: bool = False
    cache_results: bool = True
    memory_limit_mb: int | None = None
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
