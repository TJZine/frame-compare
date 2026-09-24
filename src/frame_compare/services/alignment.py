"""Audio alignment service using cross-correlation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path

import structlog
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
from frame_compare.services.errors import (
    AudioAlignmentCleanupError,
    AudioAlignmentError,
    raise_if_alignment_cancelled,
)
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
    AlignmentReviewSummary,
    AudioAlignmentAttempt,
)
from frame_compare.utils.progress import RichProgressReporter
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal_theme import (
    ACCENT,
    BORDER_NEUTRAL,
    BORDER_PENDING,
    MUTED,
    OK,
    VALUE,
    WARN,
    glyphs_for_console,
    human_console,
)
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

log = structlog.get_logger()

_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"
_CHANNEL_FALLBACK_ACTIVITY = (
    "Checking individual audio channels for a review hint. Any hint will need visual confirmation."
)

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


def _build_audio_review_map(
    *,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
) -> dict[str, str]:
    payloads: dict[str, str] = {}
    for comparison in comparisons:
        key = _alignment_key(reference, comparison)
        result = results_map[key]
        provenance = provenances[key]
        payload = {
            "current_authority": {
                "origin": provenance.provenance if result.applied else "none",
                "frame_offset": result.frame_offset if result.applied else None,
            },
            "evidence_availability": provenance.evidence_availability,
            "audio_attempt": asdict(result.audio_attempt)
            if result.audio_attempt is not None
            else None,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > 128 * 1024:
            raise AudioAlignmentError("Native alignment-review audio evidence exceeds 128 KiB.")
        payloads[key] = encoded
    return payloads


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


def _source_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _request_identity_matches(path: Path, request: AlignmentClipRequest) -> bool:
    try:
        return path.resolve() == request.identity.path.resolve() and _source_identity(path) == (
            request.identity.size_bytes,
            request.identity.mtime_ns,
        )
    except OSError:
        return False


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
    window_records = consensus.window_records
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
        windows=window_records,
        decision=consensus.decision,
        stability=consensus.stability,
        collection_observation="observed" if consensus.collection_summaries else "not_observed",
        collection_summaries=consensus.collection_summaries,
        channel_corroboration=consensus.channel_corroboration,
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
    on_comparison_started: Callable[[AlignmentClipRequest], None] | None = None,
    on_channel_fallback_started: Callable[[AlignmentClipRequest], None] | None = None,
    cancellation: threading.Event | None = None,
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
        raise_if_alignment_cancelled(cancellation)
        comparison_ordinal = (comparison_ordinals or {}).get(comp.path, fallback_ordinal)
        if progress:
            progress.set_description(descriptions.get(comp.path, f"ALIGN | {comp.path.name}"))
        if on_comparison_started is not None:
            on_comparison_started(comp)

        def report_channel_fallback_started(
            comparison: AlignmentClipRequest = comp,
        ) -> None:
            if on_channel_fallback_started is not None:
                on_channel_fallback_started(comparison)

        estimate = alignment_consensus.hold_automatic_consensus(
            _estimate_audio_pair(
                reference.path,
                comp.path,
                config=config,
                fps_reference=fps_reference,
                reference_stream_loader=load_reference_stream,
                reference_request=reference,
                comparison_request=comp,
                comparison_ordinal=comparison_ordinal,
                cancellation=cancellation,
                on_channel_fallback_started=(
                    report_channel_fallback_started
                    if on_channel_fallback_started is not None
                    else None
                ),
            )
        )
        raise_if_alignment_cancelled(cancellation)
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
    on_channel_fallback_started: Callable[[], None] | None = None,
    cancellation: threading.Event | None = None,
) -> alignment_consensus.AlignmentConsensus:
    raise_if_alignment_cancelled(cancellation)
    if (
        reference_request is not None
        and not _request_identity_matches(reference, reference_request)
    ) or (
        comparison_request is not None
        and not _request_identity_matches(comparison, comparison_request)
    ):
        return alignment_consensus.rejected_analysis(
            "source_identity_changed",
            config=config,
            fps=fps_reference,
        )
    frozen_identities = (_source_identity(reference), _source_identity(comparison))

    def check_identities() -> None:
        try:
            current_identities = (_source_identity(reference), _source_identity(comparison))
        except OSError as exc:
            raise AudioAlignmentError(
                "source identity changed during staged audio collection",
                category="source_identity_changed",
                stage="collection",
            ) from exc
        if frozen_identities != current_identities:
            raise AudioAlignmentError(
                "source identity changed during staged audio collection",
                category="source_identity_changed",
                stage="collection",
            )

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

        def load_discovery() -> alignment_audio.CollectedAudioPhase:
            check_identities()
            phase = alignment_audio.collect_discovery_phase(
                reference,
                comparison,
                reference_stream,
                comparison_stream,
                plan,
                channel_strategy=config.channel_strategy,
                cancellation=cancellation,
            )
            try:
                check_identities()
            except AudioAlignmentError as exc:
                exc.collection_summaries = phase.summaries
                raise
            return phase

        def build_verification_specs(
            offsets: tuple[tuple[int, Fraction], ...],
        ) -> tuple[alignment_audio.AudioVerificationSpec, ...]:
            return alignment_audio.verification_specs(
                plan,
                offsets,
                reference_stream=reference_stream,
                comparison_stream=comparison_stream,
                max_offset_seconds=config.max_offset_seconds,
            )

        def load_verification(
            specs: tuple[alignment_audio.AudioVerificationSpec, ...],
        ) -> alignment_audio.CollectedAudioPhase:
            check_identities()
            phase = alignment_audio.collect_verification_phase(
                reference,
                comparison,
                reference_stream,
                comparison_stream,
                plan,
                specs,
                channel_strategy=config.channel_strategy,
                cancellation=cancellation,
            )
            try:
                check_identities()
            except AudioAlignmentError as exc:
                exc.collection_summaries = phase.summaries
                raise
            return phase

        consensus = alignment_consensus.estimate_staged_consensus_offset(
            plan=plan,
            config=config,
            fps=fps_reference,
            discovery_phase_loader=load_discovery,
            verification_phase_loader=load_verification,
            verification_spec_builder=build_verification_specs,
            cancellation=cancellation,
        )
        eligible_indices = alignment_consensus.channel_corroboration_window_indices(consensus)
        views = (
            alignment_audio.common_named_channel_views(reference_stream, comparison_stream)
            if config.channel_strategy == "mono_downmix"
            else ()
        )
        channel_plan = alignment_audio.plan_channel_view_corroboration(
            plan,
            eligible_indices,
            views=views,
        )
        if isinstance(channel_plan, alignment_audio.AudioChannelViewPlan):
            if on_channel_fallback_started is not None:
                on_channel_fallback_started()

            def load_channel_view(
                view: alignment_audio.AudioChannelView,
            ) -> alignment_audio.CollectedAudioPhase:
                check_identities()
                phase = alignment_audio.collect_channel_view_phase(
                    reference,
                    comparison,
                    reference_stream,
                    comparison_stream,
                    channel_plan,
                    view,
                    sample_rate=config.sample_rate,
                    cancellation=cancellation,
                )
                try:
                    check_identities()
                except AudioAlignmentError as exc:
                    exc.collection_summaries = phase.summaries
                    raise
                return phase

            consensus = alignment_consensus.corroborate_channel_views(
                consensus,
                plan=plan,
                channel_plan=channel_plan,
                config=config,
                fps=fps_reference,
                phase_loader=load_channel_view,
                cancellation=cancellation,
            )
    consensus = alignment_consensus.hold_automatic_consensus(consensus)
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
    on_comparison_started: Callable[[AlignmentClipRequest], None] | None = None,
    on_channel_fallback_started: Callable[[AlignmentClipRequest], None] | None = None,
    cancellation: threading.Event | None = None,
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
        on_comparison_started=on_comparison_started,
        on_channel_fallback_started=on_channel_fallback_started,
        cancellation=cancellation,
    )
    raise_if_alignment_cancelled(cancellation)
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


def _compute_requested_alignments(
    *,
    request: AlignmentRequest,
    requested_comparisons: list[AlignmentClipRequest],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    fps_reference: Fraction | None,
    on_comparison_started: Callable[[AlignmentClipRequest], None] | None,
    on_channel_fallback_started: Callable[[AlignmentClipRequest], None] | None,
    cancellation: threading.Event,
) -> Fraction:
    """Run only blocking probe, collection, and numeric work in the owned worker."""
    raise_if_alignment_cancelled(cancellation)
    resolved_fps = fps_reference or alignment_audio.probe_fps(request.reference.path)
    _compute_missing_alignments_with_provenance(
        reference=request.reference,
        requested_comparisons=requested_comparisons,
        config=config,
        results_map=results_map,
        provenances=provenances,
        fps_reference=resolved_fps,
        progress=None,
        progress_descriptions={},
        comparison_ordinals={
            comparison.path: ordinal
            for ordinal, comparison in enumerate(request.comparisons, start=1)
        },
        on_comparison_started=on_comparison_started,
        on_channel_fallback_started=on_channel_fallback_started,
        cancellation=cancellation,
    )
    raise_if_alignment_cancelled(cancellation)
    return resolved_fps


async def _await_audio_computation(
    *,
    request: AlignmentRequest,
    requested_comparisons: list[AlignmentClipRequest],
    config: AlignmentConfig,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    fps_reference: Fraction | None,
    progress: ProgressReporter | None,
    quiet: bool,
    json_output: bool,
) -> Fraction:
    cancellation = threading.Event()
    loop = asyncio.get_running_loop()
    analysis_descriptions = _request_analysis_progress_descriptions(request)

    def report_comparison_started(comparison: AlignmentClipRequest) -> None:
        if progress is not None:
            loop.call_soon_threadsafe(
                progress.set_description,
                analysis_descriptions[comparison.path],
            )

    def report_channel_fallback_started(comparison: AlignmentClipRequest) -> None:
        if progress is not None and not quiet and not json_output:
            loop.call_soon_threadsafe(
                progress.set_description,
                f"{_request_progress_descriptions(request)[comparison.path]} | "
                f"{_CHANNEL_FALLBACK_ACTIVITY}",
            )

    worker = asyncio.create_task(
        asyncio.to_thread(
            _compute_requested_alignments,
            request=request,
            requested_comparisons=requested_comparisons,
            config=config,
            results_map=results_map,
            provenances=provenances,
            fps_reference=fps_reference,
            on_comparison_started=report_comparison_started,
            on_channel_fallback_started=(
                report_channel_fallback_started
                if progress is not None and not quiet and not json_output
                else None
            ),
            cancellation=cancellation,
        ),
        name="alignment-audio-computation",
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancelled:
        cancellation.set()
        while not worker.done():
            with suppress(asyncio.CancelledError):
                await asyncio.wait((worker,))
        # Cancellation outranks ordinary worker failures, but never hides a failed
        # release of an owned child, reader, pipe, or handle.
        error = None if worker.cancelled() else worker.exception()
        if isinstance(error, AudioAlignmentCleanupError):
            raise error from cancelled
        raise


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
    provenances: dict[str, AlignmentProvenance],
    cached_audio_evidence_only: bool = False,
) -> None:
    progress_descriptions = _request_progress_descriptions(request)
    comparisons = request.comparisons
    if cached_audio_evidence_only:
        comparisons = [
            comparison
            for comparison in request.comparisons
            if (
                provenance := provenances.get(
                    _alignment_key(request.reference.path, comparison.path)
                )
            )
            is not None
            and provenance.provenance == "shared_computed_offsets"
        ]
    for comparison in request.comparisons:
        key = _alignment_key(request.reference.path, comparison.path)
        provenance = provenances.get(key)
        if provenance is not None and provenance.provenance == "shared_computed_offsets":
            progress_descriptions[comparison.path] = progress_descriptions[comparison.path].replace(
                "ALIGN | ", "ALIGN | Using cached audio evidence | ", 1
            )
    _record_resolved_alignment_progress(
        progress=progress,
        reference=request.reference.path,
        comparisons=[comparison.path for comparison in comparisons],
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


def _request_analysis_progress_descriptions(request: AlignmentRequest) -> dict[Path, str]:
    return {
        path: description.replace("ALIGN | ", "ALIGN | Analyzing audio | ", 1)
        for path, description in _request_progress_descriptions(request).items()
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


def _format_stream_summary(attempt: AudioAlignmentAttempt) -> str:
    reference, comparison = attempt.selected_streams
    reference_method = (
        "explicit override"
        if reference.selection_method == "explicit_override"
        else "automatic metadata selection"
    )
    comparison_method = (
        "explicit override"
        if comparison.selection_method == "explicit_override"
        else "automatic metadata selection"
    )
    methods = (
        reference_method
        if reference_method == comparison_method
        else f"Reference {reference_method}; Comparison {comparison_method}"
    )
    return (
        f"Streams: Reference a:{reference.audio_stream_index} -> "
        f"Comparison a:{comparison.audio_stream_index} ({methods})."
    )


def _normal_evidence_lines(
    *, ordinal: int, result: AlignmentResult, provenance: AlignmentProvenance
) -> list[str]:
    prefix = f"Comparison {ordinal} - "
    offset = result.frame_offset
    if result.applied and offset is not None:
        if provenance.provenance == "shared_computed_offsets":
            heading = "Accepted audio alignment reused"
            detail = (
                "Historical window and selected-stream details are unavailable; "
                "no audio analysis ran this time."
            )
        elif provenance.provenance == "shared_previous_offsets":
            heading = "Manually confirmed alignment reused"
            detail = (
                "Historical audio details are unavailable."
                if result.audio_attempt is None
                else None
            )
        elif result.source == "manual" or provenance.provenance in {
            "interactive_confirmed_this_run",
            "preexisting_manual_override",
        }:
            heading = "Manually confirmed alignment"
            detail = (
                "Historical audio details are unavailable."
                if result.audio_attempt is None
                else None
            )
        else:
            heading = "Audio alignment accepted"
            detail = None
        lines = [
            f"{prefix}{heading}: {offset:+d}f - APPLIED",
            "No additional confirmation needed.",
        ]
        if detail is not None:
            lines.append(detail)
        return lines

    attempt = result.audio_attempt
    decision = attempt.decision if attempt is not None else None
    candidate = decision.candidate if decision is not None else None
    if (
        attempt is not None
        and decision is not None
        and decision.state == "provisional"
        and candidate is not None
    ):
        lines = [
            f"{prefix}Provisional audio candidate: {candidate.frame_offset:+d}f - NOT APPLIED",
            "Visual confirmation required to use this hint. Align manually or keep the current alignment.",
        ]
        if decision.primary_reason == alignment_consensus.AUTOMATIC_AUTHORITY_HOLD_REASON:
            lines[0:0] = [
                "Audio alignment automatic application is temporarily disabled.",
                "Audio evidence is available for manual review; no computed correction was applied.",
            ]
            stability_scope = _stability_scope_line(attempt)
            if stability_scope is not None:
                lines.append(stability_scope)
        return lines

    lines = [
        f"{prefix}No usable audio candidate - NOT APPLIED",
        "Align manually or keep the current alignment.",
    ]
    if (
        attempt is not None
        and decision is not None
        and decision.primary_reason == alignment_consensus.AUTOMATIC_AUTHORITY_HOLD_REASON
    ):
        lines[0:0] = [
            "Audio alignment automatic application is temporarily disabled.",
            "Audio evidence is available for manual review; no computed correction was applied.",
        ]
        stability_scope = _stability_scope_line(attempt)
        if stability_scope is not None:
            lines.append(stability_scope)
    return lines


def _original_audio_attempt_line(attempt: AudioAlignmentAttempt) -> str:
    decision = attempt.decision
    candidate = decision.candidate
    if decision.state == "trusted_automatic" and candidate is not None:
        return f"Original audio attempt: Audio alignment accepted: {candidate.frame_offset:+d}f - APPLIED"
    if decision.state == "provisional" and candidate is not None:
        return f"Original audio attempt: Provisional audio candidate: {candidate.frame_offset:+d}f - NOT APPLIED"
    return "Original audio attempt: No usable audio candidate - NOT APPLIED"


def _stability_scope_line(attempt: AudioAlignmentAttempt) -> str | None:
    stability = attempt.stability
    if stability is None:
        return None
    scope = f"{stability.valid_windows}/{attempt.planned_window_count} qualified observed windows"
    if stability.valid_windows < attempt.planned_window_count:
        scope += "; rejected or unobserved planned intervals remain unassessed"
    return (
        f"Stability: {stability.classification.replace('_', ' ')}; "
        f"scoped to {scope} (diagnostic only)."
    )


def _alignment_evidence_row(line: str, *, waiting_glyph: str = "›") -> tuple[str, str, str]:
    """Return the key, value, and style for one interactive evidence row."""
    stripped = line.strip()
    if stripped.startswith("Comparison ") and " - " in stripped:
        _comparison, value = stripped.split(" - ", 1)
        if "not applied" in value.lower():
            return "  status", value, WARN
        if "applied" in value.lower():
            return "  status", value, OK
        return "  status", value, VALUE
    prefixes = {
        "Reason: ": "  reason",
        "Streams: ": "  streams",
        "Runtime/policy: ": "  runtime",
        "Thresholds: ": "  thresholds",
        "Decision: ": "  decision",
        "Evidence: ": "  evidence",
        "Work: ": "  work",
    }
    for prefix, key in prefixes.items():
        if stripped.startswith(prefix):
            return key, stripped.removeprefix(prefix), VALUE
    if stripped.startswith("Audio alignment automatic application"):
        return "  authority", stripped, WARN
    if stripped.startswith(("Audio evidence", "Continuing without")):
        return "  outcome", stripped, WARN
    if "correlated windows agree" in stripped or "windows planned" in stripped:
        return "  evidence", stripped, VALUE
    if stripped.startswith("Opening VSView"):
        return "  review", f"{waiting_glyph} {stripped}", ACCENT
    if stripped.startswith("Audio diagnostics: "):
        return "diagnostics", stripped.removeprefix("Audio diagnostics: "), VALUE
    if "warning" in stripped.lower() or "not applied" in stripped.lower():
        return "  warning", stripped, WARN
    return "  detail", stripped, MUTED


def _render_alignment_evidence_panel(
    *,
    entries: list[tuple[str, list[str]]],
    diagnostics_written: bool,
    no_color: bool,
    actionable: bool,
    needs_review_count: int = 0,
) -> None:
    table = Table(
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=True,
    )
    table.add_column("key", style="dim", no_wrap=True, min_width=14, overflow="fold")
    table.add_column("value", overflow="fold")
    console = human_console(stderr=True, no_color=no_color, height=1000)
    waiting_glyph = glyphs_for_console(console).waiting
    for index, (comparison_name, lines) in enumerate(entries):
        if index:
            table.add_row("", "")
        table.add_row("comparison", f"[bold]{escape(comparison_name)}[/]")
        for line in lines:
            key, value, style = _alignment_evidence_row(line, waiting_glyph=waiting_glyph)
            if style:
                table.add_row(key, f"[{style}]{escape(value)}[/]")
            else:
                table.add_row(key, escape(value))
    if diagnostics_written:
        table.add_row("", "")
        table.add_row("diagnostics", "alignment_diagnostics/")

    title = f"[bold {ACCENT}]Audio alignment[/]"
    if actionable:
        title += f" [dim]· {needs_review_count} needs review[/]"
    console.print(
        Padding(
            Panel(
                table,
                title=title,
                border_style=BORDER_PENDING if actionable else BORDER_NEUTRAL,
            ),
            (0, 0, 0, 2),
        ),
        crop=False,
    )


def _verbose_evidence_lines(attempt: AudioAlignmentAttempt) -> list[str]:
    decision = attempt.decision
    lines = [
        _original_audio_attempt_line(attempt),
        f"  Runtime/policy: {attempt.media_runtime_fingerprint}; {attempt.estimator_policy}; "
        f"diagnostic={attempt.diagnostic_policy}",
        f"  Thresholds: score={attempt.confidence_threshold}; peak={attempt.ambiguity_peak_ratio}; "
        f"minimum windows={attempt.minimum_valid_windows}; consensus={attempt.consensus_minimum_ratio}",
        f"  Decision: state={decision.state}; reason={decision.primary_reason}; "
        f"failed={','.join(decision.failed_gates) or 'none'}; "
        f"unassessed={','.join(decision.unassessed_gates) or 'none'}",
        f"  Evidence: raw={decision.raw_correlated_windows}; credible={decision.credible_windows}; "
        f"voting={decision.voting_windows}; winning={decision.winning_windows}; "
        f"independent={decision.independent_windows}; ratio={decision.consensus_ratio}; "
        f"score={decision.aggregate_score}; peak={decision.minimum_peak_ratio}",
        f"  Work: planned={attempt.planned_window_count}; analysis rate={attempt.analysis_rate}; "
        f"FFT peak/total={attempt.peak_fft_points}/{attempt.total_fft_points}; "
        f"planning={attempt.planning_reason or 'complete'}",
    ]
    stability_scope = _stability_scope_line(attempt)
    if stability_scope is not None:
        lines.append(stability_scope)
    lines.extend(
        [
            _format_stream_summary(attempt),
            "  Audio details:",
        ]
    )
    for stream in attempt.selected_streams:
        lines.append(
            f"    {stream.role}: a:{stream.audio_stream_index} (absolute {stream.absolute_stream_index}), "
            f"codec={stream.codec_name or 'unknown'}, language={stream.language or 'unknown'}, "
            f"channels={stream.channels or 'unknown'}/{stream.channel_layout or 'unknown'}, "
            f"rate={stream.sample_rate or 'unknown'}, selection={stream.selection_method}, "
            f"rank={stream.selection_rank}, start={stream.stream_start_num}/{stream.stream_start_den} "
            f"({stream.stream_start_basis}), input={stream.input_start_num}/{stream.input_start_den} "
            f"({stream.input_start_basis}), duration={stream.duration_num}/{stream.duration_den} "
            f"({stream.duration_basis}), language-match={stream.language_match}, "
            f"commentary-match={stream.commentary_match}"
        )
    for window in attempt.windows:
        peak = window.peak_ratio if window.peak_ratio is not None else "unknown"
        lines.append(
            f"    {window.logical_id}: ref={window.planned_reference_start}+{window.planned_reference_count}, "
            f"cmp={window.planned_comparison_start}+{window.planned_comparison_count}, "
            f"actual={window.actual_reference_count}/{window.actual_comparison_count}, "
            f"scoring={window.scoring_reference_count}/{window.scoring_comparison_count}, "
            f"overlap={window.effective_aligned_overlap}, origin={window.origin_basis}, "
            f"rates={window.analysis_rate}/{window.requested_rate}, "
            f"lag={window.local_lag}/{window.global_analysis_lag}/{window.requested_sample_lag}, "
            f"frame={window.requested_frame_candidate}, score={window.requested_score} "
            f"({window.score_stage}), peak={peak} ({window.peak_stage}@{window.peak_rate}), "
            f"quality={window.configured_quality}, vote={window.vote_disposition}, "
            f"review={window.review_qualified}, result={window.terminal_stage}/"
            f"{window.terminal_category}, relation={window.purpose}/"
            f"{window.parent_id or 'root'}"
        )
    _reference, comparison = attempt.selected_streams
    mismatches: list[str] = []
    if comparison.language_match == "mismatch":
        mismatches.append("language")
    if comparison.commentary_match == "mismatch":
        mismatches.append("commentary")
    if mismatches:
        lines.append(
            f"Selected audio metadata differs ({'/'.join(mismatches)}); "
            "matching content is not established."
        )
    channel = attempt.channel_corroboration
    if channel is not None:
        lines.append(
            f"  Channel-view evidence: status={channel.status}; reason={channel.reason}; "
            f"independent={channel.independent_windows}; collections={len(channel.collections)}"
        )
        for window in channel.windows:
            lines.append(
                f"    {window.logical_id}/channel: corroborated={window.corroborated}; "
                f"representative={window.representative_sample_lag}/"
                f"{window.representative_frame_candidate}; agreeing={window.agreeing_views}; "
                f"score={window.minimum_credible_score}; peak={window.minimum_peak_ratio}; "
                f"contradiction={window.contradiction}; reason={window.reason}"
            )
    return lines


def _print_pre_review_summary(
    *,
    request: AlignmentRequest,
    results_map: dict[str, AlignmentResult],
    progress: ProgressReporter | None,
    no_color: bool,
) -> None:
    """Print the Rich-only Align summary line before native review."""
    if not isinstance(progress, RichProgressReporter):
        return
    states: list[tuple[str, bool]] = []
    for comparison in request.comparisons:
        key = _alignment_key(request.reference.path, comparison.path)
        result = results_map[key]
        short = comparison.short_name or comparison.label or comparison.path.name
        states.append((short, result.applied))
    actionable = any(not applied for _, applied in states)
    console = human_console(stderr=True, no_color=no_color)
    glyphs = glyphs_for_console(console)
    if actionable:
        glyph, style = glyphs.warning, WARN
    else:
        glyph, style = glyphs.ok, OK
    line = Text.assemble((glyph, style), f" {'Align':<9} ")
    for index, (short, applied) in enumerate(states):
        if index:
            line.append(" · ", style="dim")
        if applied:
            line.append(f"{short} audio applied")
        else:
            line.append(f"{short} needs visual confirmation", style=WARN)
    progress.suspend()
    try:
        console.print(line)
    finally:
        progress.resume()


def _present_alignment_evidence(
    *,
    request: AlignmentRequest,
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
    config: AlignmentConfig,
    progress: ProgressReporter | None,
    verbose: bool,
    quiet: bool,
    json_output: bool,
    diagnostics_written: bool,
) -> None:
    lines: list[str] = []
    entries: list[tuple[str, list[str]]] = []
    has_actionable_result = False
    needs_review_count = 0
    for ordinal, comparison in enumerate(request.comparisons, start=1):
        key = _alignment_key(request.reference.path, comparison.path)
        result = results_map[key]
        provenance = provenances[key]
        decision = result.audio_attempt.decision if result.audio_attempt is not None else None
        human_actionable = not result.applied
        json_actionable = human_actionable or (
            decision is not None and decision.state != "trusted_automatic"
        )
        has_actionable_result = has_actionable_result or human_actionable
        if json_output:
            if json_actionable:
                log.warning(
                    "audio_alignment_requires_review",
                    comparison_ordinal=ordinal,
                    decision_state=decision.state if decision is not None else "unavailable",
                    candidate_frame=(
                        decision.candidate.frame_offset
                        if decision is not None and decision.candidate is not None
                        else None
                    ),
                    reason=(decision.primary_reason if decision is not None else result.diagnostic),
                )
            continue
        if quiet and not human_actionable:
            continue
        comparison_lines = _normal_evidence_lines(
            ordinal=ordinal,
            result=result,
            provenance=provenance,
        )
        if verbose and not quiet and result.audio_attempt is not None:
            comparison_lines.extend(_verbose_evidence_lines(result.audio_attempt))
        if human_actionable and (config.use_vsview or config.force_interactive):
            if decision is not None and decision.candidate is not None:
                comparison_lines.append(
                    "Opening VSView for manual review. The candidate is a hint, not a "
                    "confirmed alignment."
                )
            else:
                comparison_lines.append(
                    "Opening VSView for manual review. No automatic candidate is available; "
                    "align the sources manually."
                )
        lines.extend(comparison_lines)
        if human_actionable:
            needs_review_count += 1
        entries.append(
            (
                comparison.compact_name
                or comparison.presentation_name
                or comparison.label
                or comparison.path.name,
                comparison_lines,
            )
        )
    if diagnostics_written and not quiet and not json_output:
        lines.append("Audio diagnostics: alignment_diagnostics/.")
    if not lines:
        return
    if progress is not None:
        progress.suspend()
    try:
        if isinstance(progress, RichProgressReporter):
            _render_alignment_evidence_panel(
                entries=entries,
                diagnostics_written=diagnostics_written,
                no_color=config.no_color,
                actionable=has_actionable_result,
                needs_review_count=needs_review_count,
            )
        else:
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
    emit_success_log: bool,
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
    if written and emit_success_log:
        log.info("alignment_diagnostics_written", path="alignment_diagnostics/")
    return written


async def align_clips_from_request(
    request: AlignmentRequest,
    config: AlignmentConfig,
    progress: ProgressReporter | None = None,
    reference_fps: Fraction | None = None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    verbose: bool = False,
    quiet: bool = False,
    json_output: bool = False,
    review_summary: AlignmentReviewSummary | None = None,
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
            provenances=provenances,
        )
        fps_reference = await _await_audio_computation(
            request=request,
            requested_comparisons=requested_comparisons,
            config=config,
            results_map=results_map,
            provenances=provenances,
            fps_reference=fps_reference,
            progress=progress,
            quiet=quiet,
            json_output=json_output,
        )
        descriptions = _request_progress_descriptions(request)
        for comparison in requested_comparisons:
            _record_alignment_progress(
                progress=progress,
                result=results_map[_alignment_key(reference, comparison.path)],
                description=descriptions[comparison.path],
            )
    else:
        _record_resolved_alignment_request_progress(
            progress=progress,
            request=request,
            results_map=results_map,
            provenances=provenances,
            cached_audio_evidence_only=True,
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
        emit_success_log=json_output,
    )
    if initial_outcome == "pending" and not quiet and not json_output:
        _print_pre_review_summary(
            request=request,
            results_map=results_map,
            progress=progress,
            no_color=config.no_color,
        )
    _present_alignment_evidence(
        request=request,
        results_map=results_map,
        provenances=provenances,
        config=config,
        progress=progress,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
        diagnostics_written=bool(diagnostic_keys),
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
    audio_review_by_key = _build_audio_review_map(
        reference=reference,
        comparisons=comparisons,
        results_map=results_map,
        provenances=provenances,
    )
    review = maybe_launch_alignment_vsview(
        reference=request.reference,
        comparisons=request.comparisons,
        offsets_by_key=offsets_by_key,
        audio_review_by_key=audio_review_by_key,
        cache_dir=request.generated_dir,
        config=config,
        progress=progress,
        frame_props_by_stem=frame_props_by_stem,
        verbose=verbose,
        review_summary=review_summary,
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
            emit_success_log=json_output,
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
