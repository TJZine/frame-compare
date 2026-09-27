"""Terminal presentation for audio alignment evidence."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from math import floor
from statistics import median
from typing import Literal

import structlog
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
)
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    EvidenceRow,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoTargetEvidence,
    audio_evidence_rows,
    audio_unavailable_phrase,
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
from frame_compare.utils.types import AlignmentRequest

log = structlog.get_logger()

type _StyledRow = tuple[str, str, str]
type _RegionStatus = Literal["confirmed by video", "not settled", "not checked"]


@dataclass(frozen=True, slots=True)
class _Region:
    offset: int
    start: float
    end: float
    status: _RegionStatus


def _format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _format_region(region: _Region, *, panel: bool = False) -> str:
    separator = "–" if panel else "-"
    return f"{_format_time(region.start)}{separator}{_format_time(region.end)}"


def _frame_for_lag(attempt: AudioAlignmentAttempt, lag: int) -> int:
    compensation = attempt.audio.compensation_seconds or 0.0
    seconds = lag / attempt.analysis.analysis_rate + compensation
    return floor(seconds * attempt.fps_num / attempt.fps_den + 0.5)


def _chunk_bounds(attempt: AudioAlignmentAttempt, first: int, last: int) -> tuple[float, float]:
    starts = attempt.chunks.starts
    counts = attempt.chunks.counts
    rate = attempt.analysis.analysis_rate
    if starts and 0 <= first < len(starts) and 0 <= last < len(starts):
        return starts[first] / rate, (starts[last] + counts[last]) / rate
    chunk = attempt.analysis.chunk_samples / rate
    return first * chunk, (last + 1) * chunk


def _target_map(
    video: VideoCheckObservation,
) -> dict[tuple[str, int, int], VideoTargetEvidence]:
    return {
        (target.kind, target.first_chunk_index, target.last_chunk_index): target
        for target in video.targets
    }


def _target_status(target: VideoTargetEvidence | None) -> _RegionStatus:
    if target is None:
        return "not settled"
    if target.resolution in {"resolved", "alternative_confirmed"}:
        return "confirmed by video"
    return "not checked" if target.resolution == "unexamined" else "not settled"


def _regions(attempt: AudioAlignmentAttempt, suggested: int | None) -> tuple[_Region, ...]:
    video = attempt.video_check
    targets = _target_map(video)
    regions: list[_Region] = []
    seen: set[tuple[int, int, int]] = set()
    for run in attempt.runs:
        offset = (
            suggested
            if suggested is not None and run.lag == attempt.audio.global_lag
            else _frame_for_lag(attempt, run.lag)
        )
        primary = suggested is not None and offset == suggested
        target = targets.get(("run", run.first_index, run.last_index))
        start, end = _chunk_bounds(attempt, run.first_index, run.last_index)
        if not primary or not regions:
            region = _Region(
                offset=offset,
                start=start,
                end=end,
                status=(
                    "confirmed by video"
                    if video.confirmed_offset is not None and offset == video.confirmed_offset
                    else _target_status(target)
                ),
            )
            key = (region.offset, run.first_index, run.last_index)
            if key not in seen:
                regions.append(region)
                seen.add(key)
    if suggested is not None and not any(region.offset == suggested for region in regions):
        planned = attempt.analysis.planned_chunk_count
        if planned:
            start, end = _chunk_bounds(attempt, 0, planned - 1)
        else:
            start, end = 0.0, 0.0
        regions.insert(
            0,
            _Region(
                offset=suggested,
                start=start,
                end=end,
                status=(
                    "confirmed by video" if video.confirmed_offset == suggested else "not settled"
                ),
            ),
        )
    for target in video.targets:
        key = (target.kind, target.first_chunk_index, target.last_chunk_index)
        if target.kind == "run" and any(
            (target.first_chunk_index, target.last_chunk_index) == (run.first_index, run.last_index)
            for run in attempt.runs
        ):
            continue
        if not target.alternative_offsets:
            continue
        start, end = _chunk_bounds(attempt, target.first_chunk_index, target.last_chunk_index)
        region = _Region(
            offset=target.alternative_offsets[0],
            start=start,
            end=end,
            status=_target_status(target),
        )
        dedupe = (region.offset, target.first_chunk_index, target.last_chunk_index)
        if dedupe not in seen:
            regions.append(region)
            seen.add(dedupe)
    return tuple(regions)


def _suggested_offset(attempt: AudioAlignmentAttempt) -> int | None:
    if attempt.video_check.confirmed_offset is not None:
        return attempt.video_check.confirmed_offset
    candidate = attempt.decision.candidate
    return candidate.frame_offset if candidate is not None else None


def _display_reasons(attempt: AudioAlignmentAttempt) -> tuple[str, ...]:
    decision = attempt.decision
    reasons = decision.failed_gates or (decision.primary_reason,)
    return tuple(dict.fromkeys(reasons))


def _reason_region(
    regions: tuple[_Region, ...], *, suggested: int | None, reason: str
) -> _Region | None:
    candidates = tuple(region for region in regions if region.offset != suggested)
    if reason == "competing_offset_confirmed_by_video":
        candidates = tuple(region for region in candidates if region.status == "confirmed by video")
    elif reason == "competing_offset":
        candidates = tuple(region for region in candidates if region.status != "confirmed by video")
    return candidates[0] if candidates else (regions[0] if regions else None)


def _reason_lines(attempt: AudioAlignmentAttempt, *, panel: bool = False) -> tuple[str, ...]:
    suggested = _suggested_offset(attempt)
    regions = _regions(attempt, suggested)
    lines: list[str] = []
    for reason in _display_reasons(attempt):
        region = _reason_region(regions, suggested=suggested, reason=reason)
        if reason == "competing_offset_confirmed_by_video" and region is not None:
            lines.append(
                f"The video confirms {region.offset:+d}f in {_format_region(region, panel=panel)}, "
                "so the sources likely differ by an edit there."
            )
        elif reason == "competing_offset" and region is not None:
            lines.append(
                f"Audio in {_format_region(region, panel=panel)} points to {region.offset:+d}f, "
                "and the video could not settle which offset is right there."
            )
        elif reason == "unresolved_audio_disagreement":
            unexamined = sum(
                max(1, target.last_chunk_index - target.first_chunk_index + 1)
                for target in attempt.video_check.targets
                if target.resolution == "unexamined"
            )
            if unexamined:
                lines.append(
                    f"Audio in {unexamined} more section{'' if unexamined == 1 else 's'} points "
                    "elsewhere; they were not checked, so the offset is not applied."
                )
            elif region is not None:
                lines.append(
                    f"Audio in {_format_region(region, panel=panel)} points to {region.offset:+d}f, "
                    "and the video could not rule that out."
                )
        elif reason == "video_check_inconclusive" and suggested is not None:
            lines.append(
                f"The audio points to {suggested:+d}f, but the video could not confirm the exact "
                "frame (little motion or different framing at the checked points)."
            )
        elif reason == "video_check_unavailable" and suggested is not None:
            lines.append(
                f"The audio points to {suggested:+d}f, but the video could not be read to confirm "
                "the exact frame."
            )
        elif reason == "video_check_pending":
            lines.append("Video confirmation pending; not applied.")
        elif reason == "no_single_offset" and attempt.video_check.confirmed_offset is not None:
            lines.append(
                "The audio does not agree on one offset across the track; the video suggests "
                f"{attempt.video_check.confirmed_offset:+d}f at the checked points."
            )
    return tuple(dict.fromkeys(lines))


def _check_point_line(point: VideoCheckPoint, *, panel: bool = False) -> str:
    offset = point.reference_frame - point.suggested_comparison_frame
    separator = "↔" if panel else "<->"
    dash = "—" if panel else " "
    return (
        f"Check {_format_time(point.timestamp_seconds)}{dash} reference "
        f"{point.reference_frame:,} {separator} comparison "
        f"{point.suggested_comparison_frame:,} ({offset:+d}f)"
    )


def _video_established_line(attempt: AudioAlignmentAttempt) -> str:
    video = attempt.video_check
    if video.observation != "observed":
        return "Video: not observed."
    if video.confirmed_offset is None:
        return f"Video: did not confirm an offset at {len(video.positions)} check points."
    confirmed_index = video.scored_offsets.index(video.confirmed_offset)
    wins = sum(
        min(position.score_by_offset) == position.score_by_offset[confirmed_index]
        for position in video.positions
    )
    margins: list[float] = []
    for position in video.positions:
        best = min(position.score_by_offset)
        runner = (
            min(score for score in position.score_by_offset if score != best)
            if len(set(position.score_by_offset)) > 1
            else best
        )
        if best == 0 and runner > 0:
            margins.append(float("inf"))
        elif best > 0:
            margins.append(runner / best)
    margin = (
        "∞"
        if not margins or any(value == float("inf") for value in margins)
        else f"{median(margins):.1f}"
    )
    return (
        f"Video: confirmed {video.confirmed_offset:+d}f at {wins} of {len(video.positions)} "
        f"check points (median margin {margin}×)."
    )


def _context_lines(attempt: AudioAlignmentAttempt, *, panel: bool = False) -> tuple[str, ...]:
    lines: list[str] = []
    if attempt.authority_recount is not None:
        recount = attempt.authority_recount
        if recount.raw_agreeing_chunks != recount.authority_agreeing_chunks:
            lines.append(
                f"Audio (raw): {recount.raw_agreeing_chunks} of {attempt.audio.credible_chunks} "
                "sections agree; "
                f"{recount.authority_agreeing_chunks - recount.raw_agreeing_chunks} more are "
                "within the same frame, so "
                f"{recount.authority_agreeing_chunks} of {attempt.audio.credible_chunks} agree "
                "for this offset."
            )
    for item in attempt.video_check.same_frame_context:
        start, end = _chunk_bounds(attempt, item.chunk_index, item.chunk_index)
        lines.append(
            f"{1} section differs by less than a frame ({_format_region(_Region(0, start, end, 'not settled'), panel=panel)}); "
            "not a disagreement."
        )
        break
    for target in attempt.video_check.targets:
        if target.resolution == "alternative_confirmed":
            continue
        if target.kind == "chunk" and target.resolution in {"resolved", "unresolved"}:
            start, end = _chunk_bounds(attempt, target.first_chunk_index, target.last_chunk_index)
            credible = (
                target.first_chunk_index < len(attempt.chunks.credible)
                and attempt.chunks.credible[target.first_chunk_index]
            )
            if credible and target.resolution == "resolved":
                lines.append(
                    f"Audio differed in {_format_region(_Region(0, start, end, 'not settled'), panel=panel)}; "
                    "the video confirmed the offset there."
                )
            else:
                lines.append(
                    f"Picture differs in {_format_region(_Region(0, start, end, 'not settled'), panel=panel)} "
                    "(for example a replaced shot); offset still holds."
                )
            break
    return tuple(lines)


def _noted_line(attempt: AudioAlignmentAttempt) -> str | None:
    suggested = _suggested_offset(attempt)
    if suggested is None:
        return None
    context = _context_lines(attempt)
    if attempt.video_check.same_frame_context:
        count = len(attempt.video_check.same_frame_context)
        item = attempt.video_check.same_frame_context[0]
        start, end = _chunk_bounds(attempt, item.chunk_index, item.chunk_index)
        return (
            f"Noted: audio differed in {count} section{'s' if count != 1 else ''} "
            f"({_format_region(_Region(0, start, end, 'not settled'))}); the video confirmed "
            f"{suggested:+d}f there."
        )
    if context:
        for target in attempt.video_check.targets:
            if target.kind == "chunk" and target.resolution == "resolved":
                index = target.first_chunk_index
                if index < len(attempt.chunks.credible) and attempt.chunks.credible[index]:
                    start, end = _chunk_bounds(attempt, index, target.last_chunk_index)
                    count = target.last_chunk_index - target.first_chunk_index + 1
                    return (
                        f"Noted: audio differed in {count} section{'s' if count != 1 else ''} "
                        f"({_format_region(_Region(0, start, end, 'not settled'))}); the video "
                        f"confirmed {suggested:+d}f there."
                    )
        return context[-1]
    return None


def _review_evidence_rows(attempt: AudioAlignmentAttempt) -> tuple[EvidenceRow, ...]:
    suggested = _suggested_offset(attempt)
    rows: list[EvidenceRow] = []
    authority = attempt.authority_recount
    agreeing = (
        authority.authority_agreeing_chunks
        if authority is not None
        else attempt.audio.agreeing_chunks
    )
    rows.append(
        EvidenceRow(
            key="Established",
            value=(
                f"Audio: {agreeing} of {attempt.audio.credible_chunks} sections agree on "
                f"{(suggested if suggested is not None else attempt.audio.rounded_frame or 0):+d}f "
                f"({max(0, attempt.audio.credible_chunks - agreeing)} differ, "
                f"{max(0, attempt.audio.active_chunks - attempt.audio.credible_chunks)} quiet)."
            ),
            style="value",
        )
    )
    rows.append(EvidenceRow(key="", value=_video_established_line(attempt), style="value"))
    regions = _regions(attempt, suggested)
    for index, region in enumerate(regions):
        rows.append(
            EvidenceRow(
                key="Regions" if index == 0 else "",
                value=(f"{region.offset:+d}f  {_format_region(region)}  {region.status}"),
                style="muted",
            )
        )
    for line in _context_lines(attempt):
        rows.append(EvidenceRow(key="Context", value=line, style="muted"))
    for index, point in enumerate(attempt.video_check.check_points):
        rows.append(
            EvidenceRow(
                key="Check points" if index == 0 else "",
                value=_check_point_line(point),
                style="muted",
            )
        )
    decision = attempt.decision
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


def _normal_evidence_rows(
    *, ordinal: int, result: AlignmentResult, provenance: AlignmentProvenance
) -> tuple[_StyledRow, ...]:
    prefix = f"Comparison {ordinal} - "
    offset = result.frame_offset
    if result.applied and offset is not None:
        if provenance.provenance == "shared_computed_offsets":
            heading = "Accepted audio alignment reused"
            detail = (
                "Historical chunk and selected-stream details are unavailable; "
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
            # U4 video-confirm seam: U3 never applies a fresh computed
            # result, so only the reuse/manual branches above are live until
            # the video check can confirm a fresh candidate.
            heading = "Audio alignment accepted"
            detail = None
        rows: list[_StyledRow] = [
            ("", f"{prefix}{heading}: {offset:+d}f - APPLIED", OK),
            ("", "No additional confirmation needed.", MUTED),
        ]
        if detail is not None:
            rows.append(("", detail, MUTED))
        elif result.source == "computed" and result.audio_attempt is not None:
            noted = _noted_line(result.audio_attempt)
            if noted is not None:
                rows.append(("", noted, MUTED))
        return tuple(rows)

    attempt = result.audio_attempt
    decision = attempt.decision if attempt is not None else None
    if (
        attempt is not None
        and decision is not None
        and decision.state in {"provisional", "unavailable"}
        and _suggested_offset(attempt) is not None
    ):
        suggested = _suggested_offset(attempt)
        assert suggested is not None
        rows = [
            (
                "",
                f"{prefix}Provisional audio candidate: {suggested:+d}f - NOT APPLIED",
                WARN,
            ),
        ]
        if decision.primary_reason == "video_check_pending":
            rows.append(("", "Video confirmation pending; not applied.", WARN))
        else:
            rows.extend(("", line, WARN) for line in _reason_lines(attempt))
            if any(
                reason
                in {
                    "competing_offset_confirmed_by_video",
                    "competing_offset",
                    "unresolved_audio_disagreement",
                }
                for reason in _display_reasons(attempt)
            ):
                regions = _regions(attempt, suggested)
                shown_regions = regions[:3]
                rows.extend(
                    (
                        "",
                        f"  {region.offset:+d}f  {_format_region(region)}  {region.status}",
                        MUTED,
                    )
                    for region in shown_regions
                )
                if len(regions) > len(shown_regions):
                    rows.append(
                        ("", f"and {len(regions) - len(shown_regions)} more regions", MUTED)
                    )
            for point in attempt.video_check.check_points[:2]:
                rows.append(("", _check_point_line(point), MUTED))
            rows.append(("", "Align manually or keep the current alignment.", MUTED))
        return tuple(rows)

    reason = decision.primary_reason if decision is not None else result.diagnostic
    phrase = audio_unavailable_phrase(reason) if reason else "no usable audio signal"
    return (
        ("", f"{prefix}No usable audio candidate ({phrase}) - NOT APPLIED", WARN),
        ("", "Align manually or keep the current alignment.", MUTED),
    )


def _original_audio_attempt_line(attempt: AudioAlignmentAttempt) -> str:
    decision = attempt.decision
    candidate = decision.candidate
    if decision.state == "trusted_automatic" and candidate is not None:
        return f"Original audio attempt: Audio alignment accepted: {candidate.frame_offset:+d}f - APPLIED"
    if decision.state == "provisional" and candidate is not None:
        return f"Original audio attempt: Provisional audio candidate: {candidate.frame_offset:+d}f - NOT APPLIED"
    return (
        "Original audio attempt: No usable audio candidate "
        f"({audio_unavailable_phrase(decision.primary_reason)}) - NOT APPLIED"
    )


_ROW_STYLES = {"value": VALUE, "warn": WARN, "muted": MUTED}


def _verbose_evidence_rows(attempt: AudioAlignmentAttempt) -> tuple[EvidenceRow, ...]:
    """Return the shared evidence rows plus the original-attempt context (m2)."""
    return (
        EvidenceRow(key="Original", value=_original_audio_attempt_line(attempt), style="muted"),
        *_review_evidence_rows(attempt),
        *audio_evidence_rows(attempt),
    )


def _verbose_evidence_lines(attempt: AudioAlignmentAttempt) -> list[str]:
    lines = [
        _original_audio_attempt_line(attempt),
        _format_stream_summary(attempt),
    ]
    lines.extend(f"{row.key}: {row.value}" for row in _review_evidence_rows(attempt))
    lines.extend(f"  {row.key}: {row.value}" for row in audio_evidence_rows(attempt))
    return lines


def _render_alignment_evidence_panel(
    *,
    entries: list[
        tuple[
            str,
            tuple[_StyledRow, ...],
            tuple[EvidenceRow, ...],
            tuple[_StyledRow, ...],
        ]
    ],
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
    for index, (comparison_name, lines, verbose_rows, review_lines) in enumerate(entries):
        if index:
            table.add_row("", "")
        table.add_row("", f"[bold]{escape(comparison_name)}[/]")
        for key, value, style in lines:
            table.add_row(key, f"[{style}]{escape(value)}[/]")
        for row in verbose_rows:
            style = _ROW_STYLES[row.style]
            table.add_row(f"  {row.key}", f"[{style}]{escape(row.value)}[/]")
        for key, value, style in review_lines:
            value = f"{waiting_glyph} {value}"
            table.add_row(key, f"[{style}]{escape(value)}[/]")
    if diagnostics_written:
        table.add_row("", "")
        table.add_row("diagnostics", "alignment_diagnostics/")

    title = f"[bold {ACCENT} not dim]Audio alignment[/]"
    if actionable:
        title += f" [dim]· {needs_review_count} needs review[/]"
    console.print(
        Padding(
            Panel(
                table,
                title=title,
                title_align="left",
                border_style=BORDER_PENDING if actionable else BORDER_NEUTRAL,
            ),
            (0, 0, 0, 2),
        ),
        crop=False,
    )


def print_pre_review_summary(
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
        key = alignment_key(request.reference.path, comparison.path)
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


def present_alignment_evidence(
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
    entries: list[
        tuple[
            str,
            tuple[_StyledRow, ...],
            tuple[EvidenceRow, ...],
            tuple[_StyledRow, ...],
        ]
    ] = []
    has_actionable_result = False
    needs_review_count = 0
    for ordinal, comparison in enumerate(request.comparisons, start=1):
        key = alignment_key(request.reference.path, comparison.path)
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
        normal_rows = _normal_evidence_rows(
            ordinal=ordinal,
            result=result,
            provenance=provenance,
        )
        normal_lines = [value for _key, value, _style in normal_rows]
        verbose_lines: list[str] = []
        verbose_rows: tuple[EvidenceRow, ...] = ()
        if verbose and not quiet and result.audio_attempt is not None:
            verbose_lines = _verbose_evidence_lines(result.audio_attempt)
            verbose_rows = _verbose_evidence_rows(result.audio_attempt)
        review_lines: list[str] = []
        review_rows: list[_StyledRow] = []
        if human_actionable and (config.use_vsview or config.force_interactive):
            if decision is not None and decision.candidate is not None:
                review_line = (
                    "Opening VSView for manual review. The candidate is a hint, not a "
                    "confirmed alignment."
                )
            else:
                review_line = (
                    "Opening VSView for manual review. No automatic candidate is available; "
                    "align the sources manually."
                )
            review_lines.append(review_line)
            review_rows.append(("  review", review_line, ACCENT))
        comparison_lines = [*normal_lines, *verbose_lines, *review_lines]
        lines.extend(comparison_lines)
        if human_actionable:
            needs_review_count += 1
        entries.append(
            (
                comparison.compact_name
                or comparison.presentation_name
                or comparison.label
                or comparison.path.name,
                normal_rows,
                verbose_rows,
                tuple(review_rows),
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
