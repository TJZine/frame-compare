"""Direct tests for alignment VSPreview launch policy."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vspreview as alignment_vspreview
from frame_compare.services.alignment_vspreview import maybe_launch_alignment_vspreview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewSessionRequest,
)
from frame_compare.vspreview.errors import VSPreviewError


def _call_maybe_launch(
    *,
    tmp_path: Path,
    config: AlignmentConfig,
) -> None:
    maybe_launch_alignment_vspreview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=config,
        progress=None,
    )


def _set_tty(monkeypatch: pytest.MonkeyPatch, is_tty: bool) -> None:
    monkeypatch.setattr(
        alignment_vspreview,
        "_current_tty_status",
        lambda: alignment_vspreview._TTYStatus(
            stdin=is_tty,
            stdout=is_tty,
            stderr=is_tty,
        ),
    )


def _availability(status: VSPreviewAvailabilityStatus) -> VSPreviewAvailability:
    if status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        return VSPreviewAvailability(
            status=status,
            message="probe failed",
            hint="check install",
            error_details={"exception_type": "RuntimeError", "exception": "raw detail"},
        )
    return VSPreviewAvailability(
        status=status,
        message=status.value,
        hint="install VSPreview",
    )


def test_disabled_config_returns_without_availability_or_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(side_effect=AssertionError("availability should not be checked")),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=AssertionError("VSPreview should not launch")),
    )

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=False))


def test_force_interactive_unavailable_raises_without_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(
            return_value=_availability(VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE),
        ),
    )
    mock_launch = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)

    with pytest.raises(AudioAlignmentError, match="VSPreview is not available"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vspreview=True, force_interactive=True),
        )

    mock_launch.assert_not_called()


@pytest.mark.parametrize(
    ("status", "expected_warning"),
    [
        (VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE, "vspreview_unavailable"),
        (VSPreviewAvailabilityStatus.PROBE_FAILED, "vspreview_availability_probe_failed"),
    ],
)
def test_optional_unavailable_generates_script_without_launch_and_logs_warning(
    status: VSPreviewAvailabilityStatus,
    expected_warning: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(status)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vspreview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert isinstance(launch_kwargs["request"], VSPreviewSessionRequest)
    assert launch_kwargs["config"].enabled is False
    warning_args, warning_kwargs = mock_warning.call_args_list[0]
    assert warning_args == (expected_warning,)
    assert warning_kwargs["hint"] in {"install VSPreview", "check install"}
    if status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        assert warning_kwargs["reason"] == "availability probe failed (RuntimeError)"
        assert warning_kwargs["exception_type"] == "RuntimeError"


def test_available_without_tty_generates_script_disabled_and_logs_no_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=False)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vspreview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert isinstance(launch_kwargs["request"], VSPreviewSessionRequest)
    assert launch_kwargs["config"].enabled is False
    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vspreview_no_tty",)
    assert warning_kwargs["stdin_tty"] is False
    assert warning_kwargs["stdout_tty"] is False
    assert warning_kwargs["stderr_tty"] is False


def test_optional_launch_error_logs_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSPreviewError("launch exited with code 7")),
    )
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vspreview_optional_launch_failed",)
    assert warning_kwargs["reason"] == "VSPreview failed: launch exited with code 7"
    assert warning_kwargs["code"] == "FC-4019"


def test_forced_launch_error_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSPreviewError("launch exited with code 7")),
    )

    with pytest.raises(VSPreviewError, match="launch exited with code 7"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vspreview=False, force_interactive=True),
        )
