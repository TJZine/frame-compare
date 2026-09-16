"""Core audio alignment computation and progress workflow tests."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np
import pytest
import tomli_w

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_audio import (
    AudioAnalysisPlan,
    AudioStreamInfo,
    AudioStreamTimeline,
    AudioWindow,
    AudioWindowSpec,
)
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.alignment_correlation import CorrelationEstimate
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress_protocol import ProgressReporter
from tests.services.alignment_request_test_support import alignment_request
from tests.services.test_alignment_diagnostics import audio_attempt


@pytest.fixture(autouse=True)
def automatic_authority_is_disabled_for_workflow_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep pre-R0 workflow fixtures focused on sequencing and presentation."""
    monkeypatch.setattr(
        "frame_compare.services.alignment_consensus._AUTOMATIC_AUTHORITY_HELD",
        False,
    )


def test_alignment_duplicate_stems_fail_before_starting_progress(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "dup.mkv"
    comp_b = tmp_path / "dup.mp4"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    reporter = MagicMock(spec=ProgressReporter)

    config = AlignmentConfig()
    request = alignment_request(
        reference=ref,
        comparisons=[comp_a, comp_b],
        config=config,
        generated_dir=tmp_path,
    )
    with pytest.raises(AudioAlignmentError, match="Duplicate comparison clip stems detected"):
        align_clips_from_request(request, config, progress=reporter)

    reporter.start_phase.assert_not_called()
    reporter.complete_phase.assert_not_called()


@patch("frame_compare.services.alignment_audio.probe_fps")
@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_alignment_computed_results_advance_phase_progress(
    mock_estimate: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    mock_probe.return_value = Fraction(24, 1)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    reporter = MagicMock(spec=ProgressReporter)

    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=tmp_path,
    )
    align_clips_from_request(request, config, progress=reporter)

    reporter.advance.assert_called_once_with(1)
    reporter.start_indeterminate.assert_not_called()
    descriptions = [args[0] for args, _kwargs in reporter.set_description.call_args_list]
    assert descriptions[0] == "ALIGN | Checking saved offsets"
    assert descriptions.count("ALIGN | Comparison 1 | comp.mkv") == 1


@patch("frame_compare.services.alignment_audio.probe_fps")
@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_alignment_advances_each_computed_comparison_before_starting_next(
    mock_estimate: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()
    mock_probe.return_value = Fraction(24, 1)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    reporter = MagicMock(spec=ProgressReporter)

    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=ref,
        comparisons=[comp_a, comp_b],
        config=config,
        generated_dir=tmp_path,
    )
    align_clips_from_request(request, config, progress=reporter)

    assert reporter.advance.call_count == 2
    descriptions = [args[0] for args, _kwargs in reporter.set_description.call_args_list]
    assert descriptions.count("ALIGN | Comparison 1 | comp_a.mkv") == 1
    assert descriptions.count("ALIGN | Comparison 2 | comp_b.mkv") == 1


@patch("frame_compare.services.alignment_audio.probe_fps")
@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_alignment_uses_supplied_reference_fps_for_computed_frame_offsets(
    mock_estimate: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    mock_estimate.return_value = AlignmentConsensus(
        8000,
        0.99,
        True,
        "accepted",
        1,
        1,
        1.0,
        None,
    )

    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=tmp_path,
    )
    results = align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(24000, 1001),
    )

    assert results[0].frame_offset == 24
    mock_probe.assert_not_called()


@pytest.mark.parametrize(
    ("reference", "comparison", "expected_offset"),
    [
        (
            np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32),
            np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32),
            2,
        ),
        (
            np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32),
            np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32),
            -2,
        ),
    ],
)
@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_computed_alignment_offset_is_reference_frame_minus_comparison_frame(
    mock_estimate: MagicMock,
    reference: np.ndarray,
    comparison: np.ndarray,
    expected_offset: int,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    del reference, comparison
    mock_estimate.return_value = AlignmentConsensus(
        expected_offset,
        0.99,
        True,
        "accepted",
        1,
        1,
        1.0,
        None,
    )

    config = AlignmentConfig(sample_rate=24, cache_results=False)
    request = alignment_request(
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=tmp_path,
    )

    results = align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(24, 1),
    )

    assert results[0].frame_offset == expected_offset
    assert results[0].time_offset_seconds == expected_offset / 24


@patch("frame_compare.services.alignment_audio.probe_fps")
@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_alignment_full_manual_hit_stays_in_parent_align_phase(
    mock_estimate: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    manual_overrides = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref",
            "comparison_clip": "comp",
            "frame_offset": 3,
            "timestamp": "2026-05-21T00:00:00Z",
            "confirmed": True,
        },
    }
    (tmp_path / "manual_overrides.toml").write_text(
        tomli_w.dumps(manual_overrides),
        encoding="utf-8",
    )
    mock_probe.return_value = Fraction(24, 1)
    mock_estimate.side_effect = AssertionError("manual alignment should not extract audio")
    reporter = MagicMock(spec=ProgressReporter)

    config = AlignmentConfig(cache_results=True)
    request = alignment_request(
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=tmp_path,
    )
    align_clips_from_request(request, config, progress=reporter)

    reporter.start_indeterminate.assert_not_called()
    reporter.advance.assert_not_called()
    descriptions = [args[0] for args, _kwargs in reporter.set_description.call_args_list]
    assert descriptions == ["ALIGN | Checking saved offsets"]
    assert "Reused manually confirmed alignment: +3f" in capsys.readouterr().err


@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_alignment_passes_config_to_audio_pair_owner(
    mock_estimate: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    config = AlignmentConfig(
        cache_results=False,
        channel_strategy="best_channel",
        reference_stream=2,
        comparison_streams={"comp_b": 1},
    )

    request = alignment_request(
        reference=ref,
        comparisons=[comp_a, comp_b],
        config=config,
        generated_dir=tmp_path,
    )
    align_clips_from_request(request, config, reference_fps=Fraction(24, 1))

    assert mock_estimate.call_args_list == [
        call(
            ref,
            comp_a,
            config=config,
            fps_reference=Fraction(24, 1),
            reference_stream_loader=ANY,
            reference_request=request.reference,
            comparison_request=request.comparisons[0],
            comparison_ordinal=1,
        ),
        call(
            ref,
            comp_b,
            config=config,
            fps_reference=Fraction(24, 1),
            reference_stream_loader=ANY,
            reference_request=request.reference,
            comparison_request=request.comparisons[1],
            comparison_ordinal=2,
        ),
    ]


@patch("frame_compare.services.alignment_audio.probe_fps")
@patch("frame_compare.services.alignment._estimate_audio_pair")
def test_diagnostic_write_failure_does_not_change_alignment_authority(
    mock_estimate: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    reference = tmp_path / "ref.mkv"
    comparison = tmp_path / "comp.mkv"
    reference.touch()
    comparison.touch()
    mock_probe.return_value = Fraction(24, 1)
    mock_estimate.return_value = AlignmentConsensus(
        8000,
        0.99,
        True,
        "accepted",
        1,
        1,
        1.0,
        2.0,
    )
    config = AlignmentConfig(cache_results=False)
    request = replace(
        alignment_request(
            reference=reference,
            comparisons=[comparison],
            config=config,
            generated_dir=tmp_path,
        ),
        alignment_diagnostics_dir=tmp_path / "alignment_diagnostics",
        alignment_diagnostics_root=tmp_path.parent,
    )

    with patch(
        "frame_compare.services.alignment.write_alignment_diagnostic",
        side_effect=OSError("disk full"),
    ):
        result = align_clips_from_request(request, config)[0]

    assert result.applied
    assert result.frame_offset == 24


def test_computed_attempt_retains_resolved_stream_and_window_facts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    reference_stream = AudioStreamInfo(
        audio_stream_index=1,
        absolute_stream_index=2,
        codec_name="aac",
        channels=2,
        channel_layout="stereo",
        sample_rate=48000,
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=AudioStreamTimeline(
            start_time=Fraction(0),
            duration=Fraction(60),
            time_base=Fraction(1, 48000),
            duration_basis="duration_ts",
            start_time_basis="metadata",
            input_start_time_basis="metadata",
        ),
    )
    comparison_stream = replace(
        reference_stream,
        audio_stream_index=2,
        absolute_stream_index=3,
    )
    plan = AudioAnalysisPlan(
        sample_rate=8000,
        requested_sample_rate=8000,
        windows=(AudioWindowSpec(0, 200, 0, 400),),
        peak_fft_points=1024,
        total_fft_points=1024,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.select_reference_audio_stream",
        lambda *_args, **_kwargs: reference_stream,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.select_matching_audio_stream",
        lambda *_args, **_kwargs: comparison_stream,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.plan_audio_analysis",
        lambda *_args, **_kwargs: plan,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.extract_planned_window",
        lambda *_args, **_kwargs: AudioWindow(
            np.ones(200),
            np.ones(400),
            0,
            0,
        ),
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_consensus.estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(0, 0.99, 2.0),
    )
    config = AlignmentConfig(
        cache_results=False,
        reference_stream=1,
        comparison_streams={"comparison": 2},
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.applied
    assert result.audio_attempt is not None
    attempt = result.audio_attempt
    assert [stream.audio_stream_index for stream in attempt.selected_streams] == [1, 2]
    assert [stream.selection_method for stream in attempt.selected_streams] == [
        "explicit_override",
        "explicit_override",
    ]
    assert [stream.selection_rank for stream in attempt.selected_streams] == [(1,), (2,)]
    assert attempt.planned_window_count == 1
    assert attempt.windows[0].actual_reference_count == 200
    assert attempt.windows[0].actual_comparison_count == 400
    assert attempt.windows[0].requested_sample_lag == 0


def _presented_attempt_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    state: str,
    verbose: bool = False,
    quiet: bool = False,
    json_output: bool = False,
) -> None:
    attempt = audio_attempt()
    decision = attempt.decision
    if state == "trusted_automatic":
        decision = replace(decision, state="trusted_automatic", primary_reason="accepted")
        consensus = AlignmentConsensus(
            0,
            0.99,
            True,
            "accepted",
            5,
            4,
            0.8,
            2.0,
            audio_attempt=replace(attempt, decision=decision),
        )
    elif state == "unavailable":
        decision = replace(
            decision,
            state="unavailable",
            candidate=None,
            primary_reason="no_usable_windows",
            raw_correlated_windows=0,
            consensus_windows=0,
            consensus_ratio=None,
            aggregate_score=None,
            minimum_peak_ratio=None,
        )
        windows = tuple(
            replace(window, terminal_category="insufficient_signal") for window in attempt.windows
        )
        consensus = AlignmentConsensus(
            None,
            0.0,
            False,
            "no_usable_windows",
            0,
            0,
            0.0,
            None,
            window_records=windows,
            decision=decision,
            audio_attempt=replace(attempt, windows=windows, decision=decision),
        )
    else:
        consensus = AlignmentConsensus(
            None,
            0.99,
            False,
            "insufficient_consensus",
            5,
            4,
            0.8,
            2.0,
            window_records=attempt.windows,
            decision=attempt.decision,
            audio_attempt=attempt,
        )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: consensus,
    )
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(cache_results=False, no_color=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(24),
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("trusted_automatic", "Audio alignment accepted: +0f"),
        ("provisional", "Provisional candidate: +0f (not applied)"),
        ("unavailable", "No usable audio candidate"),
    ],
)
def test_normal_terminal_distinguishes_audio_states(
    state: str,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _presented_attempt_result(tmp_path, monkeypatch, state=state)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert expected in captured.err
    assert "Streams: Reference a:0 -> Comparison a:0" in captured.err
    assert "\x1b[" not in captured.err


def test_verbose_terminal_adds_bounded_stream_and_window_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _presented_attempt_result(tmp_path, monkeypatch, state="provisional", verbose=True)

    captured = capsys.readouterr()
    assert "Audio details:" in captured.err
    assert "primary-00:" in captured.err
    assert "actual=8000/8000" in captured.err
    assert captured.out == ""


def test_quiet_suppresses_routine_acceptance_but_keeps_actionable_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _presented_attempt_result(tmp_path, monkeypatch, state="trusted_automatic", quiet=True)
    accepted = capsys.readouterr()
    _presented_attempt_result(tmp_path, monkeypatch, state="provisional", quiet=True)
    rejected = capsys.readouterr()

    assert accepted.out == accepted.err == ""
    assert rejected.out == ""
    assert "Provisional candidate: +0f (not applied)" in rejected.err


def test_json_mode_emits_no_human_alignment_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _presented_attempt_result(tmp_path, monkeypatch, state="provisional", json_output=True)

    captured = capsys.readouterr()
    assert "Provisional candidate" not in captured.out + captured.err
    assert "audio_alignment_requires_review" in captured.out + captured.err
