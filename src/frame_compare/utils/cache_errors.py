"""Cache exception types shared by runtime owners."""

from pathlib import Path

from frame_compare.errors import ErrorContext, ProcessingError


class CacheCorruptionError(ProcessingError):
    """Cache file invalid/unreadable (FC-4006)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4006",
                name="CACHE_CORRUPTION",
                message=f"Cache file corrupted: {path}",
                hint="Clear cache directory",
                details={"path": str(path)},
            )
        )


class CacheVersionMismatchError(ProcessingError):
    """Cache schema version mismatch (FC-4007)."""

    def __init__(self, found: str, expected: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4007",
                name="CACHE_VERSION_MISMATCH",
                message=f"Cache version mismatch (found {found}, expected {expected})",
                hint="Clear cache directory",
                details={"found": found, "expected": expected},
            )
        )
