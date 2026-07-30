"""Shared input error types."""

from __future__ import annotations

from pathlib import Path

from frame_compare.error_categories import InputError
from frame_compare.error_context import ErrorContext


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
    "PathEscapesRootError",
]
