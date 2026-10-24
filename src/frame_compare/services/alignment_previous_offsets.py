"""Previous-offset reuse policy for audio alignment."""

from __future__ import annotations

from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_resolution import resolution_from_reuse
from frame_compare.services.alignment_reuse_cache import (
    comparison_cache_key,
    load_reusable_offset_entries,
)
from frame_compare.services.alignment_reuse_prompt import (
    PreviousOffsetPromptInput,
    PreviousOffsetPromptRow,
    previous_offset_prompt_input_from_rows,
    prompt_for_previous_offset_reuse,
)
from frame_compare.services.alignment_sources import require_current_alignment_sources
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    ComparisonResolution,
    ReusableAlignmentEntry,
)
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest

__all__ = [
    "apply_shared_reuse",
    "prompt_for_previous_alignment_offset_reuse",
    "validate_previous_offsets_policy",
]


def _alignment_key_from_request(
    request: AlignmentRequest,
    comparison: AlignmentClipRequest,
) -> str:
    return alignment_key(request.reference.path, comparison.path)


def validate_previous_offsets_policy(request: AlignmentRequest, config: AlignmentConfig) -> None:
    if request.previous_offsets == "disabled":
        return
    if not config.cache_results:
        raise AudioAlignmentError(
            "audio_alignment.previous_offsets requires audio_alignment.cache_results = true."
        )
    if config.force_interactive:
        raise AudioAlignmentError(
            "audio_alignment.force_interactive is incompatible with previous offset reuse."
        )


def _shared_reuse_prompt_input(
    *,
    request: AlignmentRequest,
    unresolved_comparisons: list[AlignmentClipRequest],
    reusable_entries: dict[str, ReusableAlignmentEntry],
) -> PreviousOffsetPromptInput:
    rows: list[PreviousOffsetPromptRow] = []
    for comparison in unresolved_comparisons:
        entry = reusable_entries[comparison_cache_key(comparison)]
        result = entry.result
        assert result.frame_offset is not None
        assert result.time_offset_seconds is not None
        rows.append(
            PreviousOffsetPromptRow(
                label=comparison.label,
                filename=comparison.path.name,
                stem=comparison.path.stem,
                path=str(comparison.path),
                frame_offset=result.frame_offset,
                time_offset_seconds=result.time_offset_seconds,
                accepted_at=entry.accepted_at,
                source="computed" if entry.origin == "computed" else "confirmed",
                short_name=comparison.short_name,
            )
        )
    return previous_offset_prompt_input_from_rows(
        request=request,
        rows=rows,
    )


def _apply_cached_alignment_result(
    *,
    request: AlignmentRequest,
    comparison: AlignmentClipRequest,
    result: AlignmentResult,
    resolutions: dict[str, ComparisonResolution],
    computed_cache_hit: bool,
) -> None:
    raise_if_cancelling()
    require_current_alignment_sources(request)
    key = _alignment_key_from_request(request, comparison)
    comparison_key = comparison_cache_key(comparison)
    resolutions[key] = resolution_from_reuse(
        result, comparison_cache_key=comparison_key, computed=computed_cache_hit
    )


def apply_shared_reuse(
    *,
    request: AlignmentRequest,
    unresolved_comparisons: list[AlignmentClipRequest],
    cache_results: bool,
    progress: ProgressReporter | None,
    no_color: bool,
    verbose: bool = False,
) -> tuple[dict[str, ComparisonResolution], bool]:
    """Apply shared cache hits and return whether confirmed reuse completed alignment."""
    resolutions: dict[str, ComparisonResolution] = {}
    if not cache_results or not unresolved_comparisons:
        return resolutions, False

    reusable_entries = load_reusable_offset_entries(
        request,
        comparisons=unresolved_comparisons,
    )
    if reusable_entries is None:
        return resolutions, False

    confirmed_comparisons: list[AlignmentClipRequest] = []
    for comparison in unresolved_comparisons:
        entry = reusable_entries[comparison_cache_key(comparison)]
        if entry.origin == "computed":
            _apply_cached_alignment_result(
                request=request,
                comparison=comparison,
                result=entry.result,
                resolutions=resolutions,
                computed_cache_hit=True,
            )
            continue
        confirmed_comparisons.append(comparison)

    if not confirmed_comparisons:
        return resolutions, False

    if request.previous_offsets == "disabled":
        for comparison in confirmed_comparisons:
            entry = reusable_entries[comparison_cache_key(comparison)]
            if entry.computed_result is None:
                continue
            _apply_cached_alignment_result(
                request=request,
                comparison=comparison,
                result=entry.computed_result,
                resolutions=resolutions,
                computed_cache_hit=True,
            )
        return resolutions, False

    prompt_accepted_confirmed = False
    if request.previous_offsets == "prompt":
        accepted = prompt_for_previous_alignment_offset_reuse(
            prompt_input=_shared_reuse_prompt_input(
                request=request,
                unresolved_comparisons=confirmed_comparisons,
                reusable_entries=reusable_entries,
            ),
            progress=progress,
            no_color=no_color,
            verbose=verbose,
        )
        if not accepted:
            for comparison in confirmed_comparisons:
                entry = reusable_entries[comparison_cache_key(comparison)]
                if entry.computed_result is None:
                    continue
                _apply_cached_alignment_result(
                    request=request,
                    comparison=comparison,
                    result=entry.computed_result,
                    resolutions=resolutions,
                    computed_cache_hit=True,
                )
            return resolutions, False
        prompt_accepted_confirmed = True

    for comparison in confirmed_comparisons:
        comparison_key = comparison_cache_key(comparison)
        result = reusable_entries[comparison_key].result
        _apply_cached_alignment_result(
            request=request,
            comparison=comparison,
            result=result,
            resolutions=resolutions,
            computed_cache_hit=False,
        )
    return resolutions, prompt_accepted_confirmed or request.previous_offsets == "always"


def prompt_for_previous_alignment_offset_reuse(
    *,
    prompt_input: PreviousOffsetPromptInput,
    progress: ProgressReporter | None,
    no_color: bool,
    verbose: bool = False,
) -> bool:
    """Prompt for shared previous-offset reuse without owning reuse precedence."""
    return prompt_for_previous_offset_reuse(
        prompt_input=prompt_input,
        progress=progress,
        no_color=no_color,
        verbose=verbose,
    )
