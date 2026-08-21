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
type AlignmentReuseCacheOrigin = Literal["computed", "vspreview_confirmed"]
type AlignmentWriteProvenance = Literal[
    "computed_this_run",
    "vspreview_confirmed_this_run",
    "shared_computed_offsets",
    "shared_previous_offsets",
    "preexisting_manual_override",
]


def _empty_comparison_streams() -> dict[str, int]:
    return {}


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


@dataclass(frozen=True)
class AlignmentProvenance:
    """Current-run provenance used to decide shared alignment-cache write eligibility."""

    result: AlignmentResult
    comparison_cache_key: str
    provenance: AlignmentWriteProvenance
    computed_result: AlignmentResult | None = None


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
    use_vspreview: bool = False
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
    comparison_streams: dict[str, int] = field(default_factory=_empty_comparison_streams)
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
