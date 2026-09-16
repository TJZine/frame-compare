"""Windowed consensus and gating for computed audio alignment."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from statistics import median_low
from typing import Literal

import numpy as np

from frame_compare.services import alignment_audio
from frame_compare.services.alignment_audio import AudioAnalysisPlan, AudioWindow, AudioWindowSpec
from frame_compare.services.alignment_correlation import (
    CorrelationEstimate,
    estimate_alignment_offset,
    refine_aligned_score,
)
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.alignment_stability import classify_alignment_stability
from frame_compare.services.errors import (
    AudioAlignmentCancellationError,
    AudioAlignmentCleanupError,
    AudioAlignmentError,
    raise_if_alignment_cancelled,
)
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    AlignmentStabilitySummary,
    AlignmentWindowEvidence,
    AudioAlignmentAttempt,
    AudioAlignmentCandidate,
    AudioAlignmentCollectionRecord,
    AudioAlignmentDecision,
    AudioAlignmentWindowRecord,
    AudioPeakRatio,
)

_REVIEW_SCORE_FLOOR = 0.90
_REVIEW_PEAK_RATIO_FLOOR = 1.50
AUTOMATIC_AUTHORITY_HOLD_REASON = "automatic_authority_held"
_AUTOMATIC_AUTHORITY_HELD = True


def automatic_authority_is_held() -> bool:
    """Return the internal release latch for computed alignment authority."""
    return _AUTOMATIC_AUTHORITY_HELD


def hold_computed_result(result: AlignmentResult) -> AlignmentResult:
    """Remove automatic authority from a computed result while the latch is held."""
    if not automatic_authority_is_held() or not result.applied:
        return result
    return replace(
        result,
        frame_offset=None,
        time_offset_seconds=None,
        applied=False,
        diagnostic=AUTOMATIC_AUTHORITY_HOLD_REASON,
    )


def hold_automatic_consensus(result: AlignmentConsensus) -> AlignmentConsensus:
    """Remove automatic authority from a computed consensus while held."""
    if not automatic_authority_is_held() or not result.applied:
        return result
    decision = result.decision
    if decision is not None and decision.state == "trusted_automatic":
        decision = replace(
            decision,
            state="provisional",
            primary_reason=AUTOMATIC_AUTHORITY_HOLD_REASON,
            failed_gates=(*decision.failed_gates, AUTOMATIC_AUTHORITY_HOLD_REASON),
        )
    attempt = result.audio_attempt
    if attempt is not None and decision is not None:
        attempt = replace(attempt, decision=decision)
    return replace(
        result,
        sample_offset=None,
        applied=False,
        diagnostic=AUTOMATIC_AUTHORITY_HOLD_REASON,
        decision=decision,
        audio_attempt=attempt,
    )


def _peak_value(value: float) -> AudioPeakRatio:
    return "unbounded" if math.isinf(value) else value


def _candidate_record(
    members: list[tuple[CorrelationEstimate, str]],
    *,
    sample_rate: int,
    fps: Fraction,
) -> AudioAlignmentCandidate:
    sample_offset = int(median_low(estimate.sample_offset for estimate, _ in members))
    peak_ratio = min(estimate.peak_ratio for estimate, _ in members)
    return AudioAlignmentCandidate(
        sample_offset=sample_offset,
        sample_rate=sample_rate,
        frame_offset=samples_to_frames(sample_offset, sample_rate, fps),
        supporting_window_ids=tuple(logical_id for _, logical_id in members),
        median_score=float(np.median([estimate.score for estimate, _ in members])),
        minimum_peak_ratio=_peak_value(peak_ratio),
    )


def _review_decision(
    result: AlignmentConsensus,
    candidates: list[CorrelationEstimate],
    candidate_ids: list[str],
    window_records: list[AudioAlignmentWindowRecord],
    config: AlignmentConfig,
    fps: Fraction,
) -> AudioAlignmentDecision:
    members = list(zip(candidates, candidate_ids, strict=True))
    failed_gates, unassessed_gates = _legacy_gate_evidence(candidates, config, fps)
    if result.diagnostic == AUTOMATIC_AUTHORITY_HOLD_REASON:
        failed_gates = (*failed_gates, AUTOMATIC_AUTHORITY_HOLD_REASON)
    consensus_ratio = result.consensus_ratio if candidates else None
    aggregate_score = result.score if candidates else None
    minimum_peak_ratio = (
        _peak_value(result.ambiguity_ratio) if result.ambiguity_ratio is not None else None
    )
    if result.applied:
        if result.sample_offset is None:
            raise ValueError("applied consensus is missing its sample offset")
        accepted_frame = samples_to_frames(result.sample_offset, config.sample_rate, fps)
        accepted_members = [
            item
            for item in members
            if samples_to_frames(item[0].sample_offset, config.sample_rate, fps) == accepted_frame
        ]
        return AudioAlignmentDecision(
            state="trusted_automatic",
            candidate=_candidate_record(
                accepted_members,
                sample_rate=config.sample_rate,
                fps=fps,
            ),
            primary_reason="accepted",
            raw_correlated_windows=result.valid_windows,
            consensus_windows=result.consensus_windows,
            consensus_ratio=consensus_ratio,
            aggregate_score=aggregate_score,
            minimum_peak_ratio=minimum_peak_ratio,
            failed_gates=failed_gates,
            unassessed_gates=unassessed_gates,
        )

    review_ids = {record.logical_id for record in window_records if record.review_qualified}
    review_groups: dict[int, list[tuple[CorrelationEstimate, str]]] = {}
    for estimate, logical_id in members:
        if logical_id not in review_ids:
            continue
        frame = samples_to_frames(estimate.sample_offset, config.sample_rate, fps)
        review_groups.setdefault(frame, []).append((estimate, logical_id))
    if not review_groups:
        return AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason=(result.diagnostic if candidates else "no_usable_windows"),
            raw_correlated_windows=result.valid_windows,
            consensus_windows=result.consensus_windows,
            consensus_ratio=consensus_ratio,
            aggregate_score=aggregate_score,
            minimum_peak_ratio=minimum_peak_ratio,
            failed_gates=failed_gates,
            unassessed_gates=unassessed_gates,
        )
    ordered = sorted(review_groups.values(), key=lambda group: (-len(group), group[0][1]))
    if len(ordered) > 1 and len(ordered[0]) == len(ordered[1]):
        return AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason="no_unique_candidate",
            raw_correlated_windows=result.valid_windows,
            consensus_windows=result.consensus_windows,
            consensus_ratio=consensus_ratio,
            aggregate_score=aggregate_score,
            minimum_peak_ratio=minimum_peak_ratio,
            failed_gates=(*failed_gates, "no_unique_candidate"),
            unassessed_gates=unassessed_gates,
        )
    return AudioAlignmentDecision(
        state="provisional",
        candidate=_candidate_record(ordered[0], sample_rate=config.sample_rate, fps=fps),
        primary_reason=result.diagnostic,
        raw_correlated_windows=result.valid_windows,
        consensus_windows=result.consensus_windows,
        consensus_ratio=consensus_ratio,
        aggregate_score=aggregate_score,
        minimum_peak_ratio=minimum_peak_ratio,
        failed_gates=failed_gates,
        unassessed_gates=unassessed_gates,
    )


def _legacy_gate_evidence(
    candidates: list[CorrelationEstimate],
    config: AlignmentConfig,
    fps: Fraction,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if len(candidates) < config.minimum_valid_windows:
        return (
            ("insufficient_valid_windows",),
            ("low_confidence", "insufficient_consensus", "ambiguous_correlation_peak"),
        )
    groups: dict[int, list[CorrelationEstimate]] = {}
    for candidate in candidates:
        frame = samples_to_frames(candidate.sample_offset, config.sample_rate, fps)
        groups.setdefault(frame, []).append(candidate)
    winner = max(
        groups.values(),
        key=lambda group: (len(group), max(candidate.score for candidate in group)),
    )
    score = float(np.median([candidate.score for candidate in winner]))
    ratio = len(winner) / len(candidates)
    peak_ratio = min(candidate.peak_ratio for candidate in winner)
    failed: list[str] = []
    if score < config.confidence_threshold:
        failed.append("low_confidence")
    if ratio < config.consensus_minimum_ratio:
        failed.append("insufficient_consensus")
    if peak_ratio < config.ambiguity_peak_ratio:
        failed.append("ambiguous_correlation_peak")
    return tuple(failed), ()


@dataclass(frozen=True)
class AlignmentConsensus:
    """Selected computed candidate, or diagnostics for a rejected estimate."""

    sample_offset: int | None
    score: float
    applied: bool
    diagnostic: str
    valid_windows: int
    consensus_windows: int
    consensus_ratio: float
    ambiguity_ratio: float | None
    window_evidence: tuple[AlignmentWindowEvidence, ...] = ()
    stability: AlignmentStabilitySummary | None = None
    window_records: tuple[AudioAlignmentWindowRecord, ...] = ()
    decision: AudioAlignmentDecision | None = None
    audio_attempt: AudioAlignmentAttempt | None = None
    collection_summaries: tuple[AudioAlignmentCollectionRecord, ...] = ()


@dataclass
class _StagedWindow:
    index: int
    logical_id: str
    spec: AudioWindowSpec
    actual_reference_count: int
    actual_comparison_count: int
    local_estimate: CorrelationEstimate
    local_lag: float
    global_analysis_offset: Fraction


def _valid_evidence(
    estimate: CorrelationEstimate | None,
    *,
    start: int,
    end: int,
    config: AlignmentConfig,
) -> AlignmentWindowEvidence | None:
    if (
        estimate is None
        or estimate.score < config.confidence_threshold
        or estimate.peak_ratio < config.ambiguity_peak_ratio
    ):
        return None
    return AlignmentWindowEvidence(
        start_sample=start,
        end_sample=end,
        sample_offset=estimate.sample_offset,
        score=estimate.score,
        peak_ratio=estimate.peak_ratio,
    )


def _reject(
    diagnostic: str,
    *,
    score: float,
    valid_windows: int,
    consensus_windows: int,
    consensus_ratio: float,
    ambiguity_ratio: float | None,
    window_evidence: tuple[AlignmentWindowEvidence, ...],
    stability: AlignmentStabilitySummary,
) -> AlignmentConsensus:
    return AlignmentConsensus(
        sample_offset=None,
        score=score,
        applied=False,
        diagnostic=diagnostic,
        valid_windows=valid_windows,
        consensus_windows=consensus_windows,
        consensus_ratio=consensus_ratio,
        ambiguity_ratio=ambiguity_ratio,
        window_evidence=window_evidence,
        stability=stability,
    )


def rejected_analysis(
    diagnostic: str,
    *,
    config: AlignmentConfig,
    fps: Fraction,
) -> AlignmentConsensus:
    """Return a typed non-applied result before any windows can be analyzed."""
    stability = classify_alignment_stability((), sample_rate=config.sample_rate, fps=fps)
    result = _reject(
        diagnostic,
        score=0.0,
        valid_windows=0,
        consensus_windows=0,
        consensus_ratio=0.0,
        ambiguity_ratio=None,
        window_evidence=(),
        stability=stability,
    )
    return replace(
        result,
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason=diagnostic,
            raw_correlated_windows=0,
            consensus_windows=0,
            consensus_ratio=None,
            aggregate_score=None,
            minimum_peak_ratio=None,
            failed_gates=(diagnostic,),
            unassessed_gates=(
                "insufficient_valid_windows",
                "low_confidence",
                "insufficient_consensus",
                "ambiguous_correlation_peak",
            ),
        ),
    )


def analysis_budget_exceeded(*, config: AlignmentConfig, fps: Fraction) -> AlignmentConsensus:
    """Return the typed non-applied outcome for a request outside fixed work limits."""
    return rejected_analysis("analysis_budget_exceeded", config=config, fps=fps)


def _finish_consensus(
    candidates: list[CorrelationEstimate],
    candidate_ids: list[str],
    evidence: list[AlignmentWindowEvidence],
    window_records: list[AudioAlignmentWindowRecord],
    *,
    config: AlignmentConfig,
    fps: Fraction,
) -> AlignmentConsensus:
    window_evidence = tuple(sorted(evidence, key=lambda item: item.start_sample))
    stability = classify_alignment_stability(
        window_evidence,
        sample_rate=config.sample_rate,
        fps=fps,
    )

    if len(candidates) < config.minimum_valid_windows:
        result = _reject(
            "insufficient_valid_windows",
            score=0.0,
            valid_windows=len(candidates),
            consensus_windows=0,
            consensus_ratio=0.0,
            ambiguity_ratio=None,
            window_evidence=window_evidence,
            stability=stability,
        )
        return replace(
            result,
            window_records=tuple(window_records),
            decision=_review_decision(
                result, candidates, candidate_ids, window_records, config, fps
            ),
        )

    groups: dict[int, list[tuple[CorrelationEstimate, str]]] = {}
    for candidate, logical_id in zip(candidates, candidate_ids, strict=True):
        frame_offset = samples_to_frames(candidate.sample_offset, config.sample_rate, fps)
        groups.setdefault(frame_offset, []).append((candidate, logical_id))
    winning_group = max(
        groups.values(),
        key=lambda group: (len(group), max(candidate.score for candidate, _ in group)),
    )
    winner_count = len(winning_group)
    winner_offset = int(median_low(candidate.sample_offset for candidate, _ in winning_group))
    consensus_ratio = winner_count / len(candidates)
    winning_scores = [candidate.score for candidate, _ in winning_group]
    score = float(np.median(winning_scores))
    winning_peak_ratios = [candidate.peak_ratio for candidate, _ in winning_group]
    ambiguity_ratio = min(winning_peak_ratios)

    if score < config.confidence_threshold:
        result = _reject(
            "low_confidence",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
            window_evidence=window_evidence,
            stability=stability,
        )
        return replace(
            result,
            window_records=tuple(window_records),
            decision=_review_decision(
                result, candidates, candidate_ids, window_records, config, fps
            ),
        )

    if consensus_ratio < config.consensus_minimum_ratio:
        result = _reject(
            "insufficient_consensus",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
            window_evidence=window_evidence,
            stability=stability,
        )
        return replace(
            result,
            window_records=tuple(window_records),
            decision=_review_decision(
                result, candidates, candidate_ids, window_records, config, fps
            ),
        )

    if ambiguity_ratio < config.ambiguity_peak_ratio:
        result = _reject(
            "ambiguous_correlation_peak",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
            window_evidence=window_evidence,
            stability=stability,
        )
        return replace(
            result,
            window_records=tuple(window_records),
            decision=_review_decision(
                result, candidates, candidate_ids, window_records, config, fps
            ),
        )

    result = AlignmentConsensus(
        sample_offset=winner_offset,
        score=score,
        applied=True,
        diagnostic="accepted",
        valid_windows=len(candidates),
        consensus_windows=winner_count,
        consensus_ratio=consensus_ratio,
        ambiguity_ratio=ambiguity_ratio,
        window_evidence=window_evidence,
        stability=stability,
        window_records=tuple(window_records),
    )
    result = hold_automatic_consensus(result)
    return replace(
        result,
        decision=_review_decision(result, candidates, candidate_ids, window_records, config, fps),
    )


def _support_facts(
    *,
    reference_start: int,
    reference_count: int,
    comparison_start: int,
    comparison_count: int,
    planned_reference_start: int,
    planned_reference_count: int,
    planned_comparison_start: int,
    planned_comparison_count: int,
    requested_offset: int,
) -> tuple[int, int, int, float, Literal["complete", "short", "empty"]]:
    actual_start = max(reference_start, comparison_start + requested_offset)
    actual_end = min(
        reference_start + reference_count,
        comparison_start + comparison_count + requested_offset,
    )
    actual_end = max(actual_start, actual_end)
    expected_start = max(
        planned_reference_start,
        planned_comparison_start + requested_offset,
    )
    expected_end = min(
        planned_reference_start + planned_reference_count,
        planned_comparison_start + planned_comparison_count + requested_offset,
    )
    expected = max(0, expected_end - expected_start)
    actual = actual_end - actual_start
    coverage = actual / expected if expected else 0.0
    if reference_count == 0 or comparison_count == 0 or actual == 0:
        state = "empty"
    elif reference_count < planned_reference_count or comparison_count < planned_comparison_count:
        state = "short"
    else:
        state = "complete"
    return actual_start, actual_end, expected, min(1.0, coverage), state


def estimate_staged_consensus_offset(
    *,
    plan: AudioAnalysisPlan,
    config: AlignmentConfig,
    fps: Fraction,
    discovery_phase_loader: Callable[[], alignment_audio.CollectedAudioPhase],
    verification_phase_loader: Callable[
        [tuple[alignment_audio.AudioVerificationSpec, ...]], alignment_audio.CollectedAudioPhase
    ],
    verification_spec_builder: Callable[
        [tuple[tuple[int, Fraction], ...]], tuple[alignment_audio.AudioVerificationSpec, ...]
    ],
    cancellation: threading.Event | None = None,
) -> AlignmentConsensus:
    """Collect each phase once, then analyze its logical windows sequentially."""
    local_config = replace(config, sample_rate=plan.sample_rate)
    margin = math.ceil(config.max_offset_seconds * plan.sample_rate)
    requested_limit = int(config.max_offset_seconds * plan.requested_sample_rate)
    try:
        raise_if_alignment_cancelled(cancellation)
        discovery = discovery_phase_loader()
    except (AudioAlignmentCancellationError, AudioAlignmentCleanupError):
        raise
    except AudioAlignmentError as exc:
        window_records = tuple(
            AudioAlignmentWindowRecord(
                logical_id=f"primary-{index + 1:02d}",
                purpose="primary",
                attempt_number=1,
                parent_id=None,
                planned_reference_start=spec.reference_start_sample,
                planned_reference_count=spec.reference_sample_count,
                planned_comparison_start=spec.comparison_start_sample,
                planned_comparison_count=spec.comparison_sample_count,
                analysis_rate=plan.sample_rate,
                requested_rate=plan.requested_sample_rate,
                quality_disposition="rejected",
                terminal_stage=exc.stage,
                terminal_category=exc.category,
                failed_role=(
                    "reference"
                    if exc.role == "reference"
                    else "comparison"
                    if exc.role == "comparison"
                    else None
                ),
            )
            for index, spec in enumerate(plan.windows)
        )
        result = _finish_consensus(
            [],
            [],
            [],
            list(window_records),
            config=config,
            fps=fps,
        )
        return replace(result, collection_summaries=exc.collection_summaries)
    if len(discovery.windows) != len(plan.windows):
        raise ValueError("discovery collection does not match the admitted plan")

    staged: list[_StagedWindow] = []
    records: dict[int, AudioAlignmentWindowRecord] = {}
    for index, (spec, window) in enumerate(zip(plan.windows, discovery.windows, strict=True)):
        raise_if_alignment_cancelled(cancellation)
        logical_id = f"primary-{index + 1:02d}"
        reference_count = int(window.reference.size)
        comparison_count = int(window.comparison.size)
        try:
            origin_delta = window.reference_start_sample - window.comparison_start_sample
            estimate = estimate_alignment_offset(
                window.reference,
                window.comparison,
                config=local_config,
                alignment_offset_bounds_samples=(
                    -margin - origin_delta,
                    margin - origin_delta,
                ),
                cancellation=cancellation,
            )
            local_offset = (
                estimate.subsample_offset
                if estimate.subsample_offset is not None
                else estimate.sample_offset
            )
            exact_local_offset = Fraction(local_offset).limit_denominator(
                config.refinement_sample_rate or plan.sample_rate
            )
            staged.append(
                _StagedWindow(
                    index=index,
                    logical_id=logical_id,
                    spec=spec,
                    actual_reference_count=reference_count,
                    actual_comparison_count=comparison_count,
                    local_estimate=estimate,
                    local_lag=float(local_offset),
                    global_analysis_offset=exact_local_offset + origin_delta,
                )
            )
        except AudioAlignmentError as exc:
            records[index] = AudioAlignmentWindowRecord(
                logical_id=logical_id,
                purpose="primary",
                attempt_number=1,
                parent_id=None,
                planned_reference_start=spec.reference_start_sample,
                planned_reference_count=spec.reference_sample_count,
                planned_comparison_start=spec.comparison_start_sample,
                planned_comparison_count=spec.comparison_sample_count,
                analysis_rate=plan.sample_rate,
                requested_rate=plan.requested_sample_rate,
                actual_reference_count=reference_count,
                actual_comparison_count=comparison_count,
                discovery_reference_count=reference_count,
                discovery_comparison_count=comparison_count,
                quality_disposition="rejected",
                terminal_stage=exc.stage,
                terminal_category=exc.category,
                failed_role=(
                    "reference"
                    if exc.role == "reference"
                    else "comparison"
                    if exc.role == "comparison"
                    else None
                ),
            )
        del window

    summaries = discovery.summaries
    verification_failure: AudioAlignmentError | None = None
    verification_by_index: dict[int, tuple[alignment_audio.AudioVerificationSpec, AudioWindow]] = {}
    if plan.sample_rate != plan.requested_sample_rate and staged:
        frozen = verification_spec_builder(
            tuple((item.index, item.global_analysis_offset) for item in staged)
        )
        if frozen:
            # Dropping the last discovery owner before verification enforces the
            # phase-store lifetime even when the caller keeps no other reference.
            del discovery
            try:
                raise_if_alignment_cancelled(cancellation)
                verification = verification_phase_loader(frozen)
            except (AudioAlignmentCancellationError, AudioAlignmentCleanupError):
                raise
            except AudioAlignmentError as exc:
                summaries += exc.collection_summaries
                verification_failure = exc
                verification = None
            if verification is None:
                frozen = ()
            else:
                if len(verification.windows) != len(frozen):
                    raise ValueError("verification collection does not match its frozen plan")
                summaries += verification.summaries
                verification_by_index = {
                    spec.window_index: (spec, window)
                    for spec, window in zip(frozen, verification.windows, strict=True)
                }

    candidates: list[CorrelationEstimate] = []
    candidate_ids: list[str] = []
    evidence: list[AlignmentWindowEvidence] = []
    for item in staged:
        raise_if_alignment_cancelled(cancellation)
        spec = item.spec
        score = item.local_estimate.score
        requested_offset = round(item.global_analysis_offset)
        score_stage = "analysis_rate"
        scoring_reference_count: int | None = None
        scoring_comparison_count: int | None = None
        support_reference_start = spec.reference_start_sample
        support_reference_count = item.actual_reference_count
        support_comparison_start = spec.comparison_start_sample
        support_comparison_count = item.actual_comparison_count
        planned_reference_start = spec.reference_start_sample
        planned_reference_count = spec.reference_sample_count
        planned_comparison_start = spec.comparison_start_sample
        planned_comparison_count = spec.comparison_sample_count
        continuous_origin = "discovery"
        try:
            if plan.sample_rate != plan.requested_sample_rate:
                verified = verification_by_index.get(item.index)
                if verified is None:
                    if verification_failure is not None:
                        raise AudioAlignmentError(
                            str(verification_failure),
                            category=verification_failure.category,
                            stage=verification_failure.stage,
                            role=verification_failure.role,
                        )
                    raise AudioAlignmentError(
                        "candidate leaves no selected-stream audio overlap",
                        category="insufficient_overlap",
                        stage="scoring",
                    )
                verification_spec, window = verified
                scoring_reference_count = int(window.reference.size)
                scoring_comparison_count = int(window.comparison.size)
                origin_delta = window.reference_start_sample - window.comparison_start_sample
                correction, score = refine_aligned_score(
                    window.reference,
                    window.comparison,
                    preprocessing_mode=config.preprocessing_mode,
                    correction_bounds_samples=(
                        verification_spec.global_lower_offset - origin_delta,
                        verification_spec.global_upper_offset - origin_delta,
                    ),
                    cancellation=cancellation,
                )
                requested_offset = origin_delta + correction
                score_stage = "requested_rate"
                support_reference_start = window.reference_start_sample
                support_reference_count = scoring_reference_count
                support_comparison_start = window.comparison_start_sample
                support_comparison_count = scoring_comparison_count
                planned_reference_start = verification_spec.reference_start_sample
                planned_reference_count = verification_spec.reference_sample_count
                planned_comparison_start = verification_spec.comparison_start_sample
                planned_comparison_count = verification_spec.comparison_sample_count
                continuous_origin = "verification"
        except (AudioAlignmentCancellationError, AudioAlignmentCleanupError):
            raise
        except AudioAlignmentError as exc:
            records[item.index] = AudioAlignmentWindowRecord(
                logical_id=item.logical_id,
                purpose="primary",
                attempt_number=1,
                parent_id=None,
                planned_reference_start=spec.reference_start_sample,
                planned_reference_count=spec.reference_sample_count,
                planned_comparison_start=spec.comparison_start_sample,
                planned_comparison_count=spec.comparison_sample_count,
                analysis_rate=plan.sample_rate,
                requested_rate=plan.requested_sample_rate,
                actual_reference_count=item.actual_reference_count,
                actual_comparison_count=item.actual_comparison_count,
                scoring_reference_count=scoring_reference_count,
                scoring_comparison_count=scoring_comparison_count,
                discovery_reference_count=item.actual_reference_count,
                discovery_comparison_count=item.actual_comparison_count,
                verification_reference_count=scoring_reference_count,
                verification_comparison_count=scoring_comparison_count,
                quality_disposition="rejected",
                local_lag=item.local_lag,
                global_analysis_lag=float(item.global_analysis_offset),
                peak_ratio=_peak_value(item.local_estimate.peak_ratio),
                peak_stage="analysis_rate",
                peak_rate=plan.sample_rate,
                terminal_stage=exc.stage,
                terminal_category=exc.category,
                failed_role=(
                    "reference"
                    if exc.role == "reference"
                    else "comparison"
                    if exc.role == "comparison"
                    else None
                ),
            )
            continue

        useful_start, useful_end, expected, coverage, coverage_state = _support_facts(
            reference_start=support_reference_start,
            reference_count=support_reference_count,
            comparison_start=support_comparison_start,
            comparison_count=support_comparison_count,
            planned_reference_start=planned_reference_start,
            planned_reference_count=planned_reference_count,
            planned_comparison_start=planned_comparison_start,
            planned_comparison_count=planned_comparison_count,
            requested_offset=requested_offset,
        )
        if abs(requested_offset) > requested_limit:
            terminal_category = "offset_out_of_bounds"
            review_qualified = configured_quality = False
        else:
            terminal_category = "correlated"
            review_qualified = bool(
                math.isfinite(score)
                and score >= _REVIEW_SCORE_FLOOR
                and not math.isnan(item.local_estimate.peak_ratio)
                and item.local_estimate.peak_ratio >= _REVIEW_PEAK_RATIO_FLOOR
            )
            configured_quality = bool(
                score >= config.confidence_threshold
                and item.local_estimate.peak_ratio >= config.ambiguity_peak_ratio
            )
            estimate = CorrelationEstimate(requested_offset, score, item.local_estimate.peak_ratio)
            candidates.append(estimate)
            candidate_ids.append(item.logical_id)
            valid = _valid_evidence(
                estimate,
                start=planned_reference_start,
                end=planned_reference_start + planned_reference_count,
                config=config,
            )
            if valid is not None:
                evidence.append(valid)
        records[item.index] = AudioAlignmentWindowRecord(
            logical_id=item.logical_id,
            purpose="primary",
            attempt_number=1,
            parent_id=None,
            planned_reference_start=spec.reference_start_sample,
            planned_reference_count=spec.reference_sample_count,
            planned_comparison_start=spec.comparison_start_sample,
            planned_comparison_count=spec.comparison_sample_count,
            analysis_rate=plan.sample_rate,
            requested_rate=plan.requested_sample_rate,
            actual_reference_count=item.actual_reference_count,
            actual_comparison_count=item.actual_comparison_count,
            scoring_reference_count=scoring_reference_count,
            scoring_comparison_count=scoring_comparison_count,
            discovery_reference_count=item.actual_reference_count,
            discovery_comparison_count=item.actual_comparison_count,
            verification_reference_count=scoring_reference_count,
            verification_comparison_count=scoring_comparison_count,
            continuous_sample_count=useful_end - useful_start,
            continuous_sample_count_origin=continuous_origin,
            actual_useful_reference_start=useful_start,
            actual_useful_reference_end=useful_end,
            pre_eof_expected_overlap=expected,
            actual_coverage=coverage,
            coverage_state=coverage_state,
            quality_disposition="qualified" if review_qualified else "rejected",
            effective_aligned_overlap=useful_end - useful_start,
            local_lag=item.local_lag,
            global_analysis_lag=float(item.global_analysis_offset),
            requested_sample_lag=requested_offset,
            requested_frame_candidate=samples_to_frames(requested_offset, config.sample_rate, fps),
            requested_score=score,
            score_stage=score_stage,
            peak_ratio=_peak_value(item.local_estimate.peak_ratio),
            peak_stage="analysis_rate",
            peak_rate=plan.sample_rate,
            review_qualified=review_qualified,
            configured_quality=configured_quality,
            vote_disposition="voted" if terminal_category == "correlated" else "failed",
            terminal_stage="decision" if terminal_category == "correlated" else "scoring",
            terminal_category=terminal_category,
        )

    result = _finish_consensus(
        candidates,
        candidate_ids,
        evidence,
        [records[index] for index in range(len(plan.windows))],
        config=config,
        fps=fps,
    )
    return replace(result, collection_summaries=summaries)
