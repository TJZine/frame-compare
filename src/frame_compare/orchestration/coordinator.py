"""Run coordination types for Frame Compare 2.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RunRequest:
    """Complete configuration for a comparison run.

    All fields map to CLI flags or config file sections.
    See cli-module.md for CLI flag → config mappings.
    """

    # Core paths
    root: Path
    config_path: Path | None = None
    input_dir: Path | None = None

    # Cache behavior
    no_cache: bool = False
    from_cache_only: bool = False

    # Skip flags
    skip_analysis: bool = False
    skip_metadata: bool = False
    skip_dovi: bool = False
    no_upload: bool = False

    # Tonemap overrides (highest priority)
    tm_preset: str | None = None
    tm_target_nits: int | None = None
    tm_curve: str | None = None

    # Frame selection overrides
    frame_count: int | None = None
    seed: int | None = None

    # Output behavior
    overlay_mode: str | None = None
    no_color: bool = False
    quiet: bool = False
    verbose: bool = False
    json_output: bool = False


def _empty_str_list() -> list[str]:
    return []


def _empty_phase_timings() -> dict[str, float]:
    return {}


@dataclass(frozen=True)
class RunResult:
    """Complete result from a comparison run."""

    # Outputs
    success: bool
    screenshot_dir: Path | None = None
    slowpics_url: str | None = None
    report_path: Path | None = None

    # Metrics
    frame_count: int = 0
    clips_processed: int = 0
    duration_seconds: float = 0.0
    cache_hit: bool = False

    # Diagnostics
    errors: list[str] = field(default_factory=_empty_str_list)
    warnings: list[str] = field(default_factory=_empty_str_list)
    phase_timings: dict[str, float] = field(default_factory=_empty_phase_timings)
