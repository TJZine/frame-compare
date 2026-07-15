"""Unit tests for diagnostic checks."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import frame_compare.vs.env as env_module
from frame_compare.orchestration.doctor import (
    CheckResult,
    DoctorCheck,
    collect_checks,
    run_doctor,
)
from frame_compare.vs.env import PluginPathCandidate


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

        with (
            patch.dict(sys.modules, {"vapoursynth": mock_vs}),
            patch(
                "frame_compare.orchestration.doctor_checks.candidate_lsmas_plugin_path_details",
                return_value=[
                    PluginPathCandidate(
                        path="/opt/vs/plugins/libvslsmashsource.so",
                        source="vapoursynth.get_plugin_dir",
                    ),
                    PluginPathCandidate(
                        path="/bundle/vs/plugins/libvslsmashsource.so",
                        source="bundle_vs_plugins",
                    ),
                ],
            ),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.details["checked_plugin_paths"] == [
            {
                "source": "vapoursynth.get_plugin_dir",
                "path": "/opt/vs/plugins/libvslsmashsource.so",
            },
            {"source": "bundle_vs_plugins", "path": "/bundle/vs/plugins/libvslsmashsource.so"},
        ]
        assert result.hint == (
            "Make L-SMASH-Works available to VapourSynth; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        )
        assert "install" not in result.hint.lower()

    def test_check_lsmas_plugin_fallback_loads_from_nested_extra_plugin_root(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """If autoload misses lsmas, fallback loading should recover from nested extra-plugin dirs."""

        bundle_root = tmp_path / "bundle"
        python_dir = bundle_root / "python"
        python_dir.mkdir(parents=True)
        executable = python_dir / "python.exe"
        executable.write_text("")
        extra_root = bundle_root / "vs" / "extra-plugins"
        plugin_dir = extra_root / "lsmas"
        plugin_dir.mkdir(parents=True)
        plugin_path = plugin_dir / "libvslsmashsource.dll"
        plugin_path.write_text("")
        (plugin_dir / "manifest.vs").write_text("libvslsmashsource")

        monkeypatch.setattr(env_module.sys, "executable", str(executable))
        monkeypatch.setattr(env_module, "import_vapoursynth_module", lambda: SimpleNamespace())
        monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_root))
        monkeypatch.delenv("VAPOURSYNTH_PLUGIN_PATH", raising=False)

        load_calls: list[str] = []
        mock_core = SimpleNamespace()

        def _load_plugin(*, path: str) -> None:
            load_calls.append(path)
            mock_core.lsmas = MagicMock()

        mock_core.std = SimpleNamespace(LoadPlugin=_load_plugin)
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=mock_vs,
        ):
            result = lsmas_check.check_fn()

        assert result.passed is True
        assert result.details.get("plugin_path") == str(plugin_path)
        assert load_calls == [str(plugin_path)]

    def test_check_lsmas_failure_uses_sanitized_exception_details(self) -> None:
        """Unexpected lsmas errors should not expose raw exception text."""
        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            side_effect=RuntimeError("secret path /Users/example/private"),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.message == "lsmas check failed"
        assert result.hint == (
            "Check the VapourSynth/plugin setup, then rerun doctor; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        )
        assert result.details == {"exception_type": "RuntimeError"}

    def test_check_lsmas_when_vapoursynth_is_unavailable_points_to_runtime_setup(
        self,
    ) -> None:
        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            side_effect=ImportError("missing runtime"),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.message == "Cannot check lsmas (VapourSynth not available)"
        assert result.hint == (
            "Make VapourSynth importable before checking L-SMASH-Works; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        )

    def test_check_lsmas_import_error_after_runtime_import_is_setup_failure(self) -> None:
        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")
        mock_vs = SimpleNamespace(core=object())

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
                return_value=mock_vs,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.try_load_lsmas_plugin",
                side_effect=ImportError("plugin setup import failed"),
            ),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.message == "lsmas check failed"
        assert result.details == {"exception_type": "ImportError"}
        assert "plugin setup import failed" not in str(result.details)

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
        assert result.hint == (
            "Run Frame Compare with Python 3.13+; see "
            "https://github.com/TJZine/frame-compare#requirements"
        )


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
        assert result.hint == (
            "Make VapourSynth importable; see https://github.com/TJZine/frame-compare#quick-start"
        )
        assert "pip install" not in result.hint

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
        assert result.hint == (
            "Provide an FFmpeg executable on PATH; see "
            "https://github.com/TJZine/frame-compare#requirements"
        )
        assert all(
            command not in result.hint.lower()
            for command in ("apt ", "brew ", "choco ", "pip ", "winget ")
        )
