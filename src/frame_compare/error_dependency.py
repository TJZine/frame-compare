"""Shared dependency error types."""

from __future__ import annotations

from frame_compare.error_categories import DependencyError
from frame_compare.error_context import ErrorContext


class DoviToolNotFoundError(DependencyError):
    """dovi_tool binary not found (FC-2007)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2007",
                name="DOVI_TOOL_NOT_FOUND",
                message="dovi_tool binary not found",
                hint="Install dovi_tool and add to PATH or config",
            )
        )


class PythonVersionError(DependencyError):
    """Unsupported Python version (FC-2010)."""

    def __init__(self, current_version: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2010",
                name="PYTHON_VERSION_ERROR",
                message=f"Python version {current_version} not supported",
                hint="Use Python 3.13+",
                details={"current_version": current_version},
            )
        )


__all__ = [
    "DoviToolNotFoundError",
    "PythonVersionError",
]
