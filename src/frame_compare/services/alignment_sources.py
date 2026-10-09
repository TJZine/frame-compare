"""Frozen alignment-source currentness and sanitized acceptance failures."""

from collections.abc import Iterable

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest


def require_current_alignment_clips(clips: Iterable[AlignmentClipRequest]) -> None:
    """Reject drift before frozen source facts can authorize reuse or persistence."""
    if not all(clip.identity_is_current() for clip in clips):
        raise AudioAlignmentError(
            "Alignment sources changed since preparation.",
            category="source_identity_changed",
            stage="acceptance",
        )


def require_current_alignment_sources(request: AlignmentRequest) -> None:
    require_current_alignment_clips([request.reference, *request.comparisons])
