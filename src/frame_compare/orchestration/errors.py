"""Orchestration-owned exception types."""

from fractions import Fraction
from pathlib import Path
from typing import cast

from frame_compare.errors import ErrorContext, InputError, JSONValue


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
                    "Use comparison sources with the same source FPS as the reference, "
                    "or preprocess them to a common frame rate before running frame-compare."
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
