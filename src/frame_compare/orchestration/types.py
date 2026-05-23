"""Shared orchestration data transfer objects and interfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.config.schema import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.orchestration.context import ClipState
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.loader import VSLoader

if TYPE_CHECKING:
    from frame_compare.orchestration.phases import Phase


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

    def cli_config_overrides(self) -> CLIConfigOverrides:
        """Project runtime CLI values into the config override DTO."""
        return CLIConfigOverrides(
            input_dir=self.input_dir,
            tm_preset=self.tm_preset,
            tm_target_nits=self.tm_target_nits,
            tm_curve=self.tm_curve,
            frame_count=self.frame_count,
            seed=self.seed,
            overlay_mode=self.overlay_mode,
            no_upload=self.no_upload,
            force_interactive_alignment=self.force_interactive_alignment,
        )


def _empty_str_list() -> list[str]:
    return []


def _empty_phase_timings() -> dict[str, float]:
    return {}


def _empty_frame_list() -> list[int]:
    return []


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


@dataclass
class RenderArtifacts:
    screenshots_by_label: dict[str, list[Path]]
    screenshot_dir: Path | None


@dataclass(frozen=True)
class FramePlanPhaseOutput:
    selected_frames: list[int]


@dataclass(frozen=True)
class AnalyzePhaseOutput:
    selected_frames: list[int]
    selection_breakdown: SelectionBreakdown
    metrics_cache_hit: bool


@dataclass(frozen=True)
class AlignPhaseOutput:
    reference: ClipState
    comparisons: list[ClipState]
    selected_frames: list[int]


@dataclass(frozen=True)
class RenderPhaseOutput:
    render: RenderArtifacts


@dataclass(frozen=True)
class MetadataPhaseOutput:
    resolved_metadata: TmdbMetadata | None


@dataclass(frozen=True)
class DoviPhaseOutput:
    warning: str


@dataclass(frozen=True)
class PublishPhaseOutput:
    slowpics_url: str | None


@dataclass(frozen=True)
class ReportPhaseOutput:
    report_path: Path | None


type PhaseOutput = (
    FramePlanPhaseOutput
    | AnalyzePhaseOutput
    | AlignPhaseOutput
    | RenderPhaseOutput
    | MetadataPhaseOutput
    | DoviPhaseOutput
    | PublishPhaseOutput
    | ReportPhaseOutput
)


@dataclass(init=False)
class RunArtifacts:
    """Internal carrier for artifacts accumulated during the run."""

    metrics_cache_hit: bool
    render: RenderArtifacts | None
    slowpics_url: str | None
    report_path: Path | None
    resolved_metadata: TmdbMetadata | None
    warnings: list[str]

    def __init__(
        self,
        *,
        metrics_cache_hit: bool = False,
        slowpics_url: str | None = None,
        report_path: Path | None = None,
        resolved_metadata: TmdbMetadata | None = None,
        warnings: list[str] | None = None,
        render: RenderArtifacts | None = None,
    ) -> None:
        self.metrics_cache_hit = metrics_cache_hit
        self.render = render
        self.slowpics_url = slowpics_url
        self.report_path = report_path
        self.resolved_metadata = resolved_metadata
        self.warnings = [] if warnings is None else warnings


@dataclass
class ExecutionState:
    """Mutable execution state shared explicitly by phase construction."""

    artifacts: RunArtifacts = field(default_factory=RunArtifacts)
    selected_frames: list[int] = field(default_factory=_empty_frame_list)
    phase_timings: dict[str, float] = field(default_factory=_empty_phase_timings)

    @property
    def warnings(self) -> list[str]:
        return self.artifacts.warnings


@dataclass(frozen=True)
class MetadataPrefetch:
    metadata: TmdbMetadata | None
    was_attempted: bool


@dataclass(frozen=True)
class PrepState:
    workspace: WorkspacePaths
    config: ConfigSchema
    input_videos: list[Path]
    clips: list[ClipState]
    artifacts: RunArtifacts
    metadata_prefetch: MetadataPrefetch
    preflight_warnings: list[str]
    preflight_duration: float
    load_sources_start: datetime


@dataclass(frozen=True)
class ExecutionPhasePlan:
    """Execution phases split around the post-align reporting boundary."""

    before_align: list[Phase]
    after_align: list[Phase]
