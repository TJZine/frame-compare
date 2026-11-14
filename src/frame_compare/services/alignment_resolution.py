"""Pure construction and replacement of comparison authority."""

from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path

from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.types import AlignmentResult, ComparisonResolution
from frame_compare.utils.types import AlignmentRequest


def resolution_from_override(
    result: AlignmentResult, *, comparison_cache_key: str
) -> ComparisonResolution:
    return ComparisonResolution(result, comparison_cache_key, "preexisting_manual_override")


def resolution_from_reuse(
    result: AlignmentResult, *, comparison_cache_key: str, computed: bool
) -> ComparisonResolution:
    return ComparisonResolution(
        result,
        comparison_cache_key,
        "shared_computed_offsets" if computed else "shared_previous_offsets",
    )


def resolution_from_computation(
    result: AlignmentResult, *, comparison_cache_key: str
) -> ComparisonResolution:
    return ComparisonResolution(result, comparison_cache_key, "computed_this_run")


def confirm_manual(
    resolution: ComparisonResolution,
    *,
    frame_offset: int,
    fps_reference: Fraction,
    reference_clip: Path,
    comparison_clip: Path,
) -> ComparisonResolution:
    previous = resolution.result
    result = AlignmentResult(
        reference_clip=reference_clip.name,
        comparison_clip=comparison_clip.name,
        frame_offset=frame_offset,
        time_offset_seconds=frame_offset / float(fps_reference),
        correlation_score=1.0,
        algorithm=None,
        source="manual",
        stability=previous.stability,
        audio_attempt=previous.audio_attempt,
    )
    fallback = previous if previous.applied and previous.algorithm == "cross_correlation" else None
    return ComparisonResolution(
        result, resolution.comparison_cache_key, "interactive_confirmed_this_run", fallback
    )


def ordered_results(
    request: AlignmentRequest, resolutions: Mapping[str, ComparisonResolution]
) -> tuple[AlignmentResult, ...]:
    return tuple(
        resolutions[alignment_key(request.reference.path, comparison.path)].result
        for comparison in request.comparisons
    )
