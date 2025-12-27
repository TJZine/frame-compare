"""Core utility types for Frame Compare.

This module defines cross-cutting types used throughout the application:
- WorkspacePaths: Resolved paths for a workspace
- RunMetrics: Runtime timing and statistics collection

These types are imported by orchestration, services, and other modules
that need path resolution or metrics tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Resolved absolute paths for a workspace.

    These paths are computed once during preflight and passed through
    the execution context. All paths are guaranteed to be absolute
    and (for output paths) writable.

    Attributes:
        root: Workspace root directory (contains sentinel like .frame-compare)
        input_dir: Video input directory (may be same as root or subdir)
        screenshots_dir: Screenshot output directory
        generated_dir: Cache and generated files directory
        config_dir: Config and presets directory
        config_file: Path to config.toml (or None if using defaults)
    """
    root: Path
    input_dir: Path
    screenshots_dir: Path
    generated_dir: Path
    config_dir: Path
    config_file: Path | None

    @property
    def cache_dir(self) -> Path:
        """Directory for analysis cache files."""
        return self.generated_dir / "cache"

    @property
    def probe_cache_dir(self) -> Path:
        """Directory for video probe cache."""
        return self.generated_dir / "probe"


@dataclass
class RunMetrics:
    """Runtime metrics collection for tracking execution performance.

    Used by the orchestration layer to track phase timings and provide
    summary statistics at run completion.

    Attributes:
        start_time: When the run started
        phase_timings: Mapping of phase names to duration in seconds
        video_count: Number of videos processed
        frame_count: Total frames rendered
        cache_hit: Whether analysis cache was used
    """
    start_time: datetime = field(default_factory=datetime.now)
    phase_timings: dict[str, float] = field(default_factory=dict)
    video_count: int = 0
    frame_count: int = 0
    cache_hit: bool = False

    def record_phase(self, name: str, duration_seconds: float) -> None:
        """Record timing for a completed phase."""
        self.phase_timings[name] = duration_seconds

    @property
    def total_duration_seconds(self) -> float:
        """Total elapsed time from start."""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, object]:
        """Convert to JSON-serializable dictionary."""
        return {
            "start_time": self.start_time.isoformat(),
            "total_seconds": self.total_duration_seconds,
            "phase_timings": self.phase_timings,
            "video_count": self.video_count,
            "frame_count": self.frame_count,
            "cache_hit": self.cache_hit,
        }
