"""Audio alignment service using cross-correlation."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

from frame_compare.services.alignment_audio import (
    extract_matching_audio,
    extract_reference_audio,
    probe_fps,
)
from frame_compare.services.alignment_consensus import estimate_consensus_offset
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_math import (
    calculate_alignment_trims,
    cross_correlate,
    samples_to_frames,
)
from frame_compare.services.alignment_previous_offsets import (
    apply_shared_reuse,
    prompt_for_previous_alignment_offset_reuse,
    shared_write_is_service_eligible,
    validate_previous_offsets_policy,
)
from frame_compare.services.alignment_reuse_cache import comparison_cache_key, save_reusable_offsets
from frame_compare.services.alignment_vspreview import maybe_launch_alignment_vspreview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
from frame_compare.vspreview.overrides import load_manual_overrides

log = structlog.get_logger()

_extract_matching_audio = extract_matching_audio
_extract_reference_audio = extract_reference_audio
_probe_fps = probe_fps
_cross_correlate = cross_correlate
_estimate_consensus_offset = estimate_consensus_offset
_samples_to_frames = samples_to_frames

__all__ = [
    "_cross_correlate",
    "_estimate_consensus_offset",
    "_probe_fps",
    "_samples_to_frames",
    "align_clips_from_request",
    "calculate_alignment_trims",
    "format_rejected_alignment_warning",
    "prompt_for_previous_alignment_offset_reuse",
]


def _alignment_key(reference: Path, comparison: Path) -> str:
    return alignment_key(reference, comparison)


def _safe_alignment_diagnostic(diagnostic: str | None) -> str:
    if diagnostic is None:
        return "no diagnostic"
    normalized = " ".join(diagnostic.strip().split())
    if not normalized:
        return "no diagnostic"
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.=, ")
    if any(char not in allowed_chars for char in normalized):
        return "diagnostic unavailable"
    return normalized[:120]


def format_rejected_alignment_warning(result: AlignmentResult) -> str:
    """Format a rejected computed alignment as a deterministic run warning."""
    comparison_stem = Path(result.comparison_clip).stem or result.comparison_clip
    reason = _safe_alignment_diagnostic(result.diagnostic)
    return (
        f"align: {comparison_stem} alignment left unapplied because {reason}; "
        "rendering in best-effort reference-frame domain without accepted alignment."
    )


def _build_offsets_map(
    *,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
) -> dict[str, int | None]:
    """Build stable `{reference:comparison -> frame_offset}` map for VSPreview."""
    offsets_by_key: dict[str, int | None] = {}
    for comp in comparisons:
        key = _alignment_key(reference, comp)
        res = results_map.get(key)
        offsets_by_key[key] = res.frame_offset if res is not None and res.applied else None
    return offsets_by_key


def _apply_confirmed_vspreview_offsets(
    *,
    reference: Path,
    comparisons: list[Path],
    confirmed_offsets_by_key: dict[str, int] | None,
    results_map: dict[str, AlignmentResult],
    fps_reference: Fraction | None,
) -> Fraction | None:
    if not confirmed_offsets_by_key:
        return fps_reference

    resolved_fps_reference = fps_reference
    if resolved_fps_reference is None:
        resolved_fps_reference = _probe_fps(reference)

    for comp in comparisons:
        key = _alignment_key(reference, comp)
        if key not in confirmed_offsets_by_key:
            continue
        frame_offset = int(confirmed_offsets_by_key[key])
        computed_stability = results_map[key].stability if key in results_map else None
        results_map[key] = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comp.name,
            frame_offset=frame_offset,
            time_offset_seconds=frame_offset / float(resolved_fps_reference),
            correlation_score=1.0,
            algorithm=None,
            source="manual",
            stability=computed_stability,
        )
    return resolved_fps_reference


def _check_duplicate_stems(comparisons: list[Path]) -> None:
    """Validate that comparison filenames have unique stems."""
    stems_to_paths: dict[str, list[Path]] = {}
    for comp in comparisons:
        stems_to_paths.setdefault(comp.stem, []).append(comp)
    duplicate_stems = {stem: paths for stem, paths in stems_to_paths.items() if len(paths) > 1}
    if duplicate_stems:
        formatted = ", ".join(
            f"{stem}: {[p.name for p in paths]}"
            for stem, paths in sorted(duplicate_stems.items(), key=lambda item: item[0])
        )
        raise AudioAlignmentError(
            "Duplicate comparison clip stems detected (alignment keys use filename stems). "
            f"Rename clips to be unique. Duplicates: {formatted}"
        )


def _apply_manual_overrides_with_provenance(
    *,
    reference: Path,
    comparisons: list[AlignmentClipRequest],
    cache_dir: Path,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    fps_reference: Fraction | None,
) -> Fraction | None:
    manual_overrides = load_manual_overrides(cache_dir)

    for comp in comparisons:
        key = _alignment_key(reference, comp.path)
        if key not in manual_overrides:
            continue
        override = manual_overrides[key]
        if fps_reference is None:
            fps_reference = _probe_fps(reference)
        result = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comp.path.name,
            frame_offset=override.frame_offset,
            time_offset_seconds=override.frame_offset / float(fps_reference),
            correlation_score=1.0,
            algorithm=None,
            source="manual",
        )
        results_map[key] = result
        provenances[key] = AlignmentProvenance(
            result=result,
            comparison_cache_key=comparison_cache_key(comp),
            provenance="preexisting_manual_override",
        )
    return fps_reference


def _compute_missing_alignments(
    *,
    reference: Path,
    requested_comparisons: list[Path],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
    progress_descriptions: dict[Path, str] | None = None,
) -> None:
    """Extract audio, perform cross-correlation, and populate results map."""
    descriptions = progress_descriptions or {}
    ref_audio, reference_stream = _extract_reference_audio(
        reference,
        config.sample_rate,
        stream_override=config.reference_stream,
        channel_strategy=config.channel_strategy,
    )
    for comp in requested_comparisons:
        if progress:
            progress.set_description(descriptions.get(comp, f"ALIGN | {comp.name}"))

        comp_audio = _extract_matching_audio(
            comp,
            config.sample_rate,
            reference_stream=reference_stream,
            stream_override=config.comparison_streams.get(comp.stem),
            channel_strategy=config.channel_strategy,
        )
        estimate = _estimate_consensus_offset(
            ref_audio,
            comp_audio,
            config=config,
            fps=fps_reference,
        )
        frame_offset = (
            _samples_to_frames(estimate.sample_offset, config.sample_rate, fps_reference)
            if estimate.sample_offset is not None
            else None
        )
        time_offset = (
            estimate.sample_offset / config.sample_rate
            if estimate.sample_offset is not None
            else None
        )

        res = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comp.name,
            frame_offset=frame_offset,
            time_offset_seconds=time_offset,
            correlation_score=estimate.score,
            algorithm="cross_correlation",
            source="computed",
            applied=estimate.applied,
            diagnostic=estimate.diagnostic,
            stability=estimate.stability,
        )
        results_map[_alignment_key(reference, comp)] = res
        if progress:
            progress.advance(1)


def _compute_missing_alignments_with_provenance(
    *,
    reference: Path,
    requested_comparisons: list[AlignmentClipRequest],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
    progress_descriptions: dict[Path, str],
) -> None:
    _compute_missing_alignments(
        reference=reference,
        requested_comparisons=[comparison.path for comparison in requested_comparisons],
        config=config,
        results_map=results_map,
        fps_reference=fps_reference,
        progress=progress,
        progress_descriptions=progress_descriptions,
    )
    for comparison in requested_comparisons:
        key = _alignment_key(reference, comparison.path)
        result = results_map[key]
        provenances[key] = AlignmentProvenance(
            result=result,
            comparison_cache_key=comparison_cache_key(comparison),
            provenance="computed_this_run",
        )


def _record_alignment_progress(
    *,
    progress: ProgressReporter | None,
    result: AlignmentResult,
    description: str | None = None,
) -> None:
    if progress is None:
        return

    if description is None:
        description = f"ALIGN | {result.comparison_clip}"
    progress.set_description(description)
    progress.advance(1)


def _record_resolved_alignment_progress(
    *,
    progress: ProgressReporter | None,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
    progress_descriptions: dict[Path, str] | None = None,
) -> None:
    for comp in comparisons:
        result = results_map.get(_alignment_key(reference, comp))
        if result is not None:
            _record_alignment_progress(
                progress=progress,
                result=result,
                description=(progress_descriptions or {}).get(comp),
            )


def _record_resolved_alignment_request_progress(
    *,
    progress: ProgressReporter | None,
    request: AlignmentRequest,
    results_map: dict[str, AlignmentResult],
) -> None:
    progress_descriptions = _request_progress_descriptions(request)
    _record_resolved_alignment_progress(
        progress=progress,
        reference=request.reference.path,
        comparisons=[comparison.path for comparison in request.comparisons],
        results_map=results_map,
        progress_descriptions=progress_descriptions,
    )


def _request_progress_descriptions(request: AlignmentRequest) -> dict[Path, str]:
    return {
        comparison.path: (
            f"ALIGN | Comparison {index} | {comparison.presentation_name or comparison.path.name}"
        )
        for index, comparison in enumerate(request.comparisons, start=1)
    }


def _record_vspreview_provenance(
    *,
    request: AlignmentRequest,
    confirmed_offsets_by_key: dict[str, int] | None,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
) -> None:
    if not confirmed_offsets_by_key:
        return
    for comparison in request.comparisons:
        key = _alignment_key(request.reference.path, comparison.path)
        if key not in confirmed_offsets_by_key:
            continue
        result = results_map[key]
        existing = provenances.get(key)
        computed_result = (
            existing.result
            if existing is not None
            and existing.result.algorithm == "cross_correlation"
            and existing.result.applied
            and existing.result.frame_offset is not None
            and existing.result.time_offset_seconds is not None
            else None
        )
        provenances[key] = AlignmentProvenance(
            result=result,
            comparison_cache_key=comparison_cache_key(comparison),
            provenance="vspreview_confirmed_this_run",
            computed_result=computed_result,
        )


def align_clips_from_request(
    request: AlignmentRequest,
    config: AlignmentConfig,
    progress: ProgressReporter | None = None,
    reference_fps: Fraction | None = None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    verbose: bool = False,
) -> list[AlignmentResult]:
    """Align clips from the typed request seam with shared previous-offset reuse."""
    reference = request.reference.path
    comparisons = [comparison.path for comparison in request.comparisons]
    _check_duplicate_stems(comparisons)
    if request.previous_offsets != config.previous_offsets:
        raise AudioAlignmentError("Alignment request previous_offsets does not match config.")
    validate_previous_offsets_policy(config)

    if progress:
        progress.set_description("ALIGN | Checking saved offsets")

    results_map: dict[str, AlignmentResult] = {}
    provenances: dict[str, AlignmentProvenance] = {}
    fps_reference = _apply_manual_overrides_with_provenance(
        reference=reference,
        comparisons=request.comparisons,
        cache_dir=request.generated_dir,
        results_map=results_map,
        provenances=provenances,
        fps_reference=reference_fps,
    )
    unresolved_comparisons = [
        comparison
        for comparison in request.comparisons
        if _alignment_key(reference, comparison.path) not in results_map
    ]

    completed_confirmed_reuse = apply_shared_reuse(
        request=request,
        unresolved_comparisons=unresolved_comparisons,
        results_map=results_map,
        provenances=provenances,
        cache_results=config.cache_results,
        progress=progress,
        no_color=config.no_color,
    )

    requested_comparisons = [
        comparison
        for comparison in request.comparisons
        if _alignment_key(reference, comparison.path) not in results_map
    ]
    if requested_comparisons:
        _record_resolved_alignment_request_progress(
            progress=progress,
            request=request,
            results_map=results_map,
        )
        if fps_reference is None:
            fps_reference = _probe_fps(reference)
        _compute_missing_alignments_with_provenance(
            reference=reference,
            requested_comparisons=requested_comparisons,
            config=config,
            results_map=results_map,
            provenances=provenances,
            fps_reference=fps_reference,
            progress=progress,
            progress_descriptions=_request_progress_descriptions(request),
        )

    if completed_confirmed_reuse and not requested_comparisons:
        return [
            results_map[_alignment_key(reference, comparison.path)]
            for comparison in request.comparisons
        ]

    offsets_by_key = _build_offsets_map(
        reference=reference,
        comparisons=comparisons,
        results_map=results_map,
    )
    confirmed_offsets = maybe_launch_alignment_vspreview(
        reference=reference,
        comparisons=comparisons,
        offsets_by_key=offsets_by_key,
        cache_dir=request.generated_dir,
        config=config,
        progress=progress,
        frame_props_by_stem=frame_props_by_stem,
        presentation_names_by_stem={
            request.reference.path.stem: (
                request.reference.presentation_name or request.reference.path.stem
            ),
            **{
                comparison.path.stem: (comparison.presentation_name or comparison.path.stem)
                for comparison in request.comparisons
            },
        },
        verbose=verbose,
    )
    fps_reference = _apply_confirmed_vspreview_offsets(
        reference=reference,
        comparisons=comparisons,
        confirmed_offsets_by_key=confirmed_offsets,
        results_map=results_map,
        fps_reference=fps_reference,
    )
    _record_vspreview_provenance(
        request=request,
        confirmed_offsets_by_key=confirmed_offsets,
        results_map=results_map,
        provenances=provenances,
    )

    if config.cache_results and shared_write_is_service_eligible(
        request=request,
        provenances=provenances,
    ):
        save_reusable_offsets(request, list(provenances.values()))

    return [
        results_map[_alignment_key(reference, comparison.path)]
        for comparison in request.comparisons
    ]
