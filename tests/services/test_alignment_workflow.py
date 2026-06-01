"""Audio alignment workflow orchestration tests."""

# pyright: reportPrivateUsage=false

from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest
import tomli_w

from frame_compare.services.alignment import align_clips, check_alignment_cached
from frame_compare.services.alignment_cache import save_offsets_cache
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.cache_errors import CacheCorruptionError
from frame_compare.utils.progress_protocol import ProgressReporter


def _write_cached_offsets(
    cache_dir: Path,
    *,
    reference: Path,
    comparisons: list[Path],
    results: list[AlignmentResult],
    sample_rate: int = 8000,
    max_offset_seconds: float = 30.0,
    config: AlignmentConfig | None = None,
) -> None:
    save_offsets_cache(
        cache_dir,
        reference=reference,
        comparisons=comparisons,
        sample_rate=sample_rate,
        max_offset_seconds=max_offset_seconds,
        results=results,
        config=config,
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
def test_align_clips_computed_results_do_not_advance_phase_progress(
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

    reporter.advance.assert_not_called()
    reporter.set_description.assert_any_call("Audio Alignment")
    reporter.set_description.assert_any_call("Aligning comp.mkv")


def test_align_clips_cached_results_do_not_advance_phase_progress(tmp_path: Path) -> None:
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

    reporter.advance.assert_not_called()


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
def test_align_clips_manual_results_do_not_advance_phase_progress(
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

    reporter.advance.assert_not_called()


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


def test_check_alignment_cached_uses_runtime_alignment_config_for_cache_lookup(tmp_path: Path) -> None:
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
