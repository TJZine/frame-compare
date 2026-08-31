from __future__ import annotations

import json
import os
from collections.abc import Callable
from inspect import unwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
)
from frame_compare.vsview.alignment_review_panel import (
    AlignmentReviewPanel,
    vsview_register_toolpanel,
)

_SESSION_ID = "12345678123456781234567812345678"
_APP = QApplication.instance() or QApplication([])


def _call_hook(method: Callable[..., object], *args: object) -> None:
    cast(Callable[..., None], unwrap(method))(*args)


class _Timeline:
    def __init__(self) -> None:
        self.cleared: list[tuple[str, bool]] = []
        self.added: list[tuple[object, ...]] = []

    def clear_notches(self, identifier: str, *, update: bool = True) -> None:
        self.cleared.append((identifier, update))

    def add_notch(self, *args: object) -> None:
        self.added.append(args)


class _Playback:
    def __init__(self) -> None:
        self.sought: list[int] = []

    def seek(self, frame: int) -> bool:
        self.sought.append(frame)
        return True


def _output(
    output_id: int,
    role: str,
    suggestion: int | None = 12,
    *,
    ordinal: int = 1,
    frame_count: int = 200,
) -> Any:
    return SimpleNamespace(
        vs_index=output_id,
        vs_output=SimpleNamespace(clip=SimpleNamespace(num_frames=frame_count)),
        kwargs={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: 1,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: _SESSION_ID,
            ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY: f"ref:comparison-{ordinal}",
            ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY: ordinal,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: role,
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: f"{role.title()} {ordinal}",
            ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY: suggestion,
        },
    )


def _panel(
    tmp_path: Path, *, suggestion: int | None = 12, comparison_count: int = 1
) -> tuple[AlignmentReviewPanel, Any, Path]:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    outputs = [
        _output(output_id, role, suggestion, ordinal=ordinal)
        for ordinal in range(1, comparison_count + 1)
        for output_id, role in ((ordinal * 2 - 2, "reference"), (ordinal * 2 - 1, "comparison"))
    ]
    api = SimpleNamespace(
        file_path=script,
        voutputs=outputs,
        current_voutput=outputs[0],
        current_frame=12,
        timeline=_Timeline(),
        playback=_Playback(),
    )
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)
    _call_hook(panel.on_workspace_loaded, panel)
    return panel, api, script


def test_panel_is_inert_for_ordinary_workspace(tmp_path: Path) -> None:
    del tmp_path
    timeline = _Timeline()
    api = SimpleNamespace(file_path=None, timeline=timeline)
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))

    _call_hook(panel.on_workspace_loaded, panel)

    assert "Inactive" in panel.progress_label.text()
    assert not panel.capture_button.isEnabled()
    assert timeline.cleared == [("frame_compare_alignment_review", True)]


def test_malformed_output_proxy_keeps_panel_inert(tmp_path: Path) -> None:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    timeline = _Timeline()
    playback = _Playback()
    malformed = SimpleNamespace(vs_index=0, kwargs={})
    api = SimpleNamespace(
        file_path=script,
        voutputs=[malformed],
        current_voutput=malformed,
        current_frame=0,
        timeline=timeline,
        playback=playback,
    )
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))

    _call_hook(panel.on_workspace_loaded, panel)

    assert "Inactive" in panel.progress_label.text()
    assert timeline.cleared == [("frame_compare_alignment_review", True)]
    assert timeline.added == []
    assert playback.sought == []
    assert not script.with_name(f"{script.stem}.alignment-result.json").exists()


def test_plugin_hook_registers_one_stable_tool_panel() -> None:
    assert vsview_register_toolpanel() is AlignmentReviewPanel
    assert AlignmentReviewPanel.identifier == "frame_compare_alignment_review"
    assert AlignmentReviewPanel.display_name == "Frame Compare Alignment Review"


def test_panel_shows_unavailable_suggestion_without_seek_or_prefill(tmp_path: Path) -> None:
    panel, _api, _script = _panel(tmp_path, suggestion=None)

    assert "unavailable" in panel.suggestion_label.text().lower()
    assert panel.reference_input.text() == ""
    assert panel.comparison_input.text() == ""
    assert not panel.seek_button.isEnabled()


def test_out_of_range_active_suggestion_has_no_marker_or_seek(tmp_path: Path) -> None:
    panel, api, _script = _panel(tmp_path, suggestion=250)

    assert "outside that output's 0–199 range" in panel.suggestion_label.text()
    assert "enter or capture a valid frame" in panel.suggestion_label.text()
    assert panel.reference_input.text() == ""
    assert api.timeline.cleared == [
        ("frame_compare_alignment_review", True),
        ("frame_compare_alignment_review", True),
    ]
    assert api.timeline.added == []
    assert not panel.seek_button.isEnabled()
    panel.seek_button.click()
    assert api.playback.sought == []


@pytest.mark.parametrize(
    ("text", "use_paste", "error"),
    [
        ("500", False, 'between 0 and 199; entered "500"'),
        ("200", True, 'between 0 and 199; entered "200"'),
        ("-5", False, 'non-negative; entered "-5"'),
        ("abc", True, 'whole number; entered "abc"'),
    ],
)
def test_direct_frame_input_preserves_and_rejects_invalid_text(
    tmp_path: Path, text: str, use_paste: bool, error: str
) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.reference_input.selectAll()
    if use_paste:
        QApplication.clipboard().setText(text)
        panel.reference_input.paste()
    else:
        QTest.keyClicks(panel.reference_input, text)

    assert panel.reference_input.text() == text
    assert error in panel.error_label.text()
    assert not panel.confirm_button.isEnabled()
    panel.confirm_button.click()
    assert "not reviewed" in panel.comparison_selector.currentText()


def test_valid_direct_frame_entry_writes_exact_frames(tmp_path: Path) -> None:
    panel, _api, script = _panel(tmp_path)
    panel.reference_input.setText("120")
    panel.comparison_input.setText("108")

    assert panel.confirm_button.isEnabled()
    assert "= +12 frames" in panel.equation_label.text()
    panel.confirm_button.click()
    panel.finish_button.click()

    result = json.loads(script.with_name(f"{script.stem}.alignment-result.json").read_text())
    assert result["decisions"][0] == {
        "comparison_key": "ref:comparison-1",
        "action": "confirmed",
        "reference_source_frame": 120,
        "comparison_source_frame": 108,
    }


@pytest.mark.parametrize("next_workspace", ["ordinary", "malformed"])
def test_deactivation_clears_only_owned_marker_group_with_update(
    tmp_path: Path, next_workspace: str
) -> None:
    panel, api, _script = _panel(tmp_path)
    before = len(api.timeline.cleared)
    if next_workspace == "ordinary":
        api.file_path = None
    else:
        api.voutputs = [SimpleNamespace(vs_index=0, kwargs={})]

    _call_hook(panel.on_workspace_loaded, panel)

    assert api.timeline.cleared[before:] == [("frame_compare_alignment_review", True)]
    assert {identifier for identifier, _update in api.timeline.cleared} == {
        "frame_compare_alignment_review"
    }
    assert "Inactive" in panel.progress_label.text()


def test_unavailable_suggestion_transition_publishes_owned_marker_clear(tmp_path: Path) -> None:
    panel, api, _script = _panel(tmp_path)
    before = len(api.timeline.cleared)
    for output in api.voutputs:
        output.kwargs[ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY] = None

    _call_hook(panel.on_workspace_loaded, panel)

    assert api.timeline.cleared[before:] == [
        ("frame_compare_alignment_review", True),
        ("frame_compare_alignment_review", True),
    ]
    assert not panel.seek_button.isEnabled()


def test_selector_exposes_each_comparison_decision_status(tmp_path: Path) -> None:
    panel, _api, _script = _panel(tmp_path, comparison_count=2)

    assert [panel.comparison_selector.itemText(index) for index in range(2)] == [
        "Comparison 1 — not reviewed",
        "Comparison 2 — not reviewed",
    ]
    panel.confirm_button.click()
    assert panel.comparison_selector.currentIndex() == 0
    assert panel.comparison_selector.itemText(0) == "Comparison 1 — confirmed"
    panel.comparison_selector.setCurrentIndex(1)
    panel.keep_button.click()
    assert panel.comparison_selector.currentIndex() == 1
    assert panel.comparison_selector.itemText(1) == "Comparison 2 — keeping current"
    panel.reference_input.setText("13")
    assert panel.comparison_selector.itemText(1) == "Comparison 2 — not reviewed"


def test_panel_capture_confirm_keep_and_finish_writes_result(tmp_path: Path) -> None:
    panel, api, script = _panel(tmp_path)

    assert "reference 12" in panel.suggestion_label.text().lower()
    assert api.timeline.cleared == [
        ("frame_compare_alignment_review", True),
        ("frame_compare_alignment_review", False),
    ]
    panel.capture_button.click()
    api.current_voutput = api.voutputs[1]
    api.current_frame = 5
    _call_hook(panel.on_current_voutput_changed, panel, api.current_voutput, 1)
    assert "Comparison 1 (comparison), frame 5" in panel.context_label.text()
    assert api.timeline.added[-1][0:2] == ("frame_compare_alignment_review", 0)
    assert "suggested comparison frame 0" in str(api.timeline.added[-1][3])
    panel.capture_button.click()
    assert "= +7 frames" in panel.equation_label.text()
    panel.confirm_button.click()
    assert panel.finish_button.isEnabled()
    panel.finish_button.click()

    result = json.loads(script.with_name(f"{script.stem}.alignment-result.json").read_text())
    assert result["decisions"] == [
        {
            "comparison_key": "ref:comparison-1",
            "action": "confirmed",
            "reference_source_frame": 12,
            "comparison_source_frame": 5,
        }
    ]
    assert "Result saved" in panel.progress_label.text()
    assert not panel.capture_button.isEnabled()


def test_editing_confirmed_pair_clears_decision_and_seek_uses_active_role(
    tmp_path: Path,
) -> None:
    panel, api, _script = _panel(tmp_path)
    panel.reference_input.setText("20")
    panel.comparison_input.setText("8")
    panel.confirm_button.click()
    assert panel.finish_button.isEnabled()

    panel.reference_input.setText("21")
    assert not panel.finish_button.isEnabled()
    panel.seek_button.click()
    assert api.playback.sought == [12]


def test_save_failure_remains_editable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.keep_button.click()

    def fail_write(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "frame_compare.vsview.alignment_review_panel.write_alignment_review_result",
        fail_write,
    )

    panel.finish_button.click()

    assert panel.keep_button.isEnabled()
    assert "disk full" in panel.error_label.text()
