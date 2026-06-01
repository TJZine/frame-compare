"""Audio alignment workflow VSPreview orchestration tests."""

import io
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from frame_compare.services.alignment import align_clips
from frame_compare.services.alignment_cache import save_offsets_cache
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewSessionRequest,
)
from frame_compare.vspreview.errors import VSPreviewError
from frame_compare.vspreview.overrides import load_manual_overrides


def _write_cached_offset(
    workspace: Path,
    *,
    reference: Path,
    comparison: Path,
    frame_offset: int,
    time_offset_seconds: float,
) -> None:
    save_offsets_cache(
        workspace,
        reference=reference,
        comparisons=[comparison],
        sample_rate=8000,
        max_offset_seconds=30.0,
        results=[
            AlignmentResult(
                reference_clip=reference.name,
                comparison_clip=comparison.name,
                frame_offset=frame_offset,
                time_offset_seconds=time_offset_seconds,
                correlation_score=0.95,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )


def _set_interactive_terminal(monkeypatch: pytest.MonkeyPatch, user_input: str) -> None:
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(user_input))
    monkeypatch.setattr(
        "frame_compare.services.alignment_vspreview._current_tty_status",
        lambda: SimpleNamespace(stdin=True, stdout=True, stderr=True),
    )


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_launches_vspreview_when_enabled(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """When configured, align_clips should generate/launch a VSPreview verification session."""
    _set_interactive_terminal(monkeypatch, "skip\n")

    ref = tmp_path / "ref.mkv"
    comp_a = tmp_path / "comp_a.mkv"
    comp_b = tmp_path / "comp_b.mkv"
    ref.touch()
    comp_a.touch()
    comp_b.touch()

    mock_probe.return_value = Fraction(24, 1)
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(0, 0.99, True, "accepted", 1, 1, 1.0, 2.0)
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
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_align_clips_rejected_computed_result_passes_none_hint_to_vspreview(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_interactive_terminal(monkeypatch, "skip\n")

    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    mock_probe.return_value = Fraction(24, 1)
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(
        None,
        0.2,
        False,
        "low_confidence",
        1,
        1,
        1.0,
        1.0,
    )
    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    results = align_clips(
        ref,
        [comp],
        AlignmentConfig(enable=True, use_vspreview=True, cache_results=False),
        tmp_path,
    )

    assert len(results) == 1
    assert results[0].applied is False
    assert results[0].frame_offset is None
    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    request = kwargs["request"]
    assert isinstance(request, VSPreviewSessionRequest)
    assert request.suggested_offsets_by_key == {"ref:comp": None}
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
def test_align_clips_full_cache_hit_still_launches_vspreview_when_enabled(
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached/manual-only runs should still build/launch VSPreview verification."""
    _set_interactive_terminal(monkeypatch, "skip\n")

    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=12,
        time_offset_seconds=0.5,
    )

    mock_probe.side_effect = AssertionError("should not be called")
    mock_extract_reference.side_effect = AssertionError("should not be called")
    mock_extract_matching.side_effect = AssertionError("should not be called")
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
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=2,
        time_offset_seconds=0.083,
    )

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
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=7,
        time_offset_seconds=0.292,
    )

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


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
@pytest.mark.parametrize(
    ("user_input", "expected_offset"),
    [
        ("120 108\n", 12),
        ("108 120\n", -12),
    ],
)
def test_align_clips_vspreview_confirmed_offset_is_saved_and_applied(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    user_input: str,
    expected_offset: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_interactive_terminal(monkeypatch, user_input)

    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()

    mock_probe.return_value = Fraction(24, 1)
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.return_value = AlignmentConsensus(3, 0.99, True, "accepted", 1, 1, 1.0, 2.0)
    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    results = align_clips(
        ref,
        [comp],
        AlignmentConfig(enable=True, use_vspreview=True, cache_results=False),
        tmp_path,
    )

    assert results[0].frame_offset == expected_offset
    assert results[0].source == "manual"
    manual_overrides = load_manual_overrides(tmp_path)
    assert manual_overrides["ref:comp"].frame_offset == expected_offset


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
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=7,
        time_offset_seconds=0.292,
    )

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
    _set_interactive_terminal(monkeypatch, "skip\n")

    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=3,
        time_offset_seconds=0.125,
    )

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
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=3,
        time_offset_seconds=0.125,
    )

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
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=1,
        time_offset_seconds=0.042,
    )

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adapter launch failures should fail-fast in force-interactive mode."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_cached_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=1,
        time_offset_seconds=0.042,
    )

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
