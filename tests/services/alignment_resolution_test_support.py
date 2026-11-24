"""Resolution fixtures and explicit prepare/save setup for cache tests."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_reuse_cache import (
    comparison_cache_key,
    prepare_reusable_source_set,
    save_reusable_offsets,
)
from frame_compare.services.types import AlignmentResult, ComparisonResolution
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from tests.alignment_review_test_support import trusted_audio_attempt


def resolutions_for_results(
    results: Mapping[str, AlignmentResult],
) -> dict[str, ComparisonResolution]:
    return {
        key: ComparisonResolution(result, key, "computed_this_run")
        for key, result in results.items()
    }


def save_resolutions(
    request: AlignmentRequest,
    resolutions: Sequence[ComparisonResolution],
    *,
    accepted_at: str | None = None,
) -> None:
    by_comparison_key = {item.comparison_cache_key: item for item in resolutions}
    records = {
        alignment_key(request.reference.path, comp.path): by_comparison_key[key]
        for comp in request.comparisons
        if (key := comparison_cache_key(comp)) in by_comparison_key
    }
    candidate = prepare_reusable_source_set(request, records)
    if candidate is not None:
        save_reusable_offsets(request, candidate, accepted_at=accepted_at)


def trusted_computed_result(
    reference: Path, comparison: Path, frame_offset: int
) -> AlignmentResult:
    attempt = trusted_audio_attempt(frame_offset=frame_offset)
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=frame_offset,
        time_offset_seconds=frame_offset / 24,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=attempt.stability,
        audio_attempt=attempt,
    )


def configure_computed_alignment(monkeypatch: pytest.MonkeyPatch, frame_offset: int = 3) -> None:
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda reference, comparison, **_kwargs: trusted_computed_result(
            reference, comparison, frame_offset
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=True, stdout=True, stderr=True),
    )
