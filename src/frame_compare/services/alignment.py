"""Audio alignment service using cross-correlation."""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import structlog

from frame_compare.services import alignment_audio, alignment_consensus, alignment_math
from frame_compare.services.alignment_correlation import ALIGNMENT_ESTIMATOR_POLICY
from frame_compare.services.alignment_diagnostics import (
    AlignmentReviewOutcome,
    write_alignment_diagnostic,
)
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.alignment_math import calculate_alignment_trims
from frame_compare.services.alignment_previous_offsets import (
    apply_shared_reuse,
    prompt_for_previous_alignment_offset_reuse,
    shared_write_is_service_eligible,
    validate_previous_offsets_policy,
)
from frame_compare.services.alignment_reuse_cache import comparison_cache_key, save_reusable_offsets
from frame_compare.services.alignment_vsview import maybe_launch_alignment_vsview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
    AudioAlignmentAttempt,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

log = structlog.get_logger()

_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"

__all__ = [
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


def format_rejected_alignment_warning(
    result: AlignmentResult,
    *,
    comparison_label: str,
) -> str:
    """Format a rejected computed alignment as a deterministic run warning."""
    reason = _safe_alignment_diagnostic(result.diagnostic)
    return (
        f"align: {comparison_label} alignment left unapplied because {reason}; "
        "rendering in best-effort reference-frame domain without accepted alignment."
    )


def _build_offsets_map(
    *,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
) -> dict[str, int | None]:
    """Build stable `{reference:comparison -> frame_offset}` map for VSView."""
    offsets_by_key: dict[str, int | None] = {}
    for comp in comparisons:
        key = _alignment_key(reference, comp)
        res = results_map.get(key)
        offsets_by_key[key] = res.frame_offset if res is not None and res.applied else None
    return offsets_by_key


def _apply_confirmed_vsview_offsets(
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
        resolved_fps_reference = alignment_audio.probe_fps(reference)

    for comp in comparisons:
        key = _alignment_key(reference, comp)
        if key not in confirmed_offsets_by_key:
            continue
        frame_offset = int(confirmed_offsets_by_key[key])
        previous_result = results_map.get(key)
        computed_stability = previous_result.stability if previous_result is not None else None
        results_map[key] = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comp.name,
            frame_offset=frame_offset,
            time_offset_seconds=frame_offset / float(resolved_fps_reference),
            correlation_score=1.0,
            algorithm=None,
            source="manual",
            stability=computed_stability,
            audio_attempt=(previous_result.audio_attempt if previous_result is not None else None),
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
            fps_reference = alignment_audio.probe_fps(reference)
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
            evidence_availability="historical_details_unavailable",
        )
    return fps_reference


def _clip_identity_digest(clip: AlignmentClipRequest) -> str:
    identity = clip.identity
    payload = (f"{identity.path.resolve()}\0{identity.size_bytes}\0{identity.mtime_ns}").encode()
    return hashlib.sha256(payload).hexdigest()


def _build_audio_attempt(
    *,
    reference: AlignmentClipRequest,
    comparison: AlignmentClipRequest,
    comparison_ordinal: int,
    reference_stream: alignment_audio.AudioStreamInfo,
    comparison_stream: alignment_audio.AudioStreamInfo,
    plan: alignment_audio.AudioAnalysisPlan | alignment_audio.AudioAnalysisBudgetExceeded,
    consensus: alignment_consensus.AlignmentConsensus,
    config: AlignmentConfig,
    fps_reference: Fraction,
) -> AudioAlignmentAttempt:
    if consensus.decision is None:
        raise ValueError("audio consensus is missing its diagnostic decision")
    planned = plan if isinstance(plan, alignment_audio.AudioAnalysisPlan) else None
    return AudioAlignmentAttempt(
        reference_identity_digest=_clip_identity_digest(reference),
        comparison_identity_digest=_clip_identity_digest(comparison),
        comparison_ordinal=comparison_ordinal,
        status="complete" if planned is not None else "preanalysis_rejection",
        estimator_policy=ALIGNMENT_ESTIMATOR_POLICY,
        diagnostic_policy=_DIAGNOSTIC_POLICY,
        media_runtime_fingerprint=media_runtime_fingerprint("alignment"),
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe=alignment_audio.normalized_extraction_recipe(),
        sample_rate=config.sample_rate,
        fps_num=fps_reference.numerator,
        fps_den=fps_reference.denominator,
        confidence_threshold=config.confidence_threshold,
        ambiguity_peak_ratio=config.ambiguity_peak_ratio,
        minimum_valid_windows=config.minimum_valid_windows,
        consensus_minimum_ratio=config.consensus_minimum_ratio,
        selected_streams=(
            alignment_audio.selected_stream_evidence(
                reference_stream,
                role="reference",
                source_identity_digest=_clip_identity_digest(reference),
                explicit_override=config.reference_stream is not None,
            ),
            alignment_audio.selected_stream_evidence(
                comparison_stream,
                role="comparison",
                source_identity_digest=_clip_identity_digest(comparison),
                explicit_override=config.comparison_streams.get(comparison.path.stem) is not None,
                reference_stream=reference_stream,
            ),
        ),
        analysis_rate=planned.sample_rate if planned is not None else None,
        planned_window_count=len(planned.windows) if planned is not None else 0,
        peak_fft_points=planned.peak_fft_points if planned is not None else None,
        total_fft_points=planned.total_fft_points if planned is not None else None,
        planning_reason=plan.reason
        if isinstance(plan, alignment_audio.AudioAnalysisBudgetExceeded)
        else None,
        windows=consensus.window_records,
        decision=consensus.decision,
        stability=consensus.stability,
    )


def _compute_missing_alignments(
    *,
    reference: AlignmentClipRequest,
    requested_comparisons: list[AlignmentClipRequest],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
    progress_descriptions: dict[Path, str] | None = None,
    comparison_ordinals: dict[Path, int] | None = None,
) -> None:
    """Extract audio, perform cross-correlation, and populate results map."""
    descriptions = progress_descriptions or {}
    selected_reference_stream: alignment_audio.AudioStreamInfo | None = None

    def load_reference_stream() -> alignment_audio.AudioStreamInfo:
        nonlocal selected_reference_stream
        if selected_reference_stream is None:
            selected_reference_stream = alignment_audio.select_reference_audio_stream(
                reference.path,
                stream_override=config.reference_stream,
            )
        return selected_reference_stream

    for fallback_ordinal, comp in enumerate(requested_comparisons, start=1):
        comparison_ordinal = (comparison_ordinals or {}).get(comp.path, fallback_ordinal)
        if progress:
            progress.set_description(descriptions.get(comp.path, f"ALIGN | {comp.path.name}"))

        estimate = _estimate_audio_pair(
            reference.path,
            comp.path,
            config=config,
            fps_reference=fps_reference,
            reference_stream_loader=load_reference_stream,
            reference_request=reference,
            comparison_request=comp,
            comparison_ordinal=comparison_ordinal,
        )
        frame_offset = (
            alignment_math.samples_to_frames(
                estimate.sample_offset, config.sample_rate, fps_reference
            )
            if estimate.sample_offset is not None
            else None
        )
        time_offset = (
            estimate.sample_offset / config.sample_rate
            if estimate.sample_offset is not None
            else None
        )

        res = AlignmentResult(
            reference_clip=reference.path.name,
            comparison_clip=comp.path.name,
            frame_offset=frame_offset,
            time_offset_seconds=time_offset,
            correlation_score=estimate.score,
            algorithm="cross_correlation",
            source="computed",
            applied=estimate.applied,
            diagnostic=estimate.diagnostic,
            stability=estimate.stability,
            audio_attempt=estimate.audio_attempt,
        )
        results_map[_alignment_key(reference.path, comp.path)] = res
        if progress:
            progress.advance(1)


def _estimate_audio_pair(
    reference: Path,
    comparison: Path,
    *,
    config: AlignmentConfig,
    fps_reference: Fraction,
    reference_stream_loader: Callable[[], alignment_audio.AudioStreamInfo] | None = None,
    reference_request: AlignmentClipRequest | None = None,
    comparison_request: AlignmentClipRequest | None = None,
    comparison_ordinal: int = 1,
) -> alignment_consensus.AlignmentConsensus:
    reference_stream = (
        reference_stream_loader()
        if reference_stream_loader is not None
        else alignment_audio.select_reference_audio_stream(
            reference,
            stream_override=config.reference_stream,
        )
    )
    comparison_stream = alignment_audio.select_matching_audio_stream(
        comparison,
        reference_stream=reference_stream,
        stream_override=config.comparison_streams.get(comparison.stem),
    )
    plan = alignment_audio.plan_audio_analysis(
        reference_stream,
        comparison_stream,
        config=config,
    )
    if isinstance(plan, alignment_audio.AudioAnalysisBudgetExceeded):
        if plan.reason.startswith("selected_audio_timeline_"):
            consensus = alignment_consensus.rejected_analysis(
                plan.reason,
                config=config,
                fps=fps_reference,
            )
        else:
            consensus = alignment_consensus.analysis_budget_exceeded(
                config=config,
                fps=fps_reference,
            )
    else:
        consensus = alignment_consensus.estimate_planned_consensus_offset(
            plan=plan,
            config=config,
            fps=fps_reference,
            analysis_window_loader=lambda spec: alignment_audio.extract_planned_window(
                reference,
                comparison,
                reference_stream,
                comparison_stream,
                plan,
                spec,
                channel_strategy=config.channel_strategy,
            ),
            scoring_window_loader=lambda spec, offset: (
                alignment_audio.extract_aligned_scoring_window(
                    reference,
                    comparison,
                    reference_stream,
                    comparison_stream,
                    plan,
                    spec,
                    global_analysis_offset=offset,
                    channel_strategy=config.channel_strategy,
                )
            ),
        )
    if reference_request is None or comparison_request is None:
        return consensus
    attempt = _build_audio_attempt(
        reference=reference_request,
        comparison=comparison_request,
        comparison_ordinal=comparison_ordinal,
        reference_stream=reference_stream,
        comparison_stream=comparison_stream,
        plan=plan,
        consensus=consensus,
        config=config,
        fps_reference=fps_reference,
    )
    return replace(consensus, audio_attempt=attempt)


def _compute_missing_alignments_with_provenance(
    *,
    reference: AlignmentClipRequest,
    requested_comparisons: list[AlignmentClipRequest],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
    progress_descriptions: dict[Path, str],
    comparison_ordinals: dict[Path, int],
) -> None:
    _compute_missing_alignments(
        reference=reference,
        requested_comparisons=requested_comparisons,
        config=config,
        results_map=results_map,
        fps_reference=fps_reference,
        progress=progress,
        progress_descriptions=progress_descriptions,
        comparison_ordinals=comparison_ordinals,
    )
    for comparison in requested_comparisons:
        key = _alignment_key(reference.path, comparison.path)
        result = results_map[key]
        provenances[key] = AlignmentProvenance(
            result=result,
            comparison_cache_key=comparison_cache_key(comparison),
            provenance="computed_this_run",
            evidence_availability=(
                "current_attempt"
                if result.audio_attempt is not None
                else "historical_details_unavailable"
            ),
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


def _record_interactive_provenance(
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
            provenance="interactive_confirmed_this_run",
            computed_result=computed_result,
            evidence_availability=(
                "current_attempt"
                if result.audio_attempt is not None
                else "historical_details_unavailable"
            ),
        )


def _present_pre_review_evidence(
    *,
    request: AlignmentRequest,
    results_map: dict[str, AlignmentResult],
    config: AlignmentConfig,
    progress: ProgressReporter | None,
) -> None:
    if not (config.use_vsview or config.force_interactive):
        return
    lines: list[str] = []
    for ordinal, comparison in enumerate(request.comparisons, start=1):
        result = results_map[_alignment_key(request.reference.path, comparison.path)]
        attempt = result.audio_attempt
        if result.applied or attempt is None:
            continue
        decision = attempt.decision
        if decision.state == "provisional":
            candidate = decision.candidate
            if candidate is None:
                raise ValueError("provisional audio decision is missing its candidate")
            lines.append(
                f"Comparison {ordinal} - Audio alignment requires review. "
                f"Provisional candidate: {candidate.frame_offset:+d}f (not applied)."
            )
        else:
            lines.append(
                f"Comparison {ordinal} - No usable audio candidate. "
                "No automatic correction applied."
            )
        lines.append(f"Reason: {_safe_alignment_diagnostic(decision.primary_reason)}.")
    if not lines:
        return
    if progress is not None:
        progress.suspend()
    try:
        print("\n".join(lines), file=sys.stderr)
    finally:
        if progress is not None:
            progress.resume()


def _write_run_diagnostics(
    *,
    request: AlignmentRequest,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    review_outcome: AlignmentReviewOutcome,
    only_keys: set[str] | None = None,
    confirmed_frame_pairs: tuple[tuple[str, int, int], ...] = (),
) -> set[str]:
    diagnostics_dir = request.alignment_diagnostics_dir
    diagnostics_root = request.alignment_diagnostics_root
    if diagnostics_dir is None or diagnostics_root is None:
        return set()
    written: set[str] = set()
    frame_pairs_by_key = {
        key: (reference_frame, comparison_frame)
        for key, reference_frame, comparison_frame in confirmed_frame_pairs
    }
    for ordinal, comparison in enumerate(request.comparisons, start=1):
        key = _alignment_key(request.reference.path, comparison.path)
        if only_keys is not None and key not in only_keys:
            continue
        result = results_map[key]
        provenance = provenances[key]
        try:
            write_alignment_diagnostic(
                generated_root=diagnostics_root,
                diagnostics_dir=diagnostics_dir,
                comparison_ordinal=ordinal,
                reference_label=request.reference.label,
                comparison_label=comparison.label,
                attempt=result.audio_attempt,
                evidence_availability=provenance.evidence_availability,
                review_outcome=review_outcome,
                final_result=result,
                final_origin=provenance.provenance,
                confirmed_frame_pair=frame_pairs_by_key.get(key),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            log.warning(
                "alignment_diagnostic_write_failed",
                comparison_ordinal=ordinal,
                exception_type=type(exc).__name__,
            )
            continue
        written.add(key)
    if written:
        log.info("alignment_diagnostics_written", path="alignment_diagnostics/")
    return written


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
            fps_reference = alignment_audio.probe_fps(reference)
        _compute_missing_alignments_with_provenance(
            reference=request.reference,
            requested_comparisons=requested_comparisons,
            config=config,
            results_map=results_map,
            provenances=provenances,
            fps_reference=fps_reference,
            progress=progress,
            progress_descriptions=_request_progress_descriptions(request),
            comparison_ordinals={
                comparison.path: ordinal
                for ordinal, comparison in enumerate(request.comparisons, start=1)
            },
        )

    initial_outcome: AlignmentReviewOutcome = (
        "pending"
        if (config.use_vsview or config.force_interactive) and not completed_confirmed_reuse
        else "not_requested"
    )
    diagnostic_keys = _write_run_diagnostics(
        request=request,
        results_map=results_map,
        provenances=provenances,
        review_outcome=initial_outcome,
    )
    if completed_confirmed_reuse and not requested_comparisons:
        return [
            results_map[_alignment_key(reference, comparison.path)]
            for comparison in request.comparisons
        ]

    _present_pre_review_evidence(
        request=request,
        results_map=results_map,
        config=config,
        progress=progress,
    )
    offsets_by_key = _build_offsets_map(
        reference=reference,
        comparisons=comparisons,
        results_map=results_map,
    )
    review = maybe_launch_alignment_vsview(
        reference=request.reference,
        comparisons=request.comparisons,
        offsets_by_key=offsets_by_key,
        cache_dir=request.generated_dir,
        config=config,
        progress=progress,
        frame_props_by_stem=frame_props_by_stem,
        verbose=verbose,
    )
    confirmed_offsets = review.confirmed_offsets
    fps_reference = _apply_confirmed_vsview_offsets(
        reference=reference,
        comparisons=comparisons,
        confirmed_offsets_by_key=confirmed_offsets,
        results_map=results_map,
        fps_reference=fps_reference,
    )
    _record_interactive_provenance(
        request=request,
        confirmed_offsets_by_key=confirmed_offsets,
        results_map=results_map,
        provenances=provenances,
    )

    if initial_outcome == "pending":
        _write_run_diagnostics(
            request=request,
            results_map=results_map,
            provenances=provenances,
            review_outcome=review.review_outcome,
            only_keys=diagnostic_keys,
            confirmed_frame_pairs=review.confirmed_frame_pairs,
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
