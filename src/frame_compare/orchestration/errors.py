"""Orchestration-owned exception types."""

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
