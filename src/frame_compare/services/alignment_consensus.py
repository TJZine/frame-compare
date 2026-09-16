"""Windowed consensus and gating for computed audio alignment."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from statistics import median_low

import numpy as np

from frame_compare.services.alignment_audio import AudioAnalysisPlan, AudioWindow, AudioWindowSpec
from frame_compare.services.alignment_correlation import (
    CorrelationEstimate,
    estimate_alignment_offset,
    refine_aligned_score,
)
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.alignment_stability import classify_alignment_stability
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    AlignmentStabilitySummary,
    AlignmentWindowEvidence,
    AudioAlignmentAttempt,
    AudioAlignmentCandidate,
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


def estimate_planned_consensus_offset(
    *,
    plan: AudioAnalysisPlan,
    config: AlignmentConfig,
    fps: Fraction,
    analysis_window_loader: Callable[[AudioWindowSpec], AudioWindow],
    scoring_window_loader: Callable[[AudioWindowSpec, int], AudioWindow],
) -> AlignmentConsensus:
    """Analyze planned windows sequentially and score fallback lags at the requested rate."""
    local_config = replace(config, sample_rate=plan.sample_rate)
    margin = math.ceil(config.max_offset_seconds * plan.sample_rate)
    requested_limit = int(config.max_offset_seconds * plan.requested_sample_rate)
    candidates: list[CorrelationEstimate] = []
    candidate_ids: list[str] = []
    evidence: list[AlignmentWindowEvidence] = []
    window_records: list[AudioAlignmentWindowRecord] = []
    for index, spec in enumerate(plan.windows, start=1):
        logical_id = f"primary-{index:02d}"
        actual_reference_count: int | None = None
        actual_comparison_count: int | None = None
        scoring_reference_count: int | None = None
        scoring_comparison_count: int | None = None
        local_lag: float | None = None
        global_analysis_lag: float | None = None
        requested_offset: int | None = None
        score: float | None = None
        peak_ratio: float | None = None
        score_stage: str | None = None
        scoring_started = False
        try:
            window: AudioWindow | None = None
            try:
                window = analysis_window_loader(spec)
                actual_reference_count = int(window.reference.size)
                actual_comparison_count = int(window.comparison.size)
                origin_delta = window.reference_start_sample - window.comparison_start_sample
                local_estimate = estimate_alignment_offset(
                    window.reference,
                    window.comparison,
                    config=local_config,
                    alignment_offset_bounds_samples=(
                        -margin - origin_delta,
                        margin - origin_delta,
                    ),
                )
                local_offset = (
                    local_estimate.subsample_offset
                    if local_estimate.subsample_offset is not None
                    else local_estimate.sample_offset
                )
                local_lag = float(local_offset)
                global_analysis_offset = local_offset + origin_delta
                global_analysis_lag = float(global_analysis_offset)
                peak_ratio = local_estimate.peak_ratio
            finally:
                del window

            score = local_estimate.score
            score_stage = "analysis_rate"
            if plan.sample_rate != plan.requested_sample_rate:
                scoring_window: AudioWindow | None = None
                try:
                    scoring_started = True
                    scoring_window = scoring_window_loader(spec, round(global_analysis_offset))
                    scoring_reference_count = int(scoring_window.reference.size)
                    scoring_comparison_count = int(scoring_window.comparison.size)
                    scoring_origin_delta = (
                        scoring_window.reference_start_sample
                        - scoring_window.comparison_start_sample
                    )
                    correction_radius = math.ceil(plan.requested_sample_rate / plan.sample_rate)
                    correction, score = refine_aligned_score(
                        scoring_window.reference,
                        scoring_window.comparison,
                        preprocessing_mode=config.preprocessing_mode,
                        correction_bounds_samples=(
                            max(-correction_radius, -requested_limit - scoring_origin_delta),
                            min(correction_radius, requested_limit - scoring_origin_delta),
                        ),
                    )
                    requested_offset = scoring_origin_delta + correction
                    score_stage = "requested_rate"
                finally:
                    del scoring_window
            else:
                requested_offset = round(global_analysis_offset)
        except AudioAlignmentError as exc:
            if scoring_started:
                scoring_reference_count = (
                    exc.reference_sample_count
                    if exc.reference_sample_count is not None
                    else scoring_reference_count
                )
                scoring_comparison_count = (
                    exc.comparison_sample_count
                    if exc.comparison_sample_count is not None
                    else scoring_comparison_count
                )
            else:
                actual_reference_count = (
                    exc.reference_sample_count
                    if exc.reference_sample_count is not None
                    else actual_reference_count
                )
                actual_comparison_count = (
                    exc.comparison_sample_count
                    if exc.comparison_sample_count is not None
                    else actual_comparison_count
                )
            window_records.append(
                AudioAlignmentWindowRecord(
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
                    actual_reference_count=actual_reference_count,
                    actual_comparison_count=actual_comparison_count,
                    scoring_reference_count=scoring_reference_count,
                    scoring_comparison_count=scoring_comparison_count,
                    local_lag=local_lag,
                    global_analysis_lag=global_analysis_lag,
                    requested_score=score,
                    score_stage=score_stage,
                    peak_ratio=_peak_value(peak_ratio) if peak_ratio is not None else None,
                    peak_stage="analysis_rate" if peak_ratio is not None else None,
                    peak_rate=plan.sample_rate if peak_ratio is not None else None,
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
            )
            continue

        assert requested_offset is not None
        assert score is not None
        if abs(requested_offset) > requested_limit:
            window_records.append(
                AudioAlignmentWindowRecord(
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
                    actual_reference_count=actual_reference_count,
                    actual_comparison_count=actual_comparison_count,
                    scoring_reference_count=scoring_reference_count,
                    scoring_comparison_count=scoring_comparison_count,
                    local_lag=local_lag,
                    global_analysis_lag=global_analysis_lag,
                    requested_sample_lag=requested_offset,
                    requested_score=score,
                    score_stage=score_stage,
                    peak_ratio=_peak_value(peak_ratio),
                    peak_stage="analysis_rate",
                    peak_rate=plan.sample_rate,
                    terminal_stage="scoring",
                    terminal_category="offset_out_of_bounds",
                )
            )
            continue

        estimate = CorrelationEstimate(
            sample_offset=requested_offset,
            score=score,
            peak_ratio=local_estimate.peak_ratio,
        )
        candidates.append(estimate)
        candidate_ids.append(logical_id)
        review_qualified = bool(
            math.isfinite(score)
            and score >= _REVIEW_SCORE_FLOOR
            and not math.isnan(local_estimate.peak_ratio)
            and local_estimate.peak_ratio >= _REVIEW_PEAK_RATIO_FLOOR
        )
        configured_quality = bool(
            score >= config.confidence_threshold
            and local_estimate.peak_ratio >= config.ambiguity_peak_ratio
        )
        window_records.append(
            AudioAlignmentWindowRecord(
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
                actual_reference_count=actual_reference_count,
                actual_comparison_count=actual_comparison_count,
                scoring_reference_count=scoring_reference_count,
                scoring_comparison_count=scoring_comparison_count,
                effective_aligned_overlap=min(
                    scoring_reference_count or actual_reference_count or 0,
                    scoring_comparison_count or actual_comparison_count or 0,
                ),
                local_lag=local_lag,
                global_analysis_lag=global_analysis_lag,
                requested_sample_lag=requested_offset,
                requested_frame_candidate=samples_to_frames(
                    requested_offset,
                    config.sample_rate,
                    fps,
                ),
                requested_score=score,
                score_stage=score_stage,
                peak_ratio=_peak_value(local_estimate.peak_ratio),
                peak_stage="analysis_rate",
                peak_rate=plan.sample_rate,
                review_qualified=review_qualified,
                configured_quality=configured_quality,
                vote_disposition="voted",
                terminal_stage="decision",
                terminal_category="correlated",
            )
        )
        valid = _valid_evidence(
            estimate,
            start=round(
                spec.reference_start_sample * plan.requested_sample_rate / plan.sample_rate
            ),
            end=round(
                (spec.reference_start_sample + spec.reference_sample_count)
                * plan.requested_sample_rate
                / plan.sample_rate
            ),
            config=config,
        )
        if valid is not None:
            evidence.append(valid)
    return _finish_consensus(
        candidates,
        candidate_ids,
        evidence,
        window_records,
        config=config,
        fps=fps,
    )
