"""Native VSView tool panel for Frame Compare alignment review."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from math import floor
from statistics import median
from typing import Any, Literal, Protocol, cast, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from vsview.api import PluginAPI, VideoOutputProxy, WidgetPluginBase, hookimpl, run_in_loop

from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoTargetEvidence,
    audio_evidence_rows,
    audio_unavailable_phrase,
)
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewComparisonMetadata,
    AlignmentReviewContractError,
    AlignmentReviewDecision,
    AlignmentReviewOutputCandidate,
    AlignmentReviewResult,
    AlignmentReviewSession,
    AlignmentReviewWorkspaceMetadata,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    alignment_review_session_from_script,
    parse_alignment_review_workspace_metadata,
    write_alignment_review_result,
)

_TIMELINE_GROUP = "frame_compare_alignment_review"
type _InputBasis = Literal["positions", "offsets"]
type _FrameOrigin = Literal["Viewer", "Manual"]
_MANUAL_AUTHORITY_ORIGINS = frozenset(
    {
        "interactive_confirmed_this_run",
        "shared_previous_offsets",
        "preexisting_manual_override",
    }
)
_POSITIONS_GUIDANCE = (
    "To confirm a new alignment, unlink the playheads and position each source on the same "
    "visible moment. Or keep the current alignment."
)
_OFFSETS_GUIDANCE = (
    "Enter the signed reference-minus-comparison offsets, then confirm. Or keep the current "
    "alignment."
)
_KEEP_HELP = (
    "Keeps existing alignment. Provisional candidates are not confirmed; unresolved "
    "comparisons remain unresolved."
)
_SAVED_GUIDANCE = "Close VSView to resume Frame Compare."
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


def _format_region(region: _Region) -> str:
    return f"{_format_time(region.start)}–{_format_time(region.end)}"


def _frame_for_lag(attempt: AudioAlignmentAttempt, lag: int) -> int:
    compensation = attempt.audio.compensation_seconds or 0.0
    seconds = lag / attempt.analysis.analysis_rate + compensation
    return floor(seconds * attempt.fps_num / attempt.fps_den + 0.5)


def _chunk_bounds(attempt: AudioAlignmentAttempt, first: int, last: int) -> tuple[float, float]:
    if (
        attempt.chunks.starts
        and 0 <= first < len(attempt.chunks.starts)
        and 0 <= last < len(attempt.chunks.starts)
    ):
        rate = attempt.analysis.analysis_rate
        return (
            attempt.chunks.starts[first] / rate,
            (attempt.chunks.starts[last] + attempt.chunks.counts[last]) / rate,
        )
    chunk = attempt.analysis.chunk_samples / attempt.analysis.analysis_rate
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


def _suggested_offset(comparison: AlignmentReviewComparisonMetadata) -> int | None:
    video = comparison.audio_review.audio_attempt
    if video is not None and video.video_check.confirmed_offset is not None:
        return video.video_check.confirmed_offset
    if video is not None and video.decision.candidate is not None:
        return video.decision.candidate.frame_offset
    return comparison.audio_review.current_authority.frame_offset


def _regions(attempt: AudioAlignmentAttempt, suggested: int | None) -> tuple[_Region, ...]:
    targets = _target_map(attempt.video_check)
    regions: list[_Region] = []
    seen: set[tuple[int, int, int]] = set()
    for run in attempt.runs:
        offset = (
            suggested
            if suggested is not None and run.lag == attempt.audio.global_lag
            else _frame_for_lag(attempt, run.lag)
        )
        start, end = _chunk_bounds(attempt, run.first_index, run.last_index)
        target = targets.get(("run", run.first_index, run.last_index))
        region = _Region(
            offset=offset,
            start=start,
            end=end,
            status=(
                "confirmed by video"
                if attempt.video_check.confirmed_offset == offset
                else _target_status(target)
            ),
        )
        if suggested is None or offset != suggested or not regions:
            key = (offset, run.first_index, run.last_index)
            if key not in seen:
                regions.append(region)
                seen.add(key)
    if suggested is not None and not any(region.offset == suggested for region in regions):
        planned = attempt.analysis.planned_chunk_count
        start, end = _chunk_bounds(attempt, 0, planned - 1) if planned else (0.0, 0.0)
        regions.insert(
            0,
            _Region(
                suggested,
                start,
                end,
                "confirmed by video"
                if attempt.video_check.confirmed_offset == suggested
                else "not settled",
            ),
        )
    for target in attempt.video_check.targets:
        if target.kind == "run" and any(
            (target.first_chunk_index, target.last_chunk_index) == (run.first_index, run.last_index)
            for run in attempt.runs
        ):
            continue
        if not target.alternative_offsets:
            continue
        start, end = _chunk_bounds(attempt, target.first_chunk_index, target.last_chunk_index)
        region = _Region(target.alternative_offsets[0], start, end, _target_status(target))
        key = (region.offset, target.first_chunk_index, target.last_chunk_index)
        if key not in seen:
            regions.append(region)
            seen.add(key)
    return tuple(regions)


def _reason_region(
    regions: tuple[_Region, ...], suggested: int | None, reason: str
) -> _Region | None:
    candidates = tuple(region for region in regions if region.offset != suggested)
    if reason == "competing_offset_confirmed_by_video":
        candidates = tuple(region for region in candidates if region.status == "confirmed by video")
    elif reason == "competing_offset":
        candidates = tuple(region for region in candidates if region.status != "confirmed by video")
    return candidates[0] if candidates else (regions[0] if regions else None)


def _reason_lines(attempt: AudioAlignmentAttempt) -> tuple[str, ...]:
    suggested = (
        attempt.video_check.confirmed_offset
        if attempt.video_check.confirmed_offset is not None
        else attempt.decision.candidate.frame_offset
        if attempt.decision.candidate is not None
        else None
    )
    regions = _regions(attempt, suggested)
    lines: list[str] = []
    for reason in dict.fromkeys(
        attempt.decision.failed_gates or (attempt.decision.primary_reason,)
    ):
        region = _reason_region(regions, suggested, reason)
        if reason == "competing_offset_confirmed_by_video" and region is not None:
            lines.append(
                f"The video confirms {region.offset:+d}f in {_format_region(region)}, "
                "so the sources likely differ by an edit there."
            )
        elif reason == "competing_offset" and region is not None:
            lines.append(
                f"Audio in {_format_region(region)} points to {region.offset:+d}f, and the video "
                "could not settle which offset is right there."
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
                    f"Audio in {_format_region(region)} points to {region.offset:+d}f, and the video "
                    "could not rule that out."
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
        elif reason == "no_single_offset" and attempt.video_check.confirmed_offset is not None:
            lines.append(
                "The audio does not agree on one offset across the track; the video suggests "
                f"{attempt.video_check.confirmed_offset:+d}f at the checked points."
            )
    return tuple(dict.fromkeys(lines))


def _check_point_line(point: VideoCheckPoint) -> str:
    offset = point.reference_frame - point.suggested_comparison_frame
    return (
        f"Check {_format_time(point.timestamp_seconds)} — reference {point.reference_frame:,} "
        f"↔ comparison {point.suggested_comparison_frame:,} ({offset:+d}f)"
    )


def _video_established_line(attempt: AudioAlignmentAttempt) -> str:
    video = attempt.video_check
    if video.observation != "observed":
        return "Video: not observed."
    if video.confirmed_offset is None:
        return f"Video: did not confirm an offset at {len(video.positions)} check points."
    index = video.scored_offsets.index(video.confirmed_offset)
    wins = sum(
        min(position.score_by_offset) == position.score_by_offset[index]
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


def _detail_lines(attempt: AudioAlignmentAttempt) -> tuple[str, ...]:
    recount = attempt.authority_recount
    agreeing = (
        recount.authority_agreeing_chunks if recount is not None else attempt.audio.agreeing_chunks
    )
    suggested = (
        attempt.video_check.confirmed_offset
        if attempt.video_check.confirmed_offset is not None
        else attempt.decision.candidate.frame_offset
        if attempt.decision.candidate is not None
        else attempt.audio.rounded_frame
    )
    lines = [
        (
            f"Established: Audio: {agreeing} of {attempt.audio.credible_chunks} sections agree on "
            f"{(suggested or 0):+d}f ({max(0, attempt.audio.credible_chunks - agreeing)} differ, "
            f"{max(0, attempt.audio.active_chunks - attempt.audio.credible_chunks)} quiet)."
        ),
        _video_established_line(attempt),
    ]
    for index, region in enumerate(_regions(attempt, suggested)):
        lines.append(
            f"{'Regions: ' if index == 0 else '':<9}{region.offset:+d}f  {_format_region(region)}  {region.status}"
        )
    if recount is not None and recount.raw_agreeing_chunks != recount.authority_agreeing_chunks:
        lines.append(
            f"Context: Audio (raw): {recount.raw_agreeing_chunks} of {attempt.audio.credible_chunks} "
            f"sections agree; {recount.authority_agreeing_chunks - recount.raw_agreeing_chunks} more "
            "are within the same frame, so "
            f"{recount.authority_agreeing_chunks} of {attempt.audio.credible_chunks} agree for this offset."
        )
    for item in attempt.video_check.same_frame_context:
        start, end = _chunk_bounds(attempt, item.chunk_index, item.chunk_index)
        lines.append(
            f"Context: 1 section differs by less than a frame ({_format_region(_Region(0, start, end, 'not settled'))}); not a disagreement."
        )
    for target in attempt.video_check.targets:
        if target.resolution == "alternative_confirmed" or target.kind != "chunk":
            continue
        start, end = _chunk_bounds(attempt, target.first_chunk_index, target.last_chunk_index)
        credible = (
            target.first_chunk_index < len(attempt.chunks.credible)
            and attempt.chunks.credible[target.first_chunk_index]
        )
        if credible and target.resolution == "resolved":
            lines.append(
                f"Context: Audio differed in {_format_region(_Region(0, start, end, 'not settled'))}; "
                "the video confirmed the offset there."
            )
        else:
            lines.append(
                f"Context: Picture differs in {_format_region(_Region(0, start, end, 'not settled'))} "
                "(for example a replaced shot); offset still holds."
            )
        break
    for index, point in enumerate(attempt.video_check.check_points):
        lines.append(f"{'Check points: ' if index == 0 else '':<14}{_check_point_line(point)}")
    decision = attempt.decision
    lines.append(
        f"Decision: state={decision.state}; reason={decision.primary_reason}; "
        f"also={','.join(decision.failed_gates[1:]) or 'none'}"
    )
    return tuple(lines)


def _noted_line(attempt: AudioAlignmentAttempt) -> str | None:
    suggested = (
        attempt.video_check.confirmed_offset
        if attempt.video_check.confirmed_offset is not None
        else attempt.decision.candidate.frame_offset
        if attempt.decision.candidate is not None
        else None
    )
    if suggested is None:
        return None
    if attempt.video_check.same_frame_context:
        item = attempt.video_check.same_frame_context[0]
        start, end = _chunk_bounds(attempt, item.chunk_index, item.chunk_index)
        count = len(attempt.video_check.same_frame_context)
        return (
            f"Noted: audio differed in {count} section{'s' if count != 1 else ''} "
            f"({_format_region(_Region(0, start, end, 'not settled'))}); the video confirmed "
            f"{suggested:+d}f there."
        )
    for target in attempt.video_check.targets:
        if target.resolution == "alternative_confirmed":
            continue
        if target.kind == "chunk":
            start, end = _chunk_bounds(attempt, target.first_chunk_index, target.last_chunk_index)
            credible = (
                target.first_chunk_index < len(attempt.chunks.credible)
                and attempt.chunks.credible[target.first_chunk_index]
            )
            if credible and target.resolution == "resolved":
                count = target.last_chunk_index - target.first_chunk_index + 1
                return (
                    f"Noted: audio differed in {count} section{'s' if count != 1 else ''} "
                    f"({_format_region(_Region(0, start, end, 'not settled'))}); the video "
                    f"confirmed {suggested:+d}f there."
                )
            return (
                f"Noted: the picture differs in {_format_region(_Region(0, start, end, 'not settled'))} "
                "(for example a replaced shot); the offset still holds."
            )
    return None


@dataclass(slots=True)
class _SourceDraft:
    output_id: int
    presentation_name: str
    role_label: str
    source_frame_count: int
    frame: int | None = None
    origin: _FrameOrigin | None = None
    error: str | None = None


@dataclass(slots=True)
class _OffsetDraft:
    value: int | None = None
    error: str | None = None


class _Clip(Protocol):
    num_frames: int


class _VideoOutputTuple(Protocol):
    clip: _Clip


def _source_frame_count(output: VideoOutputProxy) -> int:
    vs_output = cast(_VideoOutputTuple, getattr(output, "vs_output"))  # noqa: B009
    return vs_output.clip.num_frames


class AlignmentReviewPanel(WidgetPluginBase[Any, Any]):
    identifier = "frame_compare_alignment_review"
    display_name = "Frame Compare Alignment Review"

    def __init__(self, parent: QWidget, api: PluginAPI) -> None:
        super().__init__(parent, api)
        self._workspace: AlignmentReviewWorkspaceMetadata | None = None
        self._session: AlignmentReviewSession | None = None
        self._source_drafts = list[_SourceDraft]()
        self._offset_drafts = list[_OffsetDraft]()
        self._active_output_id: int | None = None
        self._basis: _InputBasis = "positions"
        self._saved = False
        self._kept_current = False
        self._saved_offsets: tuple[int, ...] | None = None
        self._build_ui()
        self._show_inactive(clear_marker=False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.progress_label = QLabel(self)
        self.progress_label.setWordWrap(True)
        self.progress_label.setAccessibleName("Alignment review status")
        self.progress_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        progress_font = self.progress_label.font()
        progress_font.setBold(True)
        self.progress_label.setFont(progress_font)
        layout.addWidget(self.progress_label)

        self.guidance_label = QLabel(_POSITIONS_GUIDANCE, self)
        self.guidance_label.setWordWrap(True)
        layout.addWidget(self.guidance_label)

        self.basis_status_label = QLabel("Input basis: Source frames", self)
        self.basis_status_label.setWordWrap(True)
        layout.addWidget(self.basis_status_label)

        self.body_scroll = QScrollArea(self)
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setAccessibleName("Alignment source lineup and manual inputs")
        self.body_widget = QWidget(self.body_scroll)
        self.body_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        self.body_scroll.setWidget(self.body_widget)
        layout.addWidget(self.body_scroll, 1)

        self.lineup_group = QGroupBox("Source lineup", self.body_widget)
        self.lineup_layout = QVBoxLayout(self.lineup_group)
        self.lineup_layout.setSpacing(4)
        body_layout.addWidget(self.lineup_group)
        self.source_status_labels = list[QLabel]()
        self.source_outcome_labels = list[QLabel]()

        self.audio_group = QGroupBox("Audio evidence", self.body_widget)
        self.audio_layout = QVBoxLayout(self.audio_group)
        body_layout.addWidget(self.audio_group)
        self.audio_summary_labels = list[QLabel]()
        self.audio_detail_groups = list[QGroupBox]()

        self.manual_toggle = QPushButton("Enter alignment manually...", self.body_widget)
        self.manual_toggle.setCheckable(True)
        self.manual_toggle.setAccessibleName("Enter alignment manually")
        self.manual_toggle.toggled.connect(self._toggle_manual)
        body_layout.addWidget(self.manual_toggle)

        self.manual_group = QGroupBox("Manual alignment", self.body_widget)
        manual_layout = QVBoxLayout(self.manual_group)
        manual_layout.setSpacing(8)
        basis_form = QFormLayout()
        self.basis_selector = QComboBox(self.manual_group)
        self.basis_selector.setAccessibleName("Manual alignment input basis")
        self.basis_selector.addItems(["Source frames", "Known offsets"])
        self.basis_selector.currentIndexChanged.connect(self._basis_changed)
        basis_form.addRow("Input basis:", self.basis_selector)
        manual_layout.addLayout(basis_form)

        self.frame_inputs_group = QGroupBox("Untrimmed source frames", self.manual_group)
        self.frame_inputs_form = QFormLayout(self.frame_inputs_group)
        manual_layout.addWidget(self.frame_inputs_group)
        self.frame_inputs = list[QLineEdit]()

        self.offset_inputs_group = QGroupBox("Known signed offsets", self.manual_group)
        self.offset_inputs_form = QFormLayout(self.offset_inputs_group)
        manual_layout.addWidget(self.offset_inputs_group)
        self.offset_inputs = list[QLineEdit]()
        self.offset_inputs_group.hide()
        self.manual_group.hide()
        body_layout.addWidget(self.manual_group)

        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setAccessibleName("Alignment review error")
        body_layout.addStretch()
        layout.addWidget(self.error_label)

        self.use_positions_button = QPushButton("Confirm these aligned positions", self)
        self.use_positions_button.clicked.connect(self._save_positions)
        layout.addWidget(self.use_positions_button)

        self.keep_help_label = QLabel(_KEEP_HELP, self)
        self.keep_help_label.setWordWrap(True)
        layout.addWidget(self.keep_help_label)
        self.keep_button = QPushButton("Keep current alignment", self)
        self.keep_button.clicked.connect(self._save_keep_current)
        layout.addWidget(self.keep_button)
        layout.addStretch()

    @override
    @run_in_loop(return_future=False)
    def on_workspace_loaded(self) -> None:
        self._activate_workspace()

    @override
    @run_in_loop(return_future=False)
    def on_current_voutput_changed(self, voutput: VideoOutputProxy, tab_index: int) -> None:
        del voutput, tab_index
        self._record_active_frame()

    @override
    @run_in_loop(return_future=False)
    def on_current_frame_changed(self, n: int) -> None:
        del n
        self._record_active_frame()

    def _activate_workspace(self) -> None:
        self._show_inactive()
        if self.api.file_path is None:
            return
        try:
            outputs = tuple(self.api.voutputs)
            if not any(
                isinstance(getattr(output, "kwargs", None), Mapping)
                and "frame_compare_contract_version" in output.kwargs
                for output in outputs
            ):
                return
            workspace = parse_alignment_review_workspace_metadata(
                tuple(
                    AlignmentReviewOutputCandidate(
                        output_id=output.vs_index,
                        source_frame_count=_source_frame_count(output),
                        metadata=output.kwargs,
                    )
                    for output in outputs
                )
            )
            session = alignment_review_session_from_script(
                self.api.file_path, require_result_absent=True
            )
            if session.session_id != workspace.session_id:
                raise AlignmentReviewContractError("alignment review session identity mismatch")
        except AlignmentReviewContractError as exc:
            message = str(exc)
            if message.startswith("Alignment review requires a newly generated session."):
                self.error_label.setText(message)
            else:
                self.error_label.setText(f"Alignment review rejected: {message}")
            return
        except (OSError, AttributeError, TypeError) as exc:
            self.error_label.setText(
                "Alignment review unavailable: workspace could not be read safely "
                f"({type(exc).__name__})."
            )
            return

        self._workspace = workspace
        self._session = session
        self._source_drafts = [
            _SourceDraft(
                output_id=workspace.reference.output_id,
                presentation_name=workspace.reference.presentation_name,
                role_label="Reference",
                source_frame_count=workspace.reference.source_frame_count,
            ),
            *(
                _SourceDraft(
                    output_id=comparison.output_id,
                    presentation_name=comparison.presentation_name,
                    role_label=f"Comparison {comparison.comparison_ordinal}",
                    source_frame_count=comparison.source_frame_count,
                )
                for comparison in workspace.comparisons
            ),
        ]
        self._offset_drafts = [_OffsetDraft() for _comparison in workspace.comparisons]
        self._populate_source_controls()
        self._populate_audio_evidence()
        self.manual_toggle.setEnabled(True)
        self.keep_button.setEnabled(True)
        self.basis_selector.setEnabled(True)
        self._refresh_ui()

    def _populate_source_controls(self) -> None:
        self._clear_layout(self.lineup_layout)
        self._clear_layout(self.frame_inputs_form)
        self._clear_layout(self.offset_inputs_form)
        self.source_status_labels.clear()
        self.source_outcome_labels.clear()
        self.frame_inputs.clear()
        self.offset_inputs.clear()

        for index, draft in enumerate(self._source_drafts):
            if index:
                divider = QFrame(self.lineup_group)
                divider.setFrameShape(QFrame.Shape.HLine)
                self.lineup_layout.addWidget(divider)
            name = QLabel(f"{draft.role_label} — {draft.presentation_name}", self.lineup_group)
            status = QLabel(self.lineup_group)
            outcome = QLabel(self.lineup_group)
            for label in (name, status, outcome):
                label.setWordWrap(True)
            status.setAccessibleName(f"{draft.role_label} position status")
            outcome.setAccessibleName(f"{draft.role_label} alignment outcome")
            self.lineup_layout.addWidget(name)
            self.lineup_layout.addWidget(outcome)
            self.lineup_layout.addWidget(status)
            self.source_status_labels.append(status)
            self.source_outcome_labels.append(outcome)

            field = self._manual_input(f"{draft.role_label} untrimmed source frame")
            field.textChanged.connect(partial(self._manual_frame_changed, index))
            self.frame_inputs_form.addRow(f"{draft.role_label}:", field)
            self.frame_inputs.append(field)

        if self._workspace is None:
            return
        for index, comparison in enumerate(self._workspace.comparisons):
            field = self._manual_input(
                f"{comparison.presentation_name} known signed alignment offset"
            )
            field.setPlaceholderText("e.g. +12 or -12")
            field.textChanged.connect(partial(self._offset_changed, index))
            self.offset_inputs_form.addRow(f"Comparison {comparison.comparison_ordinal}:", field)
            self.offset_inputs.append(field)

    def _populate_audio_evidence(self) -> None:
        self._clear_layout(self.audio_layout)
        self.audio_summary_labels.clear()
        self.audio_detail_groups.clear()
        if self._workspace is None:
            return
        for comparison in self._workspace.comparisons:
            summary = QLabel(_audio_summary(comparison), self.audio_group)
            summary.setWordWrap(True)
            summary.setAccessibleName(
                f"Comparison {comparison.comparison_ordinal} audio evidence summary"
            )
            self.audio_layout.addWidget(summary)
            details = QGroupBox(
                f"Audio evidence details — Comparison {comparison.comparison_ordinal}",
                self.audio_group,
            )
            details.setCheckable(True)
            details.setChecked(False)
            details.setAccessibleName(
                f"Comparison {comparison.comparison_ordinal} audio evidence details"
            )
            details_layout = QVBoxLayout(details)
            detail_label = QLabel(
                _audio_details(comparison, self._workspace.reference.source_frame_count),
                details,
            )
            detail_label.setWordWrap(True)
            details_layout.addWidget(detail_label)
            detail_label.setVisible(False)
            details.toggled.connect(detail_label.setVisible)
            self.audio_layout.addWidget(details)
            self.audio_summary_labels.append(summary)
            self.audio_detail_groups.append(details)

    def _manual_input(self, accessible_name: str) -> QLineEdit:
        field = QLineEdit(self.manual_group)
        field.setPlaceholderText("Not entered")
        field.setAccessibleName(accessible_name)
        return field

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QFormLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_inactive(self, *, clear_marker: bool = True) -> None:
        if clear_marker:
            self.api.timeline.clear_notches(_TIMELINE_GROUP)
        self._workspace = None
        self._session = None
        self._source_drafts.clear()
        self._offset_drafts.clear()
        self._active_output_id = None
        self._basis = "positions"
        self._saved = False
        self._kept_current = False
        self._saved_offsets = None
        self.guidance_label.setText(_POSITIONS_GUIDANCE)
        self.progress_label.setText("Inactive — not a Frame Compare alignment session")
        self.basis_status_label.setText("Input basis: Source frames")
        self.error_label.clear()
        self.manual_toggle.blockSignals(True)
        self.manual_toggle.setChecked(False)
        self.manual_toggle.blockSignals(False)
        self.manual_toggle.setText("Enter alignment manually...")
        self.manual_toggle.setEnabled(False)
        self.manual_group.hide()
        self.basis_selector.blockSignals(True)
        self.basis_selector.setCurrentIndex(0)
        self.basis_selector.blockSignals(False)
        self.basis_selector.setEnabled(False)
        self.frame_inputs_group.show()
        self.offset_inputs_group.hide()
        self._clear_layout(self.lineup_layout)
        self._clear_layout(self.frame_inputs_form)
        self._clear_layout(self.offset_inputs_form)
        self._clear_layout(self.audio_layout)
        self.source_status_labels.clear()
        self.source_outcome_labels.clear()
        self.frame_inputs.clear()
        self.offset_inputs.clear()
        self.audio_summary_labels.clear()
        self.audio_detail_groups.clear()
        self.use_positions_button.setText("Confirm these aligned positions")
        self.use_positions_button.setEnabled(False)
        self.keep_help_label.setText(_KEEP_HELP)
        self.keep_help_label.show()
        self.keep_button.setEnabled(False)

    def _toggle_manual(self, visible: bool) -> None:
        self.manual_group.setVisible(visible)
        self.manual_toggle.setText(
            "Hide manual alignment" if visible else "Enter alignment manually..."
        )
        self._refresh_ui()

    def _basis_changed(self, index: int) -> None:
        self._basis = "positions" if index == 0 else "offsets"
        self.frame_inputs_group.setVisible(self._basis == "positions")
        self.offset_inputs_group.setVisible(self._basis == "offsets")
        self.error_label.clear()
        self._refresh_ui()

    def _manual_frame_changed(self, index: int, text: str) -> None:
        if self._workspace is None or self._saved:
            return
        draft = self._source_drafts[index]
        draft.frame, draft.error = _parse_source_frame(
            text, draft.role_label, draft.source_frame_count
        )
        draft.origin = "Manual" if draft.frame is not None else None
        self._refresh_ui()

    def _offset_changed(self, index: int, text: str) -> None:
        if self._workspace is None or self._saved:
            return
        draft = self._offset_drafts[index]
        comparison = self._workspace.comparisons[index]
        draft.value, draft.error = _parse_offset(
            text,
            comparison,
            self._workspace.reference.source_frame_count,
        )
        self._refresh_ui()

    def _record_active_frame(self) -> None:
        if self._workspace is None or self._saved:
            return
        try:
            output_id = self.api.current_voutput.vs_index
            frame = int(self.api.current_frame)
        except (AttributeError, TypeError, ValueError):
            return
        index = next(
            (
                source_index
                for source_index, draft in enumerate(self._source_drafts)
                if draft.output_id == output_id
            ),
            None,
        )
        if index is None:
            return
        draft = self._source_drafts[index]
        if not 0 <= frame < draft.source_frame_count:
            draft.error = f"{draft.role_label} viewer frame is outside its source range."
            self._refresh_ui()
            return
        draft.frame = frame
        draft.origin = "Viewer"
        draft.error = None
        self._active_output_id = output_id
        field = self.frame_inputs[index]
        field.blockSignals(True)
        field.setText(str(frame))
        field.blockSignals(False)
        self._refresh_markers(index)
        self._refresh_ui()

    def _refresh_markers(self, source_index: int) -> None:
        if self._workspace is None:
            return
        markers = list[tuple[int, str, str]]()
        if source_index == 0:
            for comparison in self._workspace.comparisons:
                marker_offset = _marker_offset(comparison)
                suggestion = _suggested_pair(marker_offset)[0]
                if (
                    suggestion is not None
                    and suggestion < self._source_drafts[0].source_frame_count
                ):
                    markers.append(
                        (
                            suggestion,
                            _marker_color(comparison, "reference"),
                            _marker_text(comparison, suggestion, "reference"),
                        )
                    )
        else:
            comparison = self._workspace.comparisons[source_index - 1]
            marker_offset = _marker_offset(comparison)
            suggestion = _suggested_pair(marker_offset)[1]
            if suggestion is not None and suggestion < comparison.source_frame_count:
                markers.append(
                    (
                        suggestion,
                        _marker_color(comparison, "comparison"),
                        _marker_text(comparison, suggestion, "comparison"),
                    )
                )
        self.api.timeline.clear_notches(_TIMELINE_GROUP, update=not markers)
        for frame, color, label in markers:
            self.api.timeline.add_notch(_TIMELINE_GROUP, frame, color, label)

    def _refresh_ui(self) -> None:
        if self._workspace is None:
            return
        self.basis_status_label.setText(
            "Input basis: Source frames"
            if self._basis == "positions"
            else "Input basis: Known offsets"
        )
        manual_source_basis = self._basis == "positions" and (
            self.manual_toggle.isChecked()
            or any(draft.origin == "Manual" for draft in self._source_drafts)
        )
        if self._basis == "positions":
            self.guidance_label.setText(_POSITIONS_GUIDANCE)
            self.use_positions_button.setText("Confirm these aligned positions")
            ready = sum(
                draft.frame is not None and draft.error is None for draft in self._source_drafts
            )
            total = len(self._source_drafts)
            progress_unit = "source frames entered" if manual_source_basis else "positions captured"
            complete = ready == total
        else:
            self.guidance_label.setText(_OFFSETS_GUIDANCE)
            self.use_positions_button.setText("Confirm these known offsets")
            ready = sum(
                draft.value is not None and draft.error is None for draft in self._offset_drafts
            )
            total = len(self._offset_drafts)
            progress_unit = "offsets entered"
            complete = ready == total

        if self._saved:
            self.progress_label.setText("Alignment choices saved")
            self.guidance_label.setText(_SAVED_GUIDANCE)
            self.keep_help_label.hide()
        else:
            suffix = " — ready to confirm" if complete else ""
            self.progress_label.setText(f"{ready}/{total} {progress_unit}{suffix}")
            self.keep_help_label.show()

        first_error: str | None = None
        reference_frame = self._source_drafts[0].frame
        for index, (draft, status_label, outcome_label) in enumerate(
            zip(
                self._source_drafts,
                self.source_status_labels,
                self.source_outcome_labels,
                strict=True,
            )
        ):
            frame_error = draft.error if self._basis == "positions" else None
            offset_error = (
                self._offset_drafts[index - 1].error
                if self._basis == "offsets" and index > 0
                else None
            )
            if frame_error is not None:
                status = f"Needs attention — {frame_error}"
                first_error = first_error or frame_error
            elif offset_error is not None:
                status = f"Needs attention — {offset_error}"
                first_error = first_error or offset_error
            elif self._basis == "offsets" and index > 0:
                offset_draft = self._offset_drafts[index - 1]
                status = (
                    f"Entered offset: {offset_draft.value:+d}f"
                    if offset_draft.value is not None
                    else "Offset not entered"
                )
            elif draft.frame is None:
                status = (
                    "Entered source frame: not entered"
                    if manual_source_basis
                    else "Captured position: not captured"
                )
            elif (
                not self._saved
                and draft.output_id == self._active_output_id
                and draft.origin == "Viewer"
            ):
                captured_label = (
                    "Entered source frame" if manual_source_basis else "Captured position"
                )
                captured_value = str(draft.frame) if manual_source_basis else f"frame {draft.frame}"
                status = f"Viewing: frame {draft.frame}\n{captured_label}: {captured_value}"
            elif manual_source_basis or draft.origin == "Manual":
                status = f"Entered source frame: {draft.frame}"
            else:
                status = f"Captured position: frame {draft.frame}"
            status_label.setText(status)

            if index == 0:
                outcome = "Reference anchor — no offset"
            else:
                comparison = self._workspace.comparisons[index - 1]
                if self._basis == "offsets":
                    offset = self._offset_drafts[index - 1].value
                elif reference_frame is not None and draft.frame is not None:
                    offset = reference_frame - draft.frame
                else:
                    offset = None
                if self._saved_offsets is not None:
                    outcome = _manual_saved_text(comparison, self._saved_offsets[index - 1])
                elif self._kept_current:
                    outcome = _keep_saved_text(comparison)
                elif offset is not None:
                    outcome = f"{offset:+d}f — {_trim_explanation(offset)}"
                else:
                    outcome = _audio_summary(comparison).splitlines()[0]
            outcome_label.setText(outcome)

        if not self._saved:
            self.error_label.setText(first_error or "")
        self.use_positions_button.setEnabled(complete and not self._saved)

    def _save_positions(self) -> None:
        if self._workspace is None:
            return
        decisions = list[AlignmentReviewDecision]()
        if self._basis == "positions":
            reference_frame = self._source_drafts[0].frame
            if reference_frame is None or any(
                draft.frame is None or draft.error is not None for draft in self._source_drafts
            ):
                return
            for comparison, draft in zip(
                self._workspace.comparisons, self._source_drafts[1:], strict=True
            ):
                if draft.frame is None:
                    return
                decisions.append(
                    ConfirmedAlignmentReviewDecision(
                        comparison_key=comparison.comparison_key,
                        reference_source_frame=reference_frame,
                        comparison_source_frame=draft.frame,
                    )
                )
        else:
            if any(draft.value is None or draft.error is not None for draft in self._offset_drafts):
                return
            for comparison, draft in zip(
                self._workspace.comparisons, self._offset_drafts, strict=True
            ):
                if draft.value is None:
                    return
                reference_frame, comparison_frame = _canonical_pair(draft.value)
                decisions.append(
                    ConfirmedAlignmentReviewDecision(
                        comparison_key=comparison.comparison_key,
                        reference_source_frame=reference_frame,
                        comparison_source_frame=comparison_frame,
                    )
                )
        self._saved_offsets = tuple(
            decision.reference_source_frame - decision.comparison_source_frame
            for decision in decisions
            if isinstance(decision, ConfirmedAlignmentReviewDecision)
        )
        self._write_result(tuple(decisions))
        if not self._saved:
            self._saved_offsets = None

    def _save_keep_current(self) -> None:
        if self._workspace is None:
            return
        self._kept_current = True
        self._write_result(
            tuple(
                KeepCurrentAlignmentReviewDecision(comparison.comparison_key)
                for comparison in self._workspace.comparisons
            )
        )
        if not self._saved:
            self._kept_current = False

    def _write_result(self, decisions: tuple[AlignmentReviewDecision, ...]) -> None:
        if self._workspace is None or self._session is None or self._saved:
            return
        try:
            write_alignment_review_result(
                self._session,
                AlignmentReviewResult(
                    session_id=self._workspace.session_id,
                    decisions=decisions,
                ),
            )
        except (AlignmentReviewContractError, OSError) as exc:
            self.error_label.setText(
                "Could not save alignment. Check available space and folder access, then try "
                f"again. ({type(exc).__name__})"
            )
            return
        self._saved = True
        self.error_label.clear()
        for label in self.audio_summary_labels:
            label.hide()
        self.use_positions_button.setEnabled(False)
        self.keep_button.setEnabled(False)
        self.manual_toggle.setEnabled(False)
        self.basis_selector.setEnabled(False)
        for field in (*self.frame_inputs, *self.offset_inputs):
            field.setReadOnly(True)
        self._refresh_ui()
        self.progress_label.setFocus()


def _parse_source_frame(
    text: str, label: str, source_frame_count: int
) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    if text.startswith("-") and text[1:].isdecimal():
        return None, f'{label} frame must be non-negative; entered "{text}".'
    if not text.isdecimal():
        return None, f'{label} frame must be a whole number; entered "{text}".'
    try:
        frame = int(text)
    except ValueError:
        return None, f'{label} frame must be a whole number; entered "{text}".'
    if frame >= source_frame_count:
        return (
            None,
            f'{label} frame must be between 0 and {source_frame_count - 1}; entered "{text}".',
        )
    return frame, None


def _parse_offset(
    text: str,
    comparison: AlignmentReviewComparisonMetadata,
    reference_source_frame_count: int,
) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    digits = text[1:] if text[:1] in {"+", "-"} else text
    if not digits.isdecimal():
        return None, f"Comparison {comparison.comparison_ordinal} offset must be a signed integer."
    try:
        offset = int(text)
    except ValueError:
        return None, f"Comparison {comparison.comparison_ordinal} offset must be a signed integer."
    reference_frame, comparison_frame = _canonical_pair(offset)
    if reference_frame >= reference_source_frame_count:
        return None, (
            f"Comparison {comparison.comparison_ordinal} offset requires reference frame "
            f"{reference_frame}, outside 0–{reference_source_frame_count - 1}."
        )
    if comparison_frame >= comparison.source_frame_count:
        return None, (
            f"Comparison {comparison.comparison_ordinal} offset requires comparison frame "
            f"{comparison_frame}, outside 0–{comparison.source_frame_count - 1}."
        )
    return offset, None


def _suggested_pair(offset: int | None) -> tuple[int | None, int | None]:
    if offset is None:
        return None, None
    return _canonical_pair(offset)


def _candidate_offset(comparison: AlignmentReviewComparisonMetadata) -> int | None:
    attempt = comparison.audio_review.audio_attempt
    if attempt is None or attempt.decision.candidate is None:
        return None
    return attempt.decision.candidate.frame_offset


def _marker_offset(comparison: AlignmentReviewComparisonMetadata) -> int | None:
    if comparison.audio_review.current_authority.frame_offset is not None:
        return comparison.suggested_offset
    attempt = comparison.audio_review.audio_attempt
    if attempt is not None and attempt.decision.state in {"provisional", "unavailable"}:
        return _suggested_offset(comparison)
    return comparison.suggested_offset


def _marker_color(comparison: AlignmentReviewComparisonMetadata, role: str) -> str:
    origin = comparison.audio_review.current_authority.origin
    if origin in _MANUAL_AUTHORITY_ORIGINS:
        return "#8e6ccf"
    attempt = comparison.audio_review.audio_attempt
    if attempt is not None and attempt.decision.state == "provisional":
        return "#d79b35"
    return "#3daee9" if role == "reference" else "#d79b35"


def _marker_text(comparison: AlignmentReviewComparisonMetadata, frame: int, role: str) -> str:
    offset = _marker_offset(comparison)
    if offset is None:
        return ""
    attempt = comparison.audio_review.audio_attempt
    if comparison.audio_review.current_authority.origin in _MANUAL_AUTHORITY_ORIGINS:
        prefix = "[MANUAL ALIGNMENT]"
    elif (
        attempt is not None
        and comparison.audio_review.current_authority.frame_offset is None
        and _suggested_offset(comparison) is not None
    ):
        prefix = "[PROVISIONAL — NOT APPLIED]"
    elif comparison.audio_review.evidence_availability == "historical_details_unavailable":
        prefix = "[REUSED ACCEPTED AUDIO]"
    else:
        prefix = "[ACCEPTED AUDIO]"
    return f"{prefix} {offset:+d}f — {role} frame {frame}"


def _unavailable_summary_line(comparison: AlignmentReviewComparisonMetadata) -> str:
    attempt = comparison.audio_review.audio_attempt
    reason = attempt.decision.primary_reason if attempt is not None else "no_usable_audio"
    return _unavailable_summary_line_for_reason(reason)


def _audio_summary(comparison: AlignmentReviewComparisonMetadata) -> str:
    authority = comparison.audio_review.current_authority
    lines: list[str] = []
    attempt = comparison.audio_review.audio_attempt
    if authority.origin in _MANUAL_AUTHORITY_ORIGINS and authority.frame_offset is not None:
        lines.extend(
            (
                f"Manually confirmed alignment: {authority.frame_offset:+d}f — APPLIED",
                "No additional confirmation needed.",
            )
        )
    elif authority.origin == "shared_computed_offsets" and authority.frame_offset is not None:
        lines.extend(
            (
                f"Accepted audio alignment reused: {authority.frame_offset:+d}f — APPLIED",
                "No additional confirmation needed.",
            )
        )
    elif authority.origin == "computed_this_run" and authority.frame_offset is not None:
        # U4 video-confirm seam: fresh computed results stay provisional in
        # U3, so this branch only renders once the video check confirms.
        lines.extend(
            (
                f"Accepted audio alignment: {authority.frame_offset:+d}f — APPLIED",
                "No additional confirmation needed.",
            )
        )
    elif attempt is not None and attempt.decision.state in {"provisional", "unavailable"}:
        candidate = _suggested_offset(comparison)
        if candidate is not None:
            regions = _regions(attempt, candidate)
            lines.extend((f"Provisional audio candidate: {candidate:+d}f — NOT APPLIED",))
            if attempt.decision.primary_reason == "video_check_pending":
                lines.append("Video confirmation pending; not applied.")
            else:
                lines.extend(_reason_lines(attempt))
                if any(
                    reason
                    in {
                        "competing_offset_confirmed_by_video",
                        "competing_offset",
                        "unresolved_audio_disagreement",
                    }
                    for reason in dict.fromkeys(
                        attempt.decision.failed_gates or (attempt.decision.primary_reason,)
                    )
                ):
                    lines.extend(
                        f"  {region.offset:+d}f  {_format_region(region)}  {region.status}"
                        for region in regions[:3]
                    )
                    if len(regions) > 3:
                        lines.append(f"and {len(regions) - 3} more regions")
                lines.extend(
                    _check_point_line(point) for point in attempt.video_check.check_points[:2]
                )
                lines.append("Visual confirmation required to use this hint.")
    if not lines:
        lines.append(_unavailable_summary_line(comparison))

    if authority.origin in _MANUAL_AUTHORITY_ORIGINS and attempt is not None:
        original = _original_audio_summary(attempt.decision)
        if original is not None:
            lines.append(f"Original evidence: {original}")
    elif authority.origin == "computed_this_run" and attempt is not None:
        noted = _noted_line(attempt)
        if noted is not None:
            lines.append(noted)
    return "\n".join(lines)


def _original_audio_summary(decision: AudioAlignmentDecision) -> str | None:
    state = decision.state
    candidate = decision.candidate.frame_offset if decision.candidate is not None else None
    if state == "trusted_automatic" and candidate is not None:
        # U4 video-confirm seam: U3 decisions never reach trusted_automatic.
        return f"Accepted audio alignment: {candidate:+d}f — APPLIED"
    if state == "provisional" and candidate is not None:
        return f"Provisional audio candidate: {candidate:+d}f — NOT APPLIED"
    if state == "unavailable":
        return _unavailable_summary_line_for_reason(decision.primary_reason)
    return None


def _unavailable_summary_line_for_reason(reason: str) -> str:
    return f"No usable audio candidate ({audio_unavailable_phrase(reason)}) — NOT APPLIED"


def _audio_details(
    comparison: AlignmentReviewComparisonMetadata,
    reference_source_frame_count: int,
) -> str:
    attempt = comparison.audio_review.audio_attempt
    if attempt is None:
        lines = ["Historical audio details unavailable."]
        _append_marker_bounds_detail(
            lines,
            comparison,
            reference_source_frame_count,
        )
        return "\n".join(lines)
    lines = list(_detail_lines(attempt))
    lines.extend(f"{row.key}: {row.value}" for row in audio_evidence_rows(attempt))
    _append_marker_bounds_detail(lines, comparison, reference_source_frame_count)
    return "\n".join(lines)


def _append_marker_bounds_detail(
    lines: list[str],
    comparison: AlignmentReviewComparisonMetadata,
    reference_source_frame_count: int,
) -> None:
    reference_frame, comparison_frame = _suggested_pair(_marker_offset(comparison))
    if reference_frame is not None and reference_frame >= reference_source_frame_count:
        lines.append("Origin hint marker omitted: reference frame is outside raw source bounds.")
    if comparison_frame is not None and comparison_frame >= comparison.source_frame_count:
        lines.append("Origin hint marker omitted: comparison frame is outside raw source bounds.")


def _keep_saved_text(comparison: AlignmentReviewComparisonMetadata) -> str:
    authority = comparison.audio_review.current_authority
    attempt = comparison.audio_review.audio_attempt
    if authority.origin in _MANUAL_AUTHORITY_ORIGINS and authority.frame_offset is not None:
        return f"Current alignment retained: {authority.frame_offset:+d}f — manually confirmed"
    if authority.frame_offset is not None:
        return f"Accepted alignment retained: {authority.frame_offset:+d}f"
    candidate = _candidate_offset(comparison)
    if attempt is not None and attempt.decision.state == "provisional" and candidate is not None:
        return (
            f"Current alignment retained. Provisional candidate {candidate:+d}f not confirmed "
            "— NOT APPLIED. Comparison unresolved."
        )
    return "Current alignment retained. Comparison unresolved — no accepted alignment."


def _manual_saved_text(comparison: AlignmentReviewComparisonMetadata, offset: int) -> str:
    del comparison
    return f"Alignment confirmed: {offset:+d}f — manually confirmed"


def _canonical_pair(offset: int) -> tuple[int, int]:
    return (offset, 0) if offset >= 0 else (0, abs(offset))


def _trim_explanation(offset: int) -> str:
    if offset > 0:
        return f"Trim {offset} frame(s) from reference"
    if offset < 0:
        return f"Trim {abs(offset)} frame(s) from this comparison"
    return "No additional trim from this raw offset"


@hookimpl(tryfirst=True)
def vsview_register_toolpanel() -> type[WidgetPluginBase[Any, Any]]:
    return AlignmentReviewPanel
