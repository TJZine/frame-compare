"""Whole-track audio alignment service."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import partial
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, cast

import structlog

from frame_compare.services import alignment_audio, alignment_decision, alignment_video
from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkedCorrelation,
    ChunkPlan,
    plan_audio_chunks,
)
from frame_compare.services.alignment_decision import (
    ALIGNMENT_ESTIMATOR_POLICY,
    DecidedAudioStage,
)
from frame_compare.services.alignment_diagnostics import (
    AlignmentReviewOutcome,
    write_alignment_diagnostic,
)
from frame_compare.services.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    AudioAlignmentAttempt,
    AudioCollectionFacts,
    AudioCollectionFailure,
    AudioCollectionObservation,
    AudioPairSide,
    VideoCheckObservation,
    analysis_stream_start,
    audio_unavailable_phrase,
)
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_presentation import (
    panel_audio_review_lines,
    present_alignment_evidence,
)
from frame_compare.services.alignment_previous_offsets import (
    apply_shared_reuse,
    can_reuse_written_offsets_without_confirmation,
    prompt_for_previous_alignment_offset_reuse,
    validate_previous_offsets_policy,
)
from frame_compare.services.alignment_resolution import (
    confirm_manual,
    ordered_results,
    resolution_from_computation,
)
from frame_compare.services.alignment_reuse_cache import (
    comparison_cache_key,
    prepare_reusable_source_set,
    save_reusable_offsets,
)
from frame_compare.services.alignment_streaming import (
    CollectionCleanup,
    CollectionFacts,
    PairedAudioCollection,
    PairedAudioCollectionFailure,
    collect_paired_audio_chunks,
    paired_collection_timeout_seconds,
    paired_output_limit_samples,
)
from frame_compare.services.alignment_vsview import maybe_launch_alignment_vsview
from frame_compare.services.errors import (
    AudioAlignmentCancellationError,
    AudioAlignmentCleanupError,
    AudioAlignmentError,
    raise_if_alignment_cancelled,
)
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentOperationOutcome,
    AlignmentResult,
    ComparisonResolution,
)
from frame_compare.utils.cancellation import cancellation_checkpoint
from frame_compare.utils.progress import LogProgressReporter
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.types import AlignmentCacheSettings, AlignmentClipRequest, AlignmentRequest
from frame_compare.vs.runtime_contract import media_runtime_fingerprint

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader

log = structlog.get_logger()

_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"

__all__ = [
    "align_clips_from_request",
    "format_rejected_alignment_warning",
    "prompt_for_previous_alignment_offset_reuse",
]


def format_rejected_alignment_warning(
    result: AlignmentResult,
    *,
    comparison_label: str,
    comparison_path: Path,
) -> RunWarning:
    """Format a rejected computed alignment as a deterministic run warning."""
    reason = audio_unavailable_phrase(result.diagnostic or "no_usable_audio")
    return RunWarning(
        source="alignment",
        severity="warning",
        message=(
            f"{comparison_label}: alignment not applied ({reason}); "
            "frames use the reference's frame numbers."
        ),
        comparison_path=comparison_path,
    )


def _build_audio_review_map(
    *,
    reference: Path,
    comparisons: list[Path],
    resolutions: dict[str, ComparisonResolution],
) -> dict[str, str]:
    payloads: dict[str, str] = {}
    for comparison in comparisons:
        key = alignment_key(reference, comparison)
        resolution = resolutions[key]
        result = resolution.result
        attempt = result.audio_attempt
        decision = attempt.decision if attempt is not None else None
        candidate = decision.candidate if decision is not None else None
        summary_lines, detail_lines = panel_audio_review_lines(resolution)
        payload = {
            "current_authority": {
                "origin": resolution.origin if result.applied else "none",
                "frame_offset": result.frame_offset if result.applied else None,
            },
            "decision_state": decision.state if decision is not None else None,
            "candidate_offset": candidate.frame_offset if candidate is not None else None,
            "summary_lines": summary_lines,
            "detail_lines": detail_lines,
        }
        payloads[key] = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    return payloads


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


def _clip_identity_digest(clip: AlignmentClipRequest) -> str:
    identity = clip.identity
    payload = (f"{identity.path.resolve()}\0{identity.size_bytes}\0{identity.mtime_ns}").encode()
    return hashlib.sha256(payload).hexdigest()


def _computed_result(
    *,
    reference: Path,
    comparison: Path,
    decided: DecidedAudioStage,
    attempt: AudioAlignmentAttempt | None,
) -> AlignmentResult:
    """Build the computed result, applying only trusted automatic evidence."""
    candidate = decided.decision.candidate
    applied = decided.decision.state == "trusted_automatic"
    if applied and candidate is None:
        raise AudioAlignmentError("trusted automatic alignment is missing its candidate")
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=candidate.frame_offset if applied and candidate is not None else None,
        time_offset_seconds=(
            candidate.time_offset_seconds if applied and candidate is not None else None
        ),
        correlation_score=decided.correlation_score,
        algorithm="cross_correlation",
        source="computed",
        applied=applied,
        diagnostic=decided.decision.primary_reason,
        stability=decided.stability,
        audio_attempt=attempt,
    )


def _evidence_collection_facts(
    result: PairedAudioCollection | PairedAudioCollectionFailure,
) -> tuple[tuple[AudioCollectionFacts, AudioCollectionFacts], AudioCollectionFailure | None]:
    """Project U2 transport facts into evidence (no PCM, no stderr text).

    The failure category and side live once at pair level (m14), not per side.
    """
    failure = result if isinstance(result, PairedAudioCollectionFailure) else None

    def one(
        facts: CollectionFacts,
        cleanup: CollectionCleanup,
        role: AudioPairSide,
    ) -> AudioCollectionFacts:
        eof_sample = facts.emitted_sample_count if facts.returncode == 0 else None
        return AudioCollectionFacts(
            role=role,
            emitted_samples=facts.emitted_sample_count,
            eof_sample=eof_sample,
            elapsed_seconds=facts.elapsed_seconds,
            returncode=facts.returncode,
            stderr_bytes=facts.stderr_byte_count,
            stderr_truncated=facts.stderr_truncated,
            cleanup_completed=cleanup.completed,
        )

    pair_failure = (
        None
        if failure is None
        else AudioCollectionFailure(category=failure.category, side=failure.side)
    )
    return (
        (
            one(result.reference_facts, result.reference_cleanup, "reference"),
            one(result.comparison_facts, result.comparison_cleanup, "comparison"),
        ),
        pair_failure,
    )


def _selection_start_facts(
    selection: alignment_audio.AudioStreamSelection,
    *,
    timeline_scale: Fraction,
) -> tuple[Fraction, Fraction]:
    """Return the (audio start, video start) A5 facts for one selection."""
    return (
        analysis_stream_start(selection.stream.timeline.start_time, timeline_scale),
        analysis_stream_start(selection.video_start.start_time, timeline_scale),
    )


def _build_audio_attempt(
    *,
    reference: AlignmentClipRequest,
    comparison: AlignmentClipRequest,
    comparison_ordinal: int,
    reference_selection: alignment_audio.AudioStreamSelection,
    comparison_selection: alignment_audio.AudioStreamSelection,
    decided: DecidedAudioStage,
    fps_reference: Fraction,
    collection: tuple[AudioCollectionFacts, ...],
    collection_observation: AudioCollectionObservation,
    collection_failure: AudioCollectionFailure | None = None,
) -> AudioAlignmentAttempt:
    return AudioAlignmentAttempt(
        reference_identity_digest=_clip_identity_digest(reference),
        comparison_identity_digest=_clip_identity_digest(comparison),
        comparison_ordinal=comparison_ordinal,
        status=decided.attempt_status,
        estimator_policy=ALIGNMENT_ESTIMATOR_POLICY,
        diagnostic_policy=_DIAGNOSTIC_POLICY,
        media_runtime_fingerprint=media_runtime_fingerprint("alignment"),
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe=alignment_audio.normalized_extraction_recipe(),
        fps_num=fps_reference.numerator,
        fps_den=fps_reference.denominator,
        selected_streams=(
            alignment_audio.selected_stream_evidence(
                reference_selection.stream,
                role="reference",
                source_identity_digest=_clip_identity_digest(reference),
                explicit_override=reference.selected_audio_stream is not None,
                video_start=reference_selection.video_start,
                timeline_scale=reference.timeline_scale,
            ),
            alignment_audio.selected_stream_evidence(
                comparison_selection.stream,
                role="comparison",
                source_identity_digest=_clip_identity_digest(comparison),
                explicit_override=comparison.selected_audio_stream is not None,
                video_start=comparison_selection.video_start,
                timeline_scale=comparison.timeline_scale,
                reference_stream=reference_selection.stream,
            ),
        ),
        analysis=decided.analysis,
        chunks=decided.chunks,
        runs=decided.runs,
        audio=decided.audio,
        collection_observation=collection_observation,
        collection=collection,
        collection_failure=collection_failure,
        video_check=decided.video_check
        or VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        decision=decided.decision,
        stability=decided.stability,
        authority_recount=decided.authority_recount,
    )


def _video_clip_request(clip: AlignmentClipRequest) -> alignment_video.VideoClipRequest:
    values = (
        clip.active_rect_x,
        clip.active_rect_y,
        clip.active_rect_width,
        clip.active_rect_height,
    )
    active_rect = (
        cast(alignment_video.ActiveRect, values) if clip.active_rect_x is not None else None
    )
    return alignment_video.VideoClipRequest(
        path=clip.path,
        active_rect=active_rect,
    )


def _rejected_result(
    *,
    reference: Path,
    comparison: Path,
    cache_settings: AlignmentCacheSettings,
    reason: str,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int,
    fps_reference: Fraction,
    reference_selection: alignment_audio.AudioStreamSelection | None = None,
    comparison_selection: alignment_audio.AudioStreamSelection | None = None,
) -> AlignmentResult:
    """Build a preanalysis rejection, with an attempt when streams were selected."""
    if reference_selection is not None and comparison_selection is not None:
        reference_audio_start, reference_video_start = _selection_start_facts(
            reference_selection, timeline_scale=reference_request.timeline_scale
        )
        comparison_audio_start, comparison_video_start = _selection_start_facts(
            comparison_selection, timeline_scale=comparison_request.timeline_scale
        )
    else:
        reference_audio_start = reference_video_start = None
        comparison_audio_start = comparison_video_start = None
    decided = alignment_decision.decide_rejected_stage(
        max_offset_seconds=cache_settings.max_offset_seconds,
        reason=reason,
        reference_audio_start=reference_audio_start,
        reference_video_start=reference_video_start,
        comparison_audio_start=comparison_audio_start,
        comparison_video_start=comparison_video_start,
    )
    attempt: AudioAlignmentAttempt | None = None
    if reference_selection is not None and comparison_selection is not None:
        attempt = _build_audio_attempt(
            reference=reference_request,
            comparison=comparison_request,
            comparison_ordinal=comparison_ordinal,
            reference_selection=reference_selection,
            comparison_selection=comparison_selection,
            decided=decided,
            fps_reference=fps_reference,
            collection=(),
            collection_observation="not_observed",
        )
    return _computed_result(
        reference=reference,
        comparison=comparison,
        decided=decided,
        attempt=attempt,
    )


@dataclass(frozen=True)
class _PlannedAudioPair:
    """Pre-decode selection and plan for one comparison; collection has not run."""

    reference_selection: alignment_audio.AudioStreamSelection
    comparison_selection: alignment_audio.AudioStreamSelection
    plan: ChunkPlan
    total_timeout_seconds: float
    reference_limit_samples: int
    comparison_limit_samples: int


def _plan_audio_pair(
    reference: Path,
    comparison: Path,
    *,
    cache_settings: AlignmentCacheSettings,
    fps_reference: Fraction,
    reference_probe_loader: Callable[[], alignment_audio.ProbedStreams] | None,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int,
    cancellation: threading.Event | None,
) -> AlignmentResult | _PlannedAudioPair:
    """Select streams and plan chunks; return a rejection result or a plan."""
    raise_if_alignment_cancelled(cancellation)
    reference_probe = (
        reference_probe_loader()
        if reference_probe_loader is not None
        else alignment_audio.probe_streams(reference)
    )
    comparison_probe = alignment_audio.probe_streams(comparison)
    reference_selection, comparison_selection = alignment_audio.select_audio_pair(
        reference_probe,
        comparison_probe,
        reference_path=reference,
        comparison_path=comparison,
        reference_override=reference_request.selected_audio_stream,
        comparison_override=comparison_request.selected_audio_stream,
    )
    reference_selection = replace(
        reference_selection,
        stream=alignment_audio.measure_selected_audio_duration(
            reference,
            reference_selection.stream,
            video_start=reference_selection.video_start.start_time,
            video_seconds=Fraction(
                reference_request.source_frame_count * reference_request.source_fps_den,
                reference_request.source_fps_num,
            ),
            cancellation=cancellation,
        ),
    )
    comparison_selection = replace(
        comparison_selection,
        stream=alignment_audio.measure_selected_audio_duration(
            comparison,
            comparison_selection.stream,
            video_start=comparison_selection.video_start.start_time,
            video_seconds=Fraction(
                comparison_request.source_frame_count * comparison_request.source_fps_den,
                comparison_request.source_fps_num,
            ),
            cancellation=cancellation,
        ),
    )
    reference_duration = reference_selection.stream.timeline.duration
    comparison_duration = comparison_selection.stream.timeline.duration
    if reference_duration is None or comparison_duration is None:
        return _rejected_result(
            reference=reference,
            comparison=comparison,
            cache_settings=cache_settings,
            reason="selected_audio_timeline_unavailable",
            reference_request=reference_request,
            comparison_request=comparison_request,
            comparison_ordinal=comparison_ordinal,
            fps_reference=fps_reference,
            reference_selection=reference_selection,
            comparison_selection=comparison_selection,
        )
    reference_scale = reference_request.timeline_scale
    comparison_scale = comparison_request.timeline_scale
    reference_duration = reference_duration * reference_scale
    comparison_duration = comparison_duration * comparison_scale
    reference_samples = math.floor(reference_duration * AUDIO_ANALYSIS_SAMPLE_RATE)
    comparison_samples = math.floor(comparison_duration * AUDIO_ANALYSIS_SAMPLE_RATE)
    try:
        alignment_audio.retime_rates(reference_scale)
        alignment_audio.retime_rates(comparison_scale)
        plan = plan_audio_chunks(
            reference_samples,
            comparison_samples,
            cache_settings.max_offset_seconds,
        )
    except AudioAlignmentError as exc:
        return _rejected_result(
            reference=reference,
            comparison=comparison,
            cache_settings=cache_settings,
            reason=exc.category,
            reference_request=reference_request,
            comparison_request=comparison_request,
            comparison_ordinal=comparison_ordinal,
            fps_reference=fps_reference,
            reference_selection=reference_selection,
            comparison_selection=comparison_selection,
        )
    total_timeout = paired_collection_timeout_seconds(
        float(reference_duration), float(comparison_duration)
    )
    reference_limit = paired_output_limit_samples(
        float(reference_duration), AUDIO_ANALYSIS_SAMPLE_RATE
    )
    comparison_limit = paired_output_limit_samples(
        float(comparison_duration), AUDIO_ANALYSIS_SAMPLE_RATE
    )
    if total_timeout is None or reference_limit is None or comparison_limit is None:
        return _rejected_result(
            reference=reference,
            comparison=comparison,
            cache_settings=cache_settings,
            reason="selected_audio_timeline_unavailable",
            reference_request=reference_request,
            comparison_request=comparison_request,
            comparison_ordinal=comparison_ordinal,
            fps_reference=fps_reference,
            reference_selection=reference_selection,
            comparison_selection=comparison_selection,
        )
    return _PlannedAudioPair(
        reference_selection=reference_selection,
        comparison_selection=comparison_selection,
        plan=plan,
        total_timeout_seconds=total_timeout,
        reference_limit_samples=reference_limit,
        comparison_limit_samples=comparison_limit,
    )


def _collect_and_decide_audio_pair(
    reference: Path,
    comparison: Path,
    *,
    cache_settings: AlignmentCacheSettings,
    fps_reference: Fraction,
    planned: _PlannedAudioPair,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int,
    cancellation: threading.Event | None,
    vs_loader: VSLoader | None,
    on_stage: Callable[[str, int | None], None] | None = None,
    on_chunk: Callable[[], None] | None = None,
) -> AlignmentResult:
    """Collect paired audio and map the outcome; raises on cancel/failed cleanup."""
    reference_selection = planned.reference_selection
    comparison_selection = planned.comparison_selection
    plan = planned.plan

    reference_audio_start, reference_video_start = _selection_start_facts(
        reference_selection, timeline_scale=reference_request.timeline_scale
    )
    comparison_audio_start, comparison_video_start = _selection_start_facts(
        comparison_selection, timeline_scale=comparison_request.timeline_scale
    )

    def report_video_stage(stage: str) -> None:
        if on_stage is not None:
            on_stage(stage, None)

    def finish(
        decided: DecidedAudioStage,
        collection_observation: AudioCollectionObservation,
        collection_facts: tuple[AudioCollectionFacts, ...],
        collection_failure: AudioCollectionFailure | None = None,
        estimate: ChunkedAudioEstimate | None = None,
    ) -> AlignmentResult:
        attempt = _build_audio_attempt(
            reference=reference_request,
            comparison=comparison_request,
            comparison_ordinal=comparison_ordinal,
            reference_selection=reference_selection,
            comparison_selection=comparison_selection,
            decided=decided,
            fps_reference=fps_reference,
            collection=collection_facts,
            collection_observation=collection_observation,
            collection_failure=collection_failure,
        )
        if estimate is not None and attempt.audio.global_lag is not None:
            video_observation = alignment_video.check_video_alignment(
                reference=_video_clip_request(reference_request),
                comparison=_video_clip_request(comparison_request),
                attempt=attempt,
                fps_reference=fps_reference,
                loader=vs_loader,
                cancellation=cancellation,
                on_stage=report_video_stage,
            )
            decided = alignment_decision.decide_after_video(
                stage=decided,
                estimate=estimate,
                plan=plan,
                video=video_observation,
                fps_reference=fps_reference,
            )
            attempt = _build_audio_attempt(
                reference=reference_request,
                comparison=comparison_request,
                comparison_ordinal=comparison_ordinal,
                reference_selection=reference_selection,
                comparison_selection=comparison_selection,
                decided=decided,
                fps_reference=fps_reference,
                collection=collection_facts,
                collection_observation=collection_observation,
                collection_failure=collection_failure,
            )
        return _computed_result(
            reference=reference,
            comparison=comparison,
            decided=decided,
            attempt=attempt,
        )

    if on_stage is not None:
        on_stage("reading audio", len(plan.chunks))
    accumulator = ChunkedCorrelation(plan, on_chunk=on_chunk)
    collection = collect_paired_audio_chunks(
        alignment_audio.collection_argv(
            reference,
            reference_selection.stream,
            channel_strategy=cache_settings.channel_strategy,
            timeline_scale=reference_request.timeline_scale,
        ),
        alignment_audio.collection_argv(
            comparison,
            comparison_selection.stream,
            channel_strategy=cache_settings.channel_strategy,
            timeline_scale=comparison_request.timeline_scale,
        ),
        chunks=plan.chunks,
        lag_samples=plan.lag_samples,
        consume_borrowed_chunk=accumulator.add,
        reference_limit_samples=planned.reference_limit_samples,
        comparison_limit_samples=planned.comparison_limit_samples,
        total_timeout_seconds=planned.total_timeout_seconds,
        cancellation=cancellation,
    )
    if isinstance(collection, PairedAudioCollectionFailure):
        if not (collection.reference_cleanup.completed and collection.comparison_cleanup.completed):
            raise AudioAlignmentCleanupError(
                "paired audio collection cleanup did not complete",
                category=collection.category,
                stage="collection",
            )
        if collection.category == "cancelled":
            raise AudioAlignmentCancellationError(
                "audio alignment was cancelled",
                category="cancelled",
                stage="collection",
            )
        decided = alignment_decision.decide_aborted_stage(
            plan=plan,
            max_offset_seconds=cache_settings.max_offset_seconds,
            reason=collection.category,
            reference_audio_start=reference_audio_start,
            reference_video_start=reference_video_start,
            comparison_audio_start=comparison_audio_start,
            comparison_video_start=comparison_video_start,
        )
        facts, pair_failure = _evidence_collection_facts(collection)
        return finish(decided, "observed", facts, pair_failure)
    estimate = accumulator.finish()
    decided = alignment_decision.decide_completed_stage(
        estimate=estimate,
        plan=plan,
        max_offset_seconds=cache_settings.max_offset_seconds,
        reference_audio_start=reference_audio_start,
        reference_video_start=reference_video_start,
        comparison_audio_start=comparison_audio_start,
        comparison_video_start=comparison_video_start,
        fps_reference=fps_reference,
    )
    facts, pair_failure = _evidence_collection_facts(collection)
    return finish(decided, "observed", facts, pair_failure, estimate=estimate)


def _estimate_audio_pair(
    reference: Path,
    comparison: Path,
    *,
    cache_settings: AlignmentCacheSettings,
    fps_reference: Fraction,
    reference_probe_loader: Callable[[], alignment_audio.ProbedStreams] | None = None,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int = 1,
    cancellation: threading.Event | None = None,
    vs_loader: VSLoader | None = None,
    on_stage: Callable[[str, int | None], None] | None = None,
    on_chunk: Callable[[], None] | None = None,
) -> AlignmentResult:
    """Estimate one pair: pre-decode planning, then collection plus decision."""
    if on_stage is not None:
        on_stage("preparing audio", None)
    planned = _plan_audio_pair(
        reference,
        comparison,
        cache_settings=cache_settings,
        fps_reference=fps_reference,
        reference_probe_loader=reference_probe_loader,
        reference_request=reference_request,
        comparison_request=comparison_request,
        comparison_ordinal=comparison_ordinal,
        cancellation=cancellation,
    )
    if isinstance(planned, AlignmentResult):
        return planned
    return _collect_and_decide_audio_pair(
        reference,
        comparison,
        cache_settings=cache_settings,
        fps_reference=fps_reference,
        planned=planned,
        reference_request=reference_request,
        comparison_request=comparison_request,
        comparison_ordinal=comparison_ordinal,
        cancellation=cancellation,
        vs_loader=vs_loader,
        on_stage=on_stage,
        on_chunk=on_chunk,
    )


def _compute_requested_alignments(
    *,
    request: AlignmentRequest,
    requested_comparisons: list[AlignmentClipRequest],
    fps_reference: Fraction,
    on_stage: Callable[[AlignmentClipRequest, str, int | None], None],
    on_chunk: Callable[[], None],
    cancellation: threading.Event,
    vs_loader: VSLoader | None,
) -> dict[str, ComparisonResolution]:
    """Run only blocking probe, collection, and numeric work in the owned worker."""
    resolutions: dict[str, ComparisonResolution] = {}
    raise_if_alignment_cancelled(cancellation)
    reference = request.reference
    comparison_ordinals = {
        comparison.path: ordinal for ordinal, comparison in enumerate(request.comparisons, start=1)
    }
    selected_reference_probe: alignment_audio.ProbedStreams | None = None

    def load_reference_probe() -> alignment_audio.ProbedStreams:
        nonlocal selected_reference_probe
        if selected_reference_probe is None:
            selected_reference_probe = alignment_audio.probe_streams(reference.path)
        return selected_reference_probe

    for fallback_ordinal, comp in enumerate(requested_comparisons, start=1):
        raise_if_alignment_cancelled(cancellation)
        res = _estimate_audio_pair(
            reference.path,
            comp.path,
            cache_settings=request.settings,
            fps_reference=fps_reference,
            reference_probe_loader=load_reference_probe,
            reference_request=reference,
            comparison_request=comp,
            comparison_ordinal=comparison_ordinals.get(comp.path, fallback_ordinal),
            cancellation=cancellation,
            vs_loader=vs_loader,
            on_stage=partial(on_stage, comp),
            on_chunk=on_chunk,
        )
        raise_if_alignment_cancelled(cancellation)
        resolutions[alignment_key(reference.path, comp.path)] = resolution_from_computation(
            res, comparison_cache_key=comparison_cache_key(comp)
        )
    raise_if_alignment_cancelled(cancellation)
    return resolutions


async def _await_audio_computation(
    *,
    request: AlignmentRequest,
    requested_comparisons: list[AlignmentClipRequest],
    fps_reference: Fraction,
    progress: ProgressReporter | None,
    vs_loader: VSLoader | None,
) -> dict[str, ComparisonResolution]:
    await cancellation_checkpoint()
    cancellation = threading.Event()
    loop = asyncio.get_running_loop()
    # LF2 is human presentation; structured phase events retain their contract.
    if isinstance(progress, LogProgressReporter):
        progress = None
    descriptions = _request_progress_descriptions(request)
    positions = {comp.path: i for i, comp in enumerate(requested_comparisons, 1)}
    stage_active = False
    pending_chunks = 0
    last_tick = monotonic()

    def apply_stage(description: str, total: int | None) -> None:
        nonlocal stage_active
        if progress is None:
            return
        if stage_active:
            progress.complete_phase(retain=False)
        if total is None:
            progress.start_indeterminate(description)
        else:
            progress.start_phase(description, total, presentation="measurable")
        stage_active = True

    def flush_chunks() -> None:
        nonlocal pending_chunks, last_tick
        if pending_chunks and progress is not None:
            loop.call_soon_threadsafe(progress.advance, pending_chunks)
            pending_chunks = 0
            last_tick = monotonic()

    def report_stage(comparison: AlignmentClipRequest, stage: str, total: int | None) -> None:
        flush_chunks()
        if progress is not None:
            description = (
                f"{descriptions[comparison.path]} "
                f"({positions[comparison.path]} of {len(requested_comparisons)}) · {stage}"
            )
            loop.call_soon_threadsafe(apply_stage, description, total)

    def report_chunk() -> None:
        nonlocal pending_chunks
        pending_chunks += 1
        # Coalesce fast chunks to the live renderer's four-Hz refresh cadence.
        if monotonic() - last_tick >= 0.25:
            flush_chunks()

    def compute() -> dict[str, ComparisonResolution]:
        try:
            return _compute_requested_alignments(
                request=request,
                requested_comparisons=requested_comparisons,
                fps_reference=fps_reference,
                on_stage=report_stage,
                on_chunk=report_chunk,
                cancellation=cancellation,
                vs_loader=vs_loader,
            )
        finally:
            # Flush the last fast batch from the worker, including on failure.
            flush_chunks()

    worker = asyncio.create_task(
        asyncio.to_thread(compute),
        name="alignment-audio-computation",
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancellation.set()
        while not worker.done():
            with suppress(asyncio.CancelledError):
                await asyncio.wait((worker,))
        # Cancellation outranks ordinary worker failures, but never hides a failed
        # release of an owned child, reader, pipe, or handle.
        error = None if worker.cancelled() else worker.exception()
        if isinstance(error, AudioAlignmentCleanupError):
            worker.result()
        raise
    finally:
        if stage_active and progress is not None:
            progress.complete_phase(retain=False)


def _record_alignment_progress(
    *,
    progress: ProgressReporter | None,
    result: AlignmentResult,
    description: str | None = None,
) -> None:
    if progress is None:
        return

    if description is None:
        description = f"Align · {result.comparison_clip}"
    progress.set_description(description)
    progress.advance(1)


def _record_resolved_alignment_progress(
    *,
    progress: ProgressReporter | None,
    reference: Path,
    comparisons: list[Path],
    resolutions: dict[str, ComparisonResolution],
    progress_descriptions: dict[Path, str] | None = None,
) -> None:
    for comp in comparisons:
        resolution = resolutions.get(alignment_key(reference, comp))
        if resolution is not None:
            _record_alignment_progress(
                progress=progress,
                result=resolution.result,
                description=(progress_descriptions or {}).get(comp),
            )


def _record_resolved_alignment_request_progress(
    *,
    progress: ProgressReporter | None,
    request: AlignmentRequest,
    resolutions: dict[str, ComparisonResolution],
    cached_audio_evidence_only: bool = False,
) -> None:
    progress_descriptions = _request_progress_descriptions(request)
    comparisons = request.comparisons
    if cached_audio_evidence_only:
        comparisons = [
            comparison
            for comparison in request.comparisons
            if (
                resolution := resolutions.get(
                    alignment_key(request.reference.path, comparison.path)
                )
            )
            is not None
            and (
                resolution.origin == "shared_computed_offsets"
                or (
                    resolution.origin == "shared_previous_offsets"
                    and not isinstance(progress, LogProgressReporter)
                )
            )
        ]
    for comparison in request.comparisons:
        key = alignment_key(request.reference.path, comparison.path)
        resolution = resolutions.get(key)
        if resolution is not None and resolution.origin in {
            "shared_computed_offsets",
            "shared_previous_offsets",
        }:
            progress_descriptions[comparison.path] = progress_descriptions[comparison.path].replace(
                "Align · ", "Align · using cached audio evidence · ", 1
            )
    _record_resolved_alignment_progress(
        progress=progress,
        reference=request.reference.path,
        comparisons=[comparison.path for comparison in comparisons],
        resolutions=resolutions,
        progress_descriptions=progress_descriptions,
    )


def _request_progress_descriptions(request: AlignmentRequest) -> dict[Path, str]:
    return {
        comparison.path: (
            f"Align · {comparison.short_name or comparison.label or comparison.path.name}"
        )
        for comparison in request.comparisons
    }


def _write_run_diagnostics(
    *,
    request: AlignmentRequest,
    resolutions: dict[str, ComparisonResolution],
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
        key = alignment_key(request.reference.path, comparison.path)
        if only_keys is not None and key not in only_keys:
            continue
        resolution = resolutions[key]
        try:
            write_alignment_diagnostic(
                generated_root=diagnostics_root,
                diagnostics_dir=diagnostics_dir,
                comparison_ordinal=ordinal,
                reference_label=request.reference.label,
                comparison_label=comparison.label,
                resolution=resolution,
                review_outcome=review_outcome,
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
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    verbose: bool = False,
    quiet: bool = False,
    json_output: bool = False,
    vs_loader: VSLoader | None = None,
    on_reusable_cache_written: Callable[[], None] | None = None,
    on_diagnostics_written: Callable[[Path], None] | None = None,
) -> AlignmentOperationOutcome:
    """Align clips from the typed request seam with shared previous-offset reuse."""
    reference = request.reference.path
    comparisons = [comparison.path for comparison in request.comparisons]
    _check_duplicate_stems(comparisons)
    validate_previous_offsets_policy(request, config)

    if progress:
        progress.set_description("Align · checking saved offsets")

    fps_reference = Fraction(
        request.reference.effective_fps_num,
        request.reference.effective_fps_den,
    )
    resolutions, completed_confirmed_reuse = apply_shared_reuse(
        request=request,
        unresolved_comparisons=request.comparisons,
        cache_results=config.cache_results,
        progress=progress,
        no_color=config.no_color,
        verbose=verbose,
    )

    requested_comparisons = [
        comparison
        for comparison in request.comparisons
        if alignment_key(reference, comparison.path) not in resolutions
    ]
    if requested_comparisons:
        _record_resolved_alignment_request_progress(
            progress=progress,
            request=request,
            resolutions=resolutions,
        )
        computed = await _await_audio_computation(
            request=request,
            requested_comparisons=requested_comparisons,
            fps_reference=fps_reference,
            progress=progress,
            vs_loader=vs_loader,
        )
        resolutions.update(computed)
        if isinstance(progress, LogProgressReporter):
            descriptions = _request_progress_descriptions(request)
            for comparison in requested_comparisons:
                _record_alignment_progress(
                    progress=progress,
                    result=resolutions[alignment_key(reference, comparison.path)].result,
                    description=descriptions[comparison.path],
                )
    else:
        _record_resolved_alignment_request_progress(
            progress=progress,
            request=request,
            resolutions=resolutions,
            cached_audio_evidence_only=True,
        )

    initial_outcome: AlignmentReviewOutcome = (
        "pending"
        if (config.use_vsview or config.force_interactive) and not completed_confirmed_reuse
        else "not_requested"
    )
    diagnostic_keys = _write_run_diagnostics(
        request=request,
        resolutions=resolutions,
        review_outcome=initial_outcome,
        emit_success_log=json_output,
    )
    if (
        diagnostic_keys
        and on_diagnostics_written is not None
        and request.alignment_diagnostics_dir is not None
    ):
        on_diagnostics_written(request.alignment_diagnostics_dir)
    present_alignment_evidence(
        request=request,
        resolutions=resolutions,
        config=config,
        progress=progress,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
        review_pending=initial_outcome == "pending",
    )
    if completed_confirmed_reuse and not requested_comparisons:
        return AlignmentOperationOutcome(
            ordered_results(request, resolutions),
            resolutions=tuple(
                resolutions[alignment_key(reference, comp.path)] for comp in request.comparisons
            ),
        )

    audio_review_by_key = (
        _build_audio_review_map(
            reference=reference,
            comparisons=comparisons,
            resolutions=resolutions,
        )
        if initial_outcome == "pending"
        else {}
    )
    review = maybe_launch_alignment_vsview(
        reference=request.reference,
        comparisons=request.comparisons,
        audio_review_by_key=audio_review_by_key,
        cache_dir=request.generated_dir,
        config=config,
        progress=progress,
        frame_props_by_stem=frame_props_by_stem,
        vs_loader=vs_loader,
        verbose=verbose,
    )
    confirmed_offsets = review.confirmed_offsets
    if confirmed_offsets:
        for comparison in request.comparisons:
            key = alignment_key(reference, comparison.path)
            if key in confirmed_offsets:
                resolutions[key] = confirm_manual(
                    resolutions[key],
                    frame_offset=confirmed_offsets[key],
                    fps_reference=fps_reference,
                    reference_clip=reference,
                    comparison_clip=comparison.path,
                )

    if initial_outcome == "pending":
        _write_run_diagnostics(
            request=request,
            resolutions=resolutions,
            review_outcome=review.review_outcome,
            emit_success_log=json_output,
            only_keys=diagnostic_keys,
            confirmed_frame_pairs=review.confirmed_frame_pairs,
        )

    # Observe cancellation first, after the worker has completed owned cleanup.
    await cancellation_checkpoint()
    if config.cache_results:
        candidate = prepare_reusable_source_set(request, resolutions)
        if candidate is not None:
            written = save_reusable_offsets(request, candidate)
            if (
                written
                and on_reusable_cache_written is not None
                and can_reuse_written_offsets_without_confirmation(request, candidate.resolutions)
            ):
                on_reusable_cache_written()

    return AlignmentOperationOutcome(
        ordered_results(request, resolutions),
        review.summary,
        resolutions=tuple(
            resolutions[alignment_key(reference, comp.path)] for comp in request.comparisons
        ),
    )
