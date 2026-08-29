"""Audio alignment workflow VSPreview orchestration tests."""

import io
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewSessionRequest,
)
from frame_compare.vspreview.errors import VSPreviewError
from frame_compare.vspreview.overrides import (
    ManualOverride,
    load_manual_overrides,
    save_manual_override,
)
from tests.services.alignment_request_test_support import alignment_request


def _run_alignment(
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    generated_dir: Path,
    *,
    reference_fps: Fraction | None = None,
) -> list[AlignmentResult]:
    request = alignment_request(
        reference=reference,
        comparisons=comparisons,
        config=config,
        generated_dir=generated_dir,
    )
    return align_clips_from_request(
        request,
        config,
        reference_fps=reference_fps,
    )


def _write_manual_override_offset(
    workspace: Path,
    *,
    reference: Path,
    comparison: Path,
    frame_offset: int,
) -> None:
    save_manual_override(
        workspace,
        ManualOverride(
            reference_clip=reference.stem,
            comparison_clip=comparison.stem,
            frame_offset=frame_offset,
            timestamp="2026-06-07T00:00:00Z",
            confirmed=True,
        ),
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
def test_alignment_launches_vspreview_when_enabled(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """When configured, alignment should generate/launch a VSPreview verification session."""
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
    _run_alignment(ref, [comp_a, comp_b], config, tmp_path)

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
def test_alignment_rejected_computed_result_passes_none_hint_to_vspreview(
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

    results = _run_alignment(
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
def test_alignment_full_manual_override_still_launches_vspreview_when_enabled(
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual-only runs should still build/launch VSPreview verification."""
    _set_interactive_terminal(monkeypatch, "skip\n")

    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=12,
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
    results = _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

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
def test_alignment_force_interactive_raises_when_vspreview_unavailable(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Force-interactive mode must fail fast if VSPreview is unavailable."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=2,
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
        _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

    mock_launch.assert_not_called()


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_alignment_vspreview_unavailable_generates_script_without_launch(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """When optional VSPreview is unavailable, adapter should be called with enabled=False."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=7,
    )

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE,
        message="missing",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

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
def test_alignment_vspreview_confirmed_offset_is_saved_and_applied(
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

    results = _run_alignment(
        ref,
        [comp],
        AlignmentConfig(enable=True, use_vspreview=True, cache_results=False),
        tmp_path,
    )

    assert results[0].frame_offset == expected_offset
    assert results[0].source == "manual"
    manual_overrides = load_manual_overrides(tmp_path)
    assert manual_overrides["ref:comp"].frame_offset == expected_offset


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
@patch("frame_compare.services.alignment._probe_fps")
@patch("frame_compare.services.alignment._extract_matching_audio")
@patch("frame_compare.services.alignment._extract_reference_audio")
@patch("frame_compare.services.alignment._estimate_consensus_offset")
def test_alignment_vspreview_confirm_skip_confirm_keeps_prior_and_later_offsets(
    mock_estimate: MagicMock,
    mock_extract_reference: MagicMock,
    mock_extract_matching: MagicMock,
    mock_probe: MagicMock,
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_interactive_terminal(monkeypatch, "120 108\nskip\n210 216\n")

    ref = tmp_path / "ref.mkv"
    zeta = tmp_path / "zeta.mkv"
    alpha = tmp_path / "alpha.mkv"
    mid = tmp_path / "mid.mkv"
    for path in (ref, zeta, alpha, mid):
        path.touch()

    mock_probe.return_value = Fraction(24, 1)
    mock_extract_reference.return_value = (np.ones(10, dtype=np.float32), object())
    mock_extract_matching.return_value = np.ones(10, dtype=np.float32)
    mock_estimate.side_effect = [
        AlignmentConsensus(4, 0.99, True, "accepted", 1, 1, 1.0, 2.0),
        AlignmentConsensus(2667, 0.98, True, "accepted", 1, 1, 1.0, 2.0),
        AlignmentConsensus(-2, 0.97, True, "accepted", 1, 1, 1.0, 2.0),
    ]
    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    results = _run_alignment(
        ref,
        [zeta, alpha, mid],
        AlignmentConfig(enable=True, use_vspreview=True, cache_results=False),
        tmp_path,
    )

    assert [result.comparison_clip for result in results] == ["zeta.mkv", "alpha.mkv", "mid.mkv"]
    assert [result.frame_offset for result in results] == [12, 8, -6]
    assert [result.source for result in results] == ["manual", "computed", "manual"]
    manual_overrides = load_manual_overrides(tmp_path)
    assert set(manual_overrides) == {"ref:zeta", "ref:mid"}
    assert manual_overrides["ref:zeta"].frame_offset == 12
    assert manual_overrides["ref:mid"].frame_offset == -6


@patch("frame_compare.services.alignment_vspreview.log.warning")
@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_alignment_optional_vspreview_probe_failure_generates_script_without_launch(
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
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=7,
    )

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.PROBE_FAILED,
        message="VSPreview availability probe failed",
        error_details={"exception_type": "RuntimeError", "exception": "broken import metadata"},
    )
    mock_launch.return_value = tmp_path / "vspreview_script.py"

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

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
def test_alignment_force_interactive_launches_when_vspreview_available(
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
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=3,
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
    results = _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

    assert len(results) == 1
    assert results[0].frame_offset == 3
    assert mock_launch.call_count == 1
    _, kwargs = mock_launch.call_args
    assert kwargs["config"].enabled is True


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_alignment_force_interactive_probe_failure_raises_alignment_error(
    mock_check_availability: MagicMock,
    mock_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """Forced interactive mode should fail deliberately when availability cannot be checked."""
    ref = tmp_path / "ref.mkv"
    comp = tmp_path / "comp.mkv"
    ref.touch()
    comp.touch()
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=3,
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
        _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

    mock_launch.assert_not_called()


@patch("frame_compare.services.alignment_vspreview.log.warning")
@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_alignment_vspreview_errors_are_warning_only_when_not_forced(
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
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=1,
    )

    mock_check_availability.return_value = VSPreviewAvailability(
        status=VSPreviewAvailabilityStatus.AVAILABLE,
        message="available",
    )
    mock_launch.side_effect = VSPreviewError("launch exited with code 7")

    config = AlignmentConfig(enable=True, use_vspreview=True, cache_results=True)
    results = _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))

    assert len(results) == 1
    assert results[0].frame_offset == 1
    mock_warn.assert_called_once()
    _, kwargs = mock_warn.call_args
    assert kwargs["reason"] == "VSPreview failed: launch exited with code 7"
    assert kwargs["code"] == "FC-4019"
    assert kwargs["force_interactive"] is False


@patch("frame_compare.services.alignment_vspreview.launch_alignment_verification_session")
@patch("frame_compare.services.alignment_vspreview.check_vspreview_availability")
def test_alignment_vspreview_errors_raise_when_force_interactive(
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
    _write_manual_override_offset(
        tmp_path,
        reference=ref,
        comparison=comp,
        frame_offset=1,
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
        _run_alignment(ref, [comp], config, tmp_path, reference_fps=Fraction(24, 1))
