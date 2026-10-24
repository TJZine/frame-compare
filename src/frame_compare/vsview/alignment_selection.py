"""Session-opening offset hints; no viewer or persistence access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from frame_compare.vsview.alignment_review_contract import AlignmentReviewComparisonMetadata


@dataclass(frozen=True, slots=True)
class OpeningHint:
    offset: int | None
    provisional: bool = False


def opening_hint(comparison: AlignmentReviewComparisonMetadata) -> OpeningHint:
    authority = comparison.audio_review.current_authority.frame_offset
    if authority is not None:
        return OpeningHint(authority)
    attempt = comparison.audio_review.audio_attempt
    if attempt is not None and attempt.decision.state == "provisional":
        candidate = attempt.decision.candidate
        if candidate is not None:
            return OpeningHint(candidate.frame_offset, provisional=True)
    return OpeningHint(None)


@dataclass(frozen=True, slots=True)
class Projection:
    frame: int | None
    status: Literal["available", "unavailable", "outside source range"]
    provisional: bool = False


def project_frame(frame: int, own: OpeningHint, target: OpeningHint, count: int) -> Projection:
    """Project an original coordinate using session-opening edges, checking only the target."""
    if own.offset is None or target.offset is None:
        return Projection(None, "unavailable")
    predicted = frame + own.offset - target.offset
    if not 0 <= predicted < count:
        return Projection(None, "outside source range")
    return Projection(predicted, "available", own.provisional or target.provisional)
