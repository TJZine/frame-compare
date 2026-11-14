"""Analysis-specific exception types for Frame Compare."""

from enum import Enum, auto

from frame_compare.errors import ErrorContext, JSONValue, ProcessingError


class SelectionFailureKind(Enum):
    """Internal recovery classification; never part of public error payloads."""

    UNCLASSIFIED = auto()
    EMPTY_METRICS = auto()
    INSUFFICIENT_METRIC_CANDIDATES = auto()
    NO_CLIPS = auto()
    EMPTY_SELECTION_WINDOW = auto()
    INVALID_CLIP_FPS = auto()
    INSUFFICIENT_RANDOM_CANDIDATES = auto()
    NO_INITIAL_FRAMES = auto()
    EMPTY_REFERENCE_DOMAIN = auto()
    INSUFFICIENT_ALIGNED_CANDIDATES = auto()


class SelectionError(ProcessingError):
    """Frame selection algorithm failure (FC-4012)."""

    def __init__(
        self,
        reason: str,
        requested: int,
        found: int,
        *,
        kind: SelectionFailureKind = SelectionFailureKind.UNCLASSIFIED,
        hint: str = "Adjust selection criteria",
        details: dict[str, JSONValue] | None = None,
    ) -> None:
        error_details: dict[str, JSONValue] = {
            "reason": reason,
            "requested": requested,
            "found": found,
        }
        if details is not None:
            error_details.update(details)
        super().__init__(
            ErrorContext(
                code="FC-4012",
                name="SELECTION_ERROR",
                message=f"Frame selection failed: {reason}",
                hint=hint,
                details=error_details,
            )
        )
        self.kind = kind
        self.reason = reason
        self.requested = requested
        self.found = found


class ExclusionRecoverySelectionError(SelectionError):
    """Selection failure that must not enter the unrelated uniform fallback."""


class AnalysisError(ProcessingError):
    """Marker base for analysis failures."""


class MetricsCalculationError(AnalysisError):
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
