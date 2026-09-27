from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Generator
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("vsview")

# Qt must see the offscreen platform before PySide6 and VSView are imported.
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402
from vsengine.loops import get_loop, set_loop  # noqa: E402
from vsview.vsenv import QtEventLoop  # noqa: E402

from frame_compare.services.alignment_decision import (  # noqa: E402
    ALIGNMENT_ESTIMATOR_POLICY,
)
from frame_compare.utils.alignment_evidence import (  # noqa: E402
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
)
from frame_compare.vsview.alignment_review_contract import (  # noqa: E402
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
from frame_compare.vsview.alignment_review_panel import (  # noqa: E402
    AlignmentReviewPanel,
    vsview_register_toolpanel,
)
from tests.services.test_alignment_frozen_strings import (
    _audio_failed_video_confirmed_attempt,
    _review_attempt,
)

_SESSION_ID = "12345678123456781234567812345678"
_APP = QApplication.instance() or QApplication([])


def _audio_review(suggestion: int | None) -> str:
    return json.dumps(
        {
            "current_authority": {
                "origin": "shared_computed_offsets" if suggestion is not None else "none",
                "frame_offset": suggestion,
            },
            "evidence_availability": (
                "historical_details_unavailable" if suggestion is not None else "not_computed"
            ),
            "audio_attempt": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


_REFERENCE_DIGEST = "a" * 64
_COMPARISON_DIGEST = "b" * 64
_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"
_FPS_NUM = 24
_FPS_DEN = 1
_CHUNK_SAMPLES = 40000
_LAG_SAMPLES = 240000
_MAX_OFFSET_SECONDS = 30.0
_AGREE_PSR = 30.0


def _frame_lag(frame_offset: int) -> int:
    """Return the exact 8 kHz lag for the whole-frame offsets used by fixtures."""
    lag = frame_offset * 8000 // _FPS_NUM
    assert lag * _FPS_NUM == frame_offset * 8000
    return lag


def _subframe_estimate(lag: int) -> float:
    return lag / 8000 * (_FPS_NUM / _FPS_DEN)


def _stream(role: str, digest: str) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role="reference" if role == "reference" else "comparison",  # type: ignore[arg-type]
        source_identity_digest=digest,
        audio_stream_index=0,
        absolute_stream_index=1,
        selection_method="automatic_metadata",
        selection_rank=(0, 0, 0, 0),
        codec_name="aac",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        language_match="not_applicable" if role == "reference" else "match",
        commentary_match="not_applicable" if role == "reference" else "match",
        stream_start_num=0,
        stream_start_den=1,
        stream_start_basis="metadata",
        input_start_num=0,
        input_start_den=1,
        input_start_basis="metadata",
        time_base_num=1,
        time_base_den=48000,
        duration_num=120,
        duration_den=1,
        duration_basis="duration_ts",
        video_start_num=0,
        video_start_den=1,
        video_start_basis="metadata",
    )


def _analysis(*, planned_chunk_count: int) -> AudioAnalysisFacts:
    planned = planned_chunk_count > 0
    return AudioAnalysisFacts(
        analysis_rate=8000,
        max_offset_seconds=_MAX_OFFSET_SECONDS,
        chunk_samples=_CHUNK_SAMPLES if planned else 0,
        lag_samples=_LAG_SAMPLES if planned else 0,
        planned_chunk_count=planned_chunk_count,
    )


def _agreed_columns(*, lag: int, chunk_count: int) -> AudioChunkColumns:
    return AudioChunkColumns(
        starts=tuple(index * _CHUNK_SAMPLES for index in range(chunk_count)),
        counts=tuple(_CHUNK_SAMPLES for _ in range(chunk_count)),
        active=tuple(True for _ in range(chunk_count)),
        lags=tuple(lag for _ in range(chunk_count)),
        psrs=tuple(_AGREE_PSR for _ in range(chunk_count)),
        credible=tuple(True for _ in range(chunk_count)),
        agrees=tuple(True for _ in range(chunk_count)),
    )


def _attempt_shell(
    *,
    ordinal: int,
    status: str,
    analysis: AudioAnalysisFacts,
    chunks: AudioChunkColumns,
    runs: tuple[AudioChunkRun, ...],
    audio: AudioStageOutcome,
    decision: AudioAlignmentDecision,
    stability: AlignmentStabilitySummary,
) -> AudioAlignmentAttempt:
    return AudioAlignmentAttempt(
        reference_identity_digest=_REFERENCE_DIGEST,
        comparison_identity_digest=_COMPARISON_DIGEST,
        comparison_ordinal=ordinal,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        estimator_policy=ALIGNMENT_ESTIMATOR_POLICY,
        diagnostic_policy=_DIAGNOSTIC_POLICY,
        media_runtime_fingerprint="alignment-runtime-test",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe="ffmpeg -i <input> -map 0:a -f f32le -",
        fps_num=_FPS_NUM,
        fps_den=_FPS_DEN,
        selected_streams=(
            _stream("reference", _REFERENCE_DIGEST),
            _stream("comparison", _COMPARISON_DIGEST),
        ),
        analysis=analysis,
        chunks=chunks,
        runs=runs,
        audio=audio,
        collection_observation="not_observed",
        collection=(),
        video_check=VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        decision=decision,
        stability=stability,
    )


def _agreed_audio(*, lag: int, frame_offset: int, chunk_count: int) -> AudioStageOutcome:
    return AudioStageOutcome(
        status="agreed",
        global_lag=lag,
        active_chunks=chunk_count,
        credible_chunks=chunk_count,
        agreeing_chunks=chunk_count,
        compensation_seconds=0.0,
        subframe_estimate=_subframe_estimate(lag),
        rounded_frame=frame_offset,
    )


def _stable_summary(*, frame_offset: int, chunk_count: int) -> AlignmentStabilitySummary:
    return AlignmentStabilitySummary(
        classification="stable",
        valid_windows=chunk_count,
        offset_min_frames=frame_offset,
        offset_max_frames=frame_offset,
        first_offset_frames=frame_offset,
        last_offset_frames=frame_offset,
        largest_adjacent_jump_frames=0,
        change_position_seconds=None,
    )


def provisional_audio_attempt(
    *, ordinal: int = 1, frame_offset: int = 0, chunk_count: int = 4
) -> AudioAlignmentAttempt:
    """Agreed audio stage awaiting video confirmation (the U3 applied-nothing state)."""
    lag = _frame_lag(frame_offset)
    subframe = _subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    return _attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis=_analysis(planned_chunk_count=chunk_count),
        chunks=_agreed_columns(lag=lag, chunk_count=chunk_count),
        runs=(
            AudioChunkRun(
                first_index=0,
                last_index=chunk_count - 1,
                lag=lag,
                chunk_count=chunk_count,
            ),
        ),
        audio=_agreed_audio(lag=lag, frame_offset=frame_offset, chunk_count=chunk_count),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=lag / 8000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="video_check_pending",
            failed_gates=(),
        ),
        stability=_stable_summary(frame_offset=frame_offset, chunk_count=chunk_count),
    )


def trusted_audio_attempt(
    *, ordinal: int = 1, frame_offset: int = 0, chunk_count: int = 4
) -> AudioAlignmentAttempt:
    """Audio-plus-video confirmed attempt that may authorize an applied result."""
    lag = _frame_lag(frame_offset)
    subframe = _subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    return _attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis=_analysis(planned_chunk_count=chunk_count),
        chunks=_agreed_columns(lag=lag, chunk_count=chunk_count),
        runs=(
            AudioChunkRun(
                first_index=0,
                last_index=chunk_count - 1,
                lag=lag,
                chunk_count=chunk_count,
            ),
        ),
        audio=_agreed_audio(lag=lag, frame_offset=frame_offset, chunk_count=chunk_count),
        decision=AudioAlignmentDecision(
            state="trusted_automatic",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=lag / 8000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="audio_video_confirmed",
            failed_gates=(),
        ),
        stability=_stable_summary(frame_offset=frame_offset, chunk_count=chunk_count),
    )


def unavailable_audio_attempt(*, ordinal: int = 1) -> AudioAlignmentAttempt:
    """Two credible runs at different lags: no single offset, never applied."""
    near_lag = _frame_lag(12)
    far_lag = _frame_lag(24)
    chunk_count = 4
    return _attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis=_analysis(planned_chunk_count=chunk_count),
        chunks=AudioChunkColumns(
            starts=tuple(index * _CHUNK_SAMPLES for index in range(chunk_count)),
            counts=tuple(_CHUNK_SAMPLES for _ in range(chunk_count)),
            active=(True, True, True, True),
            lags=(near_lag, near_lag, far_lag, far_lag),
            psrs=(_AGREE_PSR, _AGREE_PSR, _AGREE_PSR, _AGREE_PSR),
            credible=(True, True, True, True),
            agrees=(True, True, False, False),
        ),
        runs=(
            AudioChunkRun(first_index=0, last_index=1, lag=near_lag, chunk_count=2),
            AudioChunkRun(first_index=2, last_index=3, lag=far_lag, chunk_count=2),
        ),
        audio=AudioStageOutcome(
            status="no_single_offset",
            global_lag=near_lag,
            active_chunks=chunk_count,
            credible_chunks=chunk_count,
            agreeing_chunks=2,
            compensation_seconds=0.0,
            subframe_estimate=_subframe_estimate(near_lag),
            rounded_frame=12,
        ),
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        ),
        stability=AlignmentStabilitySummary(
            classification="possible_discontinuity",
            valid_windows=chunk_count,
            offset_min_frames=12,
            offset_max_frames=24,
            first_offset_frames=12,
            last_offset_frames=24,
            largest_adjacent_jump_frames=12,
            change_position_seconds=10.0,
        ),
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

    assert panel.progress_label.text() == "0/3 positions captured"
    assert [label.text() for label in panel.source_status_labels] == [
        "Captured position: not captured",
        "Captured position: not captured",
        "Captured position: not captured",
    ]
    assert not panel.use_positions_button.isEnabled()
    assert api.timeline.added == []

    _call_hook(panel.on_current_voutput_changed, api.current_voutput, 0)

    assert panel.progress_label.text() == "1/3 positions captured"
    assert panel.source_status_labels[0].text() == (
        "Viewing: frame 12\nCaptured position: frame 12"
    )
    assert [label.text() for label in panel.source_status_labels[1:]] == [
        "Captured position: not captured",
        "Captured position: not captured",
    ]
    assert len(api.timeline.added) == 2


def test_viewer_callbacks_update_only_current_source_and_revisits_replace_it(
    tmp_path: Path,
) -> None:
    panel, api, _script = _panel(tmp_path, comparison_count=2)
    _visit(panel, api, 0, 40)
    _visit(panel, api, 1, 31)

    assert panel.source_status_labels[0].text() == "Captured position: frame 40"
    assert panel.source_status_labels[1].text() == (
        "Viewing: frame 31\nCaptured position: frame 31"
    )
    assert panel.source_status_labels[2].text() == "Captured position: not captured"
    assert panel.source_outcome_labels[1].text().startswith("+9f")

    api.current_frame = 29
    _call_hook(panel.on_current_frame_changed, 29)

    assert panel.source_status_labels[0].text() == "Captured position: frame 40"
    assert panel.source_status_labels[1].text() == (
        "Viewing: frame 29\nCaptured position: frame 29"
    )
    assert panel.source_outcome_labels[1].text().startswith("+11f")


def test_panel_is_inert_for_ordinary_workspace(tmp_path: Path) -> None:
    timeline = _Timeline()
    script = tmp_path / "ordinary.py"
    script.write_text("# ordinary VSView session\n", encoding="utf-8")
    output = SimpleNamespace(
        vs_index=0,
        vs_output=SimpleNamespace(clip=SimpleNamespace(num_frames=200)),
        kwargs={"unrelated_plugin_metadata": "untouched"},
    )
    api = SimpleNamespace(file_path=script, voutputs=[output], timeline=timeline)
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)

    _call_hook(panel.on_workspace_loaded)

    assert "Inactive" in panel.progress_label.text()
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()
    assert timeline.cleared == [("frame_compare_alignment_review", True)]


def test_malformed_frame_compare_output_proxy_reports_unavailable(tmp_path: Path) -> None:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# session\n", encoding="utf-8")
    timeline = _Timeline()
    malformed = SimpleNamespace(
        vs_index=0,
        kwargs={ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_METADATA_VERSION},
    )
    api = SimpleNamespace(file_path=script, voutputs=[malformed], timeline=timeline)
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)

    _call_hook(panel.on_workspace_loaded)

    assert "Inactive" in panel.progress_label.text()
    assert "could not be read safely (AttributeError)" in panel.error_label.text()
    assert str(tmp_path) not in panel.error_label.text()
    assert timeline.added == []
    assert not script.with_name(f"{script.stem}.alignment-result.json").exists()


def test_metadata_v1_session_requires_regeneration(tmp_path: Path) -> None:
    sessions = tmp_path / "vsview_sessions"
    sessions.mkdir()
    script = sessions / f"alignment_{_SESSION_ID}.py"
    script.write_text("# old session\n", encoding="utf-8")
    reference = _reference_output()
    reference.kwargs[ALIGNMENT_REVIEW_METADATA_VERSION_KEY] = 1
    api = SimpleNamespace(file_path=script, voutputs=[reference], timeline=_Timeline())
    parent = QWidget()
    panel = AlignmentReviewPanel(parent, cast(Any, api))
    panel.setParent(None)

    _call_hook(panel.on_workspace_loaded)

    message = panel.error_label.text()
    assert "newly generated session" in message
    assert "metadata v1" in message
    assert "requires v5" in message
    assert "Inactive" in panel.progress_label.text()
    assert not panel.keep_button.isEnabled()


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
    assert panel.guidance_label.text() == (
        "To confirm a new alignment, unlink the playheads and position each source on the "
        "same visible moment. Or keep the current alignment."
    )
    assert panel.error_label.accessibleName() == "Alignment review error"
    assert panel.manual_toggle.accessibleName() == "Enter alignment manually"
    assert panel.body_scroll.accessibleName() == "Alignment source lineup and manual inputs"
    assert panel.audio_detail_groups[0].title() == "Audio evidence details — Comparison 1"
    assert not panel.audio_detail_groups[0].isChecked()
    assert not panel.manual_group.isVisible()
    assert panel.use_positions_button.text() == "Confirm these aligned positions"


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
        "No usable audio candidate (no usable audio signal) — NOT APPLIED",
        "No usable audio candidate (no usable audio signal) — NOT APPLIED",
    ]
    assert "remain unresolved" in panel.keep_help_label.text()
    assert panel.keep_button.isEnabled()

    panel.keep_button.click()

    result = _read_result(script)
    assert result["decisions"] == [
        {"comparison_key": "ref:comparison-1", "action": "keep_current"},
        {"comparison_key": "ref:comparison-2", "action": "keep_current"},
    ]
    assert "Alignment choices saved" in panel.progress_label.text()
    assert panel.progress_label.text() == "Alignment choices saved"
    assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
    assert panel.keep_help_label.isHidden()
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()
    assert all("retained" in label.text() for label in panel.source_outcome_labels[1:])


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
    details_label = cast(QLabel, panel.audio_detail_groups[0].findChild(QLabel))
    assert "marker omitted" in details_label.text().lower()


def test_provisional_zero_is_visible_but_never_seeds_manual_authority(tmp_path: Path) -> None:
    panel, api, script = _panel(
        tmp_path,
        suggestion=None,
        audio_review=_provisional_audio_review(),
    )

    assert "Provisional audio candidate: +0f — NOT APPLIED" in panel.audio_summary_labels[0].text()
    assert [field.text() for field in panel.frame_inputs] == ["", ""]
    assert [field.text() for field in panel.offset_inputs] == [""]
    assert panel.progress_label.text() == "0/2 positions captured"
    assert not panel.use_positions_button.isEnabled()

    _visit(panel, api, 0, 12)

    assert panel.progress_label.text() == "1/2 positions captured"
    assert not panel.use_positions_button.isEnabled()
    assert api.timeline.added[0][3].startswith("[PROVISIONAL — NOT APPLIED] +0f")

    panel.keep_button.click()

    assert _read_result(script)["decisions"] == [
        {"comparison_key": "ref:comparison-1", "action": "keep_current"}
    ]
    assert panel.source_outcome_labels[1].text() == (
        "Current alignment retained. Provisional candidate +0f not confirmed — NOT APPLIED. "
        "Comparison unresolved."
    )


def test_mixed_states_keep_separate_authority_and_saved_labels(tmp_path: Path) -> None:
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

    assert [label.text().splitlines()[0] for label in panel.audio_summary_labels] == [
        "Accepted audio alignment: +0f — APPLIED",
        "Provisional audio candidate: +0f — NOT APPLIED",
        "No usable audio candidate (no single offset across the track) — NOT APPLIED",
        "Manually confirmed alignment: +0f — APPLIED",
    ]
    original_details = [
        cast(QLabel, details.findChild(QLabel)).text() for details in panel.audio_detail_groups
    ]
    assert [field.text() for field in panel.offset_inputs] == ["", "", "", ""]
    _visit(panel, api, 0, 0)
    marker_text = [cast(str, marker[3]) for marker in api.timeline.added]
    assert marker_text == [
        "[ACCEPTED AUDIO] +0f — reference frame 0",
        "[PROVISIONAL — NOT APPLIED] +0f — reference frame 0",
        "[MANUAL ALIGNMENT] +0f — reference frame 0",
    ]

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
    assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
    assert panel.keep_help_label.isHidden()

    script.with_name(f"{script.stem}.alignment-result.json").unlink()
    _call_hook(panel.on_workspace_loaded)
    assert all(not label.isHidden() for label in panel.audio_summary_labels)


def test_mixed_states_confirm_freezes_positions_and_preserves_audio_details(
    tmp_path: Path,
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
    original_details = [
        cast(QLabel, details.findChild(QLabel)).text() for details in panel.audio_detail_groups
    ]

    for output_index, frame in enumerate((10, 8, 12, 9, 11)):
        _visit(panel, api, output_index, frame)

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
        "Alignment confirmed: +2f — manually confirmed",
        "Alignment confirmed: -2f — manually confirmed",
        "Alignment confirmed: +1f — manually confirmed",
        "Alignment confirmed: -1f — manually confirmed",
    ]
    assert [label.text() for label in panel.audio_summary_labels] == original_summaries
    assert all(label.isHidden() for label in panel.audio_summary_labels)
    assert [
        cast(QLabel, details.findChild(QLabel)).text() for details in panel.audio_detail_groups
    ] == original_details
    assert all(not details.isChecked() for details in panel.audio_detail_groups)
    assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
    assert panel.keep_help_label.isHidden()

    api.current_frame = 150
    _call_hook(panel.on_current_frame_changed, 150)
    assert all("Viewing:" not in label.text() for label in panel.source_status_labels)
    assert panel.source_status_labels[-1].text() == "Captured position: frame 11"


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
    assert api.timeline.added[0][3] == "[MANUAL ALIGNMENT] +0f — reference frame 0"


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

    assert api.timeline.added[0][2] == ("#8e6ccf" if manual else "#3daee9")
    assert api.timeline.added[0][3] == f"{marker_prefix} +0f — reference frame 0"

    panel.keep_button.click()

    assert panel.source_outcome_labels[1].text() == (
        "Current alignment retained: +0f — manually confirmed"
        if manual
        else "Accepted alignment retained: +0f"
    )


def test_one_primary_action_saves_complete_viewer_positions(tmp_path: Path) -> None:
    panel, api, script = _panel(tmp_path, comparison_count=2)
    _visit(panel, api, 0, 120)
    _visit(panel, api, 1, 108)
    _visit(panel, api, 2, 127)

    assert panel.progress_label.text() == "3/3 positions captured — ready to confirm"
    assert panel.use_positions_button.isEnabled()
    assert panel.source_outcome_labels[1].text() == "+12f — Trim 12 frame(s) from reference"
    assert panel.source_outcome_labels[2].text() == ("-7f — Trim 7 frame(s) from this comparison")

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
    assert panel.progress_label.text() == "Alignment choices saved"
    assert panel.guidance_label.text() == "Close VSView to resume Frame Compare."
    assert [label.text() for label in panel.source_outcome_labels[1:]] == [
        "Alignment confirmed: +12f — manually confirmed",
        "Alignment confirmed: -7f — manually confirmed",
    ]
    assert panel.keep_help_label.isHidden()
    assert not panel.use_positions_button.isEnabled()
    assert not panel.keep_button.isEnabled()
    assert not panel.manual_toggle.isEnabled()


def test_manual_source_frames_feed_same_draft_and_viewer_can_replace_origin(
    tmp_path: Path,
) -> None:
    panel, api, script = _panel(tmp_path)
    panel.manual_toggle.click()

    assert not panel.manual_group.isHidden()
    assert panel.progress_label.text() == "0/2 source frames entered"
    panel.frame_inputs[0].setText("120")
    panel.frame_inputs[1].setText("bad")
    assert panel.frame_inputs[1].text() == "bad"
    assert "whole number" in panel.error_label.text()
    assert "Needs attention" in panel.source_status_labels[1].text()
    assert not panel.use_positions_button.isEnabled()

    panel.frame_inputs[1].setText("108")
    assert panel.progress_label.text() == "2/2 source frames entered — ready to confirm"
    assert panel.source_status_labels[0].text() == "Entered source frame: 120"
    assert panel.source_status_labels[1].text() == "Entered source frame: 108"
    assert panel.use_positions_button.isEnabled()

    _visit(panel, api, 1, 107)
    assert panel.source_status_labels[1].text() == ("Viewing: frame 107\nEntered source frame: 107")
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
    assert panel.guidance_label.text() == (
        "Enter the signed reference-minus-comparison offsets, then confirm. Or keep the "
        "current alignment."
    )
    assert panel.use_positions_button.text() == "Confirm these known offsets"
    assert not panel.offset_inputs_group.isHidden()
    assert panel.frame_inputs_group.isHidden()
    panel.offset_inputs[0].setText("+12")
    assert not panel.use_positions_button.isEnabled()
    panel.offset_inputs[1].setText("-7")

    assert panel.progress_label.text() == "2/2 offsets entered — ready to confirm"
    assert panel.source_status_labels[1].text() == "Entered offset: +12f"
    assert panel.source_outcome_labels[2].text() == ("-7f — Trim 7 frame(s) from this comparison")
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


def test_active_basis_scopes_validation_errors_and_restores_inactive_draft(
    tmp_path: Path,
) -> None:
    panel, _api, _script = _panel(tmp_path)
    panel.manual_toggle.click()
    panel.frame_inputs[0].setText("200")

    assert "Reference frame must be between 0 and 199" in panel.error_label.text()
    assert "Needs attention" in panel.source_status_labels[0].text()

    panel.basis_selector.setCurrentIndex(1)
    panel.offset_inputs[0].setText("+5")

    assert panel.progress_label.text() == "1/1 offsets entered — ready to confirm"
    assert panel.source_status_labels[0].text() == "Captured position: not captured"
    assert panel.source_status_labels[1].text() == "Entered offset: +5f"
    assert panel.error_label.text() == ""
    assert panel.use_positions_button.isEnabled()

    panel.basis_selector.setCurrentIndex(0)
    assert panel.frame_inputs[0].text() == "200"
    assert "Reference frame must be between 0 and 199" in panel.error_label.text()
    assert "Needs attention" in panel.source_status_labels[0].text()
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
    assert panel.progress_label.text() == "2/2 source frames entered — ready to confirm"
    assert panel.guidance_label.text() == (
        "To confirm a new alignment, unlink the playheads and position each source on the "
        "same visible moment. Or keep the current alignment."
    )
    assert panel.use_positions_button.text() == "Confirm these aligned positions"
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
    assert panel.guidance_label.text() == (
        "To confirm a new alignment, unlink the playheads and position each source on the "
        "same visible moment. Or keep the current alignment."
    )
    assert panel.use_positions_button.text() == "Confirm these aligned positions"


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


def test_p4a_panel_shows_review_copy_without_prefilling_provisional_values(
    tmp_path: Path,
) -> None:
    attempt = _review_attempt("competing_offset_confirmed_by_video")
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
    assert panel.progress_label.text() == "0/2 positions captured"
    assert not panel.use_positions_button.isEnabled()

    details = panel.audio_detail_groups[0]
    details.setChecked(True)
    detail_text = cast(QLabel, details.findChild(QLabel)).text()
    assert "Established:" in detail_text
    assert "Decision: state=provisional; reason=competing_offset_confirmed_by_video" in detail_text
    assert "Runtime/policy:" in detail_text
    selectable = (
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    assert panel.audio_summary_labels[0].textInteractionFlags() & selectable == selectable
    assert cast(QLabel, details.findChild(QLabel)).textInteractionFlags() & selectable == selectable


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
        _audio_failed_video_confirmed_attempt()
        if reason == "no_single_offset"
        else _review_attempt(reason)
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
