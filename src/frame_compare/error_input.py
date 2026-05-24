"""Shared input error types."""

from __future__ import annotations

from pathlib import Path

from frame_compare.error_categories import InputError
from frame_compare.error_context import ErrorContext


class VideoOpenError(InputError):
    """Failed to open video file (FC-3002)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3002",
                name="VIDEO_OPEN_ERROR",
                message=f"Failed to open video: {path}",
                hint="Check file permissions and format",
                details={"path": str(path)},
            )
        )


class VideoCorruptError(InputError):
    """Video file is corrupt/unreadable (FC-3003)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3003",
                name="VIDEO_CORRUPT",
                message=f"Video file corrupt: {path}",
                hint="Re-encode or check source integrity",
                details={"path": str(path)},
            )
        )


class IncompatibleVideosError(InputError):
    """Videos differ in dimensions/format (FC-3005)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3005",
                name="INCOMPATIBLE_VIDEOS",
                message=f"Videos incompatible: {reason}",
                hint="Ensure all videos match dimensions/colorspace",
                details={"reason": reason},
            )
        )


class DirectoryNotWritableError(InputError):
    """Cannot write to directory (FC-3007)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3007",
                name="DIRECTORY_NOT_WRITABLE",
                message=f"Directory not writable: {path}",
                hint="Check filesystem permissions",
                details={"path": str(path)},
            )
        )


class FileTooLargeError(InputError):
    """File exceeds size limit (FC-3008)."""

    def __init__(self, path: Path, size: int, limit: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3008",
                name="FILE_TOO_LARGE",
                message=f"File {path} too large ({size} > {limit})",
                hint="Use smaller file or increase limit",
                details={"path": str(path), "size": size, "limit": limit},
            )
        )


class PathEscapesRootError(InputError):
    """Path traversal attempt detected (FC-3009)."""

    def __init__(self, path: Path, root: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3009",
                name="PATH_ESCAPES_ROOT",
                message=f"Path {path} escapes root {root}",
                hint="Do not use .. in paths",
                details={"path": str(path), "root": str(root)},
            )
        )


__all__ = [
    "DirectoryNotWritableError",
    "FileTooLargeError",
    "IncompatibleVideosError",
    "PathEscapesRootError",
    "VideoCorruptError",
    "VideoOpenError",
]
