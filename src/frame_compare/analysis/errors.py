"""Analysis-specific exception types for Frame Compare."""

from pathlib import Path

from frame_compare.errors import ErrorContext, InputError, ProcessingError


class InsufficientFramesError(InputError):
    """Video too short for requested frames (FC-3004)."""

    def __init__(self, path: Path, count: int, required: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3004",
                name="INSUFFICIENT_FRAMES",
                message=f"Video has {count} frames, need at least {required}",
                hint="Use a longer video or reduce frame_count",
                details={
                    "path": str(path),
                    "count": count,
                    "required": required,
                },
            )
        )
        self.path = path


class SelectionError(ProcessingError):
    """Frame selection algorithm failure (FC-4012)."""

    def __init__(self, reason: str, requested: int, found: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4012",
                name="SELECTION_ERROR",
                message=f"Frame selection failed: {reason}",
                hint="Adjust selection criteria",
                details={"reason": reason, "requested": requested, "found": found},
            )
        )


class AnalysisError(ProcessingError):
    """Marker base for analysis failures."""


class MetricsCalculationError(ProcessingError):
    """Failed to calculate metrics (FC-4002)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4002",
                name="METRICS_CALCULATION_ERROR",
                message=f"Metrics calculation failed: {reason}",
                hint="Check input format compatibility",
                details={"reason": reason},
            )
        )
