"""Types for alignment services."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AlignmentResult:
    """Result of an audio alignment operation."""

    reference_clip: str
    comparison_clip: str
    frame_offset: int
    time_offset_seconds: float
    correlation_score: float
    method: str


@dataclass(frozen=True)
class AlignmentConfig:
    """Configuration for audio alignment."""

    enable: bool = True
    sample_rate: int = 8000
    max_offset_seconds: float = 30.0
    use_vspreview: bool = False
    cache_results: bool = True
