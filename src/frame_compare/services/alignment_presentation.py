"""Terminal presentation for audio alignment evidence."""

from __future__ import annotations

import sys
from pathlib import Path

import structlog
from rich.markup import escape
from rich.text import Text

from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.types import (
    AlignmentConfig,
    ComparisonResolution,
)
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    audio_unavailable_phrase,
)
from frame_compare.utils.alignment_review_projection import (
    EvidenceRow,
    audio_evidence_rows,
    build_audio_review_presentation,
)
from frame_compare.utils.artifact_paths import artifact_link
from frame_compare.utils.progress import RichProgressReporter
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.terminal_sections import Section, section_title
from frame_compare.utils.terminal_theme import (
    ACCENT,
    BORDER_NEUTRAL,
    BORDER_PENDING,
    MUTED,
    OK,
    WARN,
    human_console,
)
from frame_compare.utils.types import AlignmentRequest

log = structlog.get_logger()


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


def _audio_evidence_summary(attempt: AudioAlignmentAttempt) -> Text:
    agreeing = (
        attempt.authority_recount.authority_agreeing_chunks
        if attempt.authority_recount is not None
        else attempt.audio.agreeing_chunks
    )
    text = f"{agreeing} of {attempt.audio.active_chunks} sections agree"
    video = attempt.video_check
    if video.observation == "observed":
        text += (
            f" · video check {video.confirmed_offset:+d}f"
            if video.confirmed_offset is not None
            else " · video check inconclusive"
        )
    stability = attempt.stability.classification.replace("_", " ")
    line = Text(text + " · ", style=MUTED)
    line.append(
        stability,
        style=WARN
        if stability in {"possible drift", "possible discontinuity", "variable"}
        else MUTED,
    )
    return line


def _normal_evidence_rows(
    *, resolution: ComparisonResolution, review_pending: bool
) -> tuple[Text, ...]:
    result = resolution.result
    attempt = result.audio_attempt
    pending = " · confirm in VSView" if review_pending else ""
    rows: list[Text] = []
    if result.applied and result.frame_offset is not None:
        origin = resolution.origin
        state = {
            "shared_computed_offsets": "reused from last run",
            "shared_previous_offsets": "previously confirmed",
            "interactive_confirmed_this_run": "manual offset",
            "preexisting_manual_override": "manual offset",
        }.get(origin, "" if review_pending else "applied")
        heading = f"{result.frame_offset:+d}f" + (f" · {state}" if state else "")
        rows.append(Text(heading + pending, style=OK))
        if origin == "shared_computed_offsets":
            rows.append(Text("no audio analysis ran this time", style=MUTED))
        elif origin == "computed_this_run" and attempt is not None:
            rows.append(_audio_evidence_summary(attempt))
            noted = build_audio_review_presentation(attempt).noted_line()
            if noted is not None:
                rows.append(Text(noted, style=MUTED))
        return tuple(rows)

    decision = attempt.decision if attempt is not None else None
    review = build_audio_review_presentation(attempt) if attempt is not None else None
    if review is not None and review.suggested_offset is not None:
        rows.append(Text(f"{review.suggested_offset:+d}f · not applied" + pending, style=WARN))
    else:
        reason = decision.primary_reason if decision is not None else result.diagnostic
        phrase = audio_unavailable_phrase(reason) if reason else "no usable audio signal"
        rows.append(Text(f"no audio match ({phrase})" + pending, style=WARN))
    if attempt is not None:
        rows.append(_audio_evidence_summary(attempt))
        noted = review.noted_line() if review is not None else None
        if noted is not None:
            rows.append(Text(noted, style=MUTED))
    if review is not None:
        # Keep the existing reason/region/check-point copy and its bounds.
        detail_rows = review.normal_review_rows(
            panel=False, action_line="Align manually or keep the current alignment."
        )
        rows.extend(
            Text(row.value, style=WARN if row.style == "warn" else MUTED)
            for row in detail_rows
            if not (review_pending and row.value == "Align manually or keep the current alignment.")
        )
    elif not review_pending:
        rows.append(Text("Align manually or keep the current alignment.", style=MUTED))
    return tuple(rows)


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


def _verbose_evidence_rows(attempt: AudioAlignmentAttempt) -> tuple[EvidenceRow, ...]:
    """Return the shared evidence rows plus the original-attempt context (m2)."""
    return (
        EvidenceRow(key="Original", value=_original_audio_attempt_line(attempt), style="muted"),
        *build_audio_review_presentation(attempt).verbose_rows(),
        *audio_evidence_rows(attempt),
    )


def _verbose_evidence_lines(attempt: AudioAlignmentAttempt) -> list[str]:
    lines = [
        _original_audio_attempt_line(attempt),
        _format_stream_summary(attempt),
    ]
    lines.extend(build_audio_review_presentation(attempt).verbose_lines())
    lines.extend(f"  {row.key}: {row.value}" for row in audio_evidence_rows(attempt))
    return lines


def _render_alignment_evidence_panel(
    *,
    entries: list[tuple[str, tuple[Text, ...], tuple[EvidenceRow, ...]]],
    diagnostics_dir: Path | None,
    no_color: bool,
    needs_review_count: int,
    root: Path | None,
    verbose: bool,
) -> None:
    section = Section(
        title=section_title(
            "Audio alignment",
            detail=(f"{needs_review_count} needs review" if needs_review_count else None),
        ),
        rail_style=BORDER_PENDING if needs_review_count else BORDER_NEUTRAL,
    )
    for index, (name, rows, verbose_rows) in enumerate(entries):
        if index:
            section.add_line()
        section.add_line(Text.assemble((name, "bold"), "  ", rows[0]))
        for line in rows[1:]:
            section.add_line(line)
        for row in verbose_rows:
            section.add_row(row.key, f"[dim]{escape(row.value)}[/]")
    if diagnostics_dir is not None:
        section.add_line()
        section.add_row("diagnostics", artifact_link(diagnostics_dir, root=root, verbose=verbose))
    section.print(human_console(stderr=True, no_color=no_color, height=1000))


def present_alignment_evidence(
    *,
    request: AlignmentRequest,
    resolutions: dict[str, ComparisonResolution],
    config: AlignmentConfig,
    progress: ProgressReporter | None,
    verbose: bool,
    quiet: bool,
    json_output: bool,
    diagnostics_written: bool,
    review_pending: bool = False,
) -> None:
    lines: list[str] = []
    entries: list[tuple[str, tuple[Text, ...], tuple[EvidenceRow, ...]]] = []
    needs_review_count = 0
    for ordinal, comparison in enumerate(request.comparisons, start=1):
        key = alignment_key(request.reference.path, comparison.path)
        resolution = resolutions[key]
        result = resolution.result
        decision = result.audio_attempt.decision if result.audio_attempt is not None else None
        human_actionable = not result.applied
        json_actionable = human_actionable or (
            decision is not None and decision.state != "trusted_automatic"
        )
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
            resolution=resolution,
            review_pending=review_pending,
        )
        normal_lines = [line.plain for line in normal_rows]
        short = comparison.short_name or comparison.label or comparison.path.name
        normal_lines[0] = f"{short}: {normal_lines[0]}"
        normal_lines[1:] = [f"  {line}" for line in normal_lines[1:]]
        verbose_lines: list[str] = []
        verbose_rows: tuple[EvidenceRow, ...] = ()
        if verbose and not quiet and result.audio_attempt is not None:
            if isinstance(progress, RichProgressReporter):
                verbose_rows = _verbose_evidence_rows(result.audio_attempt)
            else:
                verbose_lines = _verbose_evidence_lines(result.audio_attempt)
        if human_actionable and review_pending:
            review_line = (
                "Opening VSView for manual review. The candidate is a hint, not a confirmed alignment."
                if decision is not None and decision.candidate is not None
                else "Opening VSView for manual review. No automatic candidate is available; align the sources manually."
            )
            normal_rows = (*normal_rows, Text(review_line, style=ACCENT))
            normal_lines.append("  " + review_line)
        lines.extend([*normal_lines, *(f"  {line}" for line in verbose_lines)])
        if human_actionable:
            needs_review_count += 1
        entries.append((short, normal_rows, verbose_rows))
    diagnostics_dir = request.alignment_diagnostics_dir if diagnostics_written else None
    if diagnostics_dir is not None and not quiet and not json_output:
        lines.append(f"Audio diagnostics: {diagnostics_dir}")
    if not lines:
        return
    if progress is not None:
        progress.suspend()
    try:
        if isinstance(progress, RichProgressReporter):
            _render_alignment_evidence_panel(
                entries=entries,
                diagnostics_dir=diagnostics_dir if not quiet else None,
                no_color=config.no_color,
                needs_review_count=needs_review_count,
                root=request.workspace_root,
                verbose=verbose,
            )
        else:
            print("\n".join(lines), file=sys.stderr)
    finally:
        if progress is not None:
            progress.resume()
