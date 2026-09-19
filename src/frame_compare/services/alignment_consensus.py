"""Windowed consensus and gating for computed audio alignment."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import combinations
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


def _peak_value(value: float) -> AudioPeakRatio | None:
    if value == float("inf"):
        return "unbounded"
    return value if math.isfinite(value) else None


def _candidate_record(
    members: list[tuple[CorrelationEstimate, str]],
    *,
    sample_rate: int,
    fps: Fraction,
) -> AudioAlignmentCandidate:
    sample_offset = int(median_low(estimate.sample_offset for estimate, _ in members))
    peak_ratio = min(estimate.peak_ratio for estimate, _ in members)
    encoded_peak_ratio = _peak_value(peak_ratio)
    if encoded_peak_ratio is None:
        raise ValueError("candidate peak ratio is missing or non-finite")
    return AudioAlignmentCandidate(
        sample_offset=sample_offset,
        sample_rate=sample_rate,
        frame_offset=samples_to_frames(sample_offset, sample_rate, fps),
        supporting_window_ids=tuple(logical_id for _, logical_id in members),
        median_score=float(np.median([estimate.score for estimate, _ in members])),
        minimum_peak_ratio=encoded_peak_ratio,
    )


def _peak_passes(value: float, floor: float) -> bool:
    return value == float("inf") or math.isfinite(value) and value >= floor


def _record_has_integrity(record: AudioAlignmentWindowRecord) -> bool:
    if record.actual_reference_count is None or record.actual_comparison_count is None:
        return False
    if record.actual_reference_count <= 0 or record.actual_comparison_count <= 0:
        return False
    if record.effective_aligned_overlap is None or record.effective_aligned_overlap < 3:
        return False
    if record.actual_useful_reference_start is None or record.actual_useful_reference_end is None:
        return False
    if record.actual_useful_reference_end <= record.actual_useful_reference_start:
        return False
    if record.actual_coverage is None or record.coverage_state == "not_observed":
        return False
    if record.score_stage == "requested_rate":
        return (
            record.scoring_reference_count is not None
            and record.scoring_comparison_count is not None
            and record.scoring_reference_count > 0
            and record.scoring_comparison_count > 0
        )
    return record.score_stage == "analysis_rate" and record.analysis_rate == record.requested_rate


def _collection_integrity(
    summaries: tuple[AudioAlignmentCollectionRecord, ...],
    *,
    require_verification: bool,
) -> bool:
    if not summaries:
        return False
    keys = {(summary.phase, summary.role) for summary in summaries}
    required_phases = {"discovery"}
    if require_verification:
        required_phases.add("verification")
    return (
        len(keys) == len(summaries)
        and all(
            summary.status == "complete"
            and summary.end_category in {"planned_end_reached", "observed_eof"}
            and summary.cleanup_failure_count == 0
            and summary.failure_count == 0
            and 0 <= summary.emitted_sample_count <= summary.requested_horizon
            for summary in summaries
        )
        and all({(phase, "reference"), (phase, "comparison")} <= keys for phase in required_phases)
    )


def _frame_boundary_crossed(
    lower: int,
    upper: int,
    *,
    sample_rate: int,
    fps: Fraction,
) -> bool:
    if lower >= upper:
        return False
    return samples_to_frames(lower, sample_rate, fps) != samples_to_frames(upper, sample_rate, fps)


def _is_exact_half_frame(sample_offset: int, *, sample_rate: int, fps: Fraction) -> bool:
    frame_position = Fraction(sample_offset * fps, sample_rate)
    remainder = frame_position - frame_position.numerator // frame_position.denominator
    return remainder == Fraction(1, 2)


def _minimum_independent_count(
    duration_samples: int,
    *,
    sample_rate: int,
    config: AlignmentConfig,
) -> int:
    tier_minimum = (
        1
        if duration_samples <= 30 * sample_rate
        else 2
        if duration_samples < 90 * sample_rate
        else 3
    )
    return max(config.minimum_valid_windows, tier_minimum)


def _independent_support(
    records: list[AudioAlignmentWindowRecord],
    voting_ids: set[str],
    *,
    config: AlignmentConfig,
    sample_rate: int,
    reference_duration: int,
    comparison_duration: int,
    offsets: dict[str, int],
) -> tuple[tuple[str, ...], int]:
    intervals = sorted(
        (
            record.actual_useful_reference_start,
            record.actual_useful_reference_end,
            record.logical_id,
        )
        for record in records
        if record.logical_id in voting_ids
        and record.actual_useful_reference_start is not None
        and record.actual_useful_reference_end is not None
    )
    if not intervals:
        return (), 0
    if len(intervals) > 16:
        return (), 0

    duration_samples = min(reference_duration, comparison_duration)
    required_count = _minimum_independent_count(
        duration_samples,
        sample_rate=sample_rate,
        config=config,
    )
    if duration_samples <= 30 * sample_rate:
        early_limit = None
        late_limit = None
        require_full_source = True
    elif duration_samples < 90 * sample_rate:
        early_limit = duration_samples / 3
        late_limit = 2 * duration_samples / 3
        require_full_source = False
    else:
        early_limit = duration_samples / 3
        late_limit = 2 * duration_samples / 3
        require_full_source = False

    selected: tuple[str, ...] = ()
    for subset_size in range(1, len(intervals) + 1):
        for subset in combinations(intervals, subset_size):
            if any(left[1] > right[0] for left, right in zip(subset, subset[1:], strict=False)):
                continue
            if selected or subset_size < required_count:
                continue
            if early_limit is not None and subset[0][0] > early_limit:
                continue
            if late_limit is not None and subset[-1][1] < late_limit:
                continue
            if require_full_source and not any(
                (item[1] - item[0]) * 10
                >= 9
                * max(
                    0,
                    min(
                        reference_duration,
                        comparison_duration + offsets[item[2]],
                    )
                    - max(0, offsets[item[2]]),
                )
                for item in subset
            ):
                continue
            selected = tuple(item[2] for item in subset)
    return selected, len(selected)


def _review_decision(
    result: AlignmentConsensus,
    candidates: list[CorrelationEstimate],
    candidate_ids: list[str],
    window_records: list[AudioAlignmentWindowRecord],
    config: AlignmentConfig,
    fps: Fraction,
    *,
    qualified_winning_ids: set[str],
) -> AudioAlignmentDecision:
    members = list(zip(candidates, candidate_ids, strict=True))
    failed_gates: tuple[str, ...] = ()
    unassessed_gates: tuple[str, ...] = ()
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
        accepted_members = [item for item in members if item[1] in qualified_winning_ids]
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
            credible_windows=result.credible_windows,
            voting_windows=result.voting_windows,
            winning_windows=result.consensus_windows,
            independent_windows=result.independent_windows,
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
            credible_windows=result.credible_windows,
            voting_windows=result.voting_windows,
            winning_windows=result.consensus_windows,
            independent_windows=result.independent_windows,
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
            credible_windows=result.credible_windows,
            voting_windows=result.voting_windows,
            winning_windows=result.consensus_windows,
            independent_windows=result.independent_windows,
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
        credible_windows=result.credible_windows,
        voting_windows=result.voting_windows,
        winning_windows=result.consensus_windows,
        independent_windows=result.independent_windows,
        failed_gates=failed_gates,
        unassessed_gates=unassessed_gates,
    )


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
    credible_windows: int = 0
    voting_windows: int = 0
    independent_windows: int = 0


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
    collection_summaries: tuple[AudioAlignmentCollectionRecord, ...] = (),
    boundary_guard_ids: set[str] | None = None,
    search_edge_ids: set[str] | None = None,
    source_duration_samples: tuple[int, int] = (0, 0),
    source_sample_rate: int | None = None,
) -> AlignmentConsensus:
    window_evidence = tuple(sorted(evidence, key=lambda item: item.start_sample))
    stability = classify_alignment_stability(
        window_evidence,
        sample_rate=config.sample_rate,
        fps=fps,
    )
    requires_verification = any(record.score_stage == "requested_rate" for record in window_records)
    gate_i = _collection_integrity(
        collection_summaries,
        require_verification=requires_verification,
    )
    estimates = dict(zip(candidate_ids, candidates, strict=True))
    configured_score_floor = max(_REVIEW_SCORE_FLOOR, config.confidence_threshold)
    configured_peak_floor = max(_REVIEW_PEAK_RATIO_FLOOR, config.ambiguity_peak_ratio)
    credible_ids: set[str] = set()
    voting_ids: set[str] = set()
    updated_records: list[AudioAlignmentWindowRecord] = []
    for record in window_records:
        estimate = estimates.get(record.logical_id)
        credible = False
        voting = False
        if estimate is not None:
            credible = (
                gate_i
                and _record_has_integrity(record)
                and math.isfinite(estimate.score)
                and estimate.score >= _REVIEW_SCORE_FLOOR
                and _peak_passes(estimate.peak_ratio, _REVIEW_PEAK_RATIO_FLOOR)
            )
            voting = (
                credible
                and record.actual_coverage is not None
                and record.actual_coverage >= 0.90
                and estimate.score >= configured_score_floor
                and _peak_passes(estimate.peak_ratio, configured_peak_floor)
            )
        if credible:
            credible_ids.add(record.logical_id)
        if voting:
            voting_ids.add(record.logical_id)
        if estimate is not None:
            updated_records.append(
                replace(
                    record,
                    quality_disposition="qualified" if credible else "rejected",
                    review_qualified=credible,
                    configured_quality=voting,
                    vote_disposition=("voted" if voting else "abstained" if credible else "failed"),
                )
            )
        else:
            updated_records.append(record)
    window_records = updated_records

    def group_by_frame(ids: set[str]) -> dict[int, list[tuple[CorrelationEstimate, str]]]:
        groups: dict[int, list[tuple[CorrelationEstimate, str]]] = {}
        for logical_id in candidate_ids:
            if logical_id not in ids:
                continue
            estimate = estimates[logical_id]
            frame = samples_to_frames(estimate.sample_offset, config.sample_rate, fps)
            groups.setdefault(frame, []).append((estimate, logical_id))
        return groups

    credible_groups = group_by_frame(credible_ids)
    voting_groups = group_by_frame(voting_ids)

    def ordered_groups(
        groups: dict[int, list[tuple[CorrelationEstimate, str]]],
    ) -> list[list[tuple[CorrelationEstimate, str]]]:
        return sorted(
            groups.values(),
            key=lambda group: (-len(group), -max(item[0].score for item in group), group[0][1]),
        )

    credible_ordered = ordered_groups(credible_groups)
    voting_ordered = ordered_groups(voting_groups)
    credible_winner = credible_ordered[0] if credible_ordered else []
    voting_winner = voting_ordered[0] if voting_ordered else []
    winner_count = len(voting_winner)
    consensus_ratio = winner_count / len(voting_ids) if voting_ids else 0.0
    diagnostic_group = voting_winner or credible_winner
    score = (
        float(np.median([candidate.score for candidate, _ in diagnostic_group]))
        if diagnostic_group
        else 0.0
    )
    diagnostic_peaks = [
        candidate.peak_ratio
        for candidate, _ in diagnostic_group
        if _peak_passes(candidate.peak_ratio, 0.0)
    ]
    ambiguity_ratio = min(diagnostic_peaks) if diagnostic_peaks else None
    boundary_guard_ids = boundary_guard_ids or set()
    search_edge_ids = search_edge_ids or set()
    winning_ids = {logical_id for _, logical_id in voting_winner}
    support_phase = (
        "verification"
        if any(
            record.logical_id in winning_ids and record.score_stage == "requested_rate"
            for record in window_records
        )
        else "discovery"
    )
    support_summaries = [
        summary for summary in collection_summaries if summary.phase == support_phase
    ]
    reference_summary = next(
        (summary for summary in support_summaries if summary.role == "reference"),
        None,
    )
    comparison_summary = next(
        (summary for summary in support_summaries if summary.role == "comparison"),
        None,
    )
    support_rate = (
        reference_summary.output_rate if reference_summary is not None else config.sample_rate
    )
    duration_rate = source_sample_rate or (
        next((record.analysis_rate for record in window_records), support_rate)
    )
    if all(source_duration_samples):
        reference_duration = round(
            Fraction(source_duration_samples[0] * support_rate, duration_rate)
        )
        comparison_duration = round(
            Fraction(source_duration_samples[1] * support_rate, duration_rate)
        )
    else:
        reference_duration = (
            reference_summary.requested_horizon if reference_summary is not None else 0
        )
        comparison_duration = (
            comparison_summary.requested_horizon if comparison_summary is not None else 0
        )
    _, independent_count = _independent_support(
        window_records,
        winning_ids,
        config=config,
        sample_rate=support_rate,
        reference_duration=reference_duration,
        comparison_duration=comparison_duration,
        offsets={logical_id: estimates[logical_id].sample_offset for logical_id in winning_ids},
    )
    failed: list[str] = []
    if not gate_i:
        failed.append("extraction_integrity")
    if not voting_ids:
        failed.append("no_voting_windows")
    elif len(voting_ids) < config.minimum_valid_windows:
        failed.append("insufficient_valid_windows")
    if credible_winner and any(
        samples_to_frames(estimate.sample_offset, config.sample_rate, fps)
        != samples_to_frames(credible_winner[0][0].sample_offset, config.sample_rate, fps)
        for estimate, _ in ((estimates[logical_id], logical_id) for logical_id in credible_ids)
    ):
        failed.append("credible_contradiction")
    if voting_ids and consensus_ratio < config.consensus_minimum_ratio:
        failed.append("insufficient_consensus")
    required_independent_count = _minimum_independent_count(
        min(reference_duration, comparison_duration),
        sample_rate=support_rate,
        config=config,
    )
    if independent_count < required_independent_count:
        failed.append("insufficient_independent_support")
    boundary_count = len(boundary_guard_ids & voting_ids)
    search_edge_count = len(search_edge_ids & voting_ids)
    if boundary_count:
        failed.append("frame_boundary_guard")
    if search_edge_count:
        failed.append("search_edge_guard")
    if ambiguity_ratio is not None and not _peak_passes(ambiguity_ratio, configured_peak_floor):
        failed.append("ambiguous_correlation_peak")

    # A base-credible estimate in another frame bin is a hard veto, regardless
    # of whether stricter configured thresholds excluded it from voting.
    contradiction = "credible_contradiction" in failed
    temporal_ok = "insufficient_independent_support" not in failed
    quality_ok = (
        bool(voting_winner)
        and len(voting_ids) >= config.minimum_valid_windows
        and consensus_ratio >= config.consensus_minimum_ratio
        and not contradiction
        and temporal_ok
        and not boundary_count
        and not search_edge_count
        and ambiguity_ratio is not None
        and _peak_passes(ambiguity_ratio, configured_peak_floor)
    )
    accepted = gate_i and quality_ok
    winner_offset = (
        int(median_low(candidate.sample_offset for candidate, _ in voting_winner))
        if voting_winner
        else None
    )
    diagnostic = "accepted" if accepted else (failed[0] if failed else "no_usable_windows")
    result = AlignmentConsensus(
        sample_offset=winner_offset if accepted else None,
        score=score,
        applied=accepted,
        diagnostic=diagnostic,
        valid_windows=len(candidates),
        consensus_windows=winner_count,
        consensus_ratio=consensus_ratio,
        ambiguity_ratio=ambiguity_ratio,
        window_evidence=window_evidence,
        stability=stability,
        window_records=tuple(window_records),
        credible_windows=len(credible_ids),
        voting_windows=len(voting_ids),
        independent_windows=independent_count,
    )
    if accepted:
        result = hold_automatic_consensus(result)
    decision = _review_decision(
        result,
        candidates,
        candidate_ids,
        window_records,
        config,
        fps,
        qualified_winning_ids=winning_ids,
    )
    decision = replace(
        decision,
        failed_gates=tuple(dict.fromkeys((*failed, *decision.failed_gates))),
        independent_windows=independent_count,
        winning_windows=winner_count,
    )
    return replace(result, decision=decision)


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
            collection_summaries=exc.collection_summaries,
            source_duration_samples=(
                plan.reference_duration_samples,
                plan.comparison_duration_samples,
            ),
            source_sample_rate=plan.sample_rate,
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
    boundary_guard_ids: set[str] = set()
    search_edge_ids: set[str] = set()
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
                correction_bounds = (
                    verification_spec.global_lower_offset - origin_delta,
                    verification_spec.global_upper_offset - origin_delta,
                )
                correction, score = refine_aligned_score(
                    window.reference,
                    window.comparison,
                    preprocessing_mode=config.preprocessing_mode,
                    correction_bounds_samples=correction_bounds,
                    cancellation=cancellation,
                )
                requested_offset = origin_delta + correction
                score_stage = "requested_rate"
                if correction in correction_bounds or abs(requested_offset) >= requested_limit:
                    search_edge_ids.add(item.logical_id)
                if _is_exact_half_frame(
                    requested_offset,
                    sample_rate=config.sample_rate,
                    fps=fps,
                ) or _frame_boundary_crossed(
                    verification_spec.global_lower_offset,
                    verification_spec.global_upper_offset,
                    sample_rate=config.sample_rate,
                    fps=fps,
                ):
                    boundary_guard_ids.add(item.logical_id)
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
            if abs(requested_offset) >= requested_limit or _is_exact_half_frame(
                requested_offset,
                sample_rate=config.sample_rate,
                fps=fps,
            ):
                if abs(requested_offset) >= requested_limit:
                    search_edge_ids.add(item.logical_id)
                if _is_exact_half_frame(
                    requested_offset,
                    sample_rate=config.sample_rate,
                    fps=fps,
                ):
                    boundary_guard_ids.add(item.logical_id)
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
        collection_summaries=summaries,
        boundary_guard_ids=boundary_guard_ids,
        search_edge_ids=search_edge_ids,
        source_duration_samples=(
            plan.reference_duration_samples,
            plan.comparison_duration_samples,
        ),
        source_sample_rate=plan.sample_rate,
    )
    return replace(result, collection_summaries=summaries)
