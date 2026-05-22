"""Canonical orchestration context types for Frame Compare.

This module defines the immutable per-clip state (ClipState) and the shared
execution context (RunContext) used across all orchestration phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.services.types import AlignmentSource
from frame_compare.vs.types import HDRMetadata

if TYPE_CHECKING:
    from frame_compare.analysis.types import SelectionBreakdown
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.utils.progress import ProgressReporter
    from frame_compare.utils.types import WorkspacePaths


@dataclass(frozen=True)
class ClipFingerprint:
    """Stable fingerprint for cache invalidation.

    This is intentionally simple to compute without opening VS.
    """

    path: Path
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class ClipProbeSnapshot:
    """Cached, expensive-to-derive metadata about a clip (pre-trim).

    Invariants:
    - `num_frames` and `fps` refer to the untrimmed source.
    - HDR detection uses *untrimmed* frame props (frame 0 snapshot).
    - Persisted props are a *filtered subset* needed for downstream correctness.
      Do not attempt to persist arbitrary VapourSynth prop types.
    """

    fingerprint: ClipFingerprint
    width: int
    height: int
    num_frames: int
    fps: Fraction
    is_hdr: bool
    hdr_metadata: HDRMetadata | None = None

    # Minimal, portable prop snapshot for HDR/tonemap/Dolby Vision parity.
    # Keys SHOULD include mastering display / content light level / HDR colorspace values if present.
    preserved_frame_props: dict[str, str | int | float] = field(default_factory=lambda: {})
    tonemap_prop_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ClipTrimState:
    """Effective temporal window for a clip in frames (applied trims only).

    `trim_start_frames` MUST be non-negative (trim-first invariant).
    """

    trim_start_frames: int = 0
    trim_end_frame_inclusive: int | None = None


@dataclass(frozen=True)
class ClipAlignmentState:
    """Alignment state expressed in signed, comparison-relative-to-reference offsets."""

    reference_stem: str
    comparison_stem: str
    relative_offset_frames: int
    source: AlignmentSource


@dataclass(frozen=True)
class ClipState:
    """Canonical per-clip state across orchestration phases (legacy ClipPlan analogue)."""

    path: Path
    label: str
    probe: ClipProbeSnapshot

    # FPS hierarchy (SSOT):
    # - source_fps: from probe
    # - forced_fps: user override (optional; may be added later)
    # - effective_fps: forced if set else source_fps
    source_fps: Fraction
    effective_fps: Fraction

    trim: ClipTrimState = field(default_factory=ClipTrimState)
    alignment: ClipAlignmentState | None = None

    def effective_num_frames(self) -> int:
        """Return effective frame count after applied trims.

        This MUST be used as the frame domain for FramePlan and rendering decisions.
        """
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
        """Return a new ClipState with updated trim window (never mutates in place)."""
        if trim_start_frames < 0:
            raise ValueError("trim_start_frames must be >= 0 (trim-first invariant)")
        return replace(
            self,
            trim=ClipTrimState(
                trim_start_frames=trim_start_frames,
                trim_end_frame_inclusive=trim_end_frame_inclusive,
            ),
        )


@dataclass
class RunContext:
    """Runtime context shared across phases.

    Note: This object may carry non-deterministic resources (http clients, VS core),
    but per-clip state SHOULD remain immutable (`ClipState`).
    """

    config: ConfigSchema
    workspace: WorkspacePaths
    reference: ClipState
    comparisons: list[ClipState]
    reporter: ProgressReporter | None = None
    selection_breakdown: SelectionBreakdown | None = None
