from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from time import monotonic
from typing import Any, Literal, Protocol, cast, override

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid
from vsview.api import (
    NoCurrentVideoOutputError,
    PluginAPI,
    VideoOutputProxy,
    WidgetPluginBase,
    hookimpl,
    run_in_loop,
)

from frame_compare.utils.alignment_evidence import (
    AudioAlignmentDecision,
    audio_unavailable_phrase,
)
from frame_compare.utils.alignment_review_projection import (
    AudioReviewPresentation,
    audio_evidence_rows,
    build_audio_review_presentation,
)
from frame_compare.vsview.alignment_overlay import PANEL_LABEL_EXPLANATION
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
from frame_compare.vsview.alignment_selection import OpeningHint, SelectedCohort, opening_hint

_TIMELINE_GROUP = "frame_compare_alignment_review"
type _InputBasis = Literal["positions", "offsets"]
type _FrameOrigin = Literal["Entered", "Predicted", "Viewer"]
_MANUAL_AUTHORITY_ORIGINS = frozenset(
    {
        "interactive_confirmed_this_run",
        "shared_previous_offsets",
        "preexisting_manual_override",
    }
)
_POSITIONS_GUIDANCE = "Choose an anchor, then select matching frame numbers in the other sources."
_OFFSETS_GUIDANCE = (
    "Enter the signed reference-minus-comparison offsets, then confirm. Or keep the current "
    "alignment."
)
_KEEP_HELP = (
    "Keeps existing alignment. Provisional candidates are not confirmed; unresolved "
    "comparisons remain unresolved."
)
_SAVED_GUIDANCE = "Close VSView to resume Frame Compare."


@dataclass(frozen=True, slots=True)
class _ComparisonPresentation:
    review: AudioReviewPresentation | None
    summary: str
    details: str


@dataclass(slots=True)
class _SourceDraft:
    output_id: int
    presentation_name: str
    role_label: str
    source_frame_count: int
    # Proposed entry only; explicit selected pins belong to SelectedCohort.
    frame: int | None = None
    origin: _FrameOrigin | None = None
    error: str | None = None
    following: bool = True
    viewer_ready: bool = False
    viewer_status: str | None = None


@dataclass(slots=True)
class _PendingFrame:
    token: int
    index: int
    binding: tuple[int, str, int]
    expected: int
    deadline: float
    attempts: int = 0
    deliberate: bool = False


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
        self._presentations: tuple[_ComparisonPresentation, ...] = ()
        self._source_drafts = list[_SourceDraft]()
        self._offset_drafts = list[_OffsetDraft]()
        self._active_output_id: int | None = None
        self._basis: _InputBasis = "positions"
        self._generation = 0
        self._cohort = SelectedCohort.empty(())
        self._hints: tuple[OpeningHint, ...] = ()
        self._action_error: str | None = None
        self._saved_basis: _InputBasis | None = None
        self._saved = False
        self._kept_current = False
        self._saved_offsets: tuple[int, ...] | None = None
        self._follow_token = 0
        self._pending_frame: _PendingFrame | None = None
        self._settle_handler: Callable[[], None] | None = None
        self._follow_timer = QTimer(self)
        self._follow_timer.setSingleShot(True)
        self._modal_active = False
        # Child timer dies with the widget. Invalidate Python tokens before any
        # already queued delivery can access a destroyed QObject.
        self.destroyed.connect(lambda: self._discard_pending_on_destroy())
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
        self.launch_label_explanation = QLabel(PANEL_LABEL_EXPLANATION, self.body_widget)
        self.launch_label_explanation.setWordWrap(True)
        self.launch_label_explanation.setAccessibleName("Video launch labels and current status")
        body_layout.addWidget(self.launch_label_explanation)
        self.lineup_group = QGroupBox("Source frames", self.body_widget)
        self.lineup_layout = QVBoxLayout(self.lineup_group)
        self.lineup_layout.setSpacing(4)
        body_layout.addWidget(self.lineup_group)
        self.source_status_labels = list[QLabel]()
        self.source_outcome_labels = list[QLabel]()
        self.proposal_labels = list[QLabel]()
        self.anchor_buttons = list[QPushButton]()
        self.select_buttons = list[QPushButton]()
        self.clear_buttons = list[QPushButton]()
        self.jump_buttons = list[QPushButton]()
        self.viewer_buttons = list[QPushButton]()
        self.anchor_label = QLabel("No anchor selected", self)
        self.anchor_label.setWordWrap(True)
        layout.insertWidget(3, self.anchor_label)
        self.reset_button = QPushButton("Reset selected moment", self.body_widget)
        self.reset_button.clicked.connect(self._reset_moment)
        body_layout.addWidget(self.reset_button)
        self.audio_group = QGroupBox(
            "Alignment on entry — audio evidence and provenance", self.body_widget
        )
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
        self.use_positions_button = QPushButton("Save selected alignment", self)
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
        self._cancel_follow()
        self._navigation_changed(sample=True)

    @override
    @run_in_loop(return_future=False)
    def on_current_frame_changed(self, n: int) -> None:
        self._navigation_changed()
        self._follow_notification(n)

    def _navigation_changed(self, *, sample: bool = False) -> None:
        if self._workspace is None:
            return
        active = self._current_output_id()
        if active != self._active_output_id:
            self._cancel_follow()
        self._active_output_id = active
        if active is None:
            for draft in self._source_drafts:
                if draft.following:
                    draft.viewer_ready = False
                    draft.viewer_status = "Viewer position temporarily unavailable — enter a number or use viewer frame"
        for index, draft in enumerate(self._source_drafts):
            if draft.output_id == self._active_output_id:
                self._refresh_markers(index)
                if sample:
                    self._sample_viewer(index)
                break
        self._refresh_ui()

    @override
    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.DeferredDelete, QEvent.Type.Close) and hasattr(
            self, "_follow_timer"
        ):
            self._cancel_follow()
        return super().event(event)

    def _discard_pending_on_destroy(self) -> None:
        self._follow_token += 1
        self._pending_frame = None
        self._settle_handler = None
        self._generation += 1
        self._workspace = self._session = None

    def _cancel_follow(self) -> None:
        self._follow_token += 1
        if isValid(self._follow_timer):
            self._follow_timer.stop()
            if self._settle_handler is not None:
                self._follow_timer.timeout.disconnect(self._settle_handler)
        self._settle_handler = None
        if self._pending_frame is not None:
            draft = self._source_drafts[self._pending_frame.index]
            draft.viewer_ready = False
            draft.viewer_status = (
                "Viewer position temporarily unavailable — enter a number or use viewer frame"
            )
        self._pending_frame = None

    def _current_output_id(self) -> int | None:
        try:
            value = cast(object, self.api.current_voutput.vs_index)
            return value if isinstance(value, int) and not isinstance(value, bool) else None
        except (NoCurrentVideoOutputError, AttributeError, TypeError, ValueError):
            return None

    def _can_follow(self, index: int) -> bool:
        return (
            self._workspace is not None
            and self._session is not None
            and self.api.file_path == self._session.script_path
            and self._basis == "positions"
            and not self._saved
            and not self._modal_active
            and 0 <= index < len(self._source_drafts)
            and self._source_drafts[index].following
            and self._current_output_id() == self._source_drafts[index].output_id
        )

    def _sample_viewer(
        self, index: int, *, expected: int | None = None, deliberate: bool = False
    ) -> bool:
        if not self._can_follow(index):
            return False
        draft = self._source_drafts[index]
        try:
            value = cast(object, self.api.current_frame)
        except (NoCurrentVideoOutputError, AttributeError, TypeError, ValueError):
            value = None
        # Revalidate source/file after the public read; callback n is never copied.
        if (
            not self._can_follow(index)
            or not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value < draft.source_frame_count
            or (expected is not None and value != expected)
            or (not deliberate and self.frame_inputs[index].hasFocus())
        ):
            draft.viewer_ready = False
            draft.viewer_status = (
                "Viewer position temporarily unavailable — enter a number or use viewer frame"
            )
            return False
        field = self.frame_inputs[index]
        field.blockSignals(True)
        field.setText(str(value))
        field.blockSignals(False)
        draft.frame, draft.error, draft.origin = value, None, "Viewer"
        draft.viewer_ready, draft.viewer_status = True, None
        return True

    def _follow_notification(self, expected: object) -> None:
        if self._workspace is None:
            return
        self._cancel_follow()
        for index, draft in enumerate(self._source_drafts):
            if not self._can_follow(index):
                continue
            draft.viewer_ready = False
            if (
                isinstance(expected, bool)
                or not isinstance(expected, int)
                or not 0 <= expected < draft.source_frame_count
            ):
                draft.viewer_status = (
                    "Viewer position temporarily unavailable — enter a number or use viewer frame"
                )
                self._refresh_ui()
                return
            pending = _PendingFrame(
                self._follow_token, index, self._binding(index), expected, monotonic() + 0.5
            )
            self._pending_frame = pending
            self._settle_handler = partial(self._settle_frame, pending.token)
            self._follow_timer.timeout.connect(self._settle_handler)
            self._settle_frame(pending.token)
            return
        self._refresh_ui()

    def _settle_frame(self, token: int) -> None:
        pending = self._pending_frame
        if pending is None or pending.token != token:
            return
        if not self._can_follow(pending.index) or pending.binding != self._binding(pending.index):
            self._cancel_follow()
            self._refresh_ui()
            return
        if monotonic() >= pending.deadline or pending.attempts >= 20:
            self._cancel_follow()
        else:
            pending.attempts += 1
            if self._sample_viewer(
                pending.index, expected=pending.expected, deliberate=pending.deliberate
            ):
                self._pending_frame = None
                self._cancel_follow()
            elif self._can_follow(pending.index):
                self._source_drafts[
                    pending.index
                ].viewer_status = "Waiting for viewer position — not ready to select"
                self._follow_timer.start(25)
            else:
                self._cancel_follow()
        self._refresh_ui()

    def _activate_workspace(self) -> None:
        if not isValid(self):
            return
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
        presentations: list[_ComparisonPresentation] = []
        for comparison in workspace.comparisons:
            attempt = comparison.audio_review.audio_attempt
            review = build_audio_review_presentation(attempt) if attempt is not None else None
            presentations.append(
                _ComparisonPresentation(
                    review=review,
                    summary=_audio_summary(comparison, review),
                    details=_audio_details(
                        comparison, workspace.reference.source_frame_count, review
                    ),
                )
            )
        self._presentations = tuple(presentations)
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
        self._cohort = SelectedCohort.empty(
            tuple(d.source_frame_count for d in self._source_drafts)
        )
        self._hints = (OpeningHint(0), *(opening_hint(c) for c in workspace.comparisons))
        self._populate_source_controls()
        self._populate_audio_evidence()
        self.manual_toggle.setEnabled(True)
        self.keep_button.setEnabled(True)
        self.basis_selector.setEnabled(True)
        self._navigation_changed(sample=True)

    def _binding(self, index: int) -> tuple[int, str, int]:
        assert self._workspace is not None
        return self._generation, self._workspace.session_id, self._source_drafts[index].output_id

    def _populate_source_controls(self) -> None:
        self._clear_layout(self.lineup_layout)
        self._clear_layout(self.offset_inputs_form)
        for controls in (
            self.source_status_labels,
            self.source_outcome_labels,
            self.frame_inputs,
            self.proposal_labels,
            self.anchor_buttons,
            self.select_buttons,
            self.clear_buttons,
            self.jump_buttons,
            self.viewer_buttons,
            self.offset_inputs,
        ):
            controls.clear()
        for index, draft in enumerate(self._source_drafts):
            if index:
                divider = QFrame(self.lineup_group)
                divider.setFrameShape(QFrame.Shape.HLine)
                self.lineup_layout.addWidget(divider)
            identity = f"{draft.role_label} — {draft.presentation_name}"
            name = QLabel(identity, self.lineup_group)
            name.setTextFormat(Qt.TextFormat.PlainText)
            name.setToolTip(identity)
            name.setWordWrap(True)
            self.lineup_layout.addWidget(name)
            for collection, description in (
                (self.source_outcome_labels, "prediction and alignment outcome"),
                (self.source_status_labels, "selected frame"),
                (self.proposal_labels, "proposed frame provenance"),
            ):
                label = QLabel(self.lineup_group)
                label.setWordWrap(True)
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setAccessibleName(f"{identity} {description}")
                self.lineup_layout.addWidget(label)
                collection.append(label)
            field = self._manual_input(f"{identity} — Frame to select")
            field.setToolTip(f"{identity}. Enter the video’s Original frame number.")
            field.textChanged.connect(
                partial(self._manual_frame_changed, index, self._binding(index))
            )
            field.setPlaceholderText("Frame")
            field.setMinimumWidth(45)
            field.setMaximumWidth(80)
            entry_row = QHBoxLayout()
            entry_row.setSpacing(4)
            entry_row.addWidget(QLabel("Frame", self.lineup_group))
            entry_row.addWidget(field, 1)
            action_row = QHBoxLayout()
            action_row.setSpacing(4)
            self.lineup_layout.addLayout(entry_row)
            self.lineup_layout.addLayout(action_row)
            viewer_row = QHBoxLayout()
            self.lineup_layout.addLayout(viewer_row)
            self.frame_inputs.append(field)
            for action, collection in (
                ("anchor", self.anchor_buttons),
                ("select", self.select_buttons),
                ("clear", self.clear_buttons),
                ("jump", self.jump_buttons),
                ("viewer", self.viewer_buttons),
            ):
                button = QPushButton(self.lineup_group)
                button.setToolTip(identity)
                button.clicked.connect(
                    partial(self._row_action, index, action, self._binding(index))
                )
                if action == "viewer":
                    viewer_row.addWidget(button)
                    viewer_row.addStretch()
                elif action == "select":
                    entry_row.addWidget(button, 1)
                else:
                    action_row.addWidget(button, 1 if action == "anchor" else 0)
                collection.append(button)
        if self._workspace is None:
            return
        for index, comparison in enumerate(self._workspace.comparisons):
            field = self._manual_input(
                f"{comparison.presentation_name} known signed alignment offset"
            )
            field.setPlaceholderText("e.g. +12 or -12")
            field.textChanged.connect(partial(self._offset_changed, index, self._generation))
            self.offset_inputs_form.addRow(f"Comparison {comparison.comparison_ordinal}:", field)
            self.offset_inputs.append(field)

    def _populate_audio_evidence(self) -> None:
        self._clear_layout(self.audio_layout)
        self.audio_summary_labels.clear()
        self.audio_detail_groups.clear()
        if self._workspace is None:
            return
        for comparison, presentation in zip(
            self._workspace.comparisons, self._presentations, strict=True
        ):
            summary = QLabel(presentation.summary, self.audio_group)
            summary.setWordWrap(True)
            summary.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
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
                presentation.details,
                details,
            )
            detail_label.setWordWrap(True)
            detail_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
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
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            child_layout = item.layout()
            if child_layout is not None:
                AlignmentReviewPanel._clear_layout(child_layout)
                child_layout.deleteLater()
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _show_inactive(self, *, clear_marker: bool = True) -> None:
        self._cancel_follow()
        if clear_marker:
            self.api.timeline.clear_notches(_TIMELINE_GROUP)
        self._workspace = None
        self._session = None
        self._presentations = ()
        self._generation += 1
        self._cohort = SelectedCohort.empty(())
        self._hints = ()
        self._action_error = None
        self._source_drafts.clear()
        self._offset_drafts.clear()
        self._active_output_id = None
        self._basis = "positions"
        self._saved_basis = None
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
        self.offset_inputs_group.hide()
        self._clear_layout(self.lineup_layout)
        self._clear_layout(self.offset_inputs_form)
        self._clear_layout(self.audio_layout)
        self.source_status_labels.clear()
        self.source_outcome_labels.clear()
        self.frame_inputs.clear()
        self.offset_inputs.clear()
        self.audio_summary_labels.clear()
        self.audio_detail_groups.clear()
        self.use_positions_button.setText("Save selected alignment")
        self.use_positions_button.setEnabled(False)
        self.keep_help_label.setText(_KEEP_HELP)
        self.keep_help_label.show()
        self.keep_button.setEnabled(False)
        self.anchor_label.setText("No anchor selected")
        self.reset_button.setEnabled(False)

    def _toggle_manual(self, visible: bool) -> None:
        if self._saved:
            return
        self.manual_group.setVisible(visible)
        if not visible:
            self.basis_selector.setCurrentIndex(0)
        self.manual_toggle.setText(
            "Hide manual alignment" if visible else "Enter alignment manually..."
        )
        self._refresh_ui()

    def _basis_changed(self, index: int) -> None:
        self._cancel_follow()
        self._basis = "positions" if index == 0 else "offsets"
        self.offset_inputs_group.setVisible(self._basis == "offsets")
        self.error_label.clear()
        self._refresh_ui()

    def _manual_frame_changed(self, index: int, binding: tuple[int, str, int], text: str) -> None:
        if (
            self._workspace is None
            or self._saved
            or not 0 <= index < len(self._source_drafts)
            or binding != self._binding(index)
        ):
            return
        self._cancel_follow()
        draft = self._source_drafts[index]
        draft.following, draft.viewer_ready, draft.viewer_status = False, True, None
        draft.frame, draft.error = _parse_source_frame(
            text, draft.role_label, draft.source_frame_count
        )
        draft.origin = "Entered" if text else None
        self._action_error = None
        self._refresh_ui()

    def _offset_changed(self, index: int, generation: int, text: str) -> None:
        if self._workspace is None or self._saved or generation != self._generation:
            return
        draft = self._offset_drafts[index]
        comparison = self._workspace.comparisons[index]
        draft.value, draft.error = _parse_offset(
            text, comparison, self._workspace.reference.source_frame_count
        )
        self._action_error = None
        self._refresh_ui()

    def _action_context(
        self, index: int, binding: tuple[int, str, int]
    ) -> tuple[object, ...] | None:
        if (
            self._workspace is None
            or self._saved
            or self._basis != "positions"
            or self._session is None
            or self.api.file_path != self._session.script_path
            or not 0 <= index < len(self._source_drafts)
            or binding != self._binding(index)
        ):
            return None
        return (binding, self._cohort.revision, self.frame_inputs[index].text(), self.api.file_path)

    def _confirm_reset(self, message: str) -> bool:
        self._cancel_follow()
        self._modal_active = True
        try:
            return (
                QMessageBox.question(
                    self,
                    "Choose a new alignment moment?",
                    message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )
        finally:
            self._modal_active = False

    def _row_action(
        self, index: int, action: str, binding: tuple[int, str, int], _checked: bool = False
    ) -> None:
        context = self._action_context(index, binding)
        if context is None:
            return
        draft = self._source_drafts[index]
        self._action_error = None
        if action == "viewer":
            if self._current_output_id() != draft.output_id:
                self._action_error = "Switch to this source before using its viewer frame."
            else:
                draft.following = True
                pending = self._pending_frame
                if pending is not None and pending.index == index and pending.binding == binding:
                    pending.deliberate = True
                    self._settle_frame(pending.token)
                else:
                    self._cancel_follow()
                    self._sample_viewer(index, deliberate=True)
        elif action == "clear":
            if index == self._cohort.anchor and not self._confirm_reset(
                "Clear the anchor and all selected frames? Proposed numbers and known offsets stay."
            ):
                return
            if context != self._action_context(index, binding):
                return
            self._cohort = self._cohort.clear(index)
        elif action == "jump":
            self._cancel_follow()
            prediction = self._cohort.predict(index, self._hints)
            try:
                active = self.api.current_voutput.vs_index
            except Exception:
                active = None
            if active != draft.output_id:
                self._action_error = "Switch to this source using the viewer source selector first."
            elif prediction.frame is None:
                self._action_error = (
                    "No in-range prediction is available; enter a matching frame manually."
                )
            else:
                draft.following, draft.viewer_ready, draft.viewer_status = False, True, None
                field = self.frame_inputs[index]
                field.blockSignals(True)
                field.setText(str(prediction.frame))
                field.blockSignals(False)
                draft.frame, draft.error, draft.origin = prediction.frame, None, "Predicted"
                try:
                    admitted = self.api.playback.seek(prediction.frame)
                except Exception:
                    self._action_error = (
                        "Could not request the predicted seek; no frame was selected."
                    )
                else:
                    self._action_error = (
                        "Seek requested. Verify the Original frame number before selecting; no frame was selected."
                        if admitted
                        else "Seek was not admitted. Pause playback and try again; no frame was selected."
                    )
        else:
            if draft.following and (not draft.viewer_ready or self._current_output_id() is None):
                return
            self._cancel_follow()
            number, error = _parse_source_frame(
                self.frame_inputs[index].text(), draft.role_label, draft.source_frame_count
            )
            if number is None or error is not None:
                return
            draft.following = False
            if action == "anchor":
                if self._cohort.needs_new_moment(index, number) and not self._confirm_reset(
                    "Choose a new moment and clear the other selected frames? Proposed numbers and known offsets stay."
                ):
                    return
                if context != self._action_context(index, binding):
                    return
                self._cohort = self._cohort.set_anchor(index, number)
            elif action == "select":
                if self._cohort.anchor is None or index == self._cohort.anchor:
                    return
                self._cohort = self._cohort.select(index, number)
        self._navigation_changed()

    def _reset_moment(self) -> None:
        if (
            self._workspace is None
            or self._saved
            or self._basis != "positions"
            or self._session is None
            or self.api.file_path != self._session.script_path
        ):
            return
        self._cancel_follow()
        context = self._generation, self._cohort.revision, self.api.file_path
        if not self._confirm_reset(
            "Clear the anchor and all selected frames? Proposed numbers and known offsets stay."
        ):
            return
        if (
            self._saved
            or self._basis != "positions"
            or context != (self._generation, self._cohort.revision, self.api.file_path)
        ):
            return
        self._cohort = self._cohort.reset()
        self._refresh_ui()
        self.api.timeline.clear_notches(_TIMELINE_GROUP)

    def _refresh_markers(self, source_index: int) -> None:
        self.api.timeline.clear_notches(_TIMELINE_GROUP)
        if (
            self._workspace is None
            or self._saved
            or self._source_drafts[source_index].output_id != self._active_output_id
        ):
            return
        prediction = self._cohort.predict(source_index, self._hints)
        if prediction.frame is not None:
            self.api.timeline.add_notch(
                _TIMELINE_GROUP, prediction.frame, "#e0b020", prediction.description
            )

    def _refresh_ui(self) -> None:
        if self._workspace is None:
            return
        positions = self._basis == "positions"
        self.basis_status_label.setText(
            "Input basis: Selected source frames"
            if positions
            else "Input basis: Known offsets — source pins retained, not submitted"
        )
        self.guidance_label.setText(
            _SAVED_GUIDANCE
            if self._saved
            else _POSITIONS_GUIDANCE
            if positions
            else _OFFSETS_GUIDANCE
        )
        ready = (
            sum(n is not None for n in self._cohort.selected)
            if positions
            else sum(d.value is not None and d.error is None for d in self._offset_drafts)
        )
        total = len(self._source_drafts) if positions else len(self._offset_drafts)
        complete = ready == total and (not positions or self._cohort.anchor is not None)
        self.use_positions_button.setText(
            "Save selected alignment" if positions else "Confirm these known offsets"
        )
        self.use_positions_button.setEnabled(complete and not self._saved)
        if self._saved:
            self.progress_label.setText(
                "Keep decision saved — selected lineup was not confirmed"
                if self._kept_current
                else "Alignment choices saved"
            )
            self.keep_help_label.hide()
        else:
            self.progress_label.setText(
                f"{ready}/{total} {'frames selected' if positions else 'offsets entered'}"
                + (" — ready to save" if complete else "")
            )
            self.keep_help_label.show()
        anchor = self._cohort.anchor
        self.anchor_label.setText(
            "No anchor selected"
            if anchor is None
            else f"Panel hints for pinned anchor: {self._source_drafts[anchor].role_label} — {self._source_drafts[anchor].presentation_name}, frame {self._cohort.selected[anchor]} — {'saved' if self._saved and self._saved_basis == 'positions' and not self._kept_current else 'unsaved'}"
        )
        self.reset_button.setEnabled(anchor is not None and not self._saved and positions)
        first_error = None
        for index, draft in enumerate(self._source_drafts):
            prediction = self._cohort.predict(index, self._hints)
            selected = self._cohort.selected[index]
            self.source_status_labels[index].setText(
                "Selected: not selected"
                if selected is None
                else f"{'Anchor' if index == anchor else 'Selected'}: frame {selected} — {'saved' if self._saved and self._saved_basis == 'positions' and not self._kept_current else 'unsaved'}"
            )
            outcome = prediction.description
            if not positions and index:
                offset_draft = self._offset_drafts[index - 1]
                outcome = offset_draft.error or (
                    f"Entered offset: {offset_draft.value:+d}f"
                    if offset_draft.value is not None
                    else "Offset not entered"
                )
            if self._saved_offsets is not None and index:
                outcome = _manual_saved_text(
                    self._workspace.comparisons[index - 1], self._saved_offsets[index - 1]
                )
            elif self._kept_current and index:
                outcome = _keep_saved_text(self._workspace.comparisons[index - 1])
            self.source_outcome_labels[index].setText(outcome)
            self.source_outcome_labels[index].setVisible(not self._saved or index > 0)
            proposal = (
                draft.error
                or (draft.viewer_status if draft.following else None)
                or (
                    f"Viewer position: frame {draft.frame} — not selected"
                    if draft.origin == "Viewer" and draft.frame != selected
                    else f"{draft.origin} proposal: frame {draft.frame} — not selected"
                    if draft.frame is not None and draft.frame != selected
                    else ""
                )
            )
            self.proposal_labels[index].setText(proposal)
            self.proposal_labels[index].setVisible(bool(proposal))
            if positions:
                first_error = first_error or draft.error
            elif index:
                first_error = first_error or self._offset_drafts[index - 1].error
            number = str(draft.frame) if draft.frame is not None and draft.error is None else "…"
            identity = f"{draft.role_label} — {draft.presentation_name}"
            self.anchor_buttons[index].setText(f"Anchor {draft.role_label}: {number}")
            self.select_buttons[index].setText(f"Select {draft.role_label}: {number}")
            self.clear_buttons[index].setText("Clear")
            self.jump_buttons[index].setText(
                f"Go to {prediction.frame}" if prediction.frame is not None else "Go"
            )
            for button in (self.clear_buttons[index], self.jump_buttons[index]):
                button.setFixedWidth(button.fontMetrics().horizontalAdvance(button.text()) + 20)
            enabled = positions and not self._saved
            ready = not draft.following or draft.viewer_ready
            self.viewer_buttons[index].setText("Use viewer frame")
            self.viewer_buttons[index].setVisible(draft.output_id == self._active_output_id)
            self.viewer_buttons[index].setEnabled(
                enabled and draft.output_id == self._active_output_id
            )
            self.anchor_buttons[index].setEnabled(
                enabled and ready and draft.frame is not None and draft.error is None
            )
            self.select_buttons[index].setEnabled(
                enabled
                and ready
                and anchor is not None
                and index != anchor
                and draft.frame is not None
                and draft.error is None
            )
            self.clear_buttons[index].setEnabled(enabled and selected is not None)
            self.jump_buttons[index].setEnabled(
                enabled
                and prediction.frame is not None
                and draft.output_id == self._active_output_id
            )
            for button in (
                self.anchor_buttons[index],
                self.select_buttons[index],
                self.clear_buttons[index],
                self.jump_buttons[index],
                self.viewer_buttons[index],
            ):
                description = (
                    "Clear selection"
                    if button is self.clear_buttons[index]
                    else f"Go to predicted frame {prediction.frame}"
                    if button is self.jump_buttons[index]
                    else button.text()
                )
                button.setAccessibleName(f"{description} — {identity}")
                button.setToolTip(f"{identity}. {button.text()}.")
            self.frame_inputs[index].setReadOnly(self._saved or not positions)
        if not self._saved:
            self.error_label.setText(self._action_error or first_error or "")

    def _save_positions(self) -> None:
        if (
            self._workspace is None
            or self._saved
            or self._session is None
            or self.api.file_path != self._session.script_path
        ):
            return
        decisions = list[AlignmentReviewDecision]()
        if self._basis == "positions":
            reference_frame = self._cohort.selected[0]
            if (
                self._cohort.anchor is None
                or reference_frame is None
                or any(n is None for n in self._cohort.selected)
            ):
                return
            for comparison, selected in zip(
                self._workspace.comparisons, self._cohort.selected[1:], strict=True
            ):
                if selected is None:
                    return
                decisions.append(
                    ConfirmedAlignmentReviewDecision(
                        comparison_key=comparison.comparison_key,
                        reference_source_frame=reference_frame,
                        comparison_source_frame=selected,
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
            self._action_error = (
                "Could not save alignment. Check available space and folder access, then try "
                f"again. ({type(exc).__name__})"
            )
            self.error_label.setText(self._action_error)
            return
        self._saved_basis = self._basis if not self._kept_current else None
        self._cancel_follow()
        self._saved = True
        for draft in self._source_drafts:
            draft.viewer_status = None
        self.api.timeline.clear_notches(_TIMELINE_GROUP)
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


def _candidate_offset(comparison: AlignmentReviewComparisonMetadata) -> int | None:
    attempt = comparison.audio_review.audio_attempt
    if attempt is None or attempt.decision.candidate is None:
        return None
    return attempt.decision.candidate.frame_offset


def _unavailable_summary_line(comparison: AlignmentReviewComparisonMetadata) -> str:
    attempt = comparison.audio_review.audio_attempt
    reason = attempt.decision.primary_reason if attempt is not None else "no_usable_audio"
    return _unavailable_summary_line_for_reason(reason)


def _audio_summary(
    comparison: AlignmentReviewComparisonMetadata, review: AudioReviewPresentation | None
) -> str:
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
        lines.extend(
            (
                f"Accepted audio alignment: {authority.frame_offset:+d}f — APPLIED",
                "No additional confirmation needed.",
            )
        )
    elif attempt is not None and attempt.decision.state in {"provisional", "unavailable"}:
        assert review is not None
        candidate = review.suggested_offset
        if candidate is not None:
            lines.extend((f"Provisional audio candidate: {candidate:+d}f — NOT APPLIED",))
            lines.extend(
                row.value
                for row in review.normal_review_rows(
                    panel=True,
                    action_line="Visual confirmation required to use this hint.",
                )
            )
    if not lines:
        lines.append(_unavailable_summary_line(comparison))
    if authority.origin in _MANUAL_AUTHORITY_ORIGINS and attempt is not None:
        original = _original_audio_summary(attempt.decision)
        if original is not None:
            lines.append(f"Original evidence: {original}")
    elif authority.origin == "computed_this_run" and attempt is not None:
        assert review is not None
        noted = review.noted_line(panel=True)
        if noted is not None:
            lines.append(noted)
    return "\n".join(lines)


def _original_audio_summary(decision: AudioAlignmentDecision) -> str | None:
    state = decision.state
    candidate = decision.candidate.frame_offset if decision.candidate is not None else None
    if state == "trusted_automatic" and candidate is not None:
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
    review: AudioReviewPresentation | None,
) -> str:
    attempt = comparison.audio_review.audio_attempt
    if attempt is None:
        lines = ["Historical audio details unavailable."]
        _append_origin_bounds_detail(
            lines,
            comparison,
            reference_source_frame_count,
        )
        return "\n".join(lines)
    assert review is not None
    lines = list(review.verbose_lines(panel=True))
    lines.extend(f"{row.key}: {row.value}" for row in audio_evidence_rows(attempt))
    _append_origin_bounds_detail(lines, comparison, reference_source_frame_count)
    return "\n".join(lines)


def _append_origin_bounds_detail(
    lines: list[str],
    comparison: AlignmentReviewComparisonMetadata,
    reference_source_frame_count: int,
) -> None:
    offset = opening_hint(comparison).offset
    if offset is None:
        return
    reference_frame, comparison_frame = _canonical_pair(offset)
    if reference_frame >= reference_source_frame_count:
        lines.append(
            "Opening offset's canonical Reference coordinate is outside raw source bounds."
        )
    if comparison_frame >= comparison.source_frame_count:
        lines.append(
            "Opening offset's canonical comparison coordinate is outside raw source bounds."
        )


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
    return f"Saved offset (Reference − Comparison): {offset:+d} frames — manually confirmed"


def _canonical_pair(offset: int) -> tuple[int, int]:
    return (offset, 0) if offset >= 0 else (0, abs(offset))


@hookimpl(tryfirst=True)
def vsview_register_toolpanel() -> type[WidgetPluginBase[Any, Any]]:
    return AlignmentReviewPanel
