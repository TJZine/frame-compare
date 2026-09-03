"""Native VSView tool panel for Frame Compare alignment review."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
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
_POSITIONS_GUIDANCE = (
    "Unlink playheads, then visit every source and position each on the same "
    "visible moment."
)
_OFFSETS_GUIDANCE = (
    "Enter one known signed offset for every comparison; viewer visits are not required."
)


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
        self._build_ui()
        self._show_inactive(clear_marker=False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.guidance_label = QLabel(_POSITIONS_GUIDANCE, self)
        self.guidance_label.setWordWrap(True)
        layout.addWidget(self.guidance_label)

        self.basis_status_label = QLabel("Input basis: Source frames", self)
        self.basis_status_label.setWordWrap(True)
        layout.addWidget(self.basis_status_label)

        self.progress_label = QLabel(self)
        self.progress_label.setWordWrap(True)
        self.progress_label.setAccessibleName("Alignment review status")
        self.progress_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.progress_label)

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

        self.use_positions_button = QPushButton("Use these aligned positions", self)
        self.use_positions_button.clicked.connect(self._save_positions)
        layout.addWidget(self.use_positions_button)

        self.keep_help_label = QLabel(
            "Keeps the alignment Frame Compare entered with. If no trusted suggestion "
            "exists, that comparison remains unchanged.",
            self,
        )
        self.keep_help_label.setWordWrap(True)
        layout.addWidget(self.keep_help_label)
        self.keep_button = QPushButton("Keep audio-derived alignment", self)
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
            workspace = parse_alignment_review_workspace_metadata(
                tuple(
                    AlignmentReviewOutputCandidate(
                        output_id=output.vs_index,
                        source_frame_count=_source_frame_count(output),
                        metadata=output.kwargs,
                    )
                    for output in self.api.voutputs
                )
            )
            session = alignment_review_session_from_script(
                self.api.file_path, require_result_absent=True
            )
            if session.session_id != workspace.session_id:
                raise AlignmentReviewContractError("alignment review session identity mismatch")
        except AlignmentReviewContractError as exc:
            self.error_label.setText(f"Alignment review rejected: {exc}")
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
            self.lineup_layout.addWidget(status)
            self.lineup_layout.addWidget(outcome)
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
        self.source_status_labels.clear()
        self.source_outcome_labels.clear()
        self.frame_inputs.clear()
        self.offset_inputs.clear()
        self.use_positions_button.setText("Use these aligned positions")
        self.use_positions_button.setEnabled(False)
        self.keep_button.setEnabled(False)

    def _toggle_manual(self, visible: bool) -> None:
        self.manual_group.setVisible(visible)
        self.manual_toggle.setText(
            "Hide manual alignment" if visible else "Enter alignment manually..."
        )

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
                suggestion = _suggested_pair(comparison.suggested_offset)[0]
                if (
                    suggestion is not None
                    and suggestion < self._source_drafts[0].source_frame_count
                ):
                    markers.append(
                        (
                            suggestion,
                            "#3daee9",
                            f"{comparison.presentation_name}: suggested reference frame {suggestion}",
                        )
                    )
        else:
            comparison = self._workspace.comparisons[source_index - 1]
            suggestion = _suggested_pair(comparison.suggested_offset)[1]
            if suggestion is not None and suggestion < comparison.source_frame_count:
                markers.append(
                    (
                        suggestion,
                        "#d79b35",
                        f"{comparison.presentation_name}: suggested comparison frame {suggestion}",
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
        if self._basis == "positions":
            self.guidance_label.setText(_POSITIONS_GUIDANCE)
            self.use_positions_button.setText("Use these aligned positions")
            ready = sum(
                draft.frame is not None and draft.error is None for draft in self._source_drafts
            )
            total = len(self._source_drafts)
            progress_unit = "sources"
            complete = ready == total
        else:
            self.guidance_label.setText(_OFFSETS_GUIDANCE)
            self.use_positions_button.setText("Use these known offsets")
            ready = sum(
                draft.value is not None and draft.error is None for draft in self._offset_drafts
            )
            total = len(self._offset_drafts)
            progress_unit = "comparisons"
            complete = ready == total

        if self._saved:
            self.progress_label.setText("Alignment saved — close VSView to continue Frame Compare")
        else:
            self.progress_label.setText(f"{ready} / {total} {progress_unit} ready")

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
            if self._kept_current:
                status = "Saved — audio-derived alignment retained"
            elif self._basis == "offsets" and index == 0:
                status = "Reference anchor"
            elif self._basis == "offsets":
                offset_draft = self._offset_drafts[index - 1]
                if offset_draft.error is not None:
                    status = f"Needs attention — {offset_draft.error}"
                    first_error = first_error or offset_draft.error
                elif offset_draft.value is None:
                    status = "Not entered"
                else:
                    status = f"Manual offset — {offset_draft.value:+d} frames"
            elif draft.error is not None:
                status = f"Needs attention — {draft.error}"
                first_error = first_error or draft.error
            elif draft.frame is None:
                status = "Not visited"
            elif draft.origin == "Manual":
                status = f"Ready (manual) — frame {draft.frame}"
            elif draft.output_id == self._active_output_id and not self._saved:
                status = f"Viewing — frame {draft.frame} — Viewer"
            else:
                status = f"Ready — frame {draft.frame} — Viewer"
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
                if offset is not None:
                    outcome = f"{offset:+d} frames — {_trim_explanation(offset)}"
                elif comparison.suggested_offset is None:
                    outcome = "Suggestion unavailable"
                else:
                    outcome = f"Audio suggestion: {comparison.suggested_offset:+d} frames"
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
        self._write_result(tuple(decisions))

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


def _canonical_pair(offset: int) -> tuple[int, int]:
    return (offset, 0) if offset >= 0 else (0, abs(offset))


def _trim_explanation(offset: int) -> str:
    if offset > 0:
        return f"Trim {offset} frame(s) from reference"
    if offset < 0:
        return f"Trim {abs(offset)} frame(s) from this comparison"
    return "No starting trim"


@hookimpl(tryfirst=True)
def vsview_register_toolpanel() -> type[WidgetPluginBase[Any, Any]]:
    return AlignmentReviewPanel
