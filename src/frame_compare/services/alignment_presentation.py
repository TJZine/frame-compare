"""Terminal presentation for audio alignment evidence."""

from __future__ import annotations

import sys

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
    audio_unavailable_phrase,
)
from frame_compare.utils.alignment_review_projection import (
    EvidenceRow,
    audio_evidence_rows,
    build_audio_review_presentation,
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
            heading = "Audio alignment accepted"
            detail = None
        rows: list[_StyledRow] = [
            ("", f"{prefix}{heading}: {offset:+d}f - APPLIED", OK),
            ("", "No additional confirmation needed.", MUTED),
        ]
        if detail is not None:
            rows.append(("", detail, MUTED))
        elif result.source == "computed" and result.audio_attempt is not None:
            noted = build_audio_review_presentation(result.audio_attempt).noted_line()
            if noted is not None:
                rows.append(("", noted, MUTED))
        return tuple(rows)

    attempt = result.audio_attempt
    decision = attempt.decision if attempt is not None else None
    review = build_audio_review_presentation(attempt) if attempt is not None else None
    if (
        attempt is not None
        and decision is not None
        and decision.state in {"provisional", "unavailable"}
        and review is not None
        and review.suggested_offset is not None
    ):
        suggested = review.suggested_offset
        assert suggested is not None
        rows = [
            (
                "",
                f"{prefix}Provisional audio candidate: {suggested:+d}f - NOT APPLIED",
                WARN,
            ),
        ]
        rows.extend(
            (
                "",
                row.value,
                WARN if row.style == "warn" else MUTED,
            )
            for row in review.normal_review_rows(
                panel=False,
                action_line="Align manually or keep the current alignment.",
            )
        )
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
            line.append(f"{short} alignment applied")
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
            if isinstance(progress, RichProgressReporter):
                verbose_rows = _verbose_evidence_rows(result.audio_attempt)
            else:
                verbose_lines = _verbose_evidence_lines(result.audio_attempt)
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
