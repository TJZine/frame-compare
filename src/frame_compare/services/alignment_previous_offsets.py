"""Previous-offset reuse policy for audio alignment."""

from __future__ import annotations

from frame_compare.services.alignment_keys import alignment_key
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
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
    ReusableAlignmentEntry,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest

__all__ = [
    "apply_shared_reuse",
    "prompt_for_previous_alignment_offset_reuse",
    "shared_write_is_service_eligible",
    "validate_previous_offsets_policy",
]


def _alignment_key_from_request(
    request: AlignmentRequest,
    comparison: AlignmentClipRequest,
) -> str:
    return alignment_key(request.reference.path, comparison.path)


def validate_previous_offsets_policy(config: AlignmentConfig) -> None:
    if config.previous_offsets == "disabled":
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
        if result.frame_offset is None or result.time_offset_seconds is None:
            raise AudioAlignmentError("Reusable alignment offset is missing required values.")
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
                presentation_name=comparison.presentation_name,
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
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    computed_cache_hit: bool,
) -> None:
    key = _alignment_key_from_request(request, comparison)
    comparison_key = comparison_cache_key(comparison)
    results_map[key] = result
    provenances[key] = AlignmentProvenance(
        result=result,
        comparison_cache_key=comparison_key,
        provenance="shared_computed_offsets" if computed_cache_hit else "shared_previous_offsets",
    )


def apply_shared_reuse(
    *,
    request: AlignmentRequest,
    unresolved_comparisons: list[AlignmentClipRequest],
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    cache_results: bool,
    progress: ProgressReporter | None,
    no_color: bool,
) -> bool:
    """Apply shared cache hits and return whether confirmed reuse completed alignment."""
    if not cache_results or not unresolved_comparisons:
        return False

    reusable_entries = load_reusable_offset_entries(
        request,
        comparisons=unresolved_comparisons,
    )
    if reusable_entries is None:
        return False

    confirmed_comparisons: list[AlignmentClipRequest] = []
    for comparison in unresolved_comparisons:
        entry = reusable_entries[comparison_cache_key(comparison)]
        if entry.origin == "computed":
            _apply_cached_alignment_result(
                request=request,
                comparison=comparison,
                result=entry.result,
                results_map=results_map,
                provenances=provenances,
                computed_cache_hit=True,
            )
            continue
        confirmed_comparisons.append(comparison)

    if not confirmed_comparisons:
        return False

    if request.previous_offsets == "disabled":
        for comparison in confirmed_comparisons:
            entry = reusable_entries[comparison_cache_key(comparison)]
            if entry.computed_result is None:
                continue
            _apply_cached_alignment_result(
                request=request,
                comparison=comparison,
                result=entry.computed_result,
                results_map=results_map,
                provenances=provenances,
                computed_cache_hit=True,
            )
        return False

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
                    results_map=results_map,
                    provenances=provenances,
                    computed_cache_hit=True,
                )
            return False
        prompt_accepted_confirmed = True

    for comparison in confirmed_comparisons:
        comparison_key = comparison_cache_key(comparison)
        result = reusable_entries[comparison_key].result
        _apply_cached_alignment_result(
            request=request,
            comparison=comparison,
            result=result,
            results_map=results_map,
            provenances=provenances,
            computed_cache_hit=False,
        )
    return prompt_accepted_confirmed or request.previous_offsets == "always"


def shared_write_is_service_eligible(
    *,
    request: AlignmentRequest,
    provenances: dict[str, AlignmentProvenance],
) -> bool:
    if not request.comparisons:
        return False
    has_current_run_write = False
    for comparison in request.comparisons:
        provenance = provenances.get(_alignment_key_from_request(request, comparison))
        if provenance is None:
            return False
        if provenance.provenance in {"computed_this_run", "interactive_confirmed_this_run"}:
            has_current_run_write = True
        if provenance.provenance not in {
            "computed_this_run",
            "shared_computed_offsets",
            "interactive_confirmed_this_run",
        }:
            return False
        if (
            not provenance.result.applied
            or provenance.result.frame_offset is None
            or provenance.result.time_offset_seconds is None
        ):
            return False
    return has_current_run_write


def prompt_for_previous_alignment_offset_reuse(
    *,
    prompt_input: PreviousOffsetPromptInput,
    progress: ProgressReporter | None,
    no_color: bool,
) -> bool:
    """Prompt for shared previous-offset reuse without owning reuse precedence."""
    return prompt_for_previous_offset_reuse(
        prompt_input=prompt_input,
        progress=progress,
        no_color=no_color,
    )
