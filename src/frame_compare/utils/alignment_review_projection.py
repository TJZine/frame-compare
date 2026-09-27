"""Shared terminal and VSView projection for audio-alignment review evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from statistics import median
from typing import Literal

from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoTargetEvidence,
    VideoTargetKind,
    VideoTargetResolution,
)
from frame_compare.utils.alignment_policy import (
    compensated_lag_to_frame,
    position_winner,
    sample_to_reference_video_time,
)

type EvidenceRowStyle = Literal["value", "warn", "muted"]
type _AudioReviewTargetKey = tuple[VideoTargetKind, int, int]
type _AudioReviewTargetProjection = tuple[_AudioReviewTargetKey, VideoTargetResolution]

_AUDIO_REVIEW_REGION_REASONS = frozenset(
    {
        "competing_offset_confirmed_by_video",
        "competing_offset",
        "unresolved_audio_disagreement",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    """One structured evidence row: a display key, its value, and a style token."""

    key: str
    value: str
    style: EvidenceRowStyle


def _format_compensation(compensation: float | None) -> str:
    if compensation is None:
        return "compensation=unknown"
    return f"compensation={compensation:+.3f}s"


def audio_evidence_rows(attempt: AudioAlignmentAttempt) -> tuple[EvidenceRow, ...]:
    """Return the shared verbose evidence rows for one audio attempt (m2).

    Both the terminal verbose output and the VSView panel details render
    these rows; neither rebuilds them from formatted strings.
    """
    decision = attempt.decision
    analysis = attempt.analysis
    audio = attempt.audio
    rows: list[EvidenceRow] = [
        EvidenceRow(
            key="Runtime/policy",
            value=(
                f"{attempt.media_runtime_fingerprint}; {attempt.estimator_policy}; "
                f"diagnostic={attempt.diagnostic_policy}"
            ),
            style="value",
        ),
        EvidenceRow(
            key="Decision",
            value=(
                f"state={decision.state}; reason={decision.primary_reason}; "
                f"failed={','.join(decision.failed_gates) or 'none'}"
            ),
            style="warn" if decision.state == "unavailable" else "value",
        ),
    ]
    parts = [
        f"active={audio.active_chunks}",
        f"credible={audio.credible_chunks}",
        f"agreeing={audio.agreeing_chunks}",
    ]
    if audio.global_lag is not None:
        lag_ms = audio.global_lag / analysis.analysis_rate * 1000
        parts.append(f"lag={audio.global_lag:+d} samples ({lag_ms:+.2f}ms)")
    parts.append(_format_compensation(audio.compensation_seconds))
    if audio.subframe_estimate is not None:
        parts.append(f"sub-frame=audio {audio.subframe_estimate:+.2f}f")
    if audio.rounded_frame is not None:
        parts.append(f"rounded={audio.rounded_frame:+d}f")
    rows.append(EvidenceRow(key="Evidence", value="; ".join(parts), style="value"))
    rows.append(
        EvidenceRow(
            key="Analysis",
            value=(
                f"rate={analysis.analysis_rate}; max_offset={analysis.max_offset_seconds}s; "
                f"chunk={analysis.chunk_samples}; lag_radius={analysis.lag_samples}; "
                f"planned={analysis.planned_chunk_count}"
            ),
            style="value",
        )
    )
    stability = attempt.stability
    planned = analysis.planned_chunk_count
    scope = f"{stability.valid_windows}/{planned} credible chunks"
    if stability.valid_windows < planned:
        scope += "; chunks without credible evidence are not assessed"
    rows.append(
        EvidenceRow(
            key="Stability",
            value=f"{stability.classification.replace('_', ' ')}; scoped to {scope} (diagnostic only).",
            style="value",
        )
    )
    for position in attempt.video_check.positions:
        rows.append(
            EvidenceRow(
                key=f"Video position {position.position_index}",
                value=(
                    f"frame={position.reference_frame}; "
                    + ", ".join(
                        f"{offset:+d}f={score:.3f}"
                        for offset, score in zip(
                            attempt.video_check.scored_offsets,
                            position.score_by_offset,
                            strict=True,
                        )
                    )
                ),
                style="value",
            )
        )
    if audio.status != "agreed":
        for run in attempt.runs:
            rows.append(
                EvidenceRow(
                    key=f"Run {run.first_index}-{run.last_index}",
                    value=f"lag={run.lag:+d} x{run.chunk_count} chunks",
                    style="value",
                )
            )
    for stream in attempt.selected_streams:
        rows.append(
            EvidenceRow(
                key=f"Stream {stream.role}",
                value=(
                    f"a:{stream.audio_stream_index} (absolute {stream.absolute_stream_index}), "
                    f"codec={stream.codec_name or 'unknown'}, "
                    f"language={stream.language or 'unknown'}, "
                    f"channels={stream.channels or 'unknown'}/{stream.channel_layout or 'unknown'}, "
                    f"rate={stream.sample_rate or 'unknown'}, selection={stream.selection_method}, "
                    f"rank={stream.selection_rank}, start={stream.stream_start_num}/"
                    f"{stream.stream_start_den} ({stream.stream_start_basis}), "
                    f"input={stream.input_start_num}/{stream.input_start_den} "
                    f"({stream.input_start_basis}), duration={stream.duration_num}/"
                    f"{stream.duration_den} ({stream.duration_basis}), "
                    f"video-start={stream.video_start_num}/"
                    f"{stream.video_start_den} ({stream.video_start_basis}), "
                    f"language-match={stream.language_match}, "
                    f"commentary-match={stream.commentary_match}"
                ),
                style="value",
            )
        )
    rows.append(EvidenceRow(key="Collection", value=attempt.collection_observation, style="value"))
    for facts in attempt.collection:
        rows.append(
            EvidenceRow(
                key="Collection side",
                value=(
                    f"{facts.role}: emitted={facts.emitted_samples} samples; "
                    f"EOF={facts.eof_sample}; elapsed={facts.elapsed_seconds:.1f}s; "
                    f"exit={facts.returncode}; stderr={facts.stderr_bytes} bytes "
                    f"(truncated={facts.stderr_truncated}); "
                    f"cleanup={'complete' if facts.cleanup_completed else 'incomplete'}"
                ),
                style="value",
            )
        )
    if attempt.collection_failure is not None:
        failure = attempt.collection_failure
        rows.append(
            EvidenceRow(
                key="Collection failure",
                value=f"failure={failure.category} (side={failure.side})",
                style="warn",
            )
        )
    return tuple(rows)


type AudioReviewRegionStatus = Literal["confirmed by video", "not settled", "not checked"]


@dataclass(frozen=True, slots=True)
class AudioReviewRegion:
    """One non-overlapping review region in track order."""

    offset: int
    start_seconds: float
    end_seconds: float
    status: AudioReviewRegionStatus
    target_resolution: VideoTargetResolution | None = None
    target_key: _AudioReviewTargetKey | None = None
    target_projections: tuple[_AudioReviewTargetProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class AudioReviewPresentation:
    """Shared P4/P4a policy consumed by terminal and VSView renderers."""

    attempt: AudioAlignmentAttempt
    suggested_offset: int | None
    reasons: tuple[str, ...]
    regions: tuple[AudioReviewRegion, ...]
    check_points: tuple[VideoCheckPoint, ...]
    same_frame_regions: tuple[AudioReviewRegion, ...]
    resolved_regions: tuple[AudioReviewRegion, ...]
    video_wins: int
    video_informative: int
    video_margin: float | None

    def reason_lines(self, *, panel: bool = False) -> tuple[str, ...]:
        lines: list[str] = []
        for reason in self.reasons:
            region = _review_reason_region(self.regions, self.suggested_offset, reason)
            if reason == "competing_offset_confirmed_by_video" and region is not None:
                lines.append(
                    f"The video confirms {region.offset:+d}f in {_review_region_text(region, panel=panel)}, "
                    "so the sources likely differ by an edit there."
                )
            elif reason == "competing_offset" and region is not None:
                lines.append(
                    f"Audio in {_review_region_text(region, panel=panel)} points to {region.offset:+d}f, "
                    "and the video could not settle which offset is right there."
                )
            elif reason == "unresolved_audio_disagreement":
                if region is not None:
                    lines.append(
                        f"Audio in {_review_region_text(region, panel=panel)} points to {region.offset:+d}f, "
                        "and the video could not rule that out."
                    )
                unexamined = sum(
                    1
                    for target in self.attempt.video_check.targets
                    if target.resolution == "unexamined"
                    and target.kind == "chunk"
                    and target.credible
                )
                if unexamined:
                    lines.append(
                        f"Audio in {unexamined} more section{'' if unexamined == 1 else 's'} points "
                        "elsewhere; they were not checked, so the offset is not applied."
                    )
            elif reason == "video_check_inconclusive" and self.suggested_offset is not None:
                lines.append(
                    f"The audio points to {self.suggested_offset:+d}f, but the video could not confirm "
                    "the exact frame (little motion or different framing at the checked points)."
                )
            elif reason == "video_check_unavailable" and self.suggested_offset is not None:
                lines.append(
                    f"The audio points to {self.suggested_offset:+d}f, but the video could not be read "
                    "to confirm the exact frame."
                )
            elif reason == "video_check_unavailable":
                lines.append("The video could not be read to check the audio result.")
            elif reason == "no_single_offset":
                confirmed = self.attempt.video_check.confirmed_offset
                lines.append(
                    "The audio does not agree on one offset across the track."
                    if confirmed is None
                    else (
                        "The audio does not agree on one offset across the track; the video suggests "
                        f"{confirmed:+d}f at the checked points."
                    )
                )
        return tuple(dict.fromkeys(lines))

    def region_lines(self, *, panel: bool = False, limit: int | None = None) -> tuple[str, ...]:
        regions = self.regions if limit is None else self.regions[:limit]
        return tuple(
            f"{region.offset:+d}f  {_review_region_text(region, panel=panel)}  {region.status}"
            for region in regions
        )

    def check_point_lines(
        self,
        *,
        panel: bool = False,
        limit: int | None = None,
        include_label: bool = True,
    ) -> tuple[str, ...]:
        points = self.check_points if limit is None else self.check_points[:limit]
        separator = "↔" if panel else "<->"
        dash = " — " if panel else "  "
        return tuple(
            f"{'Check ' if include_label else ''}{_review_time(point.timestamp_seconds)}{dash}reference "
            f"{point.reference_frame:,} {separator} comparison "
            f"{point.suggested_comparison_frame:,} "
            f"({point.reference_frame - point.suggested_comparison_frame:+d}f)"
            for point in points
        )

    def established_audio_line(self) -> str:
        authority = self.attempt.authority_recount
        agreeing = (
            authority.authority_agreeing_chunks
            if authority is not None
            else self.attempt.audio.agreeing_chunks
        )
        offset = self.suggested_offset
        if offset is None:
            offset = self.attempt.audio.rounded_frame or 0
        weak = max(0, self.attempt.audio.active_chunks - self.attempt.audio.credible_chunks)
        inactive = max(
            0,
            self.attempt.analysis.planned_chunk_count - self.attempt.audio.active_chunks,
        )
        ignored = f"; {weak} weak, {inactive} quiet not counted" if weak or inactive else ""
        return (
            f"Audio: {agreeing} of {self.attempt.audio.credible_chunks} clear sections agree on "
            f"{offset:+d}f ({max(0, self.attempt.audio.credible_chunks - agreeing)} differ"
            f"{ignored})."
        )

    def established_video_line(self) -> str:
        video = self.attempt.video_check
        if video.observation != "observed":
            return "Video: not observed."
        if video.confirmed_offset is None:
            return f"Video: did not confirm an offset at {len(video.positions)} check points."
        margin = "n/a" if self.video_margin is None else f"{self.video_margin:.1f}x"
        if self.video_margin is not None and math.isinf(self.video_margin):
            margin = "exact match"
        return (
            f"Video: confirmed {video.confirmed_offset:+d}f at {self.video_wins} of "
            f"{len(video.positions)} check points (median margin {margin})."
        )

    def context_lines(self, *, panel: bool = False) -> tuple[str, ...]:
        lines: list[str] = []
        recount = self.attempt.authority_recount
        if recount is not None and recount.raw_agreeing_chunks != recount.authority_agreeing_chunks:
            lines.append(
                f"Audio (raw): {recount.raw_agreeing_chunks} of {self.attempt.audio.credible_chunks} "
                "sections agree; "
                f"{recount.authority_agreeing_chunks - recount.raw_agreeing_chunks} more are within "
                "the same frame, so "
                f"{recount.authority_agreeing_chunks} of {self.attempt.audio.credible_chunks} agree "
                "for this offset."
            )
        if self.same_frame_regions:
            lines.append(
                f"{len(self.same_frame_regions)} section{'' if len(self.same_frame_regions) == 1 else 's'} "
                "differ by less than a frame (sub-frame); not a disagreement."
            )
        if self.resolved_regions:
            lines.extend(
                f"Audio differed in {_review_region_text(region, panel=panel)}; "
                "the video confirmed the offset there."
                for region in self.resolved_regions
            )
        for target in self.attempt.video_check.targets:
            if target.resolution != "local_video_inconclusive" or not target.positions:
                continue
            position = target.positions[0]
            region = AudioReviewRegion(
                target.target_offset,
                *_review_target_bounds(self.attempt, target),
                "not settled",
            )
            confirmed = self.attempt.video_check.confirmed_offset
            if confirmed is None:
                continue
            lines.append(
                f"Weak audio in {_review_region_text(region, panel=panel)} pointed to "
                f"{target.target_offset:+d}f; video inconclusive there "
                f"({confirmed:+d}f scored {position.confirmed_score:.3f}, "
                f"{target.target_offset:+d}f scored {position.alternative_score:.3f}); "
                "not counted."
            )
        return tuple(lines)

    def noted_line(self, *, panel: bool = False) -> str | None:
        if self.same_frame_regions:
            ranges = ", ".join(
                _review_region_text(region, panel=panel) for region in self.same_frame_regions
            )
            return (
                f"Noted: audio differed in {len(self.same_frame_regions)} section"
                f"{'s' if len(self.same_frame_regions) != 1 else ''} ({ranges}); the video "
                f"confirmed {self.suggested_offset:+d}f there."
                if self.suggested_offset is not None
                else None
            )
        if self.resolved_regions and self.suggested_offset is not None:
            ranges = ", ".join(
                _review_region_text(region, panel=panel) for region in self.resolved_regions
            )
            resolved_indexes = {
                index
                for target in self.attempt.video_check.targets
                if target.resolution == "resolved" and target.credible
                for index in range(target.first_chunk_index, target.last_chunk_index + 1)
            }
            count = len(resolved_indexes)
            return (
                f"Noted: audio differed in {count or len(self.resolved_regions)} section"
                f"{'s' if (count or len(self.resolved_regions)) != 1 else ''} ({ranges}); "
                f"the video confirmed {self.suggested_offset:+d}f there."
            )
        inconclusive = next(
            (
                target
                for target in self.attempt.video_check.targets
                if target.resolution == "local_video_inconclusive"
            ),
            None,
        )
        if inconclusive is not None:
            region = AudioReviewRegion(
                inconclusive.target_offset,
                *_review_target_bounds(self.attempt, inconclusive),
                "not settled",
            )
            return (
                f"Noted: weak audio in {_review_region_text(region, panel=panel)} pointed "
                "elsewhere; the video could not settle it, so it was not counted."
            )
        return None

    def normal_review_rows(self, *, panel: bool, action_line: str) -> tuple[EvidenceRow, ...]:
        """Return the shared normal P4 block after its surface-specific outcome."""
        rows = [
            EvidenceRow(key="", value=line, style="warn") for line in self.reason_lines(panel=panel)
        ]
        if _AUDIO_REVIEW_REGION_REASONS.intersection(self.reasons):
            rows.extend(
                EvidenceRow(key="", value=f"  {line}", style="muted")
                for line in self.region_lines(panel=panel, limit=3)
            )
            if len(self.regions) > 3:
                rows.append(
                    EvidenceRow(
                        key="",
                        value=f"and {len(self.regions) - 3} more regions",
                        style="muted",
                    )
                )
        rows.extend(
            EvidenceRow(key="", value=line, style="muted")
            for line in self.check_point_lines(panel=panel, limit=2)
        )
        rows.append(EvidenceRow(key="", value=action_line, style="muted"))
        return tuple(rows)

    def verbose_rows(self, *, panel: bool = False) -> tuple[EvidenceRow, ...]:
        rows: list[EvidenceRow] = [
            EvidenceRow(key="Established", value=self.established_audio_line(), style="value"),
            EvidenceRow(key="", value=self.established_video_line(), style="value"),
        ]
        for index, line in enumerate(self.region_lines(panel=panel)):
            rows.append(EvidenceRow(key="Regions" if index == 0 else "", value=line, style="muted"))
        for index, line in enumerate(self.context_lines(panel=panel)):
            rows.append(EvidenceRow(key="Context" if index == 0 else "", value=line, style="muted"))
        for index, line in enumerate(self.check_point_lines(panel=panel, include_label=False)):
            rows.append(
                EvidenceRow(key="Check points" if index == 0 else "", value=line, style="muted")
            )
        decision = self.attempt.decision
        rows.append(
            EvidenceRow(
                key="Decision",
                value=(
                    f"state={decision.state}; reason={decision.primary_reason}; "
                    f"also={','.join(decision.failed_gates[1:]) or 'none'}"
                ),
                style="value",
            )
        )
        return tuple(rows)

    def verbose_lines(self, *, panel: bool = False) -> tuple[str, ...]:
        lines: list[str] = []
        continuation_key = ""
        for row in self.verbose_rows(panel=panel):
            if row.key:
                lines.append(f"{row.key}: {row.value}")
                continuation_key = row.key
            else:
                lines.append(f"{' ' * (len(continuation_key) + 2)}{row.value}")
        return tuple(lines)


def _review_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _review_region_text(region: AudioReviewRegion, *, panel: bool) -> str:
    separator = "–" if panel else "-"
    return f"{_review_time(region.start_seconds)}{separator}{_review_time(region.end_seconds)}"


def _review_frame_for_lag(attempt: AudioAlignmentAttempt, lag: int) -> int:
    return compensated_lag_to_frame(
        lag,
        compensation_seconds=attempt.audio.compensation_seconds or 0.0,
        fps_reference=Fraction(attempt.fps_num, attempt.fps_den),
    )


def _review_sample_time(attempt: AudioAlignmentAttempt, sample: int) -> float:
    reference = next(stream for stream in attempt.selected_streams if stream.role == "reference")
    return float(
        sample_to_reference_video_time(
            sample,
            audio_start_reference=Fraction(
                reference.stream_start_num,
                reference.stream_start_den,
            ),
            video_start_reference=Fraction(
                reference.video_start_num,
                reference.video_start_den,
            ),
        )
    )


def _review_chunk_bounds(
    attempt: AudioAlignmentAttempt, first: int, last: int
) -> tuple[float, float]:
    starts = attempt.chunks.starts
    counts = attempt.chunks.counts
    if starts and 0 <= first < len(starts) and 0 <= last < len(starts):
        return (
            _review_sample_time(attempt, starts[first]),
            _review_sample_time(attempt, starts[last] + counts[last]),
        )
    chunk_samples = attempt.analysis.chunk_samples
    return (
        _review_sample_time(attempt, first * chunk_samples),
        _review_sample_time(
            attempt,
            min((last + 1) * chunk_samples, attempt.chunks.total_samples),
        ),
    )


def _review_target_bounds(
    attempt: AudioAlignmentAttempt, target: VideoTargetEvidence
) -> tuple[float, float]:
    return (
        _review_sample_time(attempt, target.start_sample),
        _review_sample_time(attempt, target.end_sample),
    )


def _review_target_map(
    video: VideoCheckObservation,
) -> dict[_AudioReviewTargetKey, VideoTargetEvidence]:
    return {
        (target.kind, target.first_chunk_index, target.last_chunk_index): target
        for target in video.targets
    }


def _review_target_status(target: VideoTargetEvidence | None) -> AudioReviewRegionStatus:
    if target is None:
        return "not settled"
    if target.resolution in {"resolved", "alternative_confirmed"}:
        return "confirmed by video"
    return "not checked" if target.resolution == "unexamined" else "not settled"


def _review_target_offset(video: VideoCheckObservation, target: VideoTargetEvidence) -> int:
    if target.resolution == "resolved" and video.confirmed_offset is not None:
        return video.confirmed_offset
    if target.resolution == "alternative_confirmed":
        actual = {
            position.alternative_offset
            for position in target.positions
            if position.winner == "alternative" and position.alternative_offset is not None
        }
        if len(actual) == 1:
            return next(iter(actual))
    return target.target_offset


def _review_target_candidates(
    attempt: AudioAlignmentAttempt,
    targets: tuple[VideoTargetEvidence, ...],
) -> tuple[AudioReviewRegion, ...]:
    regions: list[AudioReviewRegion] = []
    for target in targets:
        start, end = _review_target_bounds(attempt, target)
        regions.append(
            AudioReviewRegion(
                _review_target_offset(attempt.video_check, target),
                start,
                end,
                _review_target_status(target),
                target.resolution,
                (target.kind, target.first_chunk_index, target.last_chunk_index),
            )
        )
    return tuple(regions)


def _review_region_target_projections(
    region: AudioReviewRegion,
) -> tuple[_AudioReviewTargetProjection, ...]:
    if region.target_projections:
        return region.target_projections
    if region.target_key is None or region.target_resolution is None:
        return ()
    return ((region.target_key, region.target_resolution),)


def _review_merge_target_projections(
    first: AudioReviewRegion, second: AudioReviewRegion
) -> tuple[_AudioReviewTargetProjection, ...]:
    return tuple(
        dict.fromkeys(
            (
                *_review_region_target_projections(first),
                *_review_region_target_projections(second),
            )
        )
    )


def _review_merge_status(
    first: AudioReviewRegionStatus, second: AudioReviewRegionStatus
) -> AudioReviewRegionStatus:
    if "not checked" in {first, second}:
        return "not checked"
    if "not settled" in {first, second}:
        return "not settled"
    return "confirmed by video"


def _review_track_bounds(attempt: AudioAlignmentAttempt) -> tuple[float, float]:
    planned = attempt.analysis.planned_chunk_count
    if planned:
        return _review_chunk_bounds(attempt, 0, planned - 1)
    return 0.0, 0.0


def _review_non_overlapping(
    regions: tuple[AudioReviewRegion, ...],
) -> tuple[AudioReviewRegion, ...]:
    ordered = sorted(regions, key=lambda region: (region.start_seconds, region.end_seconds))
    clipped: list[AudioReviewRegion] = []
    cursor = 0.0
    for region in ordered:
        if (
            clipped
            and region.start_seconds == clipped[-1].start_seconds
            and region.end_seconds == clipped[-1].end_seconds
            and region.offset == clipped[-1].offset
        ):
            previous = clipped[-1]
            primary = previous if previous.target_key is not None else region
            clipped[-1] = AudioReviewRegion(
                previous.offset,
                previous.start_seconds,
                previous.end_seconds,
                (
                    primary.status
                    if primary.target_key is not None
                    else _review_merge_status(previous.status, region.status)
                ),
                primary.target_resolution,
                primary.target_key,
                _review_merge_target_projections(previous, region),
            )
            continue
        start = max(region.start_seconds, cursor)
        if region.end_seconds <= start:
            continue
        candidate = AudioReviewRegion(
            region.offset,
            start,
            region.end_seconds,
            region.status,
            region.target_resolution,
            region.target_key,
            _review_region_target_projections(region),
        )
        if (
            clipped
            and clipped[-1].offset == candidate.offset
            and clipped[-1].status == candidate.status
            and clipped[-1].target_resolution == candidate.target_resolution
            and clipped[-1].target_key == candidate.target_key
            and clipped[-1].target_projections == candidate.target_projections
        ):
            previous = clipped[-1]
            clipped[-1] = AudioReviewRegion(
                previous.offset,
                previous.start_seconds,
                max(previous.end_seconds, candidate.end_seconds),
                previous.status,
                previous.target_resolution,
                previous.target_key,
                previous.target_projections,
            )
        else:
            clipped.append(candidate)
        cursor = max(cursor, candidate.end_seconds)
    return tuple(clipped)


def _review_overlay_regions(
    base_regions: tuple[AudioReviewRegion, ...],
    target_regions: tuple[AudioReviewRegion, ...],
) -> tuple[AudioReviewRegion, ...]:
    all_regions = (*base_regions, *target_regions)
    boundaries = tuple(
        sorted(
            {
                boundary
                for region in all_regions
                for boundary in (region.start_seconds, region.end_seconds)
                if region.end_seconds > region.start_seconds
            }
        )
    )
    segments: list[AudioReviewRegion] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        if end <= start:
            continue
        active_base = tuple(
            region
            for region in base_regions
            if region.start_seconds < end and region.end_seconds > start
        )
        active_targets = tuple(
            region
            for region in target_regions
            if region.start_seconds < end and region.end_seconds > start
        )
        if not active_base and not active_targets:
            continue
        if active_targets:
            selected_target = min(
                active_targets,
                key=lambda region: (
                    region.end_seconds - region.start_seconds,
                    region.start_seconds,
                ),
            )
            active = (selected_target,) + tuple(
                region
                for region in (*active_targets, *active_base)
                if region is not selected_target
            )
            offset = selected_target.offset
        else:
            active = active_base
            offset = active_base[0].offset
        primary = next((region for region in active if region.target_key is not None), active[0])
        status = active[0].status
        projections = _review_region_target_projections(active[0])
        for region in active[1:]:
            if not active_targets:
                status = _review_merge_status(status, region.status)
            projections = tuple(
                dict.fromkeys((*projections, *_review_region_target_projections(region)))
            )
        segments.append(
            AudioReviewRegion(
                offset,
                start,
                end,
                status,
                primary.target_resolution,
                primary.target_key,
                projections,
            )
        )
    return _review_non_overlapping(tuple(segments))


def _review_regions(
    attempt: AudioAlignmentAttempt, suggested: int | None
) -> tuple[AudioReviewRegion, ...]:
    video = attempt.video_check
    targets = _review_target_map(video)
    runs: list[AudioReviewRegion] = []
    for run in attempt.runs:
        target = targets.get(("run", run.first_index, run.last_index))
        converted = _review_frame_for_lag(attempt, run.lag)
        offset = (
            _review_target_offset(video, target)
            if target is not None
            else (
                suggested
                if suggested is not None
                and (run.lag == attempt.audio.global_lag or converted == suggested)
                else converted
            )
        )
        start, end = (
            _review_target_bounds(attempt, target)
            if target is not None
            else _review_chunk_bounds(attempt, run.first_index, run.last_index)
        )
        status: AudioReviewRegionStatus = (
            "confirmed by video"
            if video.confirmed_offset is not None and offset == video.confirmed_offset
            else _review_target_status(target)
        )
        runs.append(
            AudioReviewRegion(
                offset,
                start,
                end,
                status,
                target.resolution if target is not None else None,
                ("run", run.first_index, run.last_index) if target is not None else None,
            )
        )

    majority = tuple(
        region for region in runs if suggested is not None and region.offset == suggested
    )
    if majority:
        regions = runs
    elif suggested is not None:
        start, end = _review_track_bounds(attempt)
        competing = _review_non_overlapping(tuple(runs))
        majority_regions: list[AudioReviewRegion] = []
        cursor = start
        majority_status = (
            "confirmed by video" if video.confirmed_offset == suggested else "not settled"
        )
        for region in competing:
            if region.start_seconds > cursor:
                majority_regions.append(
                    AudioReviewRegion(suggested, cursor, region.start_seconds, majority_status)
                )
            cursor = max(cursor, region.end_seconds)
        if cursor < end:
            majority_regions.append(AudioReviewRegion(suggested, cursor, end, majority_status))
        regions = (*majority_regions, *competing)
    else:
        regions = tuple(runs)

    chronological = _review_overlay_regions(
        _review_non_overlapping(tuple(regions)),
        _review_target_candidates(attempt, video.targets),
    )
    if suggested is None:
        return chronological
    return tuple(
        [region for region in chronological if region.offset == suggested]
        + [region for region in chronological if region.offset != suggested]
    )


def _review_reason_region(
    regions: tuple[AudioReviewRegion, ...], suggested: int | None, reason: str
) -> AudioReviewRegion | None:
    candidates = tuple(region for region in regions if region.offset != suggested)
    target_candidates = candidates

    def target_regions(
        kind: VideoTargetKind,
        resolutions: frozenset[VideoTargetResolution],
    ) -> tuple[AudioReviewRegion, ...]:
        return tuple(
            region
            for region in target_candidates
            if any(
                target_key[0] == kind and resolution in resolutions
                for target_key, resolution in _review_region_target_projections(region)
            )
        )

    if reason == "competing_offset_confirmed_by_video":
        candidates = tuple(
            region
            for region in candidates
            if any(
                resolution == "alternative_confirmed"
                for _target_key, resolution in _review_region_target_projections(region)
            )
        )
        return candidates[0] if candidates else None
    if reason == "competing_offset":
        candidates = target_regions("run", frozenset({"unresolved", "unexamined"}))
        return candidates[0] if candidates else None
    if reason == "unresolved_audio_disagreement":
        candidates = target_regions("chunk", frozenset({"unresolved"}))
        if not candidates:
            candidates = target_regions("run", frozenset({"unresolved"}))
        return candidates[0] if candidates else None
    return candidates[0] if candidates else (regions[0] if regions else None)


def _review_video_vote(
    video: VideoCheckObservation,
) -> tuple[int, int, float | None]:
    if video.observation != "observed" or video.confirmed_offset is None:
        return 0, 0, None
    informative: list[tuple[int, float]] = []
    for position in video.positions:
        winner, margin = position_winner(position.score_by_offset, video.scored_offsets)
        if winner is not None:
            informative.append((winner, margin))
    wins = sum(winner == video.confirmed_offset for winner, _margin in informative)
    winning_margins = [margin for winner, margin in informative if winner == video.confirmed_offset]
    return wins, len(informative), (median(winning_margins) if winning_margins else None)


def build_audio_review_presentation(attempt: AudioAlignmentAttempt) -> AudioReviewPresentation:
    """Build the shared P4/P4a presentation policy for one audio attempt."""
    video = attempt.video_check
    suggested = video.confirmed_offset
    if suggested is None and attempt.decision.candidate is not None:
        suggested = attempt.decision.candidate.frame_offset
    reasons = tuple(
        dict.fromkeys(attempt.decision.failed_gates or (attempt.decision.primary_reason,))
    )
    regions = _review_regions(attempt, suggested)
    same_frame_regions = tuple(
        AudioReviewRegion(
            (video.confirmed_offset if video.confirmed_offset is not None else item.rounded_frame),
            *_review_chunk_bounds(attempt, item.chunk_index, item.chunk_index),
            "confirmed by video",
        )
        for item in video.same_frame_context
    )
    resolved_regions: list[AudioReviewRegion] = []
    for target in video.targets:
        start, end = _review_target_bounds(attempt, target)
        target_region = AudioReviewRegion(
            (video.confirmed_offset if video.confirmed_offset is not None else suggested or 0),
            start,
            end,
            _review_target_status(target),
        )
        if target.resolution == "resolved" and target.credible:
            resolved_regions.append(target_region)
    wins, informative, margin = _review_video_vote(video)
    return AudioReviewPresentation(
        attempt=attempt,
        suggested_offset=suggested,
        reasons=reasons,
        regions=regions,
        check_points=video.check_points[:5],
        same_frame_regions=tuple(same_frame_regions),
        resolved_regions=tuple(resolved_regions),
        video_wins=wins,
        video_informative=informative,
        video_margin=margin,
    )


__all__ = [
    "AudioReviewPresentation",
    "AudioReviewRegion",
    "AudioReviewRegionStatus",
    "EvidenceRow",
    "EvidenceRowStyle",
    "audio_evidence_rows",
    "build_audio_review_presentation",
]
