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
from pathlib import Path
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
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.alignment_presentation import (
    present_alignment_evidence,
    print_pre_review_summary,
)
from frame_compare.services.alignment_previous_offsets import (
    apply_shared_reuse,
    prompt_for_previous_alignment_offset_reuse,
    shared_write_is_service_eligible,
    validate_previous_offsets_policy,
)
from frame_compare.services.alignment_reuse_cache import comparison_cache_key, save_reusable_offsets
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
    AlignmentProvenance,
    AlignmentResult,
    AlignmentReviewSummary,
)
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    MAX_ALIGNMENT_EVIDENCE_BYTES,
    AudioAlignmentAttempt,
    AudioCollectionFacts,
    AudioCollectionFailure,
    AudioCollectionObservation,
    AudioPairSide,
    VideoCheckObservation,
    audio_attempt_payload,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import AlignmentClipRequest, AlignmentRequest
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
        key = alignment_key(reference, comp)
        res = results_map.get(key)
        offsets_by_key[key] = res.frame_offset if res is not None and res.applied else None
    return offsets_by_key


def _project_audio_attempt_for_review(attempt: AudioAlignmentAttempt) -> AudioAlignmentAttempt:
    """Embed the attempt without per-chunk rows in native review metadata."""
    if attempt.chunks.rows_omitted:
        return attempt
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            starts=(),
            counts=(),
            active=(),
            lags=(),
            psrs=(),
            credible=(),
            agrees=(),
            rows_omitted=True,
        ),
    )


def _build_audio_review_map(
    *,
    reference: Path,
    comparisons: list[Path],
    results_map: dict[str, AlignmentResult],
    provenances: dict[str, AlignmentProvenance],
) -> dict[str, str]:
    payloads: dict[str, str] = {}
    for comparison in comparisons:
        key = alignment_key(reference, comparison)
        result = results_map[key]
        provenance = provenances[key]
        payload = {
            "current_authority": {
                "origin": provenance.provenance if result.applied else "none",
                "frame_offset": result.frame_offset if result.applied else None,
            },
            "evidence_availability": provenance.evidence_availability,
            "audio_attempt": (
                audio_attempt_payload(_project_audio_attempt_for_review(result.audio_attempt))
                if result.audio_attempt is not None
                else None
            ),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > MAX_ALIGNMENT_EVIDENCE_BYTES:
            raise AudioAlignmentError("Native alignment-review audio evidence exceeds 2 MiB.")
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
        key = alignment_key(reference, comp)
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
        key = alignment_key(reference, comp.path)
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
        selection.stream.timeline.start_time * timeline_scale,
        selection.video_start.start_time * timeline_scale,
    )


def _build_audio_attempt(
    *,
    reference: AlignmentClipRequest,
    comparison: AlignmentClipRequest,
    comparison_ordinal: int,
    reference_selection: alignment_audio.AudioStreamSelection,
    comparison_selection: alignment_audio.AudioStreamSelection,
    decided: DecidedAudioStage,
    config: AlignmentConfig,
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
                explicit_override=config.reference_stream is not None,
                video_start=reference_selection.video_start,
                timeline_scale=reference.timeline_scale,
            ),
            alignment_audio.selected_stream_evidence(
                comparison_selection.stream,
                role="comparison",
                source_identity_digest=_clip_identity_digest(comparison),
                explicit_override=config.comparison_streams.get(comparison.path.stem) is not None,
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
        identity=clip.identity,
        active_rect=active_rect,
    )


def _rejected_result(
    *,
    reference: Path,
    comparison: Path,
    config: AlignmentConfig,
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
        max_offset_seconds=config.max_offset_seconds,
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
            config=config,
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
    frozen_identities: tuple[tuple[int, int], tuple[int, int]]
    total_timeout_seconds: float
    reference_limit_samples: int
    comparison_limit_samples: int


def _check_pair_identities(
    reference: Path,
    comparison: Path,
    frozen_identities: tuple[tuple[int, int], tuple[int, int]],
) -> None:
    """Raise AudioAlignmentError when either source changed since planning."""
    try:
        current_identities = (_source_identity(reference), _source_identity(comparison))
    except OSError as exc:
        raise AudioAlignmentError(
            "source identity changed during paired audio collection",
            category="source_identity_changed",
            stage="collection",
        ) from exc
    if frozen_identities != current_identities:
        raise AudioAlignmentError(
            "source identity changed during paired audio collection",
            category="source_identity_changed",
            stage="collection",
        )


def _plan_audio_pair(
    reference: Path,
    comparison: Path,
    *,
    config: AlignmentConfig,
    fps_reference: Fraction,
    reference_probe_loader: Callable[[], alignment_audio.ProbedStreams] | None,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int,
    cancellation: threading.Event | None,
) -> AlignmentResult | _PlannedAudioPair:
    """Select streams and plan chunks; return a rejection result or a plan."""
    raise_if_alignment_cancelled(cancellation)
    frozen_identities: tuple[tuple[int, int], tuple[int, int]] | None = None
    try:
        if _request_identity_matches(reference, reference_request) and _request_identity_matches(
            comparison, comparison_request
        ):
            frozen_identities = (_source_identity(reference), _source_identity(comparison))
    except OSError:
        frozen_identities = None
    if frozen_identities is None:
        decided = alignment_decision.decide_rejected_stage(
            max_offset_seconds=config.max_offset_seconds,
            reason="source_identity_changed",
        )
        return _computed_result(
            reference=reference,
            comparison=comparison,
            decided=decided,
            attempt=None,
        )
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
        reference_override=config.reference_stream,
        comparison_override=config.comparison_streams.get(comparison.stem),
    )
    reference_duration = reference_selection.stream.timeline.duration
    comparison_duration = comparison_selection.stream.timeline.duration
    if reference_duration is None or comparison_duration is None:
        return _rejected_result(
            reference=reference,
            comparison=comparison,
            config=config,
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
            config.max_offset_seconds,
        )
    except AudioAlignmentError as exc:
        return _rejected_result(
            reference=reference,
            comparison=comparison,
            config=config,
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
            config=config,
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
        frozen_identities=frozen_identities,
        total_timeout_seconds=total_timeout,
        reference_limit_samples=reference_limit,
        comparison_limit_samples=comparison_limit,
    )


def _collect_and_decide_audio_pair(
    reference: Path,
    comparison: Path,
    *,
    config: AlignmentConfig,
    fps_reference: Fraction,
    planned: _PlannedAudioPair,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int,
    cancellation: threading.Event | None,
    vs_loader: VSLoader | None,
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
            config=config,
            fps_reference=fps_reference,
            collection=collection_facts,
            collection_observation=collection_observation,
            collection_failure=collection_failure,
        )
        if estimate is not None and attempt.audio.global_lag is not None:
            video_result = alignment_video.check_video_alignment(
                reference=_video_clip_request(reference_request),
                comparison=_video_clip_request(comparison_request),
                attempt=attempt,
                fps_reference=fps_reference,
                loader=vs_loader,
                cancellation=cancellation,
            )
            decided = alignment_decision.decide_after_video(
                stage=decided,
                estimate=estimate,
                plan=plan,
                video=video_result.observation,
                fps_reference=fps_reference,
            )
            attempt = _build_audio_attempt(
                reference=reference_request,
                comparison=comparison_request,
                comparison_ordinal=comparison_ordinal,
                reference_selection=reference_selection,
                comparison_selection=comparison_selection,
                decided=decided,
                config=config,
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

    def aborted_for_identity_change(
        collection_observation: AudioCollectionObservation,
        collection_facts: tuple[AudioCollectionFacts, ...],
        collection_failure: AudioCollectionFailure | None = None,
    ) -> AlignmentResult:
        decided = alignment_decision.decide_aborted_stage(
            plan=plan,
            max_offset_seconds=config.max_offset_seconds,
            reason="source_identity_changed",
            reference_audio_start=reference_audio_start,
            reference_video_start=reference_video_start,
            comparison_audio_start=comparison_audio_start,
            comparison_video_start=comparison_video_start,
        )
        return finish(decided, collection_observation, collection_facts, collection_failure)

    try:
        _check_pair_identities(reference, comparison, planned.frozen_identities)
    except AudioAlignmentError:
        return aborted_for_identity_change("not_observed", ())
    accumulator = ChunkedCorrelation(plan)
    collection = collect_paired_audio_chunks(
        alignment_audio.collection_argv(
            reference,
            reference_selection.stream,
            channel_strategy=config.channel_strategy,
            timeline_scale=reference_request.timeline_scale,
        ),
        alignment_audio.collection_argv(
            comparison,
            comparison_selection.stream,
            channel_strategy=config.channel_strategy,
            timeline_scale=comparison_request.timeline_scale,
        ),
        chunks=plan.chunks,
        lag_samples=plan.lag_samples,
        consumer=accumulator.add,
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
        try:
            _check_pair_identities(reference, comparison, planned.frozen_identities)
        except AudioAlignmentError:
            facts, pair_failure = _evidence_collection_facts(collection)
            return aborted_for_identity_change("observed", facts, pair_failure)
        decided = alignment_decision.decide_aborted_stage(
            plan=plan,
            max_offset_seconds=config.max_offset_seconds,
            reason=collection.category,
            reference_audio_start=reference_audio_start,
            reference_video_start=reference_video_start,
            comparison_audio_start=comparison_audio_start,
            comparison_video_start=comparison_video_start,
        )
        facts, pair_failure = _evidence_collection_facts(collection)
        return finish(decided, "observed", facts, pair_failure)
    try:
        _check_pair_identities(reference, comparison, planned.frozen_identities)
    except AudioAlignmentError:
        facts, pair_failure = _evidence_collection_facts(collection)
        return aborted_for_identity_change("observed", facts, pair_failure)
    estimate = accumulator.finish()
    decided = alignment_decision.decide_completed_stage(
        estimate=estimate,
        plan=plan,
        max_offset_seconds=config.max_offset_seconds,
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
    config: AlignmentConfig,
    fps_reference: Fraction,
    reference_probe_loader: Callable[[], alignment_audio.ProbedStreams] | None = None,
    reference_request: AlignmentClipRequest,
    comparison_request: AlignmentClipRequest,
    comparison_ordinal: int = 1,
    cancellation: threading.Event | None = None,
    vs_loader: VSLoader | None = None,
) -> AlignmentResult:
    """Estimate one pair: pre-decode planning, then collection plus decision."""
    planned = _plan_audio_pair(
        reference,
        comparison,
        config=config,
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
        config=config,
        fps_reference=fps_reference,
        planned=planned,
        reference_request=reference_request,
        comparison_request=comparison_request,
        comparison_ordinal=comparison_ordinal,
        cancellation=cancellation,
        vs_loader=vs_loader,
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
    cancellation: threading.Event,
    vs_loader: VSLoader | None,
) -> Fraction:
    """Run only blocking probe, collection, and numeric work in the owned worker."""
    raise_if_alignment_cancelled(cancellation)
    resolved_fps = fps_reference or alignment_audio.probe_fps(request.reference.path)
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
        if on_comparison_started is not None:
            on_comparison_started(comp)
        res = _estimate_audio_pair(
            reference.path,
            comp.path,
            config=config,
            fps_reference=resolved_fps,
            reference_probe_loader=load_reference_probe,
            reference_request=reference,
            comparison_request=comp,
            comparison_ordinal=comparison_ordinals.get(comp.path, fallback_ordinal),
            cancellation=cancellation,
            vs_loader=vs_loader,
        )
        raise_if_alignment_cancelled(cancellation)
        results_map[alignment_key(reference.path, comp.path)] = res
    raise_if_alignment_cancelled(cancellation)
    for comparison in requested_comparisons:
        key = alignment_key(reference.path, comparison.path)
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
    vs_loader: VSLoader | None,
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
            cancellation=cancellation,
            vs_loader=vs_loader,
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
        result = results_map.get(alignment_key(reference, comp))
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
                    alignment_key(request.reference.path, comparison.path)
                )
            )
            is not None
            and provenance.provenance == "shared_computed_offsets"
        ]
    for comparison in request.comparisons:
        key = alignment_key(request.reference.path, comparison.path)
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
        key = alignment_key(request.reference.path, comparison.path)
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
        key = alignment_key(request.reference.path, comparison.path)
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
    vs_loader: VSLoader | None = None,
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
        if alignment_key(reference, comparison.path) not in results_map
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
        if alignment_key(reference, comparison.path) not in results_map
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
            vs_loader=vs_loader,
        )
        descriptions = _request_progress_descriptions(request)
        for comparison in requested_comparisons:
            _record_alignment_progress(
                progress=progress,
                result=results_map[alignment_key(reference, comparison.path)],
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
        print_pre_review_summary(
            request=request,
            results_map=results_map,
            progress=progress,
            no_color=config.no_color,
        )
    present_alignment_evidence(
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
            results_map[alignment_key(reference, comparison.path)]
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
        if review_summary is not None and not review_summary.review_ran:
            review_summary.review_unresolved = True

    if config.cache_results and shared_write_is_service_eligible(
        request=request,
        provenances=provenances,
    ):
        save_reusable_offsets(request, list(provenances.values()))

    return [
        results_map[alignment_key(reference, comparison.path)] for comparison in request.comparisons
    ]
