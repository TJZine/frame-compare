"""Shared orchestration data transfer objects and interfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

import httpx

from frame_compare.analysis.types import (
    FrameMetrics,
    SelectionBreakdown,
    SelectionDetailsByFrame,
)
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.config.schema import ConfigSchema, OverlayMode, ToneCurve, TonemapPreset
from frame_compare.orchestration.context import ClipState
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.post_upload_actions import PostUploadActionResult
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
    user_frames: list[int] | None = None
    random_frame_count: int | None = None
    dark_frame_count: int | None = None
    bright_frame_count: int | None = None
    motion_frame_count: int | None = None
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
            user_frames=self.user_frames,
            random_frame_count=self.random_frame_count,
            dark_frame_count=self.dark_frame_count,
            bright_frame_count=self.bright_frame_count,
            motion_frame_count=self.motion_frame_count,
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


def _empty_selection_details_by_source_frame() -> SelectionDetailsByFrame:
    return {}


type SlowpicsUploadConfirmationDecision = Literal["confirmed", "declined"]
type MetricsCacheStatus = Literal["skipped", "hit", "miss"]
type SlowpicsUploadConfirmationStatus = Literal[
    "not_applicable",
    "confirmed",
    "declined",
    "report_unavailable",
]
type PostUploadActionResults = tuple[PostUploadActionResult, ...]


@dataclass(frozen=True)
class SlowpicsUploadConfirmationRequest:
    """Request passed to the CLI-owned slow.pics upload confirmation callback."""

    report_path: Path


class SlowpicsUploadConfirmationFn(Protocol):
    """CLI-owned callback for report-confirmed slow.pics upload decisions."""

    def __call__(
        self,
        request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision: ...


@dataclass(frozen=True)
class RunResult:
    """Complete result from a comparison run."""

    # Outputs
    success: bool
    screenshot_dir: Path | None = None
    slowpics_url: str | None = None
    report_path: Path | None = None
    post_upload_actions: PostUploadActionResults = ()
    slowpics_upload_confirmation_status: SlowpicsUploadConfirmationStatus = "not_applicable"

    # Metrics
    frame_count: int = 0
    clips_processed: int = 0
    duration_seconds: float = 0.0
    cache_hit: bool = False
    metrics_cache_status: MetricsCacheStatus = "skipped"

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
    confirm_slowpics_upload: SlowpicsUploadConfirmationFn | None = None
    clock: Callable[[], datetime] = field(default=datetime.now)


@dataclass
class RenderArtifacts:
    screenshots_by_label: dict[str, list[Path]]
    screenshot_dir: Path | None
    warnings: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class FramePlanPhaseOutput:
    selected_frames: list[int]
    selection_breakdown: SelectionBreakdown = field(default_factory=SelectionBreakdown)
    selection_details_by_source_frame: SelectionDetailsByFrame = field(
        default_factory=_empty_selection_details_by_source_frame
    )
    warnings: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class AnalyzePhaseOutput:
    selected_frames: list[int]
    selection_breakdown: SelectionBreakdown
    metrics_cache_hit: bool
    analysis_metrics: FrameMetrics
    selection_details_by_source_frame: SelectionDetailsByFrame = field(
        default_factory=_empty_selection_details_by_source_frame
    )


@dataclass(frozen=True)
class AlignPhaseOutput:
    reference: ClipState
    comparisons: list[ClipState]
    selected_frames: list[int]
    selection_breakdown: SelectionBreakdown | None = None
    selection_details_by_source_frame: SelectionDetailsByFrame | None = None
    warnings: list[str] = field(default_factory=_empty_str_list)


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
    uploaded_file_paths: tuple[Path, ...] = ()
    post_upload_actions: PostUploadActionResults = ()


@dataclass(frozen=True)
class ReportPhaseOutput:
    report_path: Path | None
    report_succeeded: bool = False


@dataclass(frozen=True)
class ConfirmSlowpicsUploadPhaseOutput:
    status: SlowpicsUploadConfirmationStatus
    warnings: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class PostReportCleanupPhaseOutput:
    warnings: list[str] = field(default_factory=_empty_str_list)


type PhaseOutput = (
    FramePlanPhaseOutput
    | AnalyzePhaseOutput
    | AlignPhaseOutput
    | RenderPhaseOutput
    | MetadataPhaseOutput
    | DoviPhaseOutput
    | PublishPhaseOutput
    | ReportPhaseOutput
    | ConfirmSlowpicsUploadPhaseOutput
    | PostReportCleanupPhaseOutput
)


@dataclass(init=False)
class RunArtifacts:
    """Internal carrier for artifacts accumulated during the run."""

    metrics_cache_hit: bool
    metrics_cache_status: MetricsCacheStatus
    render: RenderArtifacts | None
    slowpics_url: str | None
    uploaded_slowpics_file_paths: tuple[Path, ...]
    post_upload_actions: PostUploadActionResults
    slowpics_upload_confirmation_status: SlowpicsUploadConfirmationStatus
    report_path: Path | None
    report_succeeded: bool
    resolved_metadata: TmdbMetadata | None
    warnings: list[str]

    def __init__(
        self,
        *,
        metrics_cache_hit: bool = False,
        metrics_cache_status: MetricsCacheStatus = "skipped",
        slowpics_url: str | None = None,
        uploaded_slowpics_file_paths: tuple[Path, ...] = (),
        post_upload_actions: PostUploadActionResults = (),
        slowpics_upload_confirmation_status: SlowpicsUploadConfirmationStatus = "not_applicable",
        report_path: Path | None = None,
        report_succeeded: bool = False,
        resolved_metadata: TmdbMetadata | None = None,
        warnings: list[str] | None = None,
        render: RenderArtifacts | None = None,
    ) -> None:
        self.metrics_cache_hit = metrics_cache_hit
        self.metrics_cache_status = metrics_cache_status
        self.render = render
        self.slowpics_url = slowpics_url
        self.uploaded_slowpics_file_paths = uploaded_slowpics_file_paths
        self.post_upload_actions = post_upload_actions
        self.slowpics_upload_confirmation_status = slowpics_upload_confirmation_status
        self.report_path = report_path
        self.report_succeeded = report_succeeded
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
    analysis_selection_domain: str
    selection_window: SelectionWindow
    analysis_clip: ClipState | None = None
    load_source_diagnostics: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class ExecutionPhasePlan:
    """Execution phases split around the post-align reporting boundary."""

    before_align: list[Phase]
    after_align: list[Phase]
