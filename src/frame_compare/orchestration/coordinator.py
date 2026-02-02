"""Run coordination types for Frame Compare 2.0."""

from __future__ import annotations

from dataclasses import dataclass
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
