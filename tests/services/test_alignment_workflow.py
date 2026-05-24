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
from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewSessionRequest,
)
from frame_compare.vspreview.errors import VSPreviewError


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


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
@patch("frame_compare.services.alignment._cross_correlate")
def test_align_clips_launches_vspreview_when_enabled(
    mock_corr: MagicMock,
    mock_extract: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """When configured, align_clips should generate/launch a VSPreview verification session."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    mock_probe.return_value = Fraction(24, 1)

    def extract_side_effect(path: Path, sr: int) -> np.ndarray:
        return np.ones(10, dtype=np.float32)

    mock_extract.side_effect = extract_side_effect
    mock_corr.return_value = (0, 0.99)
    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=False)
    align_clips(ref, [comp_a, comp_b], config, tmp_path)

    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    request = kwargs["request"]
    assert isinstance(request, VSPreviewSessionRequest)
    assert request.reference == ref
    assert request.comparisons == [comp_a, comp_b]
    suggested = request.suggested_offsets_by_key
    assert suggested == {"ref:comp_a": 0, "ref:comp_b": 0}
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_audio")
def test_align_clips_full_cache_hit_still_launches_vspreview_when_enabled(
    mock_extract: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached/manual-only runs should still build/launch VSPreview verification."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

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
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_probe.side_effect = AssertionError("should not be called")
    mock_extract.side_effect = AssertionError("should not be called")
    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 12
    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    request = kwargs["request"]
    assert isinstance(request, VSPreviewSessionRequest)
    assert request.suggested_offsets_by_key == {"ref:comp": 12}
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_force_interactive_raises_when_vspreview_unavailable(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Force-interactive mode must fail fast if VSPreview is unavailable."""
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
            "frame_offset": 2,
            "time_offset_seconds": 0.083,
            "correlation_score": 0.98,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE,
        message="missing",
    )

    config = AlignmentConfig(
        enable=True,
        use_vspreview=True,
        force_interactive=True,
        cache_results=True,
    )
    with pytest.raises(AudioAlignmentError, match="Interactive alignment requested"):
        align_clips(ref, [comp], config, tmp_path)

    mock_launch.assert_not_called()


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_vspreview_unavailable_generates_script_without_launch(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """When optional VSPreview is unavailable, adapter should be called with enabled=False."""
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
            "frame_offset": 7,
            "time_offset_seconds": 0.292,
            "correlation_score": 0.96,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE,
        message="missing",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    align_clips(ref, [comp], config, tmp_path)

    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["config"].enabled is False


@patch("frame_compare.services.alignment_vspreview.log.warning")
@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_optional_vspreview_probe_failure_generates_script_without_launch(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    mock_warn: MagicMock,
    tmp_path: Path,
) -> None:
    """Optional VSPreview probe failures should be visible but non-fatal."""
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
            "frame_offset": 7,
            "time_offset_seconds": 0.292,
            "correlation_score": 0.96,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.PROBE_FAILED,
        message="VSPreview availability probe failed",
        error_details={"exception_type": "RuntimeError", "exception": "broken import metadata"},
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 7
    mock_warn.assert_called_once()
    warn_args, warn_kwargs = mock_warn.call_args
    assert warn_args == ("vspreview_availability_probe_failed",)
    assert warn_kwargs["reason"] == "availability probe failed (RuntimeError)"
    assert warn_kwargs["exception_type"] == "RuntimeError"
    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert launch_kwargs["config"].enabled is False


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_force_interactive_launches_when_vspreview_available(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force-interactive mode should launch VSPreview when available."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

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
            "frame_offset": 3,
            "time_offset_seconds": 0.125,
            "correlation_score": 0.99,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(
        enable=True,
        use_vspreview=False,
        force_interactive=True,
        cache_results=True,
    )
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 3
    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_force_interactive_probe_failure_raises_alignment_error(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Forced interactive mode should fail deliberately when availability cannot be checked."""
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
            "frame_offset": 3,
            "time_offset_seconds": 0.125,
            "correlation_score": 0.99,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.PROBE_FAILED,
        message="VSPreview availability probe failed",
        error_details={"exception_type": "RuntimeError", "exception": "broken import metadata"},
    )

    config = AlignmentConfig(
        enable=True,
        use_vspreview=False,
        force_interactive=True,
        cache_results=True,
    )
    with pytest.raises(AudioAlignmentError, match=r"availability probe failed \(RuntimeError\)"):
        align_clips(ref, [comp], config, tmp_path)

    mock_launch.assert_not_called()


@patch("frame_compare.services.alignment_vspreview.log.warning")
@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_vspreview_errors_are_warning_only_when_not_forced(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    mock_warn: MagicMock,
    tmp_path: Path,
) -> None:
    """Adapter launch failures are warning-only for optional VSPreview mode."""
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
            "frame_offset": 1,
            "time_offset_seconds": 0.042,
            "correlation_score": 0.91,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.side_effect = VSPreviewError("launch exited with code 7")

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = align_clips(ref, [comp], config, tmp_path)

    assert len(results) == 1
    assert results[0].frame_offset == 1
    mock_warn.assert_called_once()
    _, kwargs = mock_warn.call_args
    assert kwargs["reason"] == "VSPreview failed: launch exited with code 7"
    assert kwargs["code"] == "FC-4019"
    assert kwargs["force_interactive"] is False


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_align_clips_vspreview_errors_raise_when_force_interactive(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Adapter launch failures should fail-fast in force-interactive mode."""
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
            "frame_offset": 1,
            "time_offset_seconds": 0.042,
            "correlation_score": 0.91,
            "algorithm": "cross_correlation",
        },
    }
    with cache_file.open("wb") as f:
        f.write(tomli_w.dumps(data).encode("utf-8"))

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.side_effect = VSPreviewError("launch exited with code 7")

    config = AlignmentConfig(
        enable=True,
        use_vspreview=False,
        force_interactive=True,
        cache_results=True,
    )
    with pytest.raises(VSPreviewError, match="launch exited with code 7"):
        align_clips(ref, [comp], config, tmp_path)
