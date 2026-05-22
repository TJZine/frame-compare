from dataclasses import dataclass
from typing import Literal

type AlignmentSource = Literal["manual", "computed", "cached"]
type AlignmentAlgorithm = Literal["cross_correlation"]


@dataclass(frozen=True)
class AlignmentResult:
    """Result of an audio alignment operation."""

    reference_clip: str
    comparison_clip: str
    frame_offset: int
    time_offset_seconds: float
    correlation_score: float
    algorithm: AlignmentAlgorithm | None
    source: AlignmentSource


@dataclass(frozen=True)
class AlignmentConfig:
    """Configuration for audio alignment."""

    enable: bool = True
    sample_rate: int = 8000
    max_offset_seconds: float = 30.0
    use_vspreview: bool = False
    force_interactive: bool = False
    cache_results: bool = True


@dataclass(frozen=True)
class ParsedMetadata:
    """Metadata extracted from filename."""

    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
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
    poster_url: str | None = None
    backdrop_url: str | None = None


@dataclass(frozen=True)
class MetadataConfig:
    """Configuration for metadata service."""

    api_key: str | None = None
    unattended: bool = False  # Auto-select first match
    timeout_seconds: float = 10.0
