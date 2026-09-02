from __future__ import annotations

import json
import os
from collections.abc import Callable, Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("vsview")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from vsengine.loops import get_loop, set_loop
from vsview.vsenv import QtEventLoop

from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
    ALIGNMENT_REVIEW_SCHEMA_VERSION,
)
from frame_compare.vsview.alignment_review_panel import (
    AlignmentReviewPanel,
    vsview_register_toolpanel,
)

_SESSION_ID = "12345678123456781234567812345678"
_APP = QApplication.instance() or QApplication([])


@pytest.fixture(scope="module", autouse=True)
def qt_event_loop() -> Generator[None]:
    previous = get_loop()
    set_loop(QtEventLoop(_APP))
    try:
        yield
    finally:
        set_loop(previous)


def _call_hook(method: Callable[..., object], *args: object) -> None:
    method(*args)
    _APP.processEvents()


class _Timeline:
    def __init__(self) -> None:
        self.cleared: list[tuple[str, bool]] = []
        self.added: list[tuple[object, ...]] = []

    def clear_notches(self, identifier: str, *, update: bool = True) -> None:
        self.cleared.append((identifier, update))

    def add_notch(self, *args: object) -> None:
        self.added.append(args)


def _reference_output(*, frame_count: int = 200) -> Any:
    return SimpleNamespace(
        vs_index=0,
        vs_output=SimpleNamespace(clip=SimpleNamespace(num_frames=frame_count)),
        kwargs={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_SCHEMA_VERSION,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: _SESSION_ID,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: "reference",
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: "Reference master",
        },
    )


def _comparison_output(
    ordinal: int,
    suggestion: int | None,
    *,
    frame_count: int = 200,
) -> Any:
    return SimpleNamespace(
        vs_index=ordinal,
        vs_output=SimpleNamespace(clip=SimpleNamespace(num_frames=frame_count)),
        kwargs={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_SCHEMA_VERSION,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: _SESSION_ID,
            ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY: f"ref:comparison-{ordinal}",
            ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY: ordinal,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: "comparison",
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: f"Comparison {ordinal} source",
            ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY: suggestion,
        },
    )


def _panel(
    tmp_path: Path,
    *,
    suggestion: int | None = 12,
    comparison_count: int = 1,
    initialize_output: bool = False,
    frame_count: int = 200,
) -> tuple[AlignmentReviewPanel, Any, Path]:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    outputs = [
        _reference_output(frame_count=frame_count),
        *(
            _comparison_output(ordinal, suggestion, frame_count=frame_count)
            for ordinal in range(1, comparison_count + 1)
        ),
    ]
    api = SimpleNamespace(
        file_path=script,
        voutputs=outputs,
        current_voutput=outputs[0],
        current_frame=12,
        timeline=_Timeline(),
    )
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)
    _call_hook(panel.on_workspace_loaded)
    if initialize_output:
        _call_hook(panel.on_current_voutput_changed, api.current_voutput, 0)
    return panel, api, script


def _visit(panel: AlignmentReviewPanel, api: Any, output_index: int, frame: int) -> None:
    api.current_voutput = api.voutputs[output_index]
    api.current_frame = frame
    _call_hook(panel.on_current_voutput_changed, api.current_voutput, output_index)


def _read_result(script: Path) -> dict[str, object]:
    path = script.with_name(f"{script.stem}.alignment-result.json")
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_activation_starts_with_every_source_not_visited(tmp_path: Path) -> None:
    panel, api, _script = _panel(tmp_path, comparison_count=2)

    assert panel.progress_label.text() == "0 / 3 sources ready"
    assert [label.text() for label in panel.source_status_labels] == [
        "Not visited",
        "Not visited",
        "Not visited",
    ]
    assert not panel.use_positions_button.isEnabled()
    assert api.timeline.added == []

    _call_hook(panel.on_current_voutput_changed, api.current_voutput, 0)

    assert panel.progress_label.text() == "1 / 3 sources ready"
    assert panel.source_status_labels[0].text() == "Viewing — frame 12 — Viewer"
    assert [label.text() for label in panel.source_status_labels[1:]] == [
        "Not visited",
        "Not visited",
    ]
    assert len(api.timeline.added) == 2


def test_viewer_callbacks_update_only_current_source_and_revisits_replace_it(
    tmp_path: Path,
) -> None:
    panel, api, _script = _panel(tmp_path, comparison_count=2)
    _visit(panel, api, 0, 40)
    _visit(panel, api, 1, 31)

    assert panel.source_status_labels[0].text() == "Ready — frame 40 — Viewer"
    assert panel.source_status_labels[1].text() == "Viewing — frame 31 — Viewer"
    assert panel.source_status_labels[2].text() == "Not visited"
    assert panel.source_outcome_labels[1].text().startswith("+9 frames")

    api.current_frame = 29
    _call_hook(panel.on_current_frame_changed, 29)

    assert panel.source_status_labels[0].text() == "Ready — frame 40 — Viewer"
    assert panel.source_status_labels[1].text() == "Viewing — frame 29 — Viewer"
    assert panel.source_outcome_labels[1].text().startswith("+11 frames")


def test_panel_is_inert_for_ordinary_workspace() -> None:
    timeline = _Timeline()
    api = SimpleNamespace(file_path=None, timeline=timeline)
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))

    _call_hook(panel.on_workspace_loaded)

    assert "Inactive" in panel.progress_label.text()
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()
    assert timeline.cleared == [("frame_compare_alignment_review", True)]


def test_malformed_output_proxy_keeps_panel_inert(tmp_path: Path) -> None:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    timeline = _Timeline()
    malformed = SimpleNamespace(vs_index=0, kwargs={})
    api = SimpleNamespace(file_path=script, voutputs=[malformed], timeline=timeline)
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))

    _call_hook(panel.on_workspace_loaded)

    assert "Inactive" in panel.progress_label.text()
    assert "could not be read safely (AttributeError)" in panel.error_label.text()
    assert str(tmp_path) not in panel.error_label.text()
    assert timeline.added == []
    assert not script.with_name(f"{script.stem}.alignment-result.json").exists()


def test_session_read_failure_is_bounded_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> None:
        raise OSError(f"private path: {tmp_path}")

    monkeypatch.setattr(
        "frame_compare.vsview.alignment_review_panel.alignment_review_session_from_script",
        fail_read,
    )

    panel, _api, _script = _panel(tmp_path)

    assert "Inactive" in panel.progress_label.text()
    assert panel.error_label.text() == (
        "Alignment review unavailable: workspace could not be read safely (OSError)."
    )
    assert str(tmp_path) not in panel.error_label.text()


def test_contract_rejection_is_bounded_and_sanitized(tmp_path: Path) -> None:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    reference = _reference_output()
    reference.kwargs[ALIGNMENT_REVIEW_METADATA_NAME_KEY] = ""
    api = SimpleNamespace(file_path=script, voutputs=[reference], timeline=_Timeline())
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)

    _call_hook(panel.on_workspace_loaded)

    assert panel.error_label.text() == (
        "Alignment review rejected: alignment review output presentation name is invalid"
    )
    assert "Inactive" in panel.progress_label.text()
    assert str(tmp_path) not in panel.error_label.text()


def test_plugin_hook_and_native_accessibility_contract(tmp_path: Path) -> None:
    panel, _api, _script = _panel(tmp_path)

    assert vsview_register_toolpanel() is AlignmentReviewPanel
    assert cast(Any, vsview_register_toolpanel).vsview_impl["tryfirst"] is True
    assert AlignmentReviewPanel.identifier == "frame_compare_alignment_review"
    assert AlignmentReviewPanel.display_name == "Frame Compare Alignment Review"
    assert panel.guidance_label.wordWrap()
    assert panel.error_label.accessibleName() == "Alignment review error"
    assert panel.manual_toggle.accessibleName() == "Enter alignment manually"
    assert panel.body_scroll.accessibleName() == "Alignment source lineup and manual inputs"
    assert not panel.manual_group.isVisible()
    assert panel.use_positions_button.text() == "Use these aligned positions"


def test_growing_body_scrolls_while_whole_set_actions_stay_reachable(
    tmp_path: Path,
) -> None:
    panel, _api, _script = _panel(tmp_path, comparison_count=4)
    font = panel.font()
    font.setPointSize(font.pointSize() + 8)
    panel.setFont(font)
    panel.manual_toggle.click()
    panel.resize(320, 600)
    panel.show()
    _APP.processEvents()

    assert panel.body_scroll.verticalScrollBar().maximum() > 0
    assert panel.body_scroll.horizontalScrollBar().maximum() == 0
    assert panel.use_positions_button.isVisible()
    assert panel.keep_button.isVisible()
    assert panel.use_positions_button.parent() is panel
    assert panel.keep_button.parent() is panel

    panel.hide()


def test_unavailable_suggestions_leave_honest_whole_set_keep_available(
    tmp_path: Path,
) -> None:
    panel, _api, script = _panel(tmp_path, suggestion=None, comparison_count=2)

    assert [label.text() for label in panel.source_outcome_labels[1:]] == [
        "Suggestion unavailable",
        "Suggestion unavailable",
    ]
    assert "remains unchanged" in panel.keep_help_label.text()
    assert panel.keep_button.isEnabled()

    panel.keep_button.click()

    result = _read_result(script)
    assert result["decisions"] == [
        {"comparison_key": "ref:comparison-1", "action": "keep_current"},
        {"comparison_key": "ref:comparison-2", "action": "keep_current"},
    ]
    assert "Alignment saved" in panel.progress_label.text()
    assert all("retained" in label.text() for label in panel.source_status_labels)


def test_markers_use_only_owned_group_and_role_relevant_bounded_suggestions(
    tmp_path: Path,
) -> None:
    panel, api, _script = _panel(tmp_path, comparison_count=2)
    _visit(panel, api, 0, 20)

    assert api.timeline.cleared[-1] == ("frame_compare_alignment_review", False)
    assert [marker[1] for marker in api.timeline.added] == [12, 12]
    assert all(marker[2] == "#3daee9" for marker in api.timeline.added)

    api.timeline.added.clear()
    _visit(panel, api, 1, 5)

    assert api.timeline.cleared[-1] == ("frame_compare_alignment_review", False)
    assert api.timeline.added[0][0:3] == (
        "frame_compare_alignment_review",
        0,
        "#d79b35",
    )
    assert {identifier for identifier, _update in api.timeline.cleared} == {
        "frame_compare_alignment_review"
    }


def test_out_of_range_reference_suggestions_publish_no_marker(tmp_path: Path) -> None:
    panel, api, _script = _panel(tmp_path, suggestion=250)

    _visit(panel, api, 0, 12)

    assert api.timeline.cleared[-1] == ("frame_compare_alignment_review", True)
    assert api.timeline.added == []


def test_one_primary_action_saves_complete_viewer_positions(tmp_path: Path) -> None:
    panel, api, script = _panel(tmp_path, comparison_count=2)
    _visit(panel, api, 0, 120)
    _visit(panel, api, 1, 108)
    _visit(panel, api, 2, 127)

    assert panel.progress_label.text() == "3 / 3 sources ready"
    assert panel.use_positions_button.isEnabled()
    assert panel.source_outcome_labels[1].text() == ("+12 frames — Trim 12 frame(s) from reference")
    assert panel.source_outcome_labels[2].text() == (
        "-7 frames — Trim 7 frame(s) from this comparison"
    )

    panel.use_positions_button.click()

    result = _read_result(script)
    assert result["decisions"] == [
        {
            "comparison_key": "ref:comparison-1",
            "action": "confirmed",
            "reference_source_frame": 120,
            "comparison_source_frame": 108,
        },
        {
            "comparison_key": "ref:comparison-2",
            "action": "confirmed",
            "reference_source_frame": 120,
            "comparison_source_frame": 127,
        },
    ]
    assert panel.progress_label.focusPolicy().name == "StrongFocus"
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()
    assert not panel.manual_toggle.isEnabled()


def test_manual_source_frames_feed_same_draft_and_viewer_can_replace_origin(
    tmp_path: Path,
) -> None:
    panel, api, script = _panel(tmp_path)
    panel.manual_toggle.click()

    assert not panel.manual_group.isHidden()
    panel.frame_inputs[0].setText("120")
    panel.frame_inputs[1].setText("bad")
    assert panel.frame_inputs[1].text() == "bad"
    assert "whole number" in panel.error_label.text()
    assert "Needs attention" in panel.source_status_labels[1].text()
    assert not panel.use_positions_button.isEnabled()

    panel.frame_inputs[1].setText("108")
    assert panel.source_status_labels[0].text() == "Ready (manual) — frame 120"
    assert panel.source_status_labels[1].text() == "Ready (manual) — frame 108"
    assert panel.use_positions_button.isEnabled()

    _visit(panel, api, 1, 107)
    assert panel.source_status_labels[1].text() == "Viewing — frame 107 — Viewer"
    panel.use_positions_button.click()

    assert (
        cast(list[dict[str, object]], _read_result(script)["decisions"])[0][
            "comparison_source_frame"
        ]
        == 107
    )


def test_known_offsets_are_whole_set_and_serialize_canonical_pairs(tmp_path: Path) -> None:
    panel, _api, script = _panel(tmp_path, comparison_count=2)
    panel.manual_toggle.click()
    panel.basis_selector.setCurrentIndex(1)

    assert panel.basis_status_label.text() == "Input basis: Known offsets"
    assert not panel.offset_inputs_group.isHidden()
    assert panel.frame_inputs_group.isHidden()
    panel.offset_inputs[0].setText("+12")
    assert not panel.use_positions_button.isEnabled()
    panel.offset_inputs[1].setText("-7")

    assert panel.progress_label.text() == "2 / 2 comparisons ready"
    assert panel.source_status_labels[1].text() == "Manual offset — +12 frames"
    assert panel.source_outcome_labels[2].text() == (
        "-7 frames — Trim 7 frame(s) from this comparison"
    )
    assert panel.use_positions_button.isEnabled()
    panel.use_positions_button.click()

    assert _read_result(script)["decisions"] == [
        {
            "comparison_key": "ref:comparison-1",
            "action": "confirmed",
            "reference_source_frame": 12,
            "comparison_source_frame": 0,
        },
        {
            "comparison_key": "ref:comparison-2",
            "action": "confirmed",
            "reference_source_frame": 0,
            "comparison_source_frame": 7,
        },
    ]


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("abc", "must be a signed integer"),
        ("+200", "outside 0–199"),
        ("-200", "outside 0–199"),
    ],
)
def test_known_offset_validation_preserves_text_and_blocks_save(
    tmp_path: Path, text: str, error: str
) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.manual_toggle.click()
    panel.basis_selector.setCurrentIndex(1)

    QTest.keyClicks(panel.offset_inputs[0], text)

    assert panel.offset_inputs[0].text() == text
    assert error in panel.error_label.text()
    assert "Needs attention" in panel.source_status_labels[1].text()
    assert not panel.use_positions_button.isEnabled()


def test_switching_basis_never_combines_readiness(tmp_path: Path) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.manual_toggle.click()
    panel.frame_inputs[0].setText("50")
    panel.frame_inputs[1].setText("45")
    assert panel.use_positions_button.isEnabled()

    panel.basis_selector.setCurrentIndex(1)
    assert panel.progress_label.text() == "0 / 1 comparisons ready"
    assert not panel.use_positions_button.isEnabled()

    panel.basis_selector.setCurrentIndex(0)
    assert panel.progress_label.text() == "2 / 2 sources ready"
    assert panel.use_positions_button.isEnabled()


def test_workspace_reload_restores_collapsed_source_frame_manual_defaults(
    tmp_path: Path,
) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.manual_toggle.click()
    panel.basis_selector.setCurrentIndex(1)
    assert panel.manual_toggle.text() == "Hide manual alignment"
    assert not panel.offset_inputs_group.isHidden()

    _call_hook(panel.on_workspace_loaded)

    assert not panel.manual_toggle.isChecked()
    assert panel.manual_toggle.text() == "Enter alignment manually..."
    assert panel.manual_group.isHidden()
    assert panel.basis_selector.currentText() == "Source frames"
    assert not panel.frame_inputs_group.isHidden()
    assert panel.offset_inputs_group.isHidden()
    assert panel.basis_status_label.text() == "Input basis: Source frames"


def test_save_failure_stays_editable_unsaved_and_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel, _api, _script = _panel(tmp_path)

    def fail_write(*_args: object) -> None:
        raise OSError(f"disk full at {tmp_path}")

    monkeypatch.setattr(
        "frame_compare.vsview.alignment_review_panel.write_alignment_review_result",
        fail_write,
    )

    panel.keep_button.click()

    assert panel.keep_button.isEnabled()
    assert panel.manual_toggle.isEnabled()
    assert "Check available space" in panel.error_label.text()
    assert "OSError" in panel.error_label.text()
    assert str(tmp_path) not in panel.error_label.text()
    assert "saved" not in panel.progress_label.text().lower()


@pytest.mark.parametrize("next_workspace", ["ordinary", "malformed"])
def test_deactivation_clears_only_owned_marker_group(tmp_path: Path, next_workspace: str) -> None:
    panel, api, _script = _panel(tmp_path, initialize_output=True)
    before = len(api.timeline.cleared)
    if next_workspace == "ordinary":
        api.file_path = None
    else:
        api.voutputs = [SimpleNamespace(vs_index=0, kwargs={})]

    _call_hook(panel.on_workspace_loaded)

    assert api.timeline.cleared[before:] == [("frame_compare_alignment_review", True)]
    assert {identifier for identifier, _update in api.timeline.cleared} == {
        "frame_compare_alignment_review"
    }
    assert "Inactive" in panel.progress_label.text()
