"""Unit tests for VSPreview integration module.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
All external dependencies are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from frame_compare.vspreview.adapter import (
    VSPreviewAvailabilityStatus,
    check_vspreview_availability,
)


class TestCheckVspreviewAvailability:
    """Tests for check_vspreview_availability() function."""

    def test_check_vspreview_availability_returns_available_when_executable_in_path(self) -> None:
        """Availability check returns AVAILABLE when vspreview executable exists."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/vspreview"

            result = check_vspreview_availability()

            assert result.is_available is True
            assert result.status == VSPreviewAvailabilityStatus.AVAILABLE
            mock_which.assert_called_once_with("vspreview")

    def test_check_vspreview_availability_returns_available_when_importable(self) -> None:
        """Availability check returns AVAILABLE when vspreview module + Qt backend importable."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None  # No executable
            # Mock find_spec to return non-None for vspreview and PyQt6
            mock_find_spec.side_effect = (
                lambda name: MagicMock() if name in ("vspreview", "PyQt6") else None
            )

            result = check_vspreview_availability()

            assert result.is_available is True
            assert result.status == VSPreviewAvailabilityStatus.AVAILABLE

    def test_check_vspreview_availability_returns_available_with_pyqt5_backend(self) -> None:
        """Availability check returns AVAILABLE with PyQt5 as Qt backend."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None

            # vspreview importable, PyQt6/PySide6 missing, PyQt5 available
            def find_spec_side_effect(name: str) -> MagicMock | None:
                if name == "vspreview":
                    return MagicMock()
                if name == "PyQt5":
                    return MagicMock()
                return None

            mock_find_spec.side_effect = find_spec_side_effect

            result = check_vspreview_availability()

            assert result.is_available is True
            assert result.status == VSPreviewAvailabilityStatus.AVAILABLE

    def test_check_vspreview_availability_returns_missing_when_missing(self) -> None:
        """Availability check returns MISSING_EXEC_AND_MODULE when vspreview not found."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None
            mock_find_spec.return_value = None  # Nothing importable

            result = check_vspreview_availability()

            assert result.is_available is False
            assert result.status == VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE

    def test_check_vspreview_availability_returns_missing_qt_when_no_qt_backend(self) -> None:
        """Availability check returns MISSING_QT_BACKEND when vspreview importable but no Qt."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec") as mock_find_spec,
        ):
            mock_which.return_value = None

            # vspreview is importable, but no Qt backends
            def find_spec_side_effect(name: str) -> MagicMock | None:
                if name == "vspreview":
                    return MagicMock()
                return None

            mock_find_spec.side_effect = find_spec_side_effect

            result = check_vspreview_availability()

            assert result.is_available is False
            assert result.status == VSPreviewAvailabilityStatus.MISSING_QT_BACKEND

    def test_check_vspreview_availability_returns_probe_failed_on_exception(self) -> None:
        """Availability check returns PROBE_FAILED when find_spec raises an exception."""
        with (
            patch("shutil.which") as mock_which,
            patch("importlib.util.find_spec", side_effect=ValueError("Unexpected import error")),
        ):
            mock_which.return_value = None

            result = check_vspreview_availability()

            assert result.is_available is False
            assert result.status == VSPreviewAvailabilityStatus.PROBE_FAILED
            assert result.error_details is not None
            assert result.error_details["exception_type"] == "ValueError"
            assert "Unexpected import error" in result.error_details["exception"]
