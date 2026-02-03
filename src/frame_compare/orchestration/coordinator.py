"""Run coordination types for Frame Compare 2.0."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx

from frame_compare.orchestration.preflight import prepare_preflight
from frame_compare.orchestration.progress import select_reporter
from frame_compare.utils.progress import ProgressReporter
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from frame_compare.vs.types import HDRMetadata


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


class FFmpegRunner(Protocol):
    """Protocol for FFmpeg-based frame extraction and probing."""

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        """Extract a single frame from the given video into the output path."""
        ...

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        """Probe HDR metadata for a video, returning None if unavailable."""
        ...


class DefaultFFmpegRunner:
    """Stub FFmpeg runner for dependency injection in this slice."""

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        raise NotImplementedError(
            "DefaultFFmpegRunner is a stub in Phase 6.7; inject a runner to use FFmpeg."
        )

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        raise NotImplementedError(
            "DefaultFFmpegRunner is a stub in Phase 6.7; inject a runner to use FFmpeg."
        )


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


async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult:
    """Execute a run request asynchronously.

    Raises:
        FrameCompareError: Any preflight validation errors are propagated.
    """
    if deps is None:
        deps = RunDependencies()

    if deps.progress is None:
        deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
        )

    async def _execute_with_deps() -> RunResult:
        run_start = deps.clock()
        preflight_start = deps.clock()
        preflight = prepare_preflight(
            root=request.root,
            config_path=request.config_path,
        )
        preflight_end = deps.clock()
        run_end = preflight_end

        preflight_seconds = (preflight_end - preflight_start).total_seconds()
        duration_seconds = (run_end - run_start).total_seconds()

        return RunResult(
            success=True,
            duration_seconds=duration_seconds,
            phase_timings={"preflight": preflight_seconds},
            warnings=preflight.warnings,
        )

    if deps.http_client is not None:
        return await _execute_with_deps()

    async with httpx.AsyncClient() as http_client:
        deps.http_client = http_client
        return await _execute_with_deps()
