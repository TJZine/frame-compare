"""Video confirmation for whole-track audio alignment."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np
import numpy.typing as npt

from frame_compare.services.alignment_correlation import ChunkObservation
from frame_compare.services.alignment_decision import (
    classify_audio_observations,
    competing_run_center,
)
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    AudioSameFrameContext,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from frame_compare.utils.alignment_policy import (
    CONFIRMATION_MARGIN,
    compensated_lag_to_frame,
    sample_to_reference_frame,
)
from frame_compare.utils.alignment_policy import (
    confirmed_offset as _confirmed_offset,
)
from frame_compare.utils.alignment_policy import (
    position_winner as _position_winner,
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
class _Target:
    kind: Literal["chunk", "run"]
    first_index: int
    last_index: int
    lag: float
    credible: bool
    start_sample: int
    end_sample: int
    requested_positions: int


type _TargetKey = tuple[Literal["chunk", "run"], int, int]


@dataclass(frozen=True, slots=True)
class _CheckPointTarget:
    start: int
    end: int
    offset: int
    status: str
    order: int
    psr: float
    points: tuple[tuple[int, int], ...]


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

    try:
        load_started = time.monotonic()
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
        index_build_seconds = time.monotonic() - load_started
    except Exception:
        return _failed("video_check_unavailable")

    try:
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
        planned_target_frames: dict[_TargetKey, tuple[int, ...]] = {}
        remaining = _TARGET_POSITION_LIMIT
        next_position_index = len(base_positions)
        for target in targets:
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
            desired = _target_frames(
                target,
                fps_reference=fps_reference,
                audio_start_reference=reference_audio_start,
                video_start_reference=reference_video_start,
                alternative_frame=alternative_frame,
                confirmed=confirmed,
                reference_frame_count=reference_source.num_frames,
                comparison_frame_count=comparison_source.num_frames,
            )
            planned_target_frames[(target.kind, target.first_index, target.last_index)] = desired
            selected = desired[:remaining]
            positions_for_target: list[VideoTargetPosition] = []
            if selected:
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
                    confirmed_score, alternative_score, alternative_offset = scored
                    winner = _hypothesis_winner(
                        confirmed_score,
                        alternative_score,
                        alternative_offset=alternative_offset,
                    )
                    position = VideoTargetPosition(
                        position_index=next_position_index,
                        reference_frame=frame,
                        confirmed_score=confirmed_score,
                        alternative_score=alternative_score,
                        winner=winner,
                        alternative_offset=alternative_offset,
                    )
                    positions_for_target.append(position)
                    next_position_index += 1
                remaining -= len(positions_for_target)
                resolution = _target_resolution(
                    target.kind,
                    positions_for_target,
                    credible=target.credible,
                )
            else:
                resolution = "unexamined"
            target_evidence.append(
                VideoTargetEvidence(
                    kind=target.kind,
                    first_chunk_index=target.first_index,
                    last_chunk_index=target.last_index,
                    credible=target.credible,
                    start_sample=target.start_sample,
                    end_sample=target.end_sample,
                    target_offset=alternative_frame,
                    alternative_offsets=alternative_offsets,
                    resolution=resolution,
                    positions=tuple(positions_for_target),
                )
            )

        check_points = _check_points(
            base_positions,
            target_evidence,
            confirmed=confirmed,
            scored_offsets=scored_offsets,
            fps_reference=fps_reference,
            chunks=chunks,
            planned_target_frames=planned_target_frames,
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
    except ValueError:
        raise
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


def _chunks(attempt: AudioAlignmentAttempt) -> tuple[ChunkObservation, ...]:
    columns = attempt.chunks
    return tuple(
        ChunkObservation(*values)
        for values in zip(
            range(len(columns.starts)),
            columns.starts,
            columns.counts,
            columns.active,
            columns.lags,
            tuple(math.inf if psr == "unbounded" else psr for psr in columns.psrs),
            columns.credible,
            columns.agrees,
            strict=True,
        )
    )


def _lag_to_frame(
    lag: int | float, *, attempt: AudioAlignmentAttempt, fps_reference: Fraction
) -> int:
    return compensated_lag_to_frame(
        lag,
        compensation_seconds=float(_compensation_seconds(attempt)),
        fps_reference=fps_reference,
    )


def _compensation_seconds(attempt: AudioAlignmentAttempt) -> Fraction:
    return (
        _stream_start(attempt, role="reference", video=False)
        - _stream_start(attempt, role="reference", video=True)
        - _stream_start(attempt, role="comparison", video=False)
        + _stream_start(attempt, role="comparison", video=True)
    )


def _build_targets(
    attempt: AudioAlignmentAttempt,
    chunks: tuple[ChunkObservation, ...],
    *,
    confirmed: int,
    fps_reference: Fraction,
) -> tuple[tuple[_Target, ...], tuple[AudioSameFrameContext, ...]]:
    global_lag = attempt.audio.global_lag
    if global_lag is None:
        return (), ()
    by_index = {chunk.index: chunk for chunk in chunks}
    classification = classify_audio_observations(
        observations=chunks,
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
                lag=competing_run_center(run, chunks),
                credible=True,
                start_sample=valid_members[0].reference_start,
                end_sample=(valid_members[-1].reference_start + valid_members[-1].reference_count),
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
                credible=True,
                start_sample=chunk.reference_start,
                end_sample=chunk.reference_start + chunk.reference_count,
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
                    credible=False,
                    start_sample=chunk.reference_start,
                    end_sample=chunk.reference_start + chunk.reference_count,
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
            target.end_sample - 1,
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
) -> tuple[float, float, int | None] | None:
    try:
        reference_image = _read_frame(reference_node, reference_frame)
        confirmed_score = _frame_difference(
            reference_image,
            _read_frame(comparison_node, reference_frame - confirmed),
        )
        alternative_scores = tuple(
            (
                offset,
                _frame_difference(
                    reference_image,
                    _read_frame(comparison_node, reference_frame - offset),
                ),
            )
            for offset in alternative_offsets
        )
    except Exception:
        return None
    alternative_score = min(score for _offset, score in alternative_scores)
    winning_offsets = [offset for offset, score in alternative_scores if score == alternative_score]
    return (
        confirmed_score,
        alternative_score,
        winning_offsets[0] if len(winning_offsets) == 1 else None,
    )


def _hypothesis_winner(
    confirmed_score: float,
    alternative_score: float,
    *,
    alternative_offset: int | None,
) -> Literal["confirmed", "alternative", "neither"]:
    if confirmed_score == alternative_score:
        return "neither"
    if confirmed_score == 0.0:
        return "confirmed" if alternative_score > 0.0 else "neither"
    if alternative_score == 0.0:
        return (
            "alternative" if confirmed_score > 0.0 and alternative_offset is not None else "neither"
        )
    if (
        confirmed_score < alternative_score
        and alternative_score / confirmed_score >= CONFIRMATION_MARGIN
    ):
        return "confirmed"
    if (
        alternative_score < confirmed_score
        and confirmed_score / alternative_score >= CONFIRMATION_MARGIN
    ):
        return "alternative" if alternative_offset is not None else "neither"
    return "neither"


def _target_resolution(
    kind: Literal["chunk", "run"],
    positions: Sequence[VideoTargetPosition],
    *,
    credible: bool,
) -> Literal["resolved", "unresolved", "alternative_confirmed", "local_video_inconclusive"]:
    winners = [position.winner for position in positions]
    if "alternative" in winners:
        return "alternative_confirmed"
    required = 2 if kind == "run" else 1
    if winners.count("confirmed") >= required:
        return "resolved"
    if not credible and "neither" in winners:
        return "local_video_inconclusive"
    return "unresolved"


def _check_points(
    base_positions: Sequence[VideoPositionDifference],
    targets: Sequence[VideoTargetEvidence],
    *,
    confirmed: int,
    scored_offsets: Sequence[int],
    fps_reference: Fraction,
    chunks: Sequence[ChunkObservation] = (),
    planned_target_frames: Mapping[_TargetKey, Sequence[int]] | None = None,
) -> tuple[VideoCheckPoint, ...]:
    points: list[VideoCheckPoint] = []
    selected_base_positions: set[int] = set()
    selected_points: set[tuple[int, int]] = set()
    chunks_by_index = {chunk.index: chunk for chunk in chunks}

    def target_psr(target: VideoTargetEvidence) -> float:
        values = [
            member.psr
            for index in range(target.first_chunk_index, target.last_chunk_index + 1)
            if (member := chunks_by_index.get(index)) is not None and member.psr is not None
        ]
        return max(values, default=float("-inf"))

    def target_points(target: VideoTargetEvidence) -> tuple[tuple[int, int], ...]:
        if target.resolution == "unexamined":
            if planned_target_frames is None:
                return ()
            key = (target.kind, target.first_chunk_index, target.last_chunk_index)
            return tuple(
                (frame, target.target_offset) for frame in planned_target_frames.get(key, ())
            )[:1]
        preferred_winner = {
            "resolved": "confirmed",
            "alternative_confirmed": "alternative",
            "unresolved": "neither",
            "local_video_inconclusive": "neither",
        }[target.resolution]
        preferred = tuple(
            position for position in target.positions if position.winner == preferred_winner
        )
        remaining = tuple(
            position for position in target.positions if position.winner != preferred_winner
        )
        return tuple(
            (
                position.reference_frame,
                (
                    confirmed
                    if position.winner == "confirmed"
                    else position.alternative_offset or target.target_offset
                ),
            )
            for position in (*preferred, *remaining)
        )

    def target_offset(target: VideoTargetEvidence) -> int:
        if target.resolution == "resolved":
            return confirmed
        if target.resolution == "alternative_confirmed":
            winners = {
                position.alternative_offset
                for position in target.positions
                if position.winner == "alternative"
            }
            if len(winners) == 1:
                return next(iter(winners)) or target.target_offset
        return target.target_offset

    candidates: list[_CheckPointTarget] = []
    for order, target in enumerate(targets):
        target_check_points = target_points(target)
        if not target_check_points:
            continue
        candidates.append(
            _CheckPointTarget(
                start=target.start_sample,
                end=target.end_sample,
                offset=target_offset(target),
                status=(
                    "confirmed by video"
                    if target.resolution in {"resolved", "alternative_confirmed"}
                    else "not checked"
                    if target.resolution == "unexamined"
                    else "not settled"
                ),
                order=order,
                psr=target_psr(target),
                points=target_check_points,
            )
        )
    candidates.sort(key=lambda candidate: (candidate.start, candidate.end, candidate.order))
    grouped: list[list[_CheckPointTarget]] = []
    for candidate in candidates:
        if grouped:
            previous = grouped[-1]
            previous_end = max(item.end for item in previous)
            if (
                candidate.start <= previous_end
                and candidate.offset == previous[0].offset
                and candidate.status == previous[0].status
            ):
                previous.append(candidate)
                continue
        grouped.append([candidate])
    target_regions = [
        sorted(region, key=lambda candidate: (-candidate.psr, candidate.order))
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

    for region in target_regions:
        represented = False
        for candidate in region:
            for frame, offset in candidate.points:
                if add_point(frame, offset):
                    represented = True
                    break
            if represented:
                break

    if len(points) < 5:
        for position in base_positions:
            if add_confirmed_point(position):
                break

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
]
