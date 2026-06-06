"""Orchestration-owned exception types."""

from fractions import Fraction
from pathlib import Path
from typing import cast

from frame_compare.errors import ErrorContext, ErrorDetails, InputError, JSONValue


class NoVideosFoundError(InputError):
    """No video files found in directory (FC-3001)."""

    def __init__(self, path: Path, patterns: list[str] | None = None) -> None:
        self.path = path
        self.patterns: list[str] = patterns or []
        super().__init__(
            ErrorContext(
                code="FC-3001",
                name="NO_VIDEOS_FOUND",
                message=f"No video files found in: {path}",
                hint="Check directory path or file extensions",
                details={"path": str(path), "patterns": cast(JSONValue, self.patterns)},
            )
        )


class DirectoryNotFoundError(InputError):
    """Output/cache directory missing (FC-3006)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3006",
                name="DIRECTORY_NOT_FOUND",
                message=f"Directory not found: {path}",
                hint="Create directory or check path",
                details={"path": str(path)},
            )
        )


class InputDiscoveryError(InputError):
    """Failed to discover inputs due to filesystem error (FC-3010)."""

    def __init__(self, path: Path, cause: OSError) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3010",
                name="INPUT_DISCOVERY_ERROR",
                message=f"Failed to discover inputs in {path}: {cause}",
                hint="Check directory permissions and path existence",
                details={"path": str(path), "error": str(cause)},
                cause=cause,
            )
        )
        self.path = path


class MixedSourceFpsError(InputError):
    """Comparison source FPS differs from the reference source FPS (FC-3011)."""

    def __init__(
        self,
        *,
        reference_path: Path,
        reference_fps: Fraction,
        comparison_label: str,
        comparison_path: Path,
        comparison_fps: Fraction,
    ) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3011",
                name="MIXED_SOURCE_FPS",
                message=(
                    "Mixed source FPS is not supported: "
                    f"reference {reference_path.name} is {reference_fps} fps, "
                    f"but {comparison_label} ({comparison_path.name}) is {comparison_fps} fps."
                ),
                hint=(
                    "Use sources.match_fps = 'majority' or sources.match_fps = "
                    "'assume_reference' for AssumeFPS-style timing matching, add per-source "
                    "sources.overrides.<selector>.effective_fps entries, or preprocess sources "
                    "to a common frame rate before running frame-compare."
                ),
                details={
                    "reference_path": str(reference_path),
                    "reference_fps": str(reference_fps),
                    "comparison_label": comparison_label,
                    "comparison_path": str(comparison_path),
                    "comparison_fps": str(comparison_fps),
                },
            )
        )


class SourceSelectionError(InputError):
    """Invalid, missing, or ambiguous configured source selector (FC-3012)."""

    def __init__(
        self,
        *,
        selector: str,
        reason: str,
        role: str,
        matches: list[Path] | None = None,
    ) -> None:
        details: ErrorDetails = {
            "selector": selector,
            "reason": reason,
            "role": role,
            "matches": [str(path) for path in matches or []],
        }
        super().__init__(
            ErrorContext(
                code="FC-3012",
                name="SOURCE_SELECTION_ERROR",
                message=f"Invalid source selector for {role}: {selector!r} ({reason}).",
                hint=(
                    "Use an input-dir-relative path, filename, or unique stem. "
                    "Selectors are case-sensitive; absolute and traversal paths are rejected."
                ),
                details=details,
            )
        )


class DuplicateSourceStemError(InputError):
    """Discovered sources have duplicate stems (FC-3013)."""

    def __init__(self, *, stem: str, matches: list[Path]) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3013",
                name="DUPLICATE_SOURCE_STEM",
                message=(
                    f"Duplicate source stem {stem!r} is not supported until alignment "
                    "persistence uses stable versioned source IDs."
                ),
                hint="Rename one of the source files so every discovered source stem is unique.",
                details={
                    "stem": stem,
                    "matches": cast(JSONValue, [str(path) for path in matches]),
                },
            )
        )


class FastestAnalysisSourceCacheOnlyError(InputError):
    """Runtime-dependent fastest analysis source cannot be resolved in cache-only mode."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3014",
                name="FASTEST_ANALYSIS_SOURCE_CACHE_ONLY",
                message=(
                    "sources.analysis_source = 'fastest' is incompatible with "
                    "--from-cache-only when analysis metrics are required."
                ),
                hint=(
                    "Choose sources.analysis_source = 'reference' or a concrete source selector, "
                    "or run without --from-cache-only so frame-compare can benchmark sources."
                ),
                details={"analysis_source": "fastest", "from_cache_only": True},
            )
        )


class FastestAnalysisSourceError(InputError):
    """No usable source could be benchmarked for fastest analysis source."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3015",
                name="FASTEST_ANALYSIS_SOURCE_FAILED",
                message="No source could be benchmarked for sources.analysis_source = 'fastest'.",
                hint="Choose sources.analysis_source = 'reference' or a concrete source selector.",
                details={"analysis_source": "fastest"},
            )
        )
