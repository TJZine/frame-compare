"""Resolution fixtures and explicit prepare/save setup for cache tests."""

from collections.abc import Mapping, Sequence

from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_reuse_cache import (
    comparison_cache_key,
    prepare_reusable_source_set,
    save_reusable_offsets,
)
from frame_compare.services.types import AlignmentResult, ComparisonResolution
from frame_compare.utils.types import AlignmentRequest


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
