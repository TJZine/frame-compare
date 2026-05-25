"""Unit tests for diagnostic checks."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.orchestration.doctor import (
    CheckResult,
    DoctorCheck,
    collect_checks,
    run_doctor,
)


def _clear_tmdb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__ENABLED", raising=False)


class TestCheckLsmas:
    """Tests for lsmas plugin check via run_doctor."""

    def test_check_lsmas_plugin_passes_when_available(self) -> None:
        """Mock vs core with lsmas namespace → check passes."""
        mock_core = MagicMock()
        mock_core.lsmas = MagicMock()
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch.dict(sys.modules, {"vapoursynth": mock_vs}):
            result = lsmas_check.check_fn()

        assert result.passed is True
        assert "L-SMASH-Works" in result.message

    def test_check_lsmas_plugin_fails_when_missing(self) -> None:
        """Mock missing plugin → check fails."""
        mock_core = object()
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch.dict(sys.modules, {"vapoursynth": mock_vs}):
            result = lsmas_check.check_fn()

        assert result.passed is False

    def test_check_lsmas_plugin_fallback_loads_from_plugin_path(self) -> None:
        """If autoload misses lsmas, fallback LoadPlugin path should recover."""

        class _Core:
            pass

        class _Std:
            pass

        mock_core = _Core()
        mock_std = _Std()

        def _load_plugin(*, path: str) -> None:
            mock_core.lsmas = MagicMock()

        mock_std.LoadPlugin = _load_plugin
        mock_core.std = mock_std
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with (
            patch.dict(sys.modules, {"vapoursynth": mock_vs}),
            patch(
                "frame_compare.vs.env.candidate_lsmas_plugin_paths",
                return_value=["C:/bundle/vs/plugins/libvslsmashsource.dll"],
            ),
            patch("os.path.isfile", return_value=True),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is True
        assert result.details.get("plugin_path") == "C:/bundle/vs/plugins/libvslsmashsource.dll"

    def test_check_lsmas_failure_included_in_critical_failures(self) -> None:
        """Mock lsmas core failure → DoctorReport.critical_failures includes 'lsmas'."""
        lsmas_check = DoctorCheck(
            name="lsmas",
            category="core",
            check_fn=lambda: CheckResult(passed=False, message="L-SMASH-Works not found"),
        )

        report = run_doctor(checks=[lsmas_check])

        assert report.all_passed is False
        assert "lsmas" in report.critical_failures


class TestCheckPythonVersion:
    """Tests for python_version check via run_doctor."""

    def test_check_python_version_passes(self) -> None:
        """Mock sys.version_info to (3, 13, 0) → check passes."""
        checks = collect_checks()
        python_check = next(c for c in checks if c.name == "python_version")

        with patch.object(sys, "version_info", (3, 13, 0)):
            result = python_check.check_fn()

        assert result.passed is True
        assert "3.13" in result.message

    def test_check_python_version_fails(self) -> None:
        """Mock sys.version_info to (3, 12, 0) → check fails with hint."""
        checks = collect_checks()
        python_check = next(c for c in checks if c.name == "python_version")

        with patch.object(sys, "version_info", (3, 12, 0)):
            result = python_check.check_fn()

        assert result.passed is False
        assert "3.12" in result.message
        assert result.hint is not None
        assert "3.13" in result.hint


class TestCheckVapoursynth:
    """Tests for vapoursynth check via run_doctor."""

    def test_check_vapoursynth_passes_when_available(self) -> None:
        """Mock successful VS import → check passes."""
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")

        mock_vs = MagicMock()
        with patch.dict(sys.modules, {"vapoursynth": mock_vs}):
            result = vs_check.check_fn()

        assert result.passed is True
        assert "VapourSynth available" in result.message

    def test_check_vapoursynth_fails_when_missing(self) -> None:
        """Mock ImportError on VS import → check fails."""
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")

        with patch("builtins.__import__", side_effect=ImportError("No module")):
            result = vs_check.check_fn()

        assert result.passed is False
        assert "not found" in result.message

    def test_check_vapoursynth_registers_runtime_dirs_before_import(self) -> None:
        """Ensure runtime DLL path registration runs as an import fallback."""
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")

        original_import = __import__
        mock_vs = MagicMock()
        vs_attempts = {"count": 0}

        def _fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "vapoursynth":
                vs_attempts["count"] += 1
                if vs_attempts["count"] == 1:
                    raise ImportError("missing runtime DLL")
                return mock_vs
            return original_import(name, *args, **kwargs)

        with (
            patch("frame_compare.vs.env.register_windows_dll_dirs") as register_dirs,
            patch("builtins.__import__", side_effect=_fake_import),
        ):
            result = vs_check.check_fn()

        register_dirs.assert_called_once()
        assert vs_attempts["count"] == 2
        assert result.passed is True


class TestCheckFFmpeg:
    """Tests for ffmpeg check via run_doctor."""

    def test_check_ffmpeg_passes_when_in_path(self) -> None:
        """Mock shutil.which("ffmpeg") returns path → check passes."""
        checks = collect_checks()
        ffmpeg_check = next(c for c in checks if c.name == "ffmpeg")

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = ffmpeg_check.check_fn()

        assert result.passed is True
        assert "/usr/bin/ffmpeg" in result.message

    def test_check_ffmpeg_fails_when_missing(self) -> None:
        """Mock shutil.which("ffmpeg") returns None → check fails."""
        checks = collect_checks()
        ffmpeg_check = next(c for c in checks if c.name == "ffmpeg")

        with patch("shutil.which", return_value=None):
            result = ffmpeg_check.check_fn()

        assert result.passed is False
        assert "not found" in result.message
