"""Video confirmation for whole-track audio alignment."""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np
import numpy.typing as npt

from frame_compare.services.alignment_correlation import ChunkObservation
from frame_compare.services.alignment_decision import classify_audio_observations
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    AudioAlignmentAttempt,
    AudioSameFrameContext,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from frame_compare.utils.types import AlignmentClipIdentity
from frame_compare.vs.loader import VSLoader

if TYPE_CHECKING:
    import vapoursynth as vs


VideoCheckReason = Literal[
    "cancelled",
    "no_global_audio_lag",
    "source_identity_changed",
    "video_check_unavailable",
]
ActiveRect = tuple[int, int, int, int]
FloatFrame = npt.NDArray[np.float32]

_FRAME_WIDTH = 320
_FRAME_HEIGHT = 180
_BASE_POSITION_COUNT = 12
_MIN_INFORMATIVE_POSITIONS = 6
_INFORMATIVE_MARGIN = 1.1
_CONFIRMATION_MARGIN = 1.5
_CONFIRMATION_FRACTION = 0.75
_TARGET_POSITION_LIMIT = 12


@dataclass(frozen=True, slots=True)
class VideoClipRequest:
    """Path, freshness identity, and resolved active rectangle for one source."""

    path: Path
    identity: AlignmentClipIdentity
    active_rect: ActiveRect | None = None


@dataclass(frozen=True, slots=True)
class VideoCheckResult:
    """Video evidence plus a non-throwing failure reason for the V6 owner."""

    observation: VideoCheckObservation
    reason: VideoCheckReason | None = None

    def __post_init__(self) -> None:
        if self.reason is None and self.observation.observation != "observed":
            raise ValueError("successful video checks must be observed")
        if self.reason is not None and self.observation.observation != "not_observed":
            raise ValueError("failed video checks must be unobserved")


@dataclass(frozen=True, slots=True)
class _Chunk:
    index: int
    start: int
    count: int
    active: bool
    lag: int | None
    psr: float | None
    credible: bool
    agrees: bool


@dataclass(frozen=True, slots=True)
class _Target:
    kind: Literal["chunk", "run"]
    first_index: int
    last_index: int
    lag: int
    start_sample: int
    end_sample: int
    requested_positions: int


def sample_to_reference_frame(
    sample_index: int,
    *,
    fps_reference: Fraction,
    audio_start_reference: Fraction,
    video_start_reference: Fraction,
) -> int:
    """Map an 8 kHz reference PCM sample to its raw reference video frame."""
    if sample_index < 0:
        raise ValueError("sample_index must be non-negative")
    timestamp = (
        Fraction(sample_index, AUDIO_ANALYSIS_SAMPLE_RATE)
        + audio_start_reference
        - video_start_reference
    )
    return math.floor(timestamp * fps_reference)


def check_video_alignment(
    *,
    reference: VideoClipRequest,
    comparison: VideoClipRequest,
    attempt: AudioAlignmentAttempt,
    fps_reference: Fraction,
    loader: VSLoader | None,
    cancellation: Event | None = None,
) -> VideoCheckResult:
    """Run V1-V5 and return bounded W0 evidence without throwing runtime failures."""
    global_lag = attempt.audio.global_lag
    rounded_frame = attempt.audio.rounded_frame
    if global_lag is None or rounded_frame is None:
        return _failed("no_global_audio_lag")
    if loader is None:
        return _failed("video_check_unavailable")
    if _is_cancelled(cancellation):
        return _failed("cancelled")
    if not _identities_match(reference) or not _identities_match(comparison):
        return _failed("source_identity_changed")

    load_started = time.monotonic()
    try:
        reference_source = loader.load(reference.path)
        if _is_cancelled(cancellation):
            return _failed("cancelled")
        if not _identities_match(reference):
            return _failed("source_identity_changed")

        comparison_source = loader.load(comparison.path)
        if _is_cancelled(cancellation):
            return _failed("cancelled")
        if not _identities_match(comparison):
            return _failed("source_identity_changed")
        if not _identities_match(reference) or not _identities_match(comparison):
            return _failed("source_identity_changed")

        reference_node = _prepare_luma(reference_source.clip, reference.active_rect)
        comparison_node = _prepare_luma(comparison_source.clip, comparison.active_rect)
        overlap = _frame_overlap(
            reference_source.num_frames,
            comparison_source.num_frames,
            tuple(range(rounded_frame - 2, rounded_frame + 3)),
        )
        if overlap is None:
            return _failed("video_check_unavailable")
        positions = _base_positions(overlap)
        if not positions:
            return _failed("video_check_unavailable")
        scored_offsets = tuple(range(rounded_frame - 2, rounded_frame + 3))
        scored_positions = _score_base_positions(
            reference_node,
            comparison_node,
            positions,
            scored_offsets,
            cancellation=cancellation,
        )
        if scored_positions is None:
            return _failed(
                "cancelled" if _is_cancelled(cancellation) else "video_check_unavailable"
            )
        base_positions, winners, margins = scored_positions
        confirmed = _confirmed_offset(
            rounded_frame,
            winners,
            margins,
        )
        index_build_seconds = time.monotonic() - load_started
        if confirmed is None:
            return VideoCheckResult(
                observation=VideoCheckObservation(
                    observation="observed",
                    scored_offsets=scored_offsets,
                    confirmed_offset=None,
                    index_build_seconds=index_build_seconds,
                    positions=tuple(base_positions),
                    check_points=_base_check_points(
                        base_positions,
                        suggested_offset=rounded_frame,
                        fps_reference=fps_reference,
                    ),
                )
            )

        starts = _stream_start(attempt, role="reference", video=False)
        video_starts = _stream_start(attempt, role="reference", video=True)
        reference_audio_start, reference_video_start = starts, video_starts
        chunks = _chunks(attempt)
        targets, same_frame = _build_targets(
            attempt,
            chunks,
            confirmed=confirmed,
            fps_reference=fps_reference,
        )
        target_evidence: list[VideoTargetEvidence] = []
        remaining = _TARGET_POSITION_LIMIT
        next_position_index = len(base_positions)
        for target in targets:
            desired = _target_frames(
                target,
                fps_reference=fps_reference,
                audio_start_reference=reference_audio_start,
                video_start_reference=reference_video_start,
                alternative_frame=_lag_to_frame(
                    target.lag,
                    attempt=attempt,
                    fps_reference=fps_reference,
                ),
                confirmed=confirmed,
                reference_frame_count=reference_source.num_frames,
                comparison_frame_count=comparison_source.num_frames,
            )
            selected = desired[:remaining]
            if selected:
                alternative_frame = _lag_to_frame(
                    target.lag,
                    attempt=attempt,
                    fps_reference=fps_reference,
                )
                alternative_offsets = tuple(
                    offset
                    for offset in range(alternative_frame - 1, alternative_frame + 2)
                    if offset != confirmed
                )
                positions_for_target: list[VideoTargetPosition] = []
                for frame in selected:
                    if _is_cancelled(cancellation):
                        return _failed("cancelled")
                    if not _identities_match(reference) or not _identities_match(comparison):
                        return _failed("source_identity_changed")
                    scored = _score_hypotheses(
                        reference_node,
                        comparison_node,
                        frame,
                        confirmed,
                        alternative_offsets,
                    )
                    if scored is None:
                        return _failed("video_check_unavailable")
                    confirmed_score, alternative_score = scored
                    winner = _hypothesis_winner(confirmed_score, alternative_score)
                    position = VideoTargetPosition(
                        position_index=next_position_index,
                        reference_frame=frame,
                        confirmed_score=confirmed_score,
                        alternative_score=alternative_score,
                        winner=winner,
                    )
                    positions_for_target.append(position)
                    next_position_index += 1
                remaining -= len(positions_for_target)
                resolution = _target_resolution(target.kind, positions_for_target)
                target_evidence.append(
                    VideoTargetEvidence(
                        kind=target.kind,
                        first_chunk_index=target.first_index,
                        last_chunk_index=target.last_index,
                        alternative_offsets=alternative_offsets,
                        resolution=resolution,
                        positions=tuple(positions_for_target),
                    )
                )
            else:
                alternative_frame = _lag_to_frame(
                    target.lag,
                    attempt=attempt,
                    fps_reference=fps_reference,
                )
                alternative_offsets = tuple(
                    offset
                    for offset in range(alternative_frame - 1, alternative_frame + 2)
                    if offset != confirmed
                )
                target_evidence.append(
                    VideoTargetEvidence(
                        kind=target.kind,
                        first_chunk_index=target.first_index,
                        last_chunk_index=target.last_index,
                        alternative_offsets=alternative_offsets,
                        resolution="unexamined",
                        positions=(),
                    )
                )

        check_points = _check_points(
            base_positions,
            target_evidence,
            confirmed=confirmed,
            scored_offsets=scored_offsets,
            fps_reference=fps_reference,
            chunks=chunks,
        )
        return VideoCheckResult(
            observation=VideoCheckObservation(
                observation="observed",
                scored_offsets=scored_offsets,
                confirmed_offset=confirmed,
                index_build_seconds=index_build_seconds,
                positions=tuple(base_positions),
                targets=tuple(target_evidence),
                same_frame_context=tuple(same_frame),
                check_points=check_points,
            )
        )
    except Exception:
        return _failed("video_check_unavailable")


def _failed(reason: VideoCheckReason) -> VideoCheckResult:
    return VideoCheckResult(
        observation=VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        reason=reason,
    )


def _is_cancelled(cancellation: Event | None) -> bool:
    return cancellation is not None and cancellation.is_set()


def _identities_match(clip: VideoClipRequest) -> bool:
    try:
        stat = clip.path.stat()
        return clip.path.resolve() == clip.identity.path.resolve() and (
            stat.st_size == clip.identity.size_bytes and stat.st_mtime_ns == clip.identity.mtime_ns
        )
    except OSError:
        return False


def _prepare_luma(clip: vs.VideoNode, active_rect: ActiveRect | None) -> vs.VideoNode:
    import vapoursynth as vs

    runtime_vs = cast(Any, vs)
    runtime_clip = cast(Any, clip)
    if clip.format.color_family != vs.YUV:
        runtime_clip = runtime_clip.resize.Bicubic(format=runtime_vs.YUV444P8)
    luma = cast(
        "vs.VideoNode",
        runtime_clip.std.ShufflePlanes(planes=0, colorfamily=runtime_vs.GRAY),
    )
    if active_rect is not None:
        x, y, width, height = active_rect
        luma = cast(Any, luma).std.CropAbs(width=width, height=height, left=x, top=y)
    return cast(Any, luma).resize.Bilinear(width=_FRAME_WIDTH, height=_FRAME_HEIGHT)


def _frame_overlap(
    reference_frames: int,
    comparison_frames: int,
    offsets: Sequence[int],
) -> tuple[int, int] | None:
    start = max(0, max(offsets))
    end = min(reference_frames - 1, *(comparison_frames - 1 + offset for offset in offsets))
    return (start, end) if start <= end else None


def _evenly_spaced(start: float | int, end: float | int, count: int) -> tuple[int, ...]:
    if count < 1 or end < start:
        return ()
    if count == 1:
        return (round((start + end) / 2),)
    values = [round(start + (end - start) * index / (count - 1)) for index in range(count)]
    return tuple(dict.fromkeys(values))


def _base_positions(overlap: tuple[int, int]) -> tuple[int, ...]:
    start, end = overlap
    span = end - start
    return _evenly_spaced(start + span * 0.05, start + span * 0.95, _BASE_POSITION_COUNT)


def _score_base_positions(
    reference_node: vs.VideoNode,
    comparison_node: vs.VideoNode,
    positions: Sequence[int],
    offsets: Sequence[int],
    *,
    cancellation: Event | None,
) -> tuple[list[VideoPositionDifference], list[int | None], list[float]] | None:
    evidence: list[VideoPositionDifference] = []
    winners: list[int | None] = []
    margins: list[float] = []
    for position_index, reference_frame in enumerate(positions):
        if _is_cancelled(cancellation):
            return None
        try:
            reference_image = _read_frame(reference_node, reference_frame)
            scores = tuple(
                _frame_difference(
                    reference_image,
                    _read_frame(comparison_node, reference_frame - offset),
                )
                for offset in offsets
            )
        except Exception:
            return None
        winner, margin = _position_winner(scores, offsets)
        evidence.append(
            VideoPositionDifference(
                position_index=position_index,
                reference_frame=reference_frame,
                score_by_offset=scores,
            )
        )
        winners.append(winner)
        margins.append(margin)
    return evidence, winners, margins


def _read_frame(node: vs.VideoNode, frame: int) -> FloatFrame:
    if frame < 0 or frame >= node.num_frames:
        raise IndexError("video frame is outside the source")
    raw = node.get_frame(frame)
    try:
        image = np.asarray(raw[0], dtype=np.float32).copy()
    finally:
        del raw
    if image.size == 0 or not bool(np.all(np.isfinite(image))):
        raise ValueError("video frame contains non-finite luma")
    return image


def _average_ranks(values: FloatFrame) -> FloatFrame:
    flat = values.reshape(-1)
    order = np.argsort(flat, kind="stable")
    ranks = np.empty(flat.size, dtype=np.float32)
    start = 0
    while start < order.size:
        end = start + 1
        while end < order.size and flat[order[end]] == flat[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    return np.asarray((ranks / flat.size).reshape(values.shape), dtype=np.float32)


def _frame_difference(reference: FloatFrame, comparison: FloatFrame) -> float:
    return float(np.mean(np.abs(_average_ranks(reference) - _average_ranks(comparison))))


def _position_winner(scores: Sequence[float], offsets: Sequence[int]) -> tuple[int | None, float]:
    best_index = min(range(len(scores)), key=scores.__getitem__)
    if best_index == 0 or best_index == len(scores) - 1:
        return None, 0.0
    best = scores[best_index]
    if not best < scores[best_index - 1] or not best < scores[best_index + 1]:
        return None, 0.0
    runner_up = min(score for index, score in enumerate(scores) if index != best_index)
    if best == 0.0:
        return (offsets[best_index], math.inf) if runner_up > 0.0 else (None, 0.0)
    margin = runner_up / best
    if margin < _INFORMATIVE_MARGIN:
        return None, 0.0
    return offsets[best_index], margin


def _confirmed_offset(
    rounded_frame: int,
    winners: Sequence[int | None],
    margins: Sequence[float],
) -> int | None:
    informative = [
        (winner, margin)
        for winner, margin in zip(winners, margins, strict=True)
        if winner is not None
    ]
    if len(informative) < _MIN_INFORMATIVE_POSITIONS:
        return None
    candidates = tuple(range(rounded_frame - 1, rounded_frame + 2))
    counts = {
        candidate: sum(winner == candidate for winner, _ in informative) for candidate in candidates
    }
    best_count = max(counts.values())
    best = [candidate for candidate, count in counts.items() if count == best_count]
    if len(best) != 1 or best_count / len(informative) < _CONFIRMATION_FRACTION:
        return None
    winning_margins = [margin for winner, margin in informative if winner == best[0]]
    if float(np.median(winning_margins)) < _CONFIRMATION_MARGIN:
        return None
    return best[0]


def _stream_start(
    attempt: AudioAlignmentAttempt,
    *,
    role: Literal["reference", "comparison"],
    video: bool,
) -> Fraction:
    stream = next(item for item in attempt.selected_streams if item.role == role)
    if video:
        return Fraction(stream.video_start_num, stream.video_start_den)
    return Fraction(stream.stream_start_num, stream.stream_start_den)


def _chunks(attempt: AudioAlignmentAttempt) -> tuple[_Chunk, ...]:
    columns = attempt.chunks
    return tuple(
        _Chunk(*values)
        for values in zip(
            range(len(columns.starts)),
            columns.starts,
            columns.counts,
            columns.active,
            columns.lags,
            tuple(None if psr == "unbounded" else psr for psr in columns.psrs),
            columns.credible,
            columns.agrees,
            strict=True,
        )
    )


def _lag_to_frame(lag: int, *, attempt: AudioAlignmentAttempt, fps_reference: Fraction) -> int:
    return math.floor(_lag_to_subframe(lag, attempt=attempt, fps_reference=fps_reference) + 0.5)


def _lag_to_subframe(lag: int, *, attempt: AudioAlignmentAttempt, fps_reference: Fraction) -> float:
    compensation = _compensation_seconds(attempt)
    return float((Fraction(lag, AUDIO_ANALYSIS_SAMPLE_RATE) + compensation) * fps_reference)


def _compensation_seconds(attempt: AudioAlignmentAttempt) -> Fraction:
    return (
        _stream_start(attempt, role="reference", video=False)
        - _stream_start(attempt, role="reference", video=True)
        - _stream_start(attempt, role="comparison", video=False)
        + _stream_start(attempt, role="comparison", video=True)
    )


def _build_targets(
    attempt: AudioAlignmentAttempt,
    chunks: tuple[_Chunk, ...],
    *,
    confirmed: int,
    fps_reference: Fraction,
) -> tuple[tuple[_Target, ...], tuple[AudioSameFrameContext, ...]]:
    global_lag = attempt.audio.global_lag
    if global_lag is None:
        return (), ()
    by_index = {chunk.index: chunk for chunk in chunks}
    observations = tuple(
        ChunkObservation(
            index=chunk.index,
            reference_start=chunk.start,
            reference_count=chunk.count,
            active=chunk.active,
            lag=chunk.lag,
            psr=chunk.psr,
            credible=chunk.credible,
            agrees=chunk.agrees,
        )
        for chunk in chunks
    )
    classification = classify_audio_observations(
        observations=observations,
        global_lag=attempt.audio.global_lag,
        confirmed_offset=confirmed,
        fps_reference=fps_reference,
        compensation_seconds=float(_compensation_seconds(attempt)),
    )
    run_targets: list[_Target] = []
    run_members: set[int] = set()
    for run in classification.competing_runs:
        members = [by_index.get(index) for index in range(run.first_index, run.last_index + 1)]
        if any(member is None or member.lag is None for member in members):
            continue
        valid_members = [member for member in members if member is not None]
        run_members.update(range(run.first_index, run.last_index + 1))
        run_targets.append(
            _Target(
                kind="run",
                first_index=run.first_index,
                last_index=run.last_index,
                lag=run.lag,
                start_sample=valid_members[0].start,
                end_sample=valid_members[-1].start + valid_members[-1].count - 1,
                requested_positions=4,
            )
        )

    credible_targets: list[_Target] = []
    noncredible_targets: list[_Target] = []
    for item in classification.credible_disagreements:
        chunk = by_index.get(item.index)
        if chunk is None or chunk.lag is None or chunk.index in run_members:
            continue
        credible_targets.append(
            _Target(
                kind="chunk",
                first_index=chunk.index,
                last_index=chunk.index,
                lag=chunk.lag,
                start_sample=chunk.start,
                end_sample=chunk.start + chunk.count - 1,
                requested_positions=4,
            )
        )
    for item in classification.noncredible_disagreements:
        chunk = by_index.get(item.index)
        if chunk is None or chunk.lag is None or chunk.index in run_members:
            continue
        if chunk.active:
            noncredible_targets.append(
                _Target(
                    kind="chunk",
                    first_index=chunk.index,
                    last_index=chunk.index,
                    lag=chunk.lag,
                    start_sample=chunk.start,
                    end_sample=chunk.start + chunk.count - 1,
                    requested_positions=2,
                )
            )
    credible_targets.sort(key=lambda target: -(by_index[target.first_index].psr or 0.0))
    noncredible_targets.sort(key=lambda target: -(by_index[target.first_index].psr or 0.0))
    return (
        (*run_targets, *credible_targets, *noncredible_targets),
        classification.same_frame_context,
    )


def _target_frames(
    target: _Target,
    *,
    fps_reference: Fraction,
    audio_start_reference: Fraction,
    video_start_reference: Fraction,
    alternative_frame: int,
    confirmed: int,
    reference_frame_count: int,
    comparison_frame_count: int,
) -> tuple[int, ...]:
    offsets = tuple(
        offset
        for offset in range(alternative_frame - 1, alternative_frame + 2)
        if offset != confirmed
    )
    overlap = _frame_overlap(reference_frame_count, comparison_frame_count, (confirmed, *offsets))
    if overlap is None:
        return ()
    start = max(
        overlap[0],
        sample_to_reference_frame(
            target.start_sample,
            fps_reference=fps_reference,
            audio_start_reference=audio_start_reference,
            video_start_reference=video_start_reference,
        ),
    )
    end = min(
        overlap[1],
        sample_to_reference_frame(
            target.end_sample,
            fps_reference=fps_reference,
            audio_start_reference=audio_start_reference,
            video_start_reference=video_start_reference,
        ),
    )
    return _evenly_spaced(start, end, target.requested_positions)


def _score_hypotheses(
    reference_node: vs.VideoNode,
    comparison_node: vs.VideoNode,
    reference_frame: int,
    confirmed: int,
    alternative_offsets: Sequence[int],
) -> tuple[float, float] | None:
    try:
        reference_image = _read_frame(reference_node, reference_frame)
        confirmed_score = _frame_difference(
            reference_image,
            _read_frame(comparison_node, reference_frame - confirmed),
        )
        alternative_score = min(
            _frame_difference(
                reference_image, _read_frame(comparison_node, reference_frame - offset)
            )
            for offset in alternative_offsets
        )
    except Exception:
        return None
    return confirmed_score, alternative_score


def _hypothesis_winner(
    confirmed_score: float, alternative_score: float
) -> Literal["confirmed", "alternative", "neither"]:
    if confirmed_score == alternative_score:
        return "neither"
    if confirmed_score == 0.0:
        return "confirmed" if alternative_score > 0.0 else "neither"
    if alternative_score == 0.0:
        return "alternative" if confirmed_score > 0.0 else "neither"
    if (
        confirmed_score < alternative_score
        and alternative_score / confirmed_score >= _CONFIRMATION_MARGIN
    ):
        return "confirmed"
    if (
        alternative_score < confirmed_score
        and confirmed_score / alternative_score >= _CONFIRMATION_MARGIN
    ):
        return "alternative"
    return "neither"


def _target_resolution(
    kind: Literal["chunk", "run"], positions: Sequence[VideoTargetPosition]
) -> Literal["resolved", "unresolved", "alternative_confirmed"]:
    winners = [position.winner for position in positions]
    if "alternative" in winners:
        return "alternative_confirmed"
    required = 2 if kind == "run" else 1
    if winners.count("confirmed") >= required:
        return "resolved"
    return "unresolved"


def _check_points(
    base_positions: Sequence[VideoPositionDifference],
    targets: Sequence[VideoTargetEvidence],
    *,
    confirmed: int,
    scored_offsets: Sequence[int],
    fps_reference: Fraction,
    chunks: Sequence[_Chunk] = (),
) -> tuple[VideoCheckPoint, ...]:
    points: list[VideoCheckPoint] = []
    selected_base_positions: set[int] = set()
    selected_points: set[tuple[int, int]] = set()
    chunks_by_index = {chunk.index: chunk for chunk in chunks}

    def target_bounds(target: VideoTargetEvidence) -> tuple[int, int]:
        members = [
            chunks_by_index.get(index)
            for index in range(target.first_chunk_index, target.last_chunk_index + 1)
        ]
        if members and all(member is not None for member in members):
            present = [member for member in members if member is not None]
            return present[0].start, present[-1].start + present[-1].count
        return target.first_chunk_index, target.last_chunk_index + 1

    def target_psr(target: VideoTargetEvidence) -> float:
        values = [
            member.psr
            for index in range(target.first_chunk_index, target.last_chunk_index + 1)
            if (member := chunks_by_index.get(index)) is not None and member.psr is not None
        ]
        return max(values, default=float("-inf"))

    candidates = [
        (
            *target_bounds(target),
            target.alternative_offsets[0],
            (
                "confirmed by video"
                if target.resolution in {"resolved", "alternative_confirmed"}
                else "not checked"
                if target.resolution == "unexamined"
                else "not settled"
            ),
            order,
            target_psr(target),
            target,
        )
        for order, target in enumerate(targets)
        if target.positions
    ]
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1], candidate[5]))
    grouped: list[list[tuple[int, int, int, str, int, float, VideoTargetEvidence]]] = []
    for candidate in candidates:
        if grouped:
            previous = grouped[-1]
            previous_end = max(item[1] for item in previous)
            if (
                candidate[0] <= previous_end
                and candidate[2] == previous[0][2]
                and candidate[3] == previous[0][3]
            ):
                previous.append(candidate)
                continue
        grouped.append([candidate])
    target_regions = [
        max(region, key=lambda candidate: (candidate[5], -candidate[4]))[6]
        for region in grouped[:4]
    ]

    def add_point(reference_frame: int, suggested: int) -> bool:
        key = (reference_frame, suggested)
        if key in selected_points:
            return False
        points.append(
            VideoCheckPoint(
                timestamp_seconds=reference_frame / float(fps_reference),
                reference_frame=reference_frame,
                suggested_comparison_frame=max(0, reference_frame - suggested),
            )
        )
        selected_points.add(key)
        return True

    def add_target_point(target: VideoTargetEvidence, position: VideoTargetPosition) -> None:
        suggested = confirmed if position.winner == "confirmed" else target.alternative_offsets[0]
        add_point(position.reference_frame, suggested)

    def add_confirmed_point(position: VideoPositionDifference) -> bool:
        winner, _margin = _position_winner(
            position.score_by_offset,
            scored_offsets,
        )
        if winner != confirmed:
            return False
        if position.position_index in selected_base_positions:
            return False
        inserted = add_point(position.reference_frame, confirmed)
        if not inserted:
            return False
        selected_base_positions.add(position.position_index)
        return True

    for target in target_regions:
        add_target_point(target, target.positions[0])

    if len(points) < 5:
        for position in base_positions:
            if add_confirmed_point(position):
                break

    for target in target_regions:
        for position in target.positions[1:]:
            if len(points) >= 5:
                break
            add_target_point(target, position)
        if len(points) >= 5:
            break

    if len(points) < 5:
        for position in base_positions:
            if len(points) >= 5:
                break
            add_confirmed_point(position)
    return tuple(points)


def _base_check_points(
    positions: Sequence[VideoPositionDifference],
    *,
    suggested_offset: int,
    fps_reference: Fraction,
) -> tuple[VideoCheckPoint, ...]:
    return tuple(
        VideoCheckPoint(
            timestamp_seconds=position.reference_frame / float(fps_reference),
            reference_frame=position.reference_frame,
            suggested_comparison_frame=max(0, position.reference_frame - suggested_offset),
        )
        for position in positions[:5]
    )


__all__ = [
    "ActiveRect",
    "VideoCheckReason",
    "VideoCheckResult",
    "VideoClipRequest",
    "check_video_alignment",
    "sample_to_reference_frame",
]
