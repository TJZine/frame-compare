"""Audio alignment workflow orchestration tests."""

# pyright: reportPrivateUsage=false

from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest
import tomli_w

from frame_compare.services.alignment import (
    align_clips,
    align_clips_from_request,
    check_alignment_cached,
)
from frame_compare.services.alignment_cache import save_offsets_cache
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.alignment_reuse_cache import comparison_cache_key, save_reusable_offsets
from frame_compare.services.alignment_reuse_prompt import PreviousOffsetPromptInput
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
    ReusableAlignmentEntry,
)
from frame_compare.utils.cache_errors import CacheCorruptionError
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
)


def _write_cached_offsets(
    cache_dir: Path,
    *,
    reference: Path,
    comparisons: list[Path],
    results: list[AlignmentResult],
    sample_rate: int = 8000,
    max_offset_seconds: float = 30.0,
    config: AlignmentConfig | None = None,
    reference_fps: Fraction | None = None,
) -> None:
    save_offsets_cache(
        cache_dir,
        reference=reference,
        comparisons=comparisons,
        sample_rate=sample_rate,
        max_offset_seconds=max_offset_seconds,
        results=results,
        config=config,
        reference_fps=reference_fps,
    )


def _request_clip(path: Path, *, label: str | None = None) -> AlignmentClipRequest:
    stat = path.stat()
    return AlignmentClipRequest(
        path=path,
        label=label or path.stem,
        identity=AlignmentClipIdentity(
            path=path,
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        ),
        trim_start_frames=0,
        trim_end_frame_inclusive=None,
        effective_fps_num=24,
        effective_fps_den=1,
    )


def _alignment_cache_settings(config: AlignmentConfig) -> AlignmentCacheSettings:
    return AlignmentCacheSettings(
        sample_rate=config.sample_rate,
        max_offset_seconds=config.max_offset_seconds,
        correlation_mode=config.correlation_mode,
        preprocessing_mode=config.preprocessing_mode,
        channel_strategy=config.channel_strategy,
        confidence_threshold=config.confidence_threshold,
        ambiguity_peak_ratio=config.ambiguity_peak_ratio,
        window_length_seconds=config.window_length_seconds,
        window_stride_seconds=config.window_stride_seconds,
        minimum_valid_windows=config.minimum_valid_windows,
        consensus_minimum_ratio=config.consensus_minimum_ratio,
        refinement_mode=config.refinement_mode,
        refinement_sample_rate=config.refinement_sample_rate,
    )


def _alignment_request(
    tmp_path: Path,
    *,
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    generated_dir: Path | None = None,
    shared_cache_dir: Path | None = None,
) -> AlignmentRequest:
    return AlignmentRequest(
        reference=_request_clip(reference, label="Reference"),
        selected_reference_relationship="auto",
        comparisons=[_request_clip(comparison) for comparison in comparisons],
        previous_offsets=config.previous_offsets,
        generated_dir=generated_dir or (tmp_path / "generated"),
        shared_alignment_cache_dir=shared_cache_dir or (tmp_path / "shared-alignment"),
        settings=_alignment_cache_settings(config),
    )


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
def test_align_clips_full_cache_hit_skips_probe_and_extract(
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
):
    """Test that full cache hit skips FFmpeg/FFprobe calls."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp_a, comp_b],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp_a.mkv",
                frame_offset=10,
                time_offset_seconds=0.417,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            ),
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp_b.mkv",
                frame_offset=20,
                time_offset_seconds=0.834,
                correlation_score=0.92,
                algorithm="cross_correlation",
                source="computed",
            ),
        ],
    )

    mock_probe.side_effect = AssertionError("should not be called")
    mock_extract_reference.side_effect = AssertionError("should not be called")
    mock_extract_matching.side_effect = AssertionError("should not be called")

    config = AlignmentConfig()
    results = align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert len(results) == 2
    assert results[0].comparison_clip == "comp_a.mkv"
    assert results[0].frame_offset == 10
    assert results[1].comparison_clip == "comp_b.mkv"
    assert results[1].frame_offset == 20


def test_align_clips_duplicate_stems_fail_before_starting_progress(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "dup.mkv"
    comp_b = tmp_path / "dup.mp4"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    reporter = MagicMock(spec=ProgressReporter)

    with pytest.raises(AudioAlignmentError, match="Duplicate comparison clip stems detected"):
        align_clips(ref, [comp_a, comp_b], AlignmentConfig(), tmp_path, progress=reporter)

    reporter.start_phase.assert_not_called()
    reporter.complete_phase.assert_not_called()


def test_check_alignment_cached_rejects_duplicate_comparison_stems(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "dup.mkv"
    comp_b = tmp_path / "dup.mp4"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    with pytest.raises(AudioAlignmentError, match="Duplicate comparison clip stems detected"):
        check_alignment_cached(ref, [comp_a, comp_b], tmp_path)


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_completes_progress_when_cache_load_raises(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    (tmp_path / "audio_offsets.toml").write_text("not valid toml {{{ ", encoding="utf-8")

    mock_probe.return_value = Fraction(24, 1)
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(ref, [comp], AlignmentConfig(), tmp_path, progress=reporter)

    reporter.set_description.assert_any_call("Audio Alignment")


def test_check_alignment_cached_corruption_raises(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    (tmp_path / "audio_offsets.toml").write_text("not valid toml {{{ ", encoding="utf-8")

    with pytest.raises(CacheCorruptionError):
        check_alignment_cached(ref, [comp], tmp_path)


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_computed_results_advance_phase_progress(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    mock_probe.return_value = Fraction(24, 1)
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(
        ref,
        [comp],
        AlignmentConfig(cache_results=False),
        tmp_path,
        progress=reporter,
    )

    reporter.advance.assert_called_once_with(1)
    reporter.start_indeterminate.assert_called_once_with("Loading alignment offsets")
    reporter.set_description.assert_any_call("Audio Alignment")
    reporter.set_description.assert_any_call("Checking alignment for comp.mkv")
    reporter.set_description.assert_any_call("Checked alignment for comp.mkv")


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_advances_each_computed_comparison_before_starting_next(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
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
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(
        ref,
        [comp_a, comp_b],
        AlignmentConfig(cache_results=False),
        tmp_path,
        progress=reporter,
    )

    relevant_calls = [
        call for call in reporter.method_calls if call[0] in {"set_description", "advance"}
    ]
    comp_a_to_comp_b_progress = [
        call.set_description("Checked alignment for comp_a.mkv"),
        call.advance(1),
        call.set_description("Checking alignment for comp_b.mkv"),
    ]
    assert any(
        relevant_calls[index : index + len(comp_a_to_comp_b_progress)] == comp_a_to_comp_b_progress
        for index in range(len(relevant_calls) - len(comp_a_to_comp_b_progress) + 1)
    )
    assert reporter.advance.call_count == 2


def test_align_clips_full_cache_hit_uses_spinner_without_progress_bar(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=12,
                time_offset_seconds=0.5,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(ref, [comp], AlignmentConfig(cache_results=True), tmp_path, progress=reporter)

    reporter.start_indeterminate.assert_called_once_with("Loading alignment offsets")
    reporter.advance.assert_not_called()
    assert call("Checking alignment for comp.mkv") not in reporter.set_description.call_args_list


def test_align_clips_partial_cache_hit_uses_spinner_then_checks_missing_progress(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp_cached = tmp_path / "comp_cached.mkv"
    comp_missing = tmp_path / "comp_missing.mkv"
    ref.touch()
    comp_cached.touch()
    comp_missing.touch()
    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp_cached, comp_missing],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp_cached.mkv",
                frame_offset=12,
                time_offset_seconds=0.5,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )
    reporter = MagicMock(spec=ProgressReporter)

    with (
        patch("frame_compare.services.alignment._probe_fps", return_value=Fraction(24, 1)),
        patch(
            "frame_compare.services.alignment._extract_reference_audio",
            return_value=(np.ones(10, dtype=np.float32), object()),
        ),
        patch(
            "frame_compare.services.alignment._extract_matching_audio",
            return_value=np.ones(10, dtype=np.float32),
        ),
        patch(
            "frame_compare.services.alignment._estimate_consensus_offset",
            return_value=AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None),
        ),
    ):
        align_clips(
            ref,
            [comp_cached, comp_missing],
            AlignmentConfig(cache_results=True),
            tmp_path,
            progress=reporter,
        )

    relevant_calls = [
        call for call in reporter.method_calls if call[0] in {"set_description", "advance"}
    ]
    assert reporter.start_indeterminate.called
    assert relevant_calls.index(
        call.set_description("Loaded cached alignment for comp_cached.mkv")
    ) < relevant_calls.index(call.set_description("Checking alignment for comp_missing.mkv"))
    assert reporter.advance.call_count == 2


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_uses_supplied_reference_fps_for_computed_frame_offsets(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
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

    results = align_clips(
        ref,
        [comp],
        AlignmentConfig(cache_results=False),
        tmp_path,
        reference_fps=Fraction(24000, 1001),
    )

    assert results[0].frame_offset == 24
    mock_probe.assert_not_called()


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_recomputes_when_cached_reference_fps_differs(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=99,
                time_offset_seconds=99 / 24,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
        reference_fps=Fraction(24, 1),
    )

    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(
        16000,
        0.99,
        True,
        "accepted",
        1,
        1,
        1.0,
        None,
    )

    results = align_clips(
        ref,
        [comp],
        AlignmentConfig(cache_results=True),
        tmp_path,
        reference_fps=Fraction(24000, 1001),
    )

    assert results[0].source == "computed"
    assert results[0].frame_offset == 48
    mock_probe.assert_not_called()
    mock_extract_reference.assert_called_once()
    mock_extract_matching.assert_called_once()


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
def test_align_clips_loads_cache_when_reference_fps_matches(
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=99,
                time_offset_seconds=99 / 24,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
        reference_fps=Fraction(24000, 1001),
    )

    results = align_clips(
        ref,
        [comp],
        AlignmentConfig(cache_results=True),
        tmp_path,
        reference_fps=Fraction(24000, 1001),
    )

    assert results[0].source == "cached"
    assert results[0].frame_offset == 99
    mock_probe.assert_not_called()
    mock_extract_reference.assert_not_called()
    mock_extract_matching.assert_not_called()


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
def test_align_clips_full_manual_hit_uses_spinner_without_progress_bar(
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
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
    mock_extract_reference.side_effect = AssertionError("manual alignment should not extract audio")
    mock_extract_matching.side_effect = AssertionError("manual alignment should not extract audio")
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(ref, [comp], AlignmentConfig(cache_results=True), tmp_path, progress=reporter)

    reporter.start_indeterminate.assert_called_once_with("Loading alignment offsets")
    reporter.advance.assert_not_called()
    assert call("Checking alignment for comp.mkv") not in reporter.set_description.call_args_list


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
):
    """Test partial cache hit behavior and result ordering."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp_a],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp_a.mkv",
                frame_offset=10,
                time_offset_seconds=0.417,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )

    mock_probe.return_value = Fraction(24, 1)
    reference_stream = object()
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), reference_stream)
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)

    config = AlignmentConfig()
    # Request comp_a and comp_b
    results = align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert len(results) == 2
    assert results[0].comparison_clip == "comp_a.mkv"
    assert results[0].frame_offset == 10  # from cache
    assert results[1].comparison_clip == "comp_b.mkv"
    assert results[1].frame_offset == 0  # from mock computation

    mock_extract_reference.assert_called_once_with(
        ref,
        config.sample_rate,
        stream_override=None,
        channel_strategy="mono_downmix",
    )
    mock_extract_matching.assert_called_once_with(
        comp_b,
        config.sample_rate,
        reference_stream=reference_stream,
        stream_override=None,
        channel_strategy="mono_downmix",
    )


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_threads_runtime_alignment_config_through_cache_io(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=12,
                time_offset_seconds=0.5,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
        config=AlignmentConfig(),
    )

    mock_probe.return_value = Fraction(24, 1)
    reference_stream = object()
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), reference_stream)
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)

    config = AlignmentConfig(correlation_mode="gcc_phat")
    results = align_clips(ref, [comp], config, tmp_path)

    assert results[0].frame_offset == 0
    mock_extract_reference.assert_called_once_with(
        ref,
        config.sample_rate,
        stream_override=None,
        channel_strategy=config.channel_strategy,
    )
    mock_extract_matching.assert_called_once_with(
        comp,
        config.sample_rate,
        reference_stream=reference_stream,
        stream_override=None,
        channel_strategy=config.channel_strategy,
    )
    assert check_alignment_cached(ref, [comp], tmp_path, config=config) == []


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_passes_stream_overrides_and_channel_strategy_to_audio_owner(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
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
    reference_stream = object()
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), reference_stream)
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None)
    config = AlignmentConfig(
        cache_results=False,
        channel_strategy="best_channel",
        reference_stream=2,
        comparison_streams={"comp_b": 1},
    )

    align_clips(ref, [comp_a, comp_b], config, tmp_path)

    mock_extract_reference.assert_called_once_with(
        ref,
        config.sample_rate,
        stream_override=2,
        channel_strategy="best_channel",
    )
    assert mock_extract_matching.call_args_list == [
        call(
            comp_a,
            config.sample_rate,
            reference_stream=reference_stream,
            stream_override=None,
            channel_strategy="best_channel",
        ),
        call(
            comp_b,
            config.sample_rate,
            reference_stream=reference_stream,
            stream_override=1,
            channel_strategy="best_channel",
        ),
    ]


def test_check_alignment_cached_uses_runtime_alignment_config_for_cache_lookup(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    cached_config = AlignmentConfig(correlation_mode="gcc_phat")
    _write_cached_offsets(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        results=[
            AlignmentResult(
                reference_clip="ref.mkv",
                comparison_clip="comp.mkv",
                frame_offset=4,
                time_offset_seconds=1 / 6,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
        config=cached_config,
    )

    assert check_alignment_cached(ref, [comp], tmp_path, config=AlignmentConfig()) == ["ref:comp"]
    assert check_alignment_cached(ref, [comp], tmp_path, config=cached_config) == []


def test_align_clips_from_request_disabled_skips_shared_reuse_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    generated_dir = tmp_path / "generated"
    ref.touch()
    comp.touch()
    generated_dir.mkdir()
    config = AlignmentConfig(cache_results=False, previous_offsets="disabled")
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=generated_dir,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment.load_reusable_offset_entries",
        lambda _request: (_ for _ in ()).throw(AssertionError("shared cache read")),
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment.save_reusable_offsets",
        lambda _request, _provenances: (_ for _ in ()).throw(AssertionError("shared cache write")),
    )

    with (
        patch("frame_compare.services.alignment._probe_fps", return_value=Fraction(24, 1)),
        patch(
            "frame_compare.services.alignment._extract_reference_audio",
            return_value=(np.ones(10, dtype=np.float32), object()),
        ),
        patch(
            "frame_compare.services.alignment._extract_matching_audio",
            return_value=np.ones(10, dtype=np.float32),
        ),
        patch(
            "frame_compare.services.alignment._estimate_consensus_offset",
            return_value=AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None),
        ),
    ):
        results = align_clips_from_request(request, config)

    assert results[0].source == "computed"
    assert results[0].frame_offset == 0


def test_align_clips_from_request_always_reuses_shared_offsets_and_skips_compute(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    generated_dir = tmp_path / "generated"
    shared_cache_dir = tmp_path / "shared-alignment"
    ref.touch()
    comp.touch()
    generated_dir.mkdir()
    shared_cache_dir.mkdir()
    config = AlignmentConfig(previous_offsets="always")
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=generated_dir,
        shared_cache_dir=shared_cache_dir,
    )
    reusable = AlignmentResult(
        reference_clip=ref.name,
        comparison_clip=comp.name,
        frame_offset=7,
        time_offset_seconds=7 / 24,
        correlation_score=0.87,
        algorithm="cross_correlation",
        source="computed",
    )
    save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=reusable,
                comparison_cache_key=comparison_cache_key(request.comparisons[0]),
                provenance="computed_this_run",
            )
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    with (
        patch("frame_compare.services.alignment._probe_fps") as mock_probe,
        patch("frame_compare.services.alignment._extract_reference_audio") as mock_extract_ref,
        patch("frame_compare.services.alignment._extract_matching_audio") as mock_extract_comp,
        patch("frame_compare.services.alignment.maybe_launch_alignment_vspreview") as mock_vs,
        patch("frame_compare.services.alignment.save_reusable_offsets") as mock_save_shared,
    ):
        results = align_clips_from_request(request, config)

    assert results[0].source == "cached"
    assert results[0].frame_offset == 7
    assert results[0].algorithm == "cross_correlation"
    assert results[0].correlation_score == pytest.approx(0.87)
    mock_probe.assert_not_called()
    mock_extract_ref.assert_not_called()
    mock_extract_comp.assert_not_called()
    mock_vs.assert_not_called()
    mock_save_shared.assert_not_called()


def test_align_clips_from_request_rejects_reuse_without_cache_results(tmp_path: Path) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    config = AlignmentConfig(cache_results=False, previous_offsets="prompt")
    request = _alignment_request(tmp_path, reference=ref, comparisons=[comp], config=config)

    with pytest.raises(AudioAlignmentError, match="cache_results"):
        align_clips_from_request(request, config)


def test_align_clips_from_request_prompt_no_falls_through_to_vspreview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    generated_dir = tmp_path / "generated"
    ref.touch()
    comp.touch()
    generated_dir.mkdir()
    config = AlignmentConfig(previous_offsets="prompt", use_vspreview=True)
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=generated_dir,
    )
    reusable = {
        comparison_cache_key(request.comparisons[0]): ReusableAlignmentEntry(
            result=AlignmentResult(
                ref.name,
                comp.name,
                3,
                0.125,
                0.9,
                "cross_correlation",
                "cached",
            ),
            accepted_at="2026-06-06T12:00:00Z",
            origin="computed",
        )
    }
    monkeypatch.setattr(
        "frame_compare.services.alignment.load_reusable_offset_entries",
        lambda _request, *, comparisons=None: reusable,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment.prompt_for_previous_alignment_offset_reuse",
        lambda **_: False,
    )

    with (
        patch("frame_compare.services.alignment._probe_fps", return_value=Fraction(24, 1)),
        patch(
            "frame_compare.services.alignment._extract_reference_audio",
            return_value=(np.ones(10, dtype=np.float32), object()),
        ),
        patch(
            "frame_compare.services.alignment._extract_matching_audio",
            return_value=np.ones(10, dtype=np.float32),
        ),
        patch(
            "frame_compare.services.alignment._estimate_consensus_offset",
            return_value=AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None),
        ),
        patch("frame_compare.services.alignment.maybe_launch_alignment_vspreview") as mock_vs,
    ):
        mock_vs.return_value = None
        results = align_clips_from_request(request, config)

    assert results[0].source == "computed"
    mock_vs.assert_called_once()


def test_align_clips_from_request_prompt_passes_real_shared_prompt_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    generated_dir = tmp_path / "generated"
    ref.touch()
    comp.touch()
    generated_dir.mkdir()
    config = AlignmentConfig(previous_offsets="prompt", use_vspreview=True)
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=generated_dir,
    )
    reusable = {
        comparison_cache_key(request.comparisons[0]): ReusableAlignmentEntry(
            result=AlignmentResult(
                ref.name,
                comp.name,
                3,
                0.125,
                1.0,
                None,
                "cached",
            ),
            accepted_at="2026-06-06T12:34:56Z",
            origin="vspreview_confirmed",
        )
    }
    captured_prompt_input: PreviousOffsetPromptInput | None = None

    def _capture_prompt(**kwargs: object) -> bool:
        nonlocal captured_prompt_input
        captured_prompt_input = kwargs["prompt_input"]
        return False

    monkeypatch.setattr(
        "frame_compare.services.alignment.load_reusable_offset_entries",
        lambda _request, *, comparisons=None: reusable,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment.prompt_for_previous_alignment_offset_reuse",
        _capture_prompt,
    )

    with (
        patch("frame_compare.services.alignment._probe_fps", return_value=Fraction(24, 1)),
        patch(
            "frame_compare.services.alignment._extract_reference_audio",
            return_value=(np.ones(10, dtype=np.float32), object()),
        ),
        patch(
            "frame_compare.services.alignment._extract_matching_audio",
            return_value=np.ones(10, dtype=np.float32),
        ),
        patch(
            "frame_compare.services.alignment._estimate_consensus_offset",
            return_value=AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None),
        ),
        patch(
            "frame_compare.services.alignment.maybe_launch_alignment_vspreview", return_value=None
        ),
    ):
        align_clips_from_request(request, config)

    assert captured_prompt_input is not None
    rows = captured_prompt_input.rows
    assert len(rows) == 1
    assert rows[0].accepted_at == "2026-06-06T12:34:56Z"
    assert rows[0].source == "confirmed"


def test_align_clips_from_request_rejects_force_interactive_previous_offsets(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    config = AlignmentConfig(previous_offsets="always", force_interactive=True)
    request = _alignment_request(tmp_path, reference=ref, comparisons=[comp], config=config)

    with pytest.raises(AudioAlignmentError, match="force_interactive"):
        align_clips_from_request(request, config)


def test_align_clips_from_request_reuses_shared_offsets_for_unresolved_only_after_manual_override(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp_manual = tmp_path / "comp_manual.mkv"
    comp_shared = tmp_path / "comp_shared.mkv"
    generated_dir = tmp_path / "generated"
    shared_cache_dir = tmp_path / "shared-alignment"
    ref.touch()
    comp_manual.touch()
    comp_shared.touch()
    generated_dir.mkdir()
    shared_cache_dir.mkdir()

    config = AlignmentConfig(previous_offsets="always")
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp_manual, comp_shared],
        config=config,
        generated_dir=generated_dir,
        shared_cache_dir=shared_cache_dir,
    )

    save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=AlignmentResult(
                    reference_clip=ref.name,
                    comparison_clip=comp_manual.name,
                    frame_offset=4,
                    time_offset_seconds=4 / 24,
                    correlation_score=0.91,
                    algorithm="cross_correlation",
                    source="computed",
                ),
                comparison_cache_key=comparison_cache_key(request.comparisons[0]),
                provenance="computed_this_run",
            ),
            AlignmentProvenance(
                result=AlignmentResult(
                    reference_clip=ref.name,
                    comparison_clip=comp_shared.name,
                    frame_offset=7,
                    time_offset_seconds=7 / 24,
                    correlation_score=0.93,
                    algorithm="cross_correlation",
                    source="computed",
                ),
                comparison_cache_key=comparison_cache_key(request.comparisons[1]),
                provenance="computed_this_run",
            ),
        ],
        accepted_at="2026-06-06T12:00:00Z",
    )

    manual_overrides = {
        "version": "1",
        "ref:comp_manual": {
            "reference_clip": "ref",
            "comparison_clip": "comp_manual",
            "frame_offset": 2,
            "timestamp": "2026-06-06T12:30:00Z",
            "confirmed": True,
        },
    }
    (generated_dir / "manual_overrides.toml").write_text(
        tomli_w.dumps(manual_overrides),
        encoding="utf-8",
    )

    with (
        patch("frame_compare.services.alignment._probe_fps") as mock_probe,
        patch("frame_compare.services.alignment._extract_reference_audio") as mock_extract_ref,
        patch("frame_compare.services.alignment._extract_matching_audio") as mock_extract_comp,
        patch("frame_compare.services.alignment._estimate_consensus_offset") as mock_estimate,
        patch("frame_compare.services.alignment.maybe_launch_alignment_vspreview") as mock_vs,
    ):
        results = align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24, 1),
        )

    assert [(result.source, result.frame_offset) for result in results] == [
        ("manual", 2),
        ("cached", 7),
    ]
    mock_probe.assert_not_called()
    mock_extract_ref.assert_not_called()
    mock_extract_comp.assert_not_called()
    mock_estimate.assert_not_called()
    mock_vs.assert_not_called()


def test_align_clips_from_request_does_not_attempt_shared_write_for_legacy_cache_result(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    generated_dir = tmp_path / "generated"
    ref.touch()
    comp.touch()
    generated_dir.mkdir()

    config = AlignmentConfig(previous_offsets="always")
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=generated_dir,
    )
    save_offsets_cache(
        generated_dir,
        reference=ref,
        comparisons=[comp],
        sample_rate=config.sample_rate,
        max_offset_seconds=config.max_offset_seconds,
        results=[
            AlignmentResult(
                reference_clip=ref.name,
                comparison_clip=comp.name,
                frame_offset=6,
                time_offset_seconds=6 / 24,
                correlation_score=0.94,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
        config=config,
        reference_fps=Fraction(24, 1),
    )

    with patch("frame_compare.services.alignment.save_reusable_offsets") as mock_save_shared:
        results = align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24, 1),
        )

    assert results[0].source == "cached"
    mock_save_shared.assert_not_called()


def test_align_clips_from_request_does_not_attempt_shared_write_for_preexisting_manual_override(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    generated_dir = tmp_path / "generated"
    ref.touch()
    comp.touch()
    generated_dir.mkdir()

    config = AlignmentConfig(previous_offsets="always")
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp],
        config=config,
        generated_dir=generated_dir,
    )
    manual_overrides = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref",
            "comparison_clip": "comp",
            "frame_offset": 2,
            "timestamp": "2026-06-06T12:30:00Z",
            "confirmed": True,
        },
    }
    (generated_dir / "manual_overrides.toml").write_text(
        tomli_w.dumps(manual_overrides),
        encoding="utf-8",
    )

    with patch("frame_compare.services.alignment.save_reusable_offsets") as mock_save_shared:
        results = align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24, 1),
        )

    assert results[0].source == "manual"
    mock_save_shared.assert_not_called()


def test_align_clips_from_request_reconfirmed_manual_override_becomes_write_eligible(
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp_manual = tmp_path / "comp_manual.mkv"
    comp_computed = tmp_path / "comp_computed.mkv"
    generated_dir = tmp_path / "generated"
    ref.touch()
    comp_manual.touch()
    comp_computed.touch()
    generated_dir.mkdir()

    config = AlignmentConfig(previous_offsets="always", use_vspreview=True)
    request = _alignment_request(
        tmp_path,
        reference=ref,
        comparisons=[comp_manual, comp_computed],
        config=config,
        generated_dir=generated_dir,
    )
    manual_overrides = {
        "version": "1",
        "ref:comp_manual": {
            "reference_clip": "ref",
            "comparison_clip": "comp_manual",
            "frame_offset": 2,
            "timestamp": "2026-06-06T12:30:00Z",
            "confirmed": True,
        },
    }
    (generated_dir / "manual_overrides.toml").write_text(
        tomli_w.dumps(manual_overrides),
        encoding="utf-8",
    )

    with (
        patch(
            "frame_compare.services.alignment._extract_reference_audio",
            return_value=(np.ones(10, dtype=np.float32), object()),
        ),
        patch(
            "frame_compare.services.alignment._extract_matching_audio",
            return_value=np.ones(10, dtype=np.float32),
        ),
        patch(
            "frame_compare.services.alignment._estimate_consensus_offset",
            return_value=AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, None),
        ),
        patch(
            "frame_compare.services.alignment.maybe_launch_alignment_vspreview",
            return_value={"ref:comp_manual": 5},
        ),
        patch("frame_compare.services.alignment.save_reusable_offsets") as mock_save_shared,
    ):
        results = align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24, 1),
        )

    assert [(result.source, result.frame_offset) for result in results] == [
        ("manual", 5),
        ("computed", 0),
    ]
    mock_save_shared.assert_called_once()
    _, provenances = mock_save_shared.call_args.args
    by_key = {item.result.comparison_clip: item.provenance for item in provenances}
    assert by_key == {
        "comp_manual.mkv": "vspreview_confirmed_this_run",
        "comp_computed.mkv": "computed_this_run",
    }


@pytest.mark.parametrize(
    "config",
    [
        AlignmentConfig(cache_results=False, previous_offsets="prompt"),
        AlignmentConfig(force_interactive=True, previous_offsets="always"),
    ],
)
def test_align_clips_rejects_invalid_previous_offset_policy_combinations(
    tmp_path: Path,
    config: AlignmentConfig,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    with pytest.raises(AudioAlignmentError, match="previous_offsets|force_interactive"):
        align_clips(ref, [comp], config, tmp_path)
