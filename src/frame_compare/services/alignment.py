"""Audio alignment service using cross-correlation."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import structlog

from frame_compare.services.alignment_audio import (
    extract_audio,
    extract_matching_audio,
    extract_reference_audio,
    probe_fps,
)
from frame_compare.services.alignment_consensus import estimate_consensus_offset
from frame_compare.services.alignment_math import (
    calculate_alignment_trims,
    cross_correlate,
    samples_to_frames,
)
from frame_compare.services.alignment_reuse_cache import (
    comparison_cache_key,
    load_reusable_offset_entries,
    save_reusable_offsets,
)
from frame_compare.services.alignment_reuse_prompt import (
    PreviousOffsetPromptInput,
    PreviousOffsetPromptRow,
    previous_offset_prompt_input_from_rows,
    prompt_for_previous_offset_reuse,
)
from frame_compare.services.alignment_vspreview import maybe_launch_alignment_vspreview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
    ReusableAlignmentEntry,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
from frame_compare.vspreview.overrides import load_manual_overrides

log = structlog.get_logger()

_extract_audio = extract_audio
_extract_matching_audio = extract_matching_audio
_extract_reference_audio = extract_reference_audio
_probe_fps = probe_fps
_cross_correlate = cross_correlate
_estimate_consensus_offset = estimate_consensus_offset
_samples_to_frames = samples_to_frames

__all__ = [
    "_cross_correlate",
    "_extract_audio",
    "_estimate_consensus_offset",
    "_probe_fps",
    "_samples_to_frames",
    "align_clips",
    "align_clips_from_request",
    "calculate_alignment_trims",
    "format_rejected_alignment_warning",
    "prompt_for_previous_alignment_offset_reuse",
]


def _alignment_key(reference: Path, comparison: Path) -> str:
    return f"{reference.stem}:{comparison.stem}"


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
        results_map[key] = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comp.name,
            frame_offset=frame_offset,
            time_offset_seconds=frame_offset / float(resolved_fps_reference),
            correlation_score=1.0,
            algorithm=None,
            source="manual",
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


def _apply_manual_overrides(
    reference: Path,
    comparisons: list[Path],
    cache_dir: Path,
    results_map: dict[str, AlignmentResult],
    fps_reference: Fraction | None,
) -> Fraction | None:
    """Apply manual offsets from overrides config, returning reference FPS if probed."""
    manual_overrides = load_manual_overrides(cache_dir)

    for comp in comparisons:
        key = _alignment_key(reference, comp)
        if key in manual_overrides:
            override = manual_overrides[key]
            if fps_reference is None:
                fps_reference = _probe_fps(reference)
            results_map[key] = AlignmentResult(
                reference_clip=reference.name,
                comparison_clip=comp.name,
                frame_offset=override.frame_offset,
                time_offset_seconds=override.frame_offset / float(fps_reference),
                correlation_score=1.0,
                algorithm=None,
                source="manual",
            )
    return fps_reference


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
) -> None:
    """Extract audio, perform cross-correlation, and populate results map."""
    ref_audio, reference_stream = _extract_reference_audio(
        reference,
        config.sample_rate,
        stream_override=config.reference_stream,
        channel_strategy=config.channel_strategy,
    )
    for comp in requested_comparisons:
        if progress:
            progress.set_description(f"Checking alignment for {comp.name}")

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
        )
        results_map[_alignment_key(reference, comp)] = res
        _record_alignment_progress(progress=progress, result=res)


def _compute_missing_alignments_with_provenance(
    *,
    reference: Path,
    requested_comparisons: list[AlignmentClipRequest],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
) -> None:
    _compute_missing_alignments(
        reference=reference,
        requested_comparisons=[comparison.path for comparison in requested_comparisons],
        config=config,
        results_map=results_map,
        fps_reference=fps_reference,
        progress=progress,
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
) -> None:
    if progress is None:
        return

    match result.source:
        case "cached":
            description = f"Loaded cached alignment for {result.comparison_clip}"
        case "manual":
            description = f"Using manual alignment for {result.comparison_clip}"
        case _:
            description = f"Checked alignment for {result.comparison_clip}"
    progress.set_description(description)
    progress.advance(1)


def _record_resolved_alignment_progress(
    *,
    progress: ProgressReporter | None,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
) -> None:
    for comp in comparisons:
        result = results_map.get(_alignment_key(reference, comp))
        if result is not None:
            _record_alignment_progress(progress=progress, result=result)


def _record_resolved_alignment_request_progress(
    *,
    progress: ProgressReporter | None,
    request: AlignmentRequest,
    results_map: dict[str, AlignmentResult],
) -> None:
    _record_resolved_alignment_progress(
        progress=progress,
        reference=request.reference.path,
        comparisons=[comparison.path for comparison in request.comparisons],
        results_map=results_map,
    )


def _validate_previous_offsets_policy(config: AlignmentConfig) -> None:
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
            )
        )
    return previous_offset_prompt_input_from_rows(
        request=request,
        rows=rows,
    )


def _apply_shared_reuse(
    *,
    request: AlignmentRequest,
    unresolved_comparisons: list[AlignmentClipRequest],
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    progress: ProgressReporter | None,
    no_color: bool,
) -> None:
    if request.previous_offsets == "disabled" or not unresolved_comparisons:
        return

    reusable_entries = load_reusable_offset_entries(
        request,
        comparisons=unresolved_comparisons,
    )
    if reusable_entries is None:
        return
    if request.previous_offsets == "prompt":
        accepted = prompt_for_previous_alignment_offset_reuse(
            prompt_input=_shared_reuse_prompt_input(
                request=request,
                unresolved_comparisons=unresolved_comparisons,
                reusable_entries=reusable_entries,
            ),
            progress=progress,
            no_color=no_color,
        )
        if not accepted:
            return

    for comparison in unresolved_comparisons:
        key = _alignment_key(request.reference.path, comparison.path)
        comparison_key = comparison_cache_key(comparison)
        result = reusable_entries[comparison_key].result
        results_map[key] = result
        provenances[key] = AlignmentProvenance(
            result=result,
            comparison_cache_key=comparison_key,
            provenance="shared_previous_offsets",
        )


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
        provenances[key] = AlignmentProvenance(
            result=result,
            comparison_cache_key=comparison_cache_key(comparison),
            provenance="vspreview_confirmed_this_run",
        )


def _shared_write_is_service_eligible(
    *,
    request: AlignmentRequest,
    provenances: dict[str, AlignmentProvenance],
) -> bool:
    if not request.comparisons:
        return False
    for comparison in request.comparisons:
        provenance = provenances.get(_alignment_key(request.reference.path, comparison.path))
        if provenance is None:
            return False
        if provenance.provenance not in {"computed_this_run", "vspreview_confirmed_this_run"}:
            return False
        if (
            not provenance.result.applied
            or provenance.result.frame_offset is None
            or provenance.result.time_offset_seconds is None
        ):
            return False
    return True


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


def align_clips_from_request(
    request: AlignmentRequest,
    config: AlignmentConfig,
    progress: ProgressReporter | None = None,
    reference_fps: Fraction | None = None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
) -> list[AlignmentResult]:
    """Align clips from the typed request seam with shared previous-offset reuse."""
    reference = request.reference.path
    comparisons = [comparison.path for comparison in request.comparisons]
    _check_duplicate_stems(comparisons)
    if request.previous_offsets != config.previous_offsets:
        raise AudioAlignmentError("Alignment request previous_offsets does not match config.")
    _validate_previous_offsets_policy(config)

    if progress:
        progress.set_description("Audio Alignment")

    results_map: dict[str, AlignmentResult] = {}
    provenances: dict[str, AlignmentProvenance] = {}
    cache_activity_status = ProgressPhaseStatus.COMPLETED
    if progress:
        progress.start_indeterminate("Loading alignment offsets")
    try:
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

        _apply_shared_reuse(
            request=request,
            unresolved_comparisons=unresolved_comparisons,
            results_map=results_map,
            provenances=provenances,
            progress=progress,
            no_color=config.no_color,
        )

        requested_comparisons = [
            comparison
            for comparison in request.comparisons
            if _alignment_key(reference, comparison.path) not in results_map
        ]
    except Exception:
        cache_activity_status = ProgressPhaseStatus.FAILED
        raise
    finally:
        if progress:
            progress.complete_phase(cache_activity_status)

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
        )

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

    if config.cache_results and _shared_write_is_service_eligible(
        request=request,
        provenances=provenances,
    ):
        save_reusable_offsets(request, list(provenances.values()))

    return [
        results_map[_alignment_key(reference, comparison.path)]
        for comparison in request.comparisons
    ]


def align_clips(
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    cache_dir: Path,
    progress: ProgressReporter | None = None,
    reference_fps: Fraction | None = None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
) -> list[AlignmentResult]:
    """
    Align comparison clips to reference using audio cross-correlation.

    Returns:
        List of AlignmentResult for each comparison, in the same order
        as the input `comparisons` list.
    """
    _check_duplicate_stems(comparisons)
    _validate_previous_offsets_policy(config)

    if progress:
        progress.set_description("Audio Alignment")

    results_map: dict[str, AlignmentResult] = {}
    cache_activity_status = ProgressPhaseStatus.COMPLETED
    if progress:
        progress.start_indeterminate("Loading alignment offsets")
    try:
        # 0. Load manual overrides (highest precedence per §2.4)
        fps_reference = _apply_manual_overrides(
            reference,
            comparisons,
            cache_dir,
            results_map,
            reference_fps,
        )

        requested_comparisons = [
            c for c in comparisons if _alignment_key(reference, c) not in results_map
        ]
    except Exception:
        cache_activity_status = ProgressPhaseStatus.FAILED
        raise
    finally:
        if progress:
            progress.complete_phase(cache_activity_status)

    if requested_comparisons:
        _record_resolved_alignment_progress(
            progress=progress,
            reference=reference,
            comparisons=comparisons,
            results_map=results_map,
        )

    # 2. Compute missing
    if requested_comparisons:
        if fps_reference is None:
            fps_reference = _probe_fps(reference)
        _compute_missing_alignments(
            reference=reference,
            requested_comparisons=requested_comparisons,
            config=config,
            results_map=results_map,
            fps_reference=fps_reference,
            progress=progress,
        )

    offsets_by_key = _build_offsets_map(
        reference=reference,
        comparisons=comparisons,
        results_map=results_map,
    )
    confirmed_offsets = maybe_launch_alignment_vspreview(
        reference=reference,
        comparisons=comparisons,
        offsets_by_key=offsets_by_key,
        cache_dir=cache_dir,
        config=config,
        progress=progress,
        frame_props_by_stem=frame_props_by_stem,
    )
    fps_reference = _apply_confirmed_vspreview_offsets(
        reference=reference,
        comparisons=comparisons,
        confirmed_offsets_by_key=confirmed_offsets,
        results_map=results_map,
        fps_reference=fps_reference,
    )

    return [results_map[_alignment_key(reference, c)] for c in comparisons]
