"""Shared processing error types."""

from __future__ import annotations

from pathlib import Path

from frame_compare.error_categories import ProcessingError
from frame_compare.error_context import ErrorContext


class ProcessingOutOfMemoryError(ProcessingError):
    """OOM during processing (FC-4010)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4010",
                name="MEMORY_ERROR",
                message="Out of memory during processing",
                hint="Reduce thread count or frame count",
            )
        )


class ProcessingTimeoutError(ProcessingError):
    """Operation timed out (FC-4011)."""

    def __init__(self, operation: str, timeout: float) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4011",
                name="TIMEOUT_ERROR",
                message=f"Operation '{operation}' timed out after {timeout}s",
                hint="Increase timeout in config",
                details={"operation": operation, "timeout": timeout},
            )
        )


class DoviError(ProcessingError):
    """Dolby Vision processing error (FC-4018)."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4018",
                name="DOVI_ERROR",
                message=f"Dolby Vision error for {path}: {reason}",
                hint="Check RPU validity or dovi_tool version",
                details={"path": str(path), "reason": reason},
            )
        )


__all__ = [
    "DoviError",
    "ProcessingOutOfMemoryError",
    "ProcessingTimeoutError",
]
