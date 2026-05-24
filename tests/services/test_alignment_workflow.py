"""Audio alignment workflow orchestration tests."""

# pyright: reportPrivateUsage=false

from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import tomli_w

from frame_compare.services.alignment import align_clips, check_alignment_cached
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.cache_errors import CacheCorruptionError
from frame_compare.utils.progress_protocol import ProgressReporter


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
def test_align_clips_full_cache_hit_skips_probe_and_extract(
    mock_extract: MagicMock, mock_probe: MagicMock, tmp_path: Path
):
    """Test that full cache hit skips FFmpeg/FFprobe calls."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 10,
            "time_offset_seconds": 0.417,
            "correlation_score": 0.95,
            "algorithm": "cross_correlation",
        },
        "ref:comp_b": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_b.mkv",
            "frame_offset": 20,
            "time_offset_seconds": 0.834,
            "correlation_score": 0.92,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_probe.side_effect = AssertionError("should not be called")
    mock_extract.side_effect = AssertionError("should not be called")

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
@patch("frame_compare.services.alignment._extract_audio")
@patch("frame_compare.services.alignment._cross_correlate")
def test_align_clips_completes_progress_when_cache_load_raises(
    mock_corr: MagicMock,
    mock_extract: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    (tmp_path / "audio_offsets.toml").write_text("not valid toml {{{ ", encoding="utf-8")

    mock_probe.return_value = Fraction(24, 1)
    mock_extract.return_value = np.ones(10, dtype=np.float32)
    mock_corr.return_value = (0, 0.99)
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
@patch("frame_compare.services.alignment._extract_audio")
@patch("frame_compare.services.alignment._cross_correlate")
def test_align_clips_computed_results_do_not_advance_phase_progress(
    mock_corr: MagicMock,
    mock_extract: MagicMock,
    mock_probe: MagicMock,
    tmp_path: Path,
) -> None:
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    mock_probe.return_value = Fraction(24, 1)
    mock_extract.return_value = np.ones(10, dtype=np.float32)
    mock_corr.return_value = (0, 0.99)
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
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp.mkv",
            "frame_offset": 12,
            "time_offset_seconds": 0.5,
            "correlation_score": 0.95,
            "algorithm": "cross_correlation",
        },
    }
    cache_file.write_text(tomli_w.dumps(data), encoding="utf-8")
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(ref, [comp], AlignmentConfig(cache_results=True), tmp_path, progress=reporter)

    reporter.advance.assert_not_called()


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
def test_align_clips_manual_results_do_not_advance_phase_progress(
    mock_extract: MagicMock,
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
    mock_extract.side_effect = AssertionError("manual alignment should not extract audio")
    reporter = MagicMock(spec=ProgressReporter)

    align_clips(ref, [comp], AlignmentConfig(cache_results=True), tmp_path, progress=reporter)

    reporter.advance.assert_not_called()


@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
@patch("frame_compare.services.alignment._cross_correlate")
def test_align_clips_partial_cache_hit_computes_only_missing_and_preserves_order(
    mock_corr: MagicMock, mock_extract: MagicMock, mock_probe: MagicMock, tmp_path: Path
):
    """Test partial cache hit behavior and result ordering."""
    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    # Cache only comp_a
    cache_file = tmp_path / "audio_offsets.toml"
    data = {
        "version": "1",
        "ref:comp_a": {
            "reference_clip": "ref.mkv",
            "comparison_clip": "comp_a.mkv",
            "frame_offset": 10,
            "time_offset_seconds": 0.417,
            "correlation_score": 0.95,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_probe.return_value = Fraction(24, 1)
    # Return dummy arrays

    def extract_side_effect(path: Path, sr: int) -> np.ndarray:
        return np.ones(10, dtype=np.float32)

    mock_extract.side_effect = extract_side_effect
    mock_corr.return_value = (0, 0.99)

    config = AlignmentConfig()
    # Request comp_a and comp_b
    results = align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert len(results) == 2
    assert results[0].comparison_clip == "comp_a.mkv"
    assert results[0].frame_offset == 10  # from cache
    assert results[1].comparison_clip == "comp_b.mkv"
    assert results[1].frame_offset == 0  # from mock computation

    # Check that extract was called for ref and comp_b, but NOT comp_a
    called_paths = [call[0][0] for call in mock_extract.call_args_list]  # type: ignore
    assert ref in called_paths
    assert comp_b in called_paths
    assert comp_a not in called_paths
