"""Shared orchestration data transfer objects and interfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from frame_compare.config import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.orchestration.context import ClipState
from frame_compare.render.ffmpeg import DefaultFFmpegRunner, FFmpegRunner
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.progress import ProgressReporter
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.loader import DefaultVSLoader, VSLoader


@dataclass(frozen=True)
class RunRequest:
    """Complete configuration for a comparison run.

    All fields map to CLI flags or config file sections.
    See docs/current-cli-contract.md for CLI flag → config mappings and persistence rules.
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
    force_interactive_alignment: bool = False

    # Tonemap overrides (highest priority)
    tm_preset: TonemapPreset | None = None
    tm_target_nits: int | None = None
    tm_curve: ToneCurve | None = None

    # Frame selection overrides
    frame_count: int | None = None
    seed: int | None = None

    # Output behavior
    overlay_mode: OverlayMode | None = None
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


@dataclass
class RunDependencies:
    """Dependency injection container for run orchestration."""

    vs_loader: VSLoader | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    http_client: httpx.AsyncClient | None = None
    progress: ProgressReporter | None = None
    clock: Callable[[], datetime] = field(default=datetime.now)

    def get_vs_loader(self) -> VSLoader:
        """Return the injected VS loader or create the default lazily."""
        if self.vs_loader is None:
            self.vs_loader = DefaultVSLoader()
        return self.vs_loader

    def get_ffmpeg_runner(self) -> FFmpegRunner:
        """Return the injected FFmpeg runner or create the default lazily."""
        if self.ffmpeg_runner is None:
            self.ffmpeg_runner = DefaultFFmpegRunner()
        return self.ffmpeg_runner


def _empty_screenshots() -> dict[str, list[Path]]:
    return {}


@dataclass
class RunArtifacts:
    """Internal carrier for artifacts accumulated during the run."""

    metrics_cache_hit: bool = False
    screenshots_by_label: dict[str, list[Path]] = field(default_factory=_empty_screenshots)
    slowpics_url: str | None = None
    report_path: Path | None = None
    screenshot_dir: Path | None = None
    resolved_metadata: TmdbMetadata | None = None
    warnings: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class PrepState:
    workspace: WorkspacePaths
    config: ConfigSchema
    input_videos: list[Path]
    clips: list[ClipState]
    artifacts: RunArtifacts
    metadata_prefetched: bool
    preflight_warnings: list[str]
    preflight_duration: float
    load_sources_start: datetime
