from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from frame_compare.services.types import AlignmentSource
from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
)
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.vs.types import HDRMetadata

if TYPE_CHECKING:
    from frame_compare.analysis.types import FrameMetrics, SelectionBreakdown, SelectionDetail
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.selection_domain import PreparedSelectionDomain
    from frame_compare.orchestration.types import FullWindowRetryConfirmationFn
    from frame_compare.services.release_identity import ReleaseIdentity
    from frame_compare.utils.progress_protocol import ProgressReporter
    from frame_compare.utils.types import WorkspacePaths


ClipActiveRectSource = Literal[
    "explicit",
    "metadata",
    "dimension-derived",
    "aspect-ratio-derived",
    "content-derived",
    "full-frame",
]
ClipActiveRectDetectionMode = Literal["provided", "dimension", "aspect_ratio", "auto"]
ClipActiveRectAlgorithmId = Literal["active_rect_resolution_v2"]
ACTIVE_RECT_RESOLUTION_ALGORITHM: ClipActiveRectAlgorithmId = "active_rect_resolution_v2"


@dataclass(frozen=True)
class ClipFingerprint:
    path: Path
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class ClipProbeSnapshot:
    fingerprint: ClipFingerprint
    width: int
    height: int
    num_frames: int
    fps: Fraction
    is_hdr: bool
    hdr_metadata: HDRMetadata | None = None

    preserved_frame_props: dict[str, str | int | float] = field(default_factory=lambda: {})
    tonemap_prop_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ClipTrimState:
    trim_start_frames: int = 0
    trim_end_frame_inclusive: int | None = None


@dataclass(frozen=True)
class ClipAlignmentState:
    reference_stem: str
    comparison_stem: str
    relative_offset_frames: int
    source: AlignmentSource
    stability: AlignmentStabilitySummary | None = None


@dataclass(frozen=True)
class ClipActiveRect:
    x: int
    y: int
    width: int
    height: int
    source: ClipActiveRectSource
    detection_mode: ClipActiveRectDetectionMode
    algorithm_id: ClipActiveRectAlgorithmId = ACTIVE_RECT_RESOLUTION_ALGORITHM


@dataclass(frozen=True)
class ClipState:
    path: Path
    label: str
    probe: ClipProbeSnapshot

    source_fps: Fraction
    effective_fps: Fraction

    trim: ClipTrimState = field(default_factory=ClipTrimState)
    alignment: ClipAlignmentState | None = None
    audio_attempt: AudioAlignmentAttempt | None = None
    active_rect: ClipActiveRect | None = None
    release_identity: ReleaseIdentity | None = None
    label_is_explicit: bool = False

    def effective_num_frames(self) -> int:
        end_inclusive = (
            self.trim.trim_end_frame_inclusive
            if self.trim.trim_end_frame_inclusive is not None
            else self.probe.num_frames - 1
        )
        available = max(
            0,
            min(end_inclusive, self.probe.num_frames - 1) - self.trim.trim_start_frames + 1,
        )
        return int(available)

    def with_trim(
        self, *, trim_start_frames: int, trim_end_frame_inclusive: int | None
    ) -> ClipState:
        if trim_start_frames < 0:
            raise ValueError("trim_start_frames must be >= 0 (trim-first invariant)")
        return replace(
            self,
            trim=ClipTrimState(
                trim_start_frames=trim_start_frames,
                trim_end_frame_inclusive=trim_end_frame_inclusive,
            ),
        )


@dataclass(frozen=True, slots=True)
class SelectionSnapshot:
    """Selected comparison frames and their source-coordinate evidence."""

    frames: tuple[int, ...] = ()
    breakdown: SelectionBreakdown | None = None
    details_by_source_frame: dict[int, SelectionDetail] | None = None
    analysis_metrics: FrameMetrics | None = None


@dataclass
class RunContext:
    config: ConfigSchema
    workspace: WorkspacePaths
    reference: ClipState
    comparisons: list[ClipState]
    selection_domain: PreparedSelectionDomain
    selection: SelectionSnapshot = field(default_factory=SelectionSnapshot)
    reporter: ProgressReporter | None = None
    confirm_full_window_retry: FullWindowRetryConfirmationFn | None = None
    run_warnings: list[RunWarning] | None = None
    preflight_warnings: list[RunWarning] | None = None
    no_color: bool = False
