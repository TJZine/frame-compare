"""Native VSView tool panel for Frame Compare alignment review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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


@dataclass(slots=True)
class _ReviewDecision:
    reference_text: str = ""
    comparison_text: str = ""
    reference_frame: int | None = None
    comparison_frame: int | None = None
    action: Literal["confirmed", "keep_current"] | None = None


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
        self._decisions = list[_ReviewDecision]()
        self._saved = False
        self._build_ui()
        self._show_inactive(clear_marker=False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        guidance = QLabel(
            "Review every comparison and finish to save. Close VSView without finishing to cancel.",
            self,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        self.comparison_selector = QComboBox(self)
        self.comparison_selector.setAccessibleName("Active comparison")
        self.comparison_selector.currentIndexChanged.connect(self._show_comparison)
        self.progress_label = QLabel(self)
        selector_form = QFormLayout()
        selector_form.addRow("Comparison:", self.comparison_selector)
        selector_form.addRow("Review status:", self.progress_label)
        layout.addLayout(selector_form)

        names_group = QGroupBox("Source outputs", self)
        names_form = QFormLayout(names_group)
        self.reference_name_label = QLabel(names_group)
        self.comparison_name_label = QLabel(names_group)
        names_form.addRow("Reference:", self.reference_name_label)
        names_form.addRow("Comparison:", self.comparison_name_label)
        layout.addWidget(names_group)

        self.suggestion_label = QLabel(self)
        self.suggestion_label.setWordWrap(True)
        layout.addWidget(self.suggestion_label)

        frames_group = QGroupBox("Matching source frames", self)
        frames_form = QFormLayout(frames_group)
        self.reference_input = self._frame_input(frames_group, "Reference source frame")
        self.comparison_input = self._frame_input(frames_group, "Comparison source frame")
        self.reference_input.textChanged.connect(self._reference_changed)
        self.comparison_input.textChanged.connect(self._comparison_changed)
        frames_form.addRow("Reference frame:", self.reference_input)
        frames_form.addRow("Comparison frame:", self.comparison_input)
        layout.addWidget(frames_group)

        self.equation_label = QLabel(self)
        equation_font = self.equation_label.font()
        equation_font.setBold(True)
        self.equation_label.setFont(equation_font)
        self.equation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.trim_label = QLabel(self)
        self.trim_label.setWordWrap(True)
        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setAccessibleName("Alignment review error")
        layout.addWidget(self.equation_label)
        layout.addWidget(self.trim_label)
        layout.addWidget(self.error_label)

        self.context_label = QLabel(self)
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)
        inspect_actions = QHBoxLayout()
        self.capture_button = QPushButton("Capture current frame", self)
        self.seek_button = QPushButton("Go to suggested frame", self)
        self.capture_button.clicked.connect(self._capture_current_frame)
        self.seek_button.clicked.connect(self._seek_suggestion)
        inspect_actions.addWidget(self.capture_button)
        inspect_actions.addWidget(self.seek_button)
        layout.addLayout(inspect_actions)

        decision_actions = QHBoxLayout()
        self.confirm_button = QPushButton("Confirm pair", self)
        self.keep_button = QPushButton("Keep current offset", self)
        self.confirm_button.clicked.connect(self._confirm_pair)
        self.keep_button.clicked.connect(self._keep_current)
        decision_actions.addWidget(self.confirm_button)
        decision_actions.addWidget(self.keep_button)
        layout.addLayout(decision_actions)

        self.finish_button = QPushButton("Finish review", self)
        self.finish_button.clicked.connect(self._finish_review)
        layout.addWidget(self.finish_button)
        layout.addStretch()

    @staticmethod
    def _frame_input(parent: QWidget, accessible_name: str) -> QLineEdit:
        field = QLineEdit(parent)
        field.setPlaceholderText("Unset")
        field.setAccessibleName(accessible_name)
        return field

    @override
    @run_in_loop(return_future=False)
    def on_workspace_loaded(self) -> None:
        self._activate_workspace()

    @override
    @run_in_loop(return_future=False)
    def on_current_voutput_changed(self, voutput: VideoOutputProxy, tab_index: int) -> None:
        del voutput, tab_index
        self._refresh_active_output()

    @override
    @run_in_loop(return_future=False)
    def on_current_frame_changed(self, n: int) -> None:
        del n
        self._refresh_active_output()

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
        except (AlignmentReviewContractError, OSError, AttributeError, TypeError):
            return
        self._workspace = workspace
        self._session = session
        self._decisions = [_initial_decision(pair) for pair in workspace.comparisons]
        self.comparison_selector.clear()
        self.comparison_selector.addItems(
            [
                _selector_text(pair, decision.action)
                for pair, decision in zip(workspace.comparisons, self._decisions, strict=True)
            ]
        )
        self._set_review_controls_enabled(True)
        self._show_comparison(0)

    def _show_inactive(self, *, clear_marker: bool = True) -> None:
        if clear_marker:
            self.api.timeline.clear_notches(_TIMELINE_GROUP)
        self._workspace = None
        self._session = None
        self._decisions.clear()
        self._saved = False
        self.finish_button.setText("Finish review")
        self.comparison_selector.clear()
        self.progress_label.setText("Inactive — not a Frame Compare alignment session")
        self.reference_name_label.clear()
        self.comparison_name_label.clear()
        self.suggestion_label.clear()
        self.equation_label.clear()
        self.trim_label.clear()
        self.context_label.clear()
        self.error_label.clear()
        self._set_review_controls_enabled(False)

    def _set_review_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.comparison_selector,
            self.reference_input,
            self.comparison_input,
            self.confirm_button,
            self.keep_button,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.capture_button.setEnabled(False)
            self.seek_button.setEnabled(False)
        self.finish_button.setEnabled(False)

    def _show_comparison(self, index: int) -> None:
        if self._workspace is None or not 0 <= index < len(self._workspace.comparisons):
            return
        pair = self._workspace.comparisons[index]
        decision = self._decisions[index]
        self.reference_name_label.setText(pair.reference.presentation_name)
        self.comparison_name_label.setText(pair.comparison.presentation_name)
        self.reference_input.blockSignals(True)
        self.comparison_input.blockSignals(True)
        self.reference_input.setText(decision.reference_text)
        self.comparison_input.setText(decision.comparison_text)
        self.reference_input.blockSignals(False)
        self.comparison_input.blockSignals(False)
        if pair.suggested_offset is None:
            self.suggestion_label.setText("Audio-derived suggestion unavailable.")
        else:
            ref, comp = _suggested_pair(pair.suggested_offset)
            suggestion_text = (
                f"Audio-derived suggestion: reference {ref}, comparison {comp} "
                f"({pair.suggested_offset:+d} frames)."
            )
            invalid = _invalid_suggestion_text(pair, ref, comp)
            self.suggestion_label.setText(
                suggestion_text if invalid is None else f"{suggestion_text} {invalid}"
            )
        self.error_label.clear()
        self._update_equation()
        self._update_progress()

    def _reference_changed(self, value: str) -> None:
        self._change_frame("reference", value)

    def _comparison_changed(self, value: str) -> None:
        self._change_frame("comparison", value)

    def _change_frame(self, role: Literal["reference", "comparison"], value: str) -> None:
        if self._workspace is None:
            return
        index = self.comparison_selector.currentIndex()
        pair = self._workspace.comparisons[index]
        decision = self._decisions[index]
        output = pair.reference if role == "reference" else pair.comparison
        frame, _error = _parse_frame_text(value, role, output.source_frame_count)
        setattr(decision, f"{role}_text", value)
        setattr(decision, f"{role}_frame", frame)
        decision.action = None
        self._update_equation()
        self._update_progress()

    def _update_equation(self) -> None:
        if self._workspace is None:
            return
        index = self.comparison_selector.currentIndex()
        pair = self._workspace.comparisons[index]
        decision = self._decisions[index]
        error = _decision_error(decision, pair)
        self.error_label.setText("" if error is None else error)
        if error is not None:
            self.equation_label.setText("Correct the frame entry to calculate the offset.")
            self.trim_label.clear()
            self.confirm_button.setEnabled(False)
            return
        if decision.reference_frame is None or decision.comparison_frame is None:
            self.equation_label.setText("Set both source frames to calculate the offset.")
            self.trim_label.clear()
            self.confirm_button.setEnabled(False)
            return
        offset = decision.reference_frame - decision.comparison_frame
        self.equation_label.setText(
            f"Reference {decision.reference_frame} - Comparison {decision.comparison_frame} "
            f"= {offset:+d} frames"
        )
        self.trim_label.setText(_trim_explanation(offset))
        self.confirm_button.setEnabled(not self._saved)

    def _update_progress(self) -> None:
        if self._workspace is None:
            return
        complete = sum(decision.action is not None for decision in self._decisions)
        current = self._decisions[self.comparison_selector.currentIndex()].action
        state = {
            None: "not reviewed",
            "confirmed": "confirmed",
            "keep_current": "keeping current",
        }[current]
        self.progress_label.setText(
            f"{complete} of {len(self._decisions)} complete — current: {state}"
        )
        for index, (pair, decision) in enumerate(
            zip(self._workspace.comparisons, self._decisions, strict=True)
        ):
            self.comparison_selector.setItemText(index, _selector_text(pair, decision.action))
        self.finish_button.setEnabled(complete == len(self._decisions) and not self._saved)

    def _active_pair_and_role(
        self,
    ) -> tuple[int, AlignmentReviewComparisonMetadata, Literal["reference", "comparison"]] | None:
        if self._workspace is None:
            return None
        output_id = self.api.current_voutput.vs_index
        for index, pair in enumerate(self._workspace.comparisons):
            if pair.reference.output_id == output_id:
                return index, pair, "reference"
            if pair.comparison.output_id == output_id:
                return index, pair, "comparison"
        return None

    def _refresh_active_output(self) -> None:
        active = self._active_pair_and_role()
        if active is None:
            return
        index, pair, role = active
        frame = int(self.api.current_frame)
        self.context_label.setText(
            f"Current output: {getattr(pair, role).presentation_name} ({role}), frame {frame}."
        )
        suggestion = _bounded_suggestion_for_role(pair, role)
        if suggestion is not None:
            self.api.timeline.clear_notches(_TIMELINE_GROUP, update=False)
            self.api.timeline.add_notch(
                _TIMELINE_GROUP,
                suggestion,
                "#d79b35" if role == "comparison" else "#3daee9",
                f"{pair.comparison.presentation_name}: suggested {role} frame {suggestion}",
            )
        else:
            self.api.timeline.clear_notches(_TIMELINE_GROUP)
        self.seek_button.setEnabled(suggestion is not None and not self._saved)
        self.capture_button.setEnabled(not self._saved)
        if self.comparison_selector.currentIndex() != index:
            self.comparison_selector.setCurrentIndex(index)

    def _capture_current_frame(self) -> None:
        active = self._active_pair_and_role()
        if active is None:
            return
        index, _pair, role = active
        self.comparison_selector.setCurrentIndex(index)
        field = self.reference_input if role == "reference" else self.comparison_input
        field.setText(str(int(self.api.current_frame)))

    def _seek_suggestion(self) -> None:
        active = self._active_pair_and_role()
        if active is None:
            return
        _index, pair, role = active
        suggestion = _bounded_suggestion_for_role(pair, role)
        if suggestion is not None and not self.api.playback.seek(suggestion):
            self.error_label.setText("Could not seek to the suggested frame in the active output.")

    def _confirm_pair(self) -> None:
        if self._workspace is None:
            return
        index = self.comparison_selector.currentIndex()
        pair = self._workspace.comparisons[index]
        decision = self._decisions[index]
        error = _decision_error(decision, pair)
        if error is not None:
            self.error_label.setText(error)
            return
        if decision.reference_frame is None or decision.comparison_frame is None:
            self.error_label.setText("Enter both source frames before confirming this pair.")
            return
        if (
            decision.reference_frame >= pair.reference.source_frame_count
            or decision.comparison_frame >= pair.comparison.source_frame_count
        ):
            self.error_label.setText("A source frame is outside its output bounds.")
            return
        decision.action = "confirmed"
        self.error_label.clear()
        self._update_progress()

    def _keep_current(self) -> None:
        if self._workspace is None:
            return
        self._decisions[self.comparison_selector.currentIndex()].action = "keep_current"
        self.error_label.clear()
        self._update_progress()

    def _finish_review(self) -> None:
        if self._workspace is None or self._session is None:
            return
        decisions = list[AlignmentReviewDecision]()
        for pair, decision in zip(self._workspace.comparisons, self._decisions, strict=True):
            if decision.action == "confirmed":
                if decision.reference_frame is None or decision.comparison_frame is None:
                    return
                decisions.append(
                    ConfirmedAlignmentReviewDecision(
                        comparison_key=pair.comparison_key,
                        reference_source_frame=decision.reference_frame,
                        comparison_source_frame=decision.comparison_frame,
                    )
                )
            elif decision.action == "keep_current":
                decisions.append(KeepCurrentAlignmentReviewDecision(pair.comparison_key))
            else:
                return
        try:
            write_alignment_review_result(
                self._session,
                AlignmentReviewResult(
                    session_id=self._workspace.session_id,
                    decisions=tuple(decisions),
                ),
            )
        except (AlignmentReviewContractError, OSError) as exc:
            self.error_label.setText(f"Could not save review result: {str(exc)[:240]}")
            return
        self._saved = True
        self._set_review_controls_enabled(False)
        self.progress_label.setText("Result saved — close VSView to continue Frame Compare.")
        self.finish_button.setText("Review saved")


def _suggested_pair(offset: int) -> tuple[int, int]:
    return (offset, 0) if offset >= 0 else (0, abs(offset))


def _initial_decision(pair: AlignmentReviewComparisonMetadata) -> _ReviewDecision:
    if pair.suggested_offset is None:
        return _ReviewDecision()
    reference, comparison = _suggested_pair(pair.suggested_offset)
    return _ReviewDecision(
        reference_text=str(reference) if reference < pair.reference.source_frame_count else "",
        comparison_text=str(comparison) if comparison < pair.comparison.source_frame_count else "",
        reference_frame=reference if reference < pair.reference.source_frame_count else None,
        comparison_frame=comparison if comparison < pair.comparison.source_frame_count else None,
    )


def _suggestion_for_role(
    offset: int | None, role: Literal["reference", "comparison"]
) -> int | None:
    if offset is None:
        return None
    return _suggested_pair(offset)[0 if role == "reference" else 1]


def _bounded_suggestion_for_role(
    pair: AlignmentReviewComparisonMetadata, role: Literal["reference", "comparison"]
) -> int | None:
    suggestion = _suggestion_for_role(pair.suggested_offset, role)
    output = pair.reference if role == "reference" else pair.comparison
    return suggestion if suggestion is not None and suggestion < output.source_frame_count else None


def _invalid_suggestion_text(
    pair: AlignmentReviewComparisonMetadata, reference: int, comparison: int
) -> str | None:
    for role, frame, output in (
        ("reference", reference, pair.reference),
        ("comparison", comparison, pair.comparison),
    ):
        if frame >= output.source_frame_count:
            return (
                f"Suggested {role} frame {frame} is outside that output's "
                f"0–{output.source_frame_count - 1} range; enter or capture a valid frame."
            )
    return None


def _selector_text(
    pair: AlignmentReviewComparisonMetadata,
    action: Literal["confirmed", "keep_current"] | None,
) -> str:
    status = {
        None: "not reviewed",
        "confirmed": "confirmed",
        "keep_current": "keeping current",
    }[action]
    return f"{pair.comparison.presentation_name} — {status}"


def _parse_frame_text(
    text: str,
    role: Literal["reference", "comparison"],
    source_frame_count: int,
) -> tuple[int | None, str | None]:
    label = role.title()
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


def _decision_error(
    decision: _ReviewDecision, pair: AlignmentReviewComparisonMetadata
) -> str | None:
    fields: tuple[tuple[str, Literal["reference", "comparison"], int], ...] = (
        (decision.reference_text, "reference", pair.reference.source_frame_count),
        (decision.comparison_text, "comparison", pair.comparison.source_frame_count),
    )
    for text, role, frame_count in fields:
        _frame, error = _parse_frame_text(text, role, frame_count)
        if error is not None:
            return error
    return None


def _trim_explanation(offset: int) -> str:
    if offset > 0:
        return f"Trim {offset} frame(s) from the reference start."
    if offset < 0:
        return f"Trim {abs(offset)} frame(s) from the comparison start."
    return "No starting-frame trim is needed."


@hookimpl
def vsview_register_toolpanel() -> type[WidgetPluginBase[Any, Any]]:
    return AlignmentReviewPanel
