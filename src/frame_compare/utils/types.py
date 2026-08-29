"""Shared utility types for Frame Compare.

This module contains cross-cutting type definitions used by multiple layers.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from frame_compare.utils.paths import (
    require_managed_descendant,
    require_managed_immediate_child,
)

type AlignmentPreviousOffsetsPolicy = Literal["disabled", "prompt", "always"]
type AlignmentSelectedReferenceRelationship = Literal["auto", "configured"]
type PreservedFrameProps = dict[str, str | int | float]


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Resolved absolute paths for a workspace.

    These paths are computed once during preflight and passed through
    the execution context. All paths are guaranteed to be absolute
    and (for output paths) writable.

    ``generated_root`` is the resolved, stable generated-data root. It remains
    unchanged when ``with_run_dir`` switches the current run's generated state
    into a child folder.

    Reserved run layout (when run_dir is set):
    - screenshots_dir and generated_dir are resolved relative to run_dir
    - analysis_cache_dir remains at the workspace-level generated cache path
    - This enables fresh per-comparison outputs beneath the contained workspace
      generated base without writing into input_dir, while preserving reusable
      analysis results across runs

    Before reservation (when run_dir is None):
    - generated_dir points at the stable generated-data root so cache-only
      prevalidation can inspect shared state without creating output

    Attributes:
        root: Workspace root directory (contains sentinel like .frame-compare)
        input_dir: Video input directory (may be same as root or subdir)
        generated_root: Resolved persistent generated-data root
        run_dir: Current run folder (None only before reservation)
        screenshots_dir: Screenshot output directory
        generated_dir: Generated files directory for the current run
        analysis_cache_dir: Workspace-level shared analysis cache directory
        alignment_cache_dir: Workspace-level shared alignment cache directory
        config_dir: Config and presets directory
        config_file: Path to config.toml (or None if using defaults)
    """

    root: Path
    input_dir: Path
    generated_root: Path
    run_dir: Path | None
    screenshots_dir: Path
    generated_dir: Path
    config_dir: Path
    config_file: Path | None
    analysis_cache_dir: Path | None = None
    alignment_cache_dir: Path | None = None

    @property
    def shared_analysis_cache_dir(self) -> Path:
        """Workspace-level shared analysis cache directory."""
        if self.analysis_cache_dir is not None:
            return self.analysis_cache_dir
        return self.generated_root / "cache" / "analysis"

    @property
    def shared_alignment_cache_dir(self) -> Path:
        """Workspace-level shared alignment reuse cache directory."""
        if self.alignment_cache_dir is not None:
            return self.alignment_cache_dir
        return self.generated_root / "cache" / "alignment"

    @property
    def cache_dir(self) -> Path:
        """Directory for shared analysis cache files."""
        return self.shared_analysis_cache_dir

    @property
    def probe_cache_dir(self) -> Path:
        """Directory for video probe cache."""
        return self.generated_dir / "probe"

    def with_run_dir(self, run_dir: Path) -> "WorkspacePaths":
        """Return a new WorkspacePaths with run_dir set and paths updated.

        This updates screenshots_dir and generated_dir to be inside run_dir while
        preserving the workspace-level shared analysis cache path.

        Args:
            run_dir: The reserved immediate-child run folder beneath generated_root.

        Returns:
            New WorkspacePaths instance with run folder mode enabled
        """
        resolved_run_dir = require_managed_immediate_child(self.generated_root, run_dir)
        resolved_root = self.generated_root.resolve()
        for managed_path in (
            resolved_run_dir / "screenshots",
            resolved_run_dir / "generated",
            self.shared_analysis_cache_dir,
            self.shared_alignment_cache_dir,
            self.generated_root / "clip_probe.toml",
        ):
            require_managed_descendant(
                resolved_run_dir if managed_path.parent == resolved_run_dir else resolved_root,
                managed_path,
            )
        return replace(
            self,
            run_dir=resolved_run_dir,
            screenshots_dir=resolved_run_dir / "screenshots",
            generated_dir=resolved_run_dir / "generated",
            analysis_cache_dir=self.shared_analysis_cache_dir,
            alignment_cache_dir=self.shared_alignment_cache_dir,
        )


@dataclass(frozen=True, slots=True)
class AlignmentClipIdentity:
    """Layer-neutral stat identity for performance-first cache validation.

    Media contents are intentionally not hashed, so a same-path, same-size,
    same-mtime replacement retains identity.
    """

    path: Path
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class AlignmentClipRequest:
    """Layer-neutral per-clip facts needed by alignment cache/request owners."""

    path: Path
    label: str
    identity: AlignmentClipIdentity
    trim_start_frames: int
    trim_end_frame_inclusive: int | None
    effective_fps_num: int
    effective_fps_den: int
    selected_audio_stream: int | None = None
    preserved_frame_props: PreservedFrameProps = field(default_factory=dict[str, str | int | float])
    presentation_name: str | None = None


@dataclass(frozen=True, slots=True)
class AlignmentCacheSettings:
    """Alignment settings that participate in shared cache identity."""

    sample_rate: int
    max_offset_seconds: float
    correlation_mode: str
    preprocessing_mode: str
    channel_strategy: str
    confidence_threshold: float
    ambiguity_peak_ratio: float
    window_length_seconds: float
    window_stride_seconds: float
    minimum_valid_windows: int
    consensus_minimum_ratio: float
    refinement_mode: str
    refinement_sample_rate: int | None


@dataclass(frozen=True, slots=True)
class AlignmentRequest:
    """Layer-neutral alignment request and cache-identity seam.

    The DTO deliberately lives in utils and uses only primitive or dependency-light
    fields so services can consume it later without importing orchestration or
    analysis-owned clip identity types.
    """

    reference: AlignmentClipRequest
    selected_reference_relationship: AlignmentSelectedReferenceRelationship
    comparisons: list[AlignmentClipRequest]
    previous_offsets: AlignmentPreviousOffsetsPolicy
    generated_dir: Path
    shared_alignment_cache_dir: Path
    settings: AlignmentCacheSettings
    presentation_content: str | None = None
