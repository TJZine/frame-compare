from __future__ import annotations

import json
import os
from collections.abc import Callable, Generator
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("vsview")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from vsengine.loops import get_loop, set_loop
from vsview.vsenv import QtEventLoop

from frame_compare.services.alignment import _build_audio_review_map
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.types import AlignmentResult, ComparisonResolution
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
)
from frame_compare.utils.alignment_review_projection import (
    build_audio_review_presentation,
)
from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    ALIGNMENT_REVIEW_METADATA_VERSION,
    ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
)
from frame_compare.vsview.alignment_review_panel import (
    AlignmentReviewPanel,
    vsview_register_toolpanel,
)
from tests.alignment_review_scenarios import (
    audio_failed_video_confirmed_attempt,
    boundary_video_inconclusive_attempt,
    established_counts_attempt,
    multi_context_attempt,
    production_nested_targets_attempt,
    resolved_run_context_attempt,
    review_attempt,
    singleton_chunk_target_attempt,
    target_context_attempt,
)
from tests.alignment_review_test_support import (
    audio_review as _audio_review,
)
from tests.alignment_review_test_support import (
    provisional_audio_attempt,
    trusted_audio_attempt,
    unavailable_audio_attempt,
)
from tests.services.alignment_evidence_test_support import retimed_comparison_stream, stream

_SESSION_ID = "12345678123456781234567812345678"
_APP = QApplication.instance() or QApplication([])


def _attempt_audio_review(attempt: AudioAlignmentAttempt, *, applied: bool = False) -> str:
    return json.dumps(
        {
            "current_authority": {
                "origin": "computed_this_run" if applied else "none",
                "frame_offset": 0 if applied else None,
            },
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(attempt),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _provisional_audio_review(ordinal: int = 1, frame_offset: int = 0) -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(
                provisional_audio_attempt(ordinal=ordinal, frame_offset=frame_offset)
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _accepted_audio_review(ordinal: int = 1, frame_offset: int = 0) -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "computed_this_run", "frame_offset": frame_offset},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(
                trusted_audio_attempt(ordinal=ordinal, frame_offset=frame_offset)
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _unavailable_audio_review(ordinal: int = 1) -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(unavailable_audio_attempt(ordinal=ordinal)),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _manual_audio_review(offset: int = 0) -> str:
    payload = {
        "current_authority": {
            "origin": "preexisting_manual_override",
            "frame_offset": offset,
        },
        "evidence_availability": "historical_details_unavailable",
        "audio_attempt": None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _manual_with_provisional_audio_review() -> str:
    payload = cast(dict[str, Any], json.loads(_provisional_audio_review()))
    payload["current_authority"] = {
        "origin": "interactive_confirmed_this_run",
        "frame_offset": 0,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _authority_audio_review(origin: str) -> str:
    if origin == "computed_this_run":
        return _accepted_audio_review()
    return json.dumps(
        {
            "current_authority": {"origin": origin, "frame_offset": 0},
            "evidence_availability": "historical_details_unavailable",
            "audio_attempt": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


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
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_METADATA_VERSION,
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
    audio_review: str | None = None,
) -> Any:
    return SimpleNamespace(
        vs_index=ordinal,
        vs_output=SimpleNamespace(clip=SimpleNamespace(num_frames=frame_count)),
        kwargs={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_METADATA_VERSION,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: _SESSION_ID,
            ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY: f"ref:comparison-{ordinal}",
            ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY: ordinal,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: "comparison",
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: f"Comparison {ordinal} source",
            ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY: suggestion,
            ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY: (
                _audio_review(suggestion) if audio_review is None else audio_review
            ),
        },
    )


def _panel(
    tmp_path: Path,
    *,
    suggestion: int | None = 12,
    comparison_count: int = 1,
    initialize_output: bool = False,
    frame_count: int = 200,
    audio_review: str | None = None,
    suggestions: tuple[int | None, ...] | None = None,
    audio_reviews: tuple[str, ...] | None = None,
) -> tuple[AlignmentReviewPanel, Any, Path]:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    outputs = [
        _reference_output(frame_count=frame_count),
        *(
            _comparison_output(
                ordinal,
                suggestions[ordinal - 1] if suggestions is not None else suggestion,
                frame_count=frame_count,
                audio_review=(
                    audio_reviews[ordinal - 1] if audio_reviews is not None else audio_review
                ),
            )
            for ordinal in range(1, comparison_count + 1)
        ),
    ]
    api = SimpleNamespace(
        file_path=script,
        voutputs=outputs,
        current_voutput=outputs[0],
        current_frame=12,
        timeline=_Timeline(),
        register_on_destroy=lambda cb: None,
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


def _enter_frame(panel: AlignmentReviewPanel, index: int, frame: int) -> None:
    panel.frame_inputs[index].setText(str(frame))


def _read_result(script: Path) -> dict[str, object]:
    path = script.with_name(f"{script.stem}.alignment-result.json")
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_known_offset_hide_restores_source_basis_without_losing_drafts(tmp_path: Path) -> None:
    panel, _, _ = _panel(tmp_path)
    _enter_frame(panel, 1, 20)
    panel.manual_toggle.click()
    panel.basis_selector.setCurrentIndex(1)
    panel.offset_inputs[0].setText("+12")
    assert panel.use_positions_button.isEnabled()
    panel.manual_toggle.click()
    assert panel._basis == "positions" and panel.offset_inputs[0].text() == "+12"
    assert panel.frame_inputs[1].text() == "20" and not panel.use_positions_button.isEnabled()


def test_panel_is_inert_for_ordinary_workspace(tmp_path: Path) -> None:
    timeline = _Timeline()
    script = tmp_path / "ordinary.py"
    script.write_text("# ordinary VSView session\n", encoding="utf-8")
    output = SimpleNamespace(
        vs_index=0,
        vs_output=SimpleNamespace(clip=SimpleNamespace(num_frames=200)),
        kwargs={"unrelated_plugin_metadata": "untouched"},
    )
    api = SimpleNamespace(
        file_path=script, voutputs=[output], timeline=timeline, register_on_destroy=lambda cb: None
    )
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)

    _call_hook(panel.on_workspace_loaded)

    assert timeline.cleared == [("frame_compare_alignment_review", True)]
    assert "Inactive" in panel.progress_label.text()
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()


@pytest.mark.parametrize("problem", ["proxy", "old-version", "presentation-name"])
def test_panel_reports_invalid_workspace_metadata(tmp_path: Path, problem: str) -> None:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text(
        "# old session\n" if problem == "old-version" else "# session\n", encoding="utf-8"
    )
    reference = _reference_output()
    if problem == "proxy":
        reference = SimpleNamespace(
            vs_index=0,
            kwargs={ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_METADATA_VERSION},
        )
    elif problem == "old-version":
        reference.kwargs[ALIGNMENT_REVIEW_METADATA_VERSION_KEY] = 1
    else:
        reference.kwargs[ALIGNMENT_REVIEW_METADATA_NAME_KEY] = ""
    api = SimpleNamespace(
        file_path=script,
        voutputs=[reference],
        timeline=_Timeline(),
        register_on_destroy=lambda cb: None,
    )
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)
    _call_hook(panel.on_workspace_loaded)
    message = panel.error_label.text()
    assert "Inactive" in panel.progress_label.text()
    if problem == "proxy":
        assert "could not be read safely (AttributeError)" in message
        assert str(tmp_path) not in message
        assert not script.with_name(f"{script.stem}.alignment-result.json").exists()
    elif problem == "old-version":
        assert "newly generated session" in message
        assert "metadata v1" in message
        assert "requires v5" in message
        assert not panel.keep_button.isEnabled()
    else:
        assert (
            message
            == "Alignment review rejected: alignment review output presentation name is invalid"
        )
        assert str(tmp_path) not in message


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


def test_plugin_hook_and_native_accessibility_contract(tmp_path: Path) -> None:
    panel, _api, _script = _panel(tmp_path)

    assert cast(Any, vsview_register_toolpanel).vsview_impl["tryfirst"] is True
    assert AlignmentReviewPanel.identifier == "frame_compare_alignment_review"
    assert AlignmentReviewPanel.display_name == "Frame Compare Alignment Review"
    assert panel.guidance_label.wordWrap()
    assert "Automatic tracking unavailable" in panel.guidance_label.text()
    assert panel.error_label.accessibleName() == "Alignment review error"
    assert panel.manual_toggle.accessibleName() == "Enter alignment manually"
    assert panel.body_scroll.accessibleName() == "Alignment source lineup and manual inputs"
    assert panel.audio_detail_groups[0].title() == "Audio evidence details — Comparison 1"
    assert not panel.audio_detail_groups[0].isChecked()
    assert not panel.manual_group.isVisible()
    assert panel.use_positions_button.text() == "Confirm matching frames"


def test_evidence_details_toggle_works_from_keyboard_and_stays_collapsed_by_default(
    tmp_path: Path,
) -> None:
    panel, _api, _script = _panel(tmp_path)
    details = panel.audio_detail_groups[0]
    detail_label = details.findChild(QLabel)

    assert detail_label is not None
    assert not details.isChecked()
    assert detail_label.isHidden()

    details.setFocus()
    QTest.keyClick(details, Qt.Key.Key_Space)

    assert details.isChecked()
    assert not detail_label.isHidden()


@pytest.mark.parametrize("boundary", [False, True], ids=["singleton", "nearby-video"])
def test_panel_summary_preserves_target_boundary_copy(tmp_path: Path, boundary: bool) -> None:
    attempt = (
        boundary_video_inconclusive_attempt() if boundary else singleton_chunk_target_attempt()
    )
    panel, _api, _script = _panel(
        tmp_path, suggestion=None, audio_review=_attempt_audio_review(attempt)
    )
    summary = panel.audio_summary_labels[0].text()
    if boundary:
        assert (
            "The audio points to +146f, but the pictures line up at +148f at the checked points."
            in summary
        )
        assert "confirmed +148f" not in summary
        assert [field.text() for field in panel.frame_inputs] == ["", ""]
        assert not panel.use_positions_button.isEnabled()
    else:
        assert (
            "Audio in 1:00–1:30 points to +246f, and the video could not rule that out." in summary
        )


def test_actual_native_payload_omits_rows_and_matches_full_terminal_and_panel_copy(
    tmp_path: Path,
) -> None:
    attempt = production_nested_targets_attempt()
    reference = Path("reference.mkv")
    comparison = Path("comparison.mkv")
    key = alignment_key(reference, comparison)
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic=attempt.decision.primary_reason,
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    native_review = _build_audio_review_map(
        reference=reference,
        comparisons=[comparison],
        resolutions={
            key: ComparisonResolution(
                result=result,
                comparison_cache_key="key",
                origin="computed_this_run",
            )
        },
    )[key]
    full_review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(attempt),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    native_attempt = json.loads(native_review)["audio_attempt"]
    assert native_attempt["chunks"]["rows_omitted"] is True
    assert all(
        native_attempt["chunks"][name] == []
        for name in ("starts", "counts", "active", "lags", "psrs", "credible", "agrees")
    )
    assert native_attempt["chunks"]["total_samples"] == attempt.chunks.total_samples

    summaries = []
    details = []
    for label, audio_review in (("full", full_review), ("native", native_review)):
        panel_dir = tmp_path / label
        panel_dir.mkdir()
        panel, _api, _script = _panel(panel_dir, suggestion=None, audio_review=audio_review)
        summaries.append(panel.audio_summary_labels[0].text())
        group = panel.audio_detail_groups[0]
        group.setChecked(True)
        details.append(cast(QLabel, group.findChild(QLabel)).text())

    assert summaries[0] == summaries[1]
    assert details[0] == details[1]
    summary = summaries[1]
    assert (
        "Audio in 0:00–1:00 points to +250f, and the video could not settle which offset is right there."
        in summary
    )
    assert "Audio in 1:00–1:30 points to +246f, and the video could not rule that out." in summary
    assert "+250f  0:00–1:00  not settled" in summary
    assert "+246f  1:00–1:30  not settled" in summary
    assert "+250f  1:30–2:00  confirmed by video" in summary
    assert [field.text() for field in panel.frame_inputs] == ["", ""]
    assert [field.text() for field in panel.offset_inputs] == [""]
    assert not panel.use_positions_button.isEnabled()


@pytest.mark.parametrize(
    ("credible", "resolution", "expected_state", "expected_noted"),
    [
        (True, "unresolved", "provisional", None),
        (
            True,
            "resolved",
            "trusted_automatic",
            "Noted: audio differed in 1 section (1:00–1:30); the video confirmed +0f there.",
        ),
        (False, "resolved", "trusted_automatic", None),
        (
            False,
            "unresolved",
            "trusted_automatic",
            (
                "Noted: weak audio in 1:00–1:30 pointed elsewhere; the video could not "
                "settle it, so it was not counted."
            ),
        ),
        (True, "unexamined", "provisional", None),
        (False, "unexamined", "trusted_automatic", None),
        (True, "alternative_confirmed", "provisional", None),
        (False, "alternative_confirmed", "provisional", None),
    ],
)
def test_panel_target_context_semantic_matrix(
    tmp_path: Path,
    credible: bool,
    resolution: str,
    expected_state: str,
    expected_noted: str | None,
) -> None:
    attempt = target_context_attempt(credible=credible, resolution=resolution)
    applied = expected_state == "trusted_automatic"
    panel, _api, _script = _panel(
        tmp_path,
        suggestion=0 if applied else None,
        audio_review=_attempt_audio_review(attempt, applied=applied),
    )
    summary = panel.audio_summary_labels[0].text()
    detail_group = panel.audio_detail_groups[0]
    detail_group.setChecked(True)
    detail_text = cast(QLabel, detail_group.findChild(QLabel)).text()
    assert "Picture differs" not in summary
    assert "the picture differs" not in summary
    if expected_noted is None:
        assert "Noted:" not in summary
    else:
        assert expected_noted in summary

    expected_details = build_audio_review_presentation(attempt).verbose_lines(panel=True)
    assert all(line in detail_text for line in expected_details)
    assert "Picture differs" not in detail_text
    assert [field.text() for field in panel.frame_inputs] == ["", ""]
    assert [field.text() for field in panel.offset_inputs] == [""]
    assert not panel.use_positions_button.isEnabled()


@pytest.mark.parametrize(
    ("shape", "expected_noted", "expected_context"),
    [
        (
            "run",
            "Noted: audio differed in 2 sections (1:00–2:00); the video confirmed +0f there.",
            ("Context: Audio differed in 1:00–2:00; the video confirmed the offset there.",),
        ),
        (
            "run_and_chunk",
            "Noted: audio differed in 3 sections (1:00–2:00, 3:30–4:00); the video confirmed +0f there.",
            (
                "Context: Audio differed in 1:00–2:00; the video confirmed the offset there.",
                "         Audio differed in 3:30–4:00; the video confirmed the offset there.",
            ),
        ),
        (
            "two_runs",
            "Noted: audio differed in 4 sections (1:00–2:00, 5:00–6:00); the video confirmed +0f there.",
            (
                "Context: Audio differed in 1:00–2:00; the video confirmed the offset there.",
                "         Audio differed in 5:00–6:00; the video confirmed the offset there.",
            ),
        ),
    ],
)
def test_panel_resolved_run_context_matrix(
    tmp_path: Path,
    shape: str,
    expected_noted: str,
    expected_context: tuple[str, ...],
) -> None:
    resolutions = ("resolved",) if shape == "run" else ("resolved", "resolved")
    attempt = resolved_run_context_attempt(shape=shape, resolutions=resolutions)
    panel, _api, _script = _panel(
        tmp_path, suggestion=0, audio_review=_attempt_audio_review(attempt, applied=True)
    )
    detail_group = panel.audio_detail_groups[0]
    detail_group.setChecked(True)
    details = cast(QLabel, detail_group.findChild(QLabel)).text()
    assert expected_noted in panel.audio_summary_labels[0].text()
    for line in expected_context:
        assert line in details


@pytest.mark.parametrize(
    ("planned", "active", "credible", "agreeing", "expected"),
    [
        (4, 4, 3, 3, "(0 differ; 1 weak, 0 quiet not counted)."),
        (4, 3, 3, 3, "(0 differ; 0 weak, 1 quiet not counted)."),
        (5, 4, 3, 3, "(0 differ; 1 weak, 1 quiet not counted)."),
        (4, 0, 0, 0, "(0 differ; 0 weak, 4 quiet not counted)."),
    ],
)
def test_panel_established_counts_matrix(
    tmp_path: Path,
    planned: int,
    active: int,
    credible: int,
    agreeing: int,
    expected: str,
) -> None:
    attempt = established_counts_attempt(
        planned=planned,
        active=active,
        credible=credible,
        agreeing=agreeing,
    )
    expected_line = f"Audio: {agreeing} of {credible} clear sections agree on +0f {expected}"
    panel, _api, _script = _panel(
        tmp_path, suggestion=None, audio_review=_attempt_audio_review(attempt)
    )
    summary = panel.audio_summary_labels[0].text()
    group = panel.audio_detail_groups[0]
    group.setChecked(True)
    details = cast(QLabel, group.findChild(QLabel)).text()
    if active:
        assert summary.startswith("Provisional audio candidate: +0f — NOT APPLIED")
    else:
        assert summary.startswith("No usable audio candidate")
    assert f"Established: {expected_line}" in details
    assert " quiet)." not in details


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

    assert all("No usable audio candidate" in label.text() for label in panel.audio_summary_labels)
    assert all(not label.text() for label in panel.source_outcome_labels)
    assert "remain unresolved" in panel.keep_help_label.text()
    assert panel.keep_button.isEnabled()

    panel.keep_button.click()

    result = _read_result(script)
    assert result["decisions"] == [
        {"comparison_key": "ref:comparison-1", "action": "keep_current"},
        {"comparison_key": "ref:comparison-2", "action": "keep_current"},
    ]
    assert panel.progress_label.text() == "Keep decision saved — frame lineup was not confirmed"
    assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
    assert panel.keep_help_label.isHidden()
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()
    assert all("retained" in label.text() for label in panel.source_outcome_labels[1:])


def test_out_of_range_reference_suggestions_publish_no_marker(tmp_path: Path) -> None:
    panel, api, _script = _panel(tmp_path, suggestion=250)
    _enter_frame(panel, 1, 0)

    _visit(panel, api, 0, 12)

    assert api.timeline.cleared[-1] == ("frame_compare_alignment_review", True)
    assert api.timeline.added == []
    details_label = cast(QLabel, panel.audio_detail_groups[0].findChild(QLabel))
    assert "outside raw source bounds" in details_label.text().lower()


def test_provisional_zero_is_visible_but_never_seeds_manual_authority(tmp_path: Path) -> None:
    panel, api, script = _panel(
        tmp_path,
        suggestion=None,
        audio_review=_provisional_audio_review(),
    )

    assert "Provisional audio candidate: +0f — NOT APPLIED" in panel.audio_summary_labels[0].text()
    assert [field.text() for field in panel.frame_inputs] == ["", ""]
    assert [field.text() for field in panel.offset_inputs] == [""]
    assert panel.progress_label.text() == "0/2 frames ready"
    assert not panel.use_positions_button.isEnabled()

    _visit(panel, api, 0, 12)

    assert panel.progress_label.text() == "0/2 frames ready"
    assert not panel.use_positions_button.isEnabled()
    _enter_frame(panel, 0, 12)
    _visit(panel, api, 1, 12)
    assert not api.timeline.added

    panel.keep_button.click()

    assert _read_result(script)["decisions"] == [
        {"comparison_key": "ref:comparison-1", "action": "keep_current"}
    ]
    assert panel.source_outcome_labels[1].text() == (
        "Current alignment retained. Provisional candidate +0f not confirmed — NOT APPLIED. "
        "Comparison unresolved."
    )


@pytest.mark.parametrize("confirm", [False, True], ids=["keep-current", "confirm-positions"])
def test_mixed_states_save_authority_labels_and_preserve_evidence(
    tmp_path: Path, confirm: bool
) -> None:
    panel, api, script = _panel(
        tmp_path,
        comparison_count=4,
        suggestions=(0, None, None, 0),
        audio_reviews=(
            _accepted_audio_review(),
            _provisional_audio_review(2),
            _unavailable_audio_review(3),
            _manual_audio_review(),
        ),
    )

    original_summaries = [label.text() for label in panel.audio_summary_labels]
    launch_note = panel.launch_label_explanation.text()
    assert "Original frame number" in launch_note
    assert "Video hints follow the viewed frame" in launch_note
    original_details = [
        cast(QLabel, details.findChild(QLabel)).text() for details in panel.audio_detail_groups
    ]
    if confirm:
        for output_index, frame in enumerate((10, 8, 12, 9, 11)):
            _enter_frame(panel, output_index, frame)

        panel.use_positions_button.click()

        assert _read_result(script)["decisions"] == [
            {
                "comparison_key": f"ref:comparison-{ordinal}",
                "action": "confirmed",
                "reference_source_frame": 10,
                "comparison_source_frame": frame,
            }
            for ordinal, frame in enumerate((8, 12, 9, 11), start=1)
        ]
        assert [label.text() for label in panel.source_outcome_labels[1:]] == [
            "Saved offset (Reference − Comparison): +2 frames — manually confirmed",
            "Saved offset (Reference − Comparison): -2 frames — manually confirmed",
            "Saved offset (Reference − Comparison): +1 frames — manually confirmed",
            "Saved offset (Reference − Comparison): -1 frames — manually confirmed",
        ]
        assert [label.text() for label in panel.audio_summary_labels] == original_summaries
    else:
        assert [label.text().splitlines()[0] for label in panel.audio_summary_labels] == [
            "Accepted audio alignment: +0f — APPLIED",
            "Provisional audio candidate: +0f — NOT APPLIED",
            "No usable audio candidate (no single offset across the track) — NOT APPLIED",
            "Manually confirmed alignment: +0f — APPLIED",
        ]
        assert [field.text() for field in panel.offset_inputs] == ["", "", "", ""]
        _visit(panel, api, 0, 0)
        assert api.timeline.added == []  # Browsing never creates panel predictions.

        panel.keep_button.click()

        assert _read_result(script)["decisions"] == [
            {"comparison_key": f"ref:comparison-{ordinal}", "action": "keep_current"}
            for ordinal in range(1, 5)
        ]
        assert [label.text() for label in panel.source_outcome_labels[1:]] == [
            "Accepted alignment retained: +0f",
            "Current alignment retained. Provisional candidate +0f not confirmed — NOT APPLIED. "
            "Comparison unresolved.",
            "Current alignment retained. Comparison unresolved — no accepted alignment.",
            "Current alignment retained: +0f — manually confirmed",
        ]
    assert all(label.isHidden() for label in panel.audio_summary_labels)
    assert [
        cast(QLabel, details.findChild(QLabel)).text() for details in panel.audio_detail_groups
    ] == original_details
    assert all(not details.isChecked() for details in panel.audio_detail_groups)
    assert panel.launch_label_explanation.text() == launch_note
    assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
    assert panel.keep_help_label.isHidden()

    if confirm:
        assert panel.launch_label_explanation.text() == launch_note
        api.current_frame = 150
        _call_hook(panel.on_current_frame_changed, 150)
        assert all("Viewing:" not in label.text() for label in panel.source_status_labels)
        assert panel.source_status_labels[-1].text() == "Original frame: 11"
    else:
        script.with_name(f"{script.stem}.alignment-result.json").unlink()
        _call_hook(panel.on_workspace_loaded)
        assert all(not label.isHidden() for label in panel.audio_summary_labels)


def test_manual_authority_stays_distinct_from_retained_provisional_attempt(
    tmp_path: Path,
) -> None:
    panel, api, _script = _panel(
        tmp_path,
        suggestion=0,
        audio_review=_manual_with_provisional_audio_review(),
    )

    summary = panel.audio_summary_labels[0].text()
    assert "Manually confirmed alignment: +0f — APPLIED" in summary
    assert "Provisional audio candidate: +0f — NOT APPLIED" in summary
    _visit(panel, api, 0, 0)
    _enter_frame(panel, 0, 0)
    _visit(panel, api, 1, 0)
    assert not api.timeline.added


@pytest.mark.parametrize(
    ("origin", "manual", "summary_prefix", "marker_prefix"),
    [
        (
            "interactive_confirmed_this_run",
            True,
            "Manually confirmed alignment: +0f — APPLIED",
            "[MANUAL ALIGNMENT]",
        ),
        (
            "shared_previous_offsets",
            True,
            "Manually confirmed alignment: +0f — APPLIED",
            "[MANUAL ALIGNMENT]",
        ),
        (
            "preexisting_manual_override",
            True,
            "Manually confirmed alignment: +0f — APPLIED",
            "[MANUAL ALIGNMENT]",
        ),
        (
            "computed_this_run",
            False,
            "Accepted audio alignment: +0f — APPLIED",
            "[ACCEPTED AUDIO]",
        ),
        (
            "shared_computed_offsets",
            False,
            "Accepted audio alignment reused: +0f — APPLIED",
            "[REUSED ACCEPTED AUDIO]",
        ),
    ],
)
def test_authority_origin_consistently_drives_alignment_presentation(
    tmp_path: Path,
    origin: str,
    manual: bool,
    summary_prefix: str,
    marker_prefix: str,
) -> None:
    panel, api, _script = _panel(
        tmp_path,
        suggestion=0,
        audio_review=_authority_audio_review(origin),
    )

    assert panel.audio_summary_labels[0].text().startswith(summary_prefix)

    _visit(panel, api, 0, 0)

    _enter_frame(panel, 0, 0)
    _visit(panel, api, 1, 0)
    assert not api.timeline.added
    assert marker_prefix  # Origin-specific evidence remains in summary, not a second marker system.

    panel.keep_button.click()

    assert panel.source_outcome_labels[1].text() == (
        "Current alignment retained: +0f — manually confirmed"
        if manual
        else "Accepted alignment retained: +0f"
    )


def test_known_offsets_are_whole_set_and_serialize_canonical_pairs(tmp_path: Path) -> None:
    panel, _api, script = _panel(tmp_path, comparison_count=2)
    panel.manual_toggle.click()
    panel.basis_selector.setCurrentIndex(1)

    assert panel.basis_status_label.text().startswith("Input basis: Known offsets")
    assert panel.guidance_label.text() == (
        "Enter the signed reference-minus-comparison offsets, then confirm. Or keep the "
        "current alignment."
    )
    assert panel.use_positions_button.text() == "Confirm these known offsets"
    assert not panel.offset_inputs_group.isHidden()
    assert all(f.isReadOnly() for f in panel.frame_inputs)
    panel.offset_inputs[0].setText("+12")
    assert not panel.use_positions_button.isEnabled()
    panel.offset_inputs[1].setText("-7")

    assert panel.progress_label.text() == "2/2 offsets entered"
    assert panel.source_outcome_labels[1].text() == "Entered offset: +12f"
    assert panel.source_outcome_labels[2].text() == "Entered offset: -7f"
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
    assert panel.error_label.text()
    assert not panel.use_positions_button.isEnabled()


def test_active_basis_scopes_validation_errors_and_restores_inactive_draft(
    tmp_path: Path,
) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.manual_toggle.click()
    panel.frame_inputs[0].setText("200")

    assert "Reference frame must be between 0 and 199" in panel.error_label.text()
    assert "must be between" in panel.proposal_labels[0].text()

    panel.basis_selector.setCurrentIndex(1)
    panel.offset_inputs[0].setText("+5")

    assert panel.progress_label.text() == "1/1 offsets entered"
    assert panel.source_status_labels[0].text() == "Original frame unavailable"
    assert panel.source_outcome_labels[1].text() == "Entered offset: +5f"
    assert panel.error_label.text() == ""
    assert panel.use_positions_button.isEnabled()

    panel.basis_selector.setCurrentIndex(0)
    assert panel.frame_inputs[0].text() == "200"
    assert "Reference frame must be between 0 and 199" in panel.error_label.text()
    assert "must be between" in panel.proposal_labels[0].text()
    assert not panel.use_positions_button.isEnabled()


def test_switching_basis_never_combines_readiness(tmp_path: Path) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.manual_toggle.click()
    panel.frame_inputs[0].setText("50")
    panel.frame_inputs[1].setText("45")
    assert panel.use_positions_button.isEnabled()

    panel.basis_selector.setCurrentIndex(1)
    assert panel.progress_label.text() == "0/1 offsets entered"
    assert panel.use_positions_button.text() == "Confirm these known offsets"
    assert not panel.use_positions_button.isEnabled()

    panel.basis_selector.setCurrentIndex(0)
    assert panel.progress_label.text() == "2/2 frames ready"
    assert "Automatic tracking unavailable" in panel.guidance_label.text()
    assert panel.use_positions_button.text() == "Confirm matching frames"
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
    assert not panel.lineup_group.isHidden()
    assert panel.offset_inputs_group.isHidden()
    assert panel.basis_status_label.text() == "Input basis: Original source frames"
    assert "Automatic tracking unavailable" in panel.guidance_label.text()
    assert panel.use_positions_button.text() == "Confirm matching frames"


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
    assert "Video hints follow the viewed frame" in panel.launch_label_explanation.text()


@pytest.mark.parametrize("next_workspace", ["ordinary", "malformed"])
def test_deactivation_clears_only_owned_marker_group(tmp_path: Path, next_workspace: str) -> None:
    panel, api, _script = _panel(tmp_path, initialize_output=True)
    if next_workspace == "ordinary":
        api.file_path = None
    else:
        api.voutputs = [SimpleNamespace(vs_index=0, kwargs={})]

    before = len(api.timeline.cleared)
    _call_hook(panel.on_workspace_loaded)

    assert api.timeline.cleared[before:] == [("frame_compare_alignment_review", True)]
    assert "Inactive" in panel.progress_label.text()


def test_p4a_panel_shows_review_copy_without_prefilling_provisional_values(
    tmp_path: Path,
) -> None:
    attempt = review_attempt("competing_offset_confirmed_by_video")
    audio_review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(attempt),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    panel, _api, _script = _panel(
        tmp_path,
        suggestion=None,
        audio_review=audio_review,
    )

    summary = panel.audio_summary_labels[0].text()
    assert "Provisional audio candidate: +146f — NOT APPLIED" in summary
    assert "The video confirms +243f in 1:00–2:00" in summary
    assert "Check 1:01:01 — reference 13,123 ↔ comparison 12,880 (+243f)" in summary
    assert [field.text() for field in panel.frame_inputs] == ["", ""]
    assert [field.text() for field in panel.offset_inputs] == [""]
    assert panel.progress_label.text() == "0/2 frames ready"
    assert not panel.use_positions_button.isEnabled()

    details = panel.audio_detail_groups[0]
    details.setChecked(True)
    detail_text = cast(QLabel, details.findChild(QLabel)).text()
    assert "Established:" in detail_text
    assert "             Video: confirmed +146f" in detail_text
    assert "Check points: 1:01:01 — reference 13,123 ↔ comparison 12,880 (+243f)" in detail_text
    assert ": Video: confirmed" not in detail_text
    assert ": +243f" not in detail_text
    assert "Check points: Check" not in detail_text
    assert "Decision: state=provisional; reason=competing_offset_confirmed_by_video" in detail_text
    assert "Runtime/policy:" in detail_text
    selectable = (
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    assert panel.audio_summary_labels[0].textInteractionFlags() & selectable == selectable
    assert cast(QLabel, details.findChild(QLabel)).textInteractionFlags() & selectable == selectable


@pytest.mark.parametrize("retimed", [False, True], ids=["multi-context", "retimed"])
def test_panel_details_preserve_context_rows(tmp_path: Path, retimed: bool) -> None:
    attempt = (
        replace(
            target_context_attempt(credible=False, resolution="unexamined"),
            selected_streams=(stream("reference"), retimed_comparison_stream()),
        )
        if retimed
        else multi_context_attempt()
    )
    panel, _api, _script = _panel(
        tmp_path,
        suggestion=0 if retimed else None,
        audio_review=_attempt_audio_review(attempt, applied=retimed),
    )
    details = panel.audio_detail_groups[0]
    details.setChecked(True)
    detail_text = cast(QLabel, details.findChild(QLabel)).text()
    if retimed:
        assert (
            "Context: Comparison audio retimed x1.0417 to its effective frame rate." in detail_text
        )
    else:
        assert (
            "Context: Audio (raw): 2 of 4 sections agree; 2 more are within the same frame"
            in detail_text
        )
        assert (
            "         2 sections differ by less than a frame (sub-frame); not a disagreement."
            in detail_text
        )
        assert detail_text.count("Context:") == 1
        assert ": 2 sections differ by less than a frame" not in detail_text


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            "competing_offset_confirmed_by_video",
            "The video confirms +243f in 1:00–2:00, so the sources likely differ by an edit there.",
        ),
        (
            "competing_offset",
            "Audio in 1:00–2:00 points to +243f, and the video could not settle which offset is right there.",
        ),
        (
            "unresolved_audio_disagreement",
            "Audio in 1:00–2:00 points to +243f, and the video could not rule that out.",
        ),
        (
            "video_check_inconclusive",
            "The audio points to +146f, but the video could not confirm the exact frame",
        ),
        (
            "video_check_unavailable",
            "The audio points to +146f, but the video could not be read to confirm the exact frame.",
        ),
        (
            "no_single_offset",
            "The audio does not agree on one offset across the track; the video suggests +146f",
        ),
    ],
)
def test_p4a_panel_covers_each_non_applied_reason(
    tmp_path: Path, reason: str, expected: str
) -> None:
    attempt = (
        audio_failed_video_confirmed_attempt()
        if reason == "no_single_offset"
        else review_attempt(reason)
    )
    audio_review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(attempt),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    panel, _api, _script = _panel(
        tmp_path,
        suggestion=None,
        audio_review=audio_review,
    )

    summary = panel.audio_summary_labels[0].text()
    assert "NOT APPLIED" in summary
    assert expected in summary
    assert [field.text() for field in panel.frame_inputs] == ["", ""]
    assert not panel.use_positions_button.isEnabled()


def test_evidence_is_built_once_per_comparison_and_replaced_with_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builds = 0
    original = build_audio_review_presentation

    def build(attempt: AudioAlignmentAttempt) -> Any:
        nonlocal builds
        builds += 1
        return original(attempt)

    monkeypatch.setattr(
        "frame_compare.vsview.alignment_review_panel.build_audio_review_presentation", build
    )
    panel, api, _script = _panel(
        tmp_path,
        comparison_count=2,
        suggestion=None,
        audio_reviews=(
            _attempt_audio_review(production_nested_targets_attempt()),
            _provisional_audio_review(ordinal=2, frame_offset=7),
        ),
    )
    assert builds == 2
    summaries = [label.text() for label in panel.audio_summary_labels]
    for frame in range(5):
        _visit(panel, api, 0, frame)
        _visit(panel, api, 1, frame + 1)
    assert builds == 2
    assert [label.text() for label in panel.audio_summary_labels] == summaries
    assert panel.frame_inputs[0].text() == ""

    api.voutputs[1].kwargs[ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY] = _provisional_audio_review(
        frame_offset=9
    )
    _call_hook(panel.on_workspace_loaded)
    assert builds == 4
    assert "+9f" in panel.audio_summary_labels[0].text()
    assert panel.source_status_labels[0].text() == "Original frame unavailable"
    _visit(panel, api, 0, 12)
    assert builds == 4


@pytest.mark.parametrize("text", ["", "-1", "x", "200"])
def test_manual_frame_validation_rejects_incomplete_or_out_of_range_set(tmp_path, text):
    panel, _api, script = _panel(tmp_path)
    panel.frame_inputs[0].setText("0")
    panel.frame_inputs[1].setText("0")
    assert panel.use_positions_button.isEnabled()
    panel.frame_inputs[1].setText(text)
    assert not panel.use_positions_button.isEnabled()
    panel._save_positions()
    assert not script.with_name(script.stem + ".alignment-result.json").exists()


def test_confirmation_revalidates_changed_snapshot_and_stale_row_generation(tmp_path):
    panel, api, script = _panel(tmp_path)
    positions = [10, 8]
    panel._positions = cast(Any, SimpleNamespace(snapshot=lambda: tuple(positions)))
    panel._update_positions()
    assert panel.use_positions_button.isEnabled()
    positions[0] = 11  # Move after button enabled and before its handler runs.
    panel._save_positions()
    assert panel.frame_inputs[0].text() == "11"
    assert "Positions changed" in panel.error_label.text()
    assert not script.with_name(script.stem + ".alignment-result.json").exists()
    old_binding = panel._binding(0)
    _call_hook(panel.on_workspace_loaded)
    panel._manual_frame_changed(0, old_binding, "75")
    assert panel.frame_inputs[0].text() == ""
    # Wrong file rejects both complete manual frames and stale Keep.
    panel.frame_inputs[0].setText("0")
    panel.frame_inputs[1].setText("0")
    api.file_path = script.with_name("other.py")
    panel._save_positions()
    panel._save_keep_current()
    assert not script.with_name(script.stem + ".alignment-result.json").exists()


def test_tracked_manual_ownership_empty_edit_focus_and_unavailable_snapshot(tmp_path):
    panel, _api, script = _panel(tmp_path)
    positions = [10, 8]
    state = SimpleNamespace(available=True)
    panel._positions = cast(
        Any,
        SimpleNamespace(
            snapshot=lambda: tuple(positions) if state.available else None,
        ),
    )
    panel._update_positions()
    panel.frame_inputs[0].setText("")
    positions[:] = [12, 9]
    panel._update_positions()
    assert [f.text() for f in panel.frame_inputs] == ["", "9"]
    panel.viewer_buttons[0].click()
    assert [f.text() for f in panel.frame_inputs] == ["12", "9"]
    panel.show()
    panel.frame_inputs[0].setFocus()
    _APP.processEvents()
    positions[0] = 13
    panel._update_positions()
    assert panel.frame_inputs[0].text() == "12"
    assert not panel.use_positions_button.isEnabled()
    panel.frame_inputs[0].clearFocus()
    panel._update_positions()
    assert panel.frame_inputs[0].text() == "13"
    state.available = False
    panel._save_positions()
    assert not panel.use_positions_button.isEnabled()
    assert not script.with_name(script.stem + ".alignment-result.json").exists()
    panel.hide()


def test_manual_zero_confirms_complete_set_without_promoting_opening_hint(tmp_path):
    panel, _api, script = _panel(
        tmp_path, suggestion=None, audio_review=_provisional_audio_review()
    )
    assert not panel.use_positions_button.isEnabled()
    panel.frame_inputs[0].setText("0")
    panel.frame_inputs[1].setText("0")
    panel.use_positions_button.click()
    assert _read_result(script)["decisions"] == [
        {
            "comparison_key": "ref:comparison-1",
            "action": "confirmed",
            "reference_source_frame": 0,
            "comparison_source_frame": 0,
        }
    ]
    assert "Provisional audio candidate: +0f" in panel.audio_summary_labels[0].text()
    assert panel.source_outcome_labels[1].text() == (
        "Saved offset (Reference − Comparison): +0 frames — manually confirmed"
    )
    frozen = panel.progress_label.text()
    panel._save_keep_current()
    panel._basis_changed(1)
    panel._refresh_ui()
    assert panel.progress_label.text() == frozen
    assert panel._basis == "positions"
