"""Literal presentation scenarios, independent of audio/video producers.

Producer parity tests in services keep these fixtures aligned with real output.
"""

from dataclasses import replace

from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAuthorityRecount,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioSameFrameContext,
    AudioStageOutcome,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from tests.services.alignment_evidence_test_support import attempt_with_chunks


def review_attempt(reason: str):
    base = attempt_with_chunks(4)
    alternate_lag = 81_000
    target_resolution = {
        "competing_offset_confirmed_by_video": "alternative_confirmed",
        "competing_offset": "unresolved",
        "unresolved_audio_disagreement": "unresolved",
    }.get(reason)
    chunks = replace(
        base.chunks,
        lags=(1177, 1177, alternate_lag, alternate_lag),
        agrees=(True, True, False, False),
    )
    runs = (
        AudioChunkRun(first_index=0, last_index=1, lag=1177, chunk_count=2),
        AudioChunkRun(first_index=2, last_index=3, lag=alternate_lag, chunk_count=2),
    )
    target = (
        (
            VideoTargetEvidence(
                kind="run",
                first_chunk_index=2,
                last_chunk_index=3,
                credible=True,
                start_sample=(2) * 240_000,
                end_sample=((3) + 1) * 240_000,
                target_offset=243,
                alternative_offsets=(242, 243, 244),
                resolution=target_resolution,  # type: ignore[arg-type]
                positions=(
                    VideoTargetPosition(
                        position_index=1,
                        reference_frame=13_123,
                        confirmed_score=1.0,
                        alternative_score=0.1,
                        winner=(
                            "alternative"
                            if reason == "competing_offset_confirmed_by_video"
                            else "neither"
                        ),
                        alternative_offset=(
                            243 if reason == "competing_offset_confirmed_by_video" else None
                        ),
                    ),
                ),
            ),
        )
        if target_resolution is not None
        else ()
    )
    video = (
        VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        )
        if reason == "video_check_unavailable"
        else VideoCheckObservation(
            observation="observed",
            scored_offsets=(144, 145, 146, 147, 148),
            confirmed_offset=(None if reason == "video_check_inconclusive" else 146),
            index_build_seconds=0.1,
            positions=(
                VideoPositionDifference(
                    position_index=0,
                    reference_frame=6_474,
                    score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
                ),
            ),
            targets=target,
            check_points=(
                VideoCheckPoint(3661.0, 13_123, 12_880),
                VideoCheckPoint(270.0, 6_474, 6_328),
            ),
        )
    )
    return replace(
        base,
        chunks=chunks,
        runs=runs,
        video_check=video,
        decision=replace(
            base.decision,
            state="provisional",
            primary_reason=reason,
            failed_gates=(reason,),
        ),
    )


def boundary_video_inconclusive_attempt(*, position_count: int = 6):
    attempt = review_attempt("video_check_inconclusive")
    positions = tuple(
        VideoPositionDifference(
            position_index=index,
            reference_frame=6_474 + index,
            score_by_offset=(2.0, 1.8, 1.4, 1.2, 0.1),
        )
        for index in range(position_count)
    )
    return replace(attempt, video_check=replace(attempt.video_check, positions=positions))


def singleton_chunk_target_attempt():
    attempt = review_attempt("unresolved_audio_disagreement")
    targets = (
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=0,
            last_chunk_index=0,
            credible=True,
            start_sample=(0) * 240_000,
            end_sample=((0) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="unexamined",
            positions=(),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=True,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=246,
            alternative_offsets=(245, 246, 247),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_000, 1.0, 1.0, "neither"),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 82_000, 1177),
            agrees=(True, False, False, True),
        ),
        runs=tuple(
            AudioChunkRun(first_index=index, last_index=index, lag=lag, chunk_count=1)
            for index, lag in enumerate((1177, 81_000, 82_000, 1177))
        ),
        video_check=replace(attempt.video_check, targets=targets),
    )


def production_nested_targets_attempt():
    attempt = review_attempt("competing_offset")
    targets = (
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=0,
            last_chunk_index=1,
            credible=True,
            start_sample=(0) * 240_000,
            end_sample=((1) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="unresolved",
            positions=(VideoTargetPosition(1, 9_000, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=False,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=246,
            alternative_offsets=(245, 246, 247),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_001, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=3,
            last_chunk_index=3,
            credible=True,
            start_sample=(3) * 240_000,
            end_sample=((3) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="alternative_confirmed",
            positions=(VideoTargetPosition(3, 9_002, 1.0, 0.1, "alternative", 250),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(81_000, 81_000, 82_000, 83_333),
            credible=(True, True, False, True),
            agrees=(False, False, False, False),
        ),
        runs=(AudioChunkRun(first_index=0, last_index=3, lag=81_000, chunk_count=3),),
        video_check=replace(attempt.video_check, targets=targets),
        decision=replace(
            attempt.decision,
            failed_gates=("competing_offset", "unresolved_audio_disagreement"),
        ),
    )


def multi_context_attempt():
    attempt = review_attempt("competing_offset_confirmed_by_video")
    return replace(
        attempt,
        audio=replace(attempt.audio, agreeing_chunks=2),
        authority_recount=AudioAuthorityRecount(
            raw_status="agreed",
            raw_agreeing_chunks=2,
            authority_status="agreed",
            authority_agreeing_chunks=4,
            passed=True,
        ),
        video_check=replace(
            attempt.video_check,
            same_frame_context=(
                AudioSameFrameContext(0, 1177, 146.23, 146),
                AudioSameFrameContext(1, 1177, 146.23, 146),
            ),
        ),
    )


def audio_failed_video_confirmed_attempt():
    attempt = review_attempt("video_check_inconclusive")
    return replace(
        attempt,
        audio=replace(attempt.audio, status="no_single_offset", agreeing_chunks=2),
        video_check=replace(attempt.video_check, confirmed_offset=146, targets=()),
        decision=replace(
            attempt.decision,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        ),
    )


def _zero_candidate() -> AudioDecisionCandidate:
    return AudioDecisionCandidate(0, 0.0, 0.0, "audio_only")


def _context_attempt(
    *,
    total: int,
    lags: tuple[int, ...],
    psrs: tuple[float, ...],
    credible: tuple[bool, ...],
    agrees: tuple[bool, ...],
    video: VideoCheckObservation,
    decision: AudioAlignmentDecision,
    runs: tuple[AudioChunkRun, ...] = (),
) -> AudioAlignmentAttempt:
    """Assemble the common literal zero-offset context used by these scenarios."""
    base = attempt_with_chunks(total)
    maximum = 3 if 1000 in lags else 2
    has_disagreement = any(c and not a for c, a in zip(credible, agrees, strict=True))
    return replace(
        base,
        fps_num=24,
        fps_den=1,
        analysis=AudioAnalysisFacts(8000, 1.0, 240000, 8000, total),
        chunks=AudioChunkColumns(
            starts=tuple(i * 240000 for i in range(total)),
            counts=(240000,) * total,
            active=(True,) * total,
            lags=lags,
            psrs=psrs,
            credible=credible,
            agrees=agrees,
            total_samples=total * 240000,
        ),
        runs=runs,
        audio=AudioStageOutcome("agreed", 0, total, sum(credible), sum(agrees), 0.0, 0.0, 0),
        video_check=video,
        decision=decision,
        stability=AlignmentStabilitySummary(
            "stable",
            sum(credible),
            0,
            maximum if has_disagreement else 0,
            0,
            0,
            maximum if has_disagreement else 0,
            None,
        ),
        authority_recount=AudioAuthorityRecount("agreed", sum(agrees), "agreed", sum(agrees), True),
    )


def target_context_attempt(*, credible: bool, resolution: str) -> AudioAlignmentAttempt:
    """One differing chunk with fixed video observations and expected decisions."""
    failures = {
        (True, "resolved"): (),
        (False, "resolved"): (),
        (True, "unresolved"): ("unresolved_audio_disagreement",),
        (False, "unresolved"): (),
        (True, "unexamined"): ("unresolved_audio_disagreement",),
        (False, "unexamined"): (),
        (True, "alternative_confirmed"): (
            "competing_offset_confirmed_by_video",
            "unresolved_audio_disagreement",
        ),
        (False, "alternative_confirmed"): ("competing_offset_confirmed_by_video",),
    }[credible, resolution]
    position = {
        "resolved": VideoTargetPosition(1, 1800, 0.1, 1.0, "confirmed"),
        "unresolved": VideoTargetPosition(1, 1800, 1.0, 1.0, "neither"),
        "alternative_confirmed": VideoTargetPosition(1, 1800, 1.0, 0.1, "alternative", 2),
    }.get(resolution)
    target = VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=2,
        last_chunk_index=2,
        credible=credible,
        start_sample=480000,
        end_sample=720000,
        target_offset=2,
        alternative_offsets=(1, 2, 3),
        resolution="local_video_inconclusive"
        if not credible and resolution == "unresolved"
        else resolution,  # type: ignore[arg-type]
        positions=() if position is None else (position,),
    )
    points = (
        ()
        if position is None
        else (VideoCheckPoint(75.0, 1800, 1800 if resolution == "resolved" else 1798),)
    )
    return _context_attempt(
        total=5,
        lags=(0, 0, 667, 0, 0),
        psrs=(30.0, 30.0, 30.0 if credible else 5.0, 30.0, 30.0),
        credible=(True, True, credible, True, True),
        agrees=(True, True, False, True, True),
        decision=AudioAlignmentDecision(
            "provisional" if failures else "trusted_automatic",
            _zero_candidate(),
            failures[0] if failures else "audio_video_confirmed",
            failures,
        ),
        video=VideoCheckObservation(
            observation="observed",
            scored_offsets=(-2, -1, 0, 1, 2),
            confirmed_offset=0,
            index_build_seconds=0.1,
            positions=(VideoPositionDifference(0, 1200, (2.0, 1.0, 0.1, 1.0, 2.0)),),
            targets=(target,),
            check_points=points + (VideoCheckPoint(50.0, 1200, 1200),),
        ),
    )


def resolved_run_context_attempt(
    *, shape: str = "run", resolutions: tuple[str, ...] = ("resolved",)
) -> AudioAlignmentAttempt:
    """Resolved run/chunk contexts with literal bounds, offsets, and checkpoint facts."""
    specs, total, runs = {
        "run": (((2, 3, 667, 2),), 10, ((0, 1, 0, 2), (2, 3, 667, 2), (4, 9, 0, 6))),
        "run_and_chunk": (
            ((2, 3, 667, 2), (7, 7, 1000, 3)),
            15,
            ((0, 1, 0, 2), (2, 3, 667, 2), (4, 6, 0, 3), (7, 7, 1000, 1), (8, 14, 0, 7)),
        ),
        "two_runs": (
            ((2, 3, 667, 2), (10, 11, 1000, 3)),
            20,
            ((0, 1, 0, 2), (2, 3, 667, 2), (4, 9, 0, 6), (10, 11, 1000, 2), (12, 19, 0, 8)),
        ),
    }[shape]
    if resolutions != ("resolved",) * len(specs):
        raise ValueError("literal run scenarios cover resolved contexts only")
    lags = {i: lag for first, last, lag, _offset in specs for i in range(first, last + 1)}
    targets = tuple(
        VideoTargetEvidence(
            kind="run" if first != last else "chunk",
            first_chunk_index=first,
            last_chunk_index=last,
            credible=True,
            start_sample=first * 240000,
            end_sample=(last + 1) * 240000,
            target_offset=offset,
            alternative_offsets=(offset - 1, offset, offset + 1),
            resolution="resolved",
            positions=tuple(
                VideoTargetPosition(p, 2000 + p, 0.1, 1.0, "confirmed")
                for p in ((1, 2) if index == 0 else (3,) if first == last else (3, 4))
            ),
        )
        for index, (first, last, _lag, offset) in enumerate(specs)
    )
    points = (VideoCheckPoint(83.375, 2001, 2001),)
    if len(specs) == 2:
        points += (VideoCheckPoint(83.45833333333333, 2003, 2003),)
    return _context_attempt(
        total=total,
        lags=tuple(lags.get(i, 0) for i in range(total)),
        psrs=tuple(40.0 - i / 100 for i in range(total)),
        credible=(True,) * total,
        agrees=tuple(i not in lags for i in range(total)),
        runs=tuple(AudioChunkRun(*run) for run in runs),
        decision=AudioAlignmentDecision(
            "trusted_automatic", _zero_candidate(), "audio_video_confirmed", ()
        ),
        video=VideoCheckObservation(
            observation="observed",
            scored_offsets=(-2, -1, 0, 1, 2),
            confirmed_offset=0,
            index_build_seconds=0.1,
            positions=(VideoPositionDifference(0, 1200, (2.0, 1.0, 0.1, 1.0, 2.0)),),
            targets=targets,
            check_points=points + (VideoCheckPoint(50.0, 1200, 1200),),
        ),
    )


def established_counts_attempt(
    *, planned: int, active: int, credible: int, agreeing: int
) -> AudioAlignmentAttempt:
    """Literal established-count examples with weak and quiet chunks kept distinct."""
    base = attempt_with_chunks(planned)
    return replace(
        base,
        fps_num=24,
        fps_den=1,
        analysis=AudioAnalysisFacts(8000, 1.0, 240000, 8000, planned),
        chunks=AudioChunkColumns(
            starts=tuple(i * 240000 for i in range(planned)),
            counts=(240000,) * planned,
            active=tuple(i < active for i in range(planned)),
            lags=tuple(0 if i < active else None for i in range(planned)),
            psrs=tuple(
                (30.0 if i < credible else 5.0) if i < active else None for i in range(planned)
            ),
            credible=tuple(i < credible for i in range(planned)),
            agrees=tuple(i < agreeing for i in range(planned)),
            total_samples=planned * 240000,
        ),
        runs=(),
        audio=AudioStageOutcome(
            "agreed" if active else "no_usable_audio",
            0 if active else None,
            active,
            credible,
            agreeing,
            0.0,
            0.0 if active else None,
            0 if active else None,
        ),
        decision=AudioAlignmentDecision(
            "provisional" if active else "unavailable",
            _zero_candidate() if active else None,
            "audio_only" if active else "no_usable_audio",
            () if active else ("no_usable_audio",),
        ),
        stability=AlignmentStabilitySummary(
            "stable" if credible else "insufficient_evidence",
            credible,
            0 if credible else None,
            0 if credible else None,
            0 if credible else None,
            0 if credible else None,
            0 if credible else None,
            None,
        ),
        authority_recount=None,
    )
