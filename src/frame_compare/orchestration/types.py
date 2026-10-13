"""Shared orchestration data transfer objects and interfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Literal, Protocol

import httpx

from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.utils.post_upload_actions import PostUploadActionResults
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.loader import VSLoader


@dataclass(frozen=True)
class RunRequest:
    """Complete configuration for a comparison run.

    All fields map to CLI flags or config file sections.
    See docs/current-cli-contract.md for CLI flag → config mappings and persistence rules.
    """

    # Paths and persistent CLI overrides
    root: Path
    config_path: Path | None = None
    config_overrides: CLIConfigOverrides = field(default_factory=CLIConfigOverrides)

    # Run-mode controls
    no_cache: bool = False
    from_cache_only: bool = False
    skip_analysis: bool = False
    skip_metadata: bool = False
    no_color: bool = False
    quiet: bool = False
    verbose: bool = False
    json_output: bool = False


def _utc_now() -> datetime:
    return datetime.now(UTC)


type SlowpicsUploadConfirmationDecision = Literal["confirmed", "declined"]
type FullWindowRetryConfirmationDecision = Literal["confirmed", "declined"]
type MetricsCacheStatus = Literal["skipped", "hit", "miss"]
type SlowpicsUploadConfirmationStatus = Literal[
    "not_applicable",
    "confirmed",
    "declined",
    "report_unavailable",
]


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


@dataclass(frozen=True, slots=True)
class FullWindowRetryConfirmationRequest:
    """Bounded facts passed to the CLI-owned full-window retry confirmation."""

    requested_frame_count: int
    eligible_frame_count: int
    ignore_lead_seconds: float
    ignore_trail_seconds: float


class FullWindowRetryConfirmationFn(Protocol):
    """CLI-owned callback for a run-only full-window retry decision."""

    def __call__(
        self,
        request: FullWindowRetryConfirmationRequest,
    ) -> FullWindowRetryConfirmationDecision: ...


@dataclass(frozen=True, slots=True)
class ReservedRunCapture:
    """Facts known immediately after a run folder's identity is durable."""

    workspace: WorkspacePaths
    clip_count: int
    preflight_duration: float
    preflight_warnings: list[RunWarning]
    run_warnings: list[RunWarning]


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
    errors: list[str] = field(default_factory=list[str])
    warnings: list[RunWarning] = field(default_factory=list[RunWarning])
    phase_timings: dict[str, float] = field(default_factory=dict[str, float])
    # Measured VSView review wait for the human summary. Memory only: never a
    # phase timing, never persisted to the run record or JSON output.
    vsview_review_seconds: float = 0.0


@dataclass
class RunDependencies:
    """Dependency injection container for run orchestration."""

    vs_loader: VSLoader | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    http_client: httpx.AsyncClient | None = None
    progress: ProgressReporter | None = None
    confirm_slowpics_upload: SlowpicsUploadConfirmationFn | None = None
    confirm_full_window_retry: FullWindowRetryConfirmationFn | None = None
    clock: Callable[[], datetime] = field(default=_utc_now)
    monotonic_timer: Callable[[], float] = field(default=monotonic)
    capture_reserved_run: Callable[[ReservedRunCapture], None] | None = field(
        default=None,
        init=False,
        repr=False,
    )
