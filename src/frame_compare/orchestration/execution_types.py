"""Internal orchestration execution data transfer objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.analysis.types import (
    FrameMetrics,
    SelectionBreakdown,
    SelectionDetailsByFrame,
)
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import ClipState
from frame_compare.orchestration.types import (
    MetricsCacheStatus,
    PostUploadActionResults,
    SlowpicsUploadConfirmationStatus,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.types import WorkspacePaths

if TYPE_CHECKING:
    from frame_compare.orchestration.full_window_retry import FullWindowRetryOverride
    from frame_compare.orchestration.phases import Phase


def _empty_str_list() -> list[str]:
    return []


def _empty_phase_timings() -> dict[str, float]:
    return {}


def _empty_frame_list() -> list[int]:
    return []


def _empty_selection_details_by_source_frame() -> SelectionDetailsByFrame:
    return {}


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
    warnings: list[str] = field(default_factory=_empty_str_list)
    replaces_frame_plan_selection: bool = False


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
    frame_plan_warnings: list[str] = field(default_factory=_empty_str_list)
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
    load_sources_start: float
    analysis_selection_domain: str
    selection_window: SelectionWindow
    analysis_clip: ClipState | None = None
    full_window_retry_override: FullWindowRetryOverride | None = None
    load_source_diagnostics: list[str] = field(default_factory=_empty_str_list)


@dataclass(frozen=True)
class ExecutionPhasePlan:
    """Execution phases split around the post-align reporting boundary."""

    before_align: list[Phase]
    after_align: list[Phase]


__all__ = [
    "AlignPhaseOutput",
    "AnalyzePhaseOutput",
    "ConfirmSlowpicsUploadPhaseOutput",
    "ExecutionPhasePlan",
    "ExecutionState",
    "FramePlanPhaseOutput",
    "MetadataPhaseOutput",
    "MetadataPrefetch",
    "PhaseOutput",
    "PostReportCleanupPhaseOutput",
    "PrepState",
    "PublishPhaseOutput",
    "RenderArtifacts",
    "RenderPhaseOutput",
    "ReportPhaseOutput",
    "RunArtifacts",
]
