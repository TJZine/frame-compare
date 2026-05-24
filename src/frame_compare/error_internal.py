"""Shared internal error types."""

from __future__ import annotations

from frame_compare.error_categories import InternalError
from frame_compare.error_context import ErrorContext


class GenericInternalError(InternalError):
    """Unclassified internal error (FC-9001)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9001",
                name="INTERNAL_ERROR",
                message=f"Internal error: {details}",
                hint="Report this bug",
                details={"reason": details},
            )
        )


class InvariantViolationError(InternalError):
    """Invariant violation (FC-9002)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9002",
                name="ASSERTION_ERROR",
                message=f"Assertion failed: {details}",
                hint="Report this bug",
                details={"assertion": details},
            )
        )


class UnexpectedStateError(InternalError):
    """State machine violation (FC-9003)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9003",
                name="UNEXPECTED_STATE",
                message=f"Unexpected state: {details}",
                hint="Report this bug",
                details={"state": details},
            )
        )


__all__ = [
    "GenericInternalError",
    "InvariantViolationError",
    "UnexpectedStateError",
]
