"""Unit tests for diagnostic checks."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from frame_compare.orchestration.doctor import (
    CheckResult,
    DoctorCheck,
    collect_checks,
    run_doctor,
)


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

        with patch("frame_compare.orchestration.doctor._register_windows_dll_dirs") as register_dirs:
            with patch("builtins.__import__", side_effect=_fake_import):
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


def test_run_doctor_survives_raising_check() -> None:
    def _boom() -> CheckResult:
        raise RuntimeError("boom")

    checks = [DoctorCheck(name="boom", category="optional", check_fn=_boom)]

    report = run_doctor(checks=checks)

    assert len(report.checks) == 1
    _, result = report.checks[0]
    assert result.passed is False
    assert "boom check raised" in result.message
    assert result.details["exception_type"] == "RuntimeError"


class TestCheckSlowpics:
    """Tests for slow.pics reachability check via run_doctor."""

    def test_check_slowpics_uses_expected_url_and_timeout(self) -> None:
        """Mock httpx.Client.head and assert URL + timeout."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.head = MagicMock(return_value=mock_response)

        checks = collect_checks()
        slowpics_check = next(c for c in checks if c.name == "slowpics")

        with patch("httpx.Client", return_value=mock_client) as mock_client_cls:
            result = slowpics_check.check_fn()

        mock_client_cls.assert_called_once_with(timeout=5.0)
        mock_client.head.assert_called_once_with("https://slow.pics/")
        assert result.passed is True

    def test_check_slowpics_fails_on_http_error_status(self) -> None:
        """Mock response status 500 → check fails with hint."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.head = MagicMock(return_value=mock_response)

        checks = collect_checks()
        slowpics_check = next(c for c in checks if c.name == "slowpics")

        with patch("httpx.Client", return_value=mock_client):
            result = slowpics_check.check_fn()

        assert result.passed is False
        assert "500" in result.message
        assert result.hint is not None


class TestCollectChecks:
    """Tests for collect_checks function."""

    def test_collect_checks_returns_all_categories(self) -> None:
        """collect_checks() returns checks with core, optional, network categories."""
        checks = collect_checks()

        categories = {check.category for check in checks}
        assert "core" in categories
        assert "optional" in categories
        assert "network" in categories

        # Verify exact count and order per SSOT §4.2.1
        assert len(checks) == 8
        assert checks[0].name == "python_version"
        assert checks[0].category == "core"
        assert checks[-1].name == "tmdb_api_key"
        assert checks[-1].category == "network"


class TestRunDoctor:
    """Tests for run_doctor function."""

    def test_run_doctor_all_pass(self) -> None:
        """Given all mocked checks pass → DoctorReport(all_passed=True, critical_failures=[])."""
        passing_check = DoctorCheck(
            name="test_check",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="OK"),
        )

        report = run_doctor(checks=[passing_check])

        assert report.all_passed is True
        assert report.critical_failures == []

    def test_run_doctor_core_failure(self) -> None:
        """Given core check fails → DoctorReport(all_passed=False, critical_failures=[name])."""
        failing_check = DoctorCheck(
            name="python_version",
            category="core",
            check_fn=lambda: CheckResult(passed=False, message="Failed"),
        )

        report = run_doctor(checks=[failing_check])

        assert report.all_passed is False
        assert "python_version" in report.critical_failures

    def test_run_doctor_optional_failure_not_critical(self) -> None:
        """Given optional check fails but core passes → all_passed=False, critical_failures=[]."""
        core_check = DoctorCheck(
            name="vapoursynth",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="OK"),
        )
        optional_check = DoctorCheck(
            name="ffmpeg",
            category="optional",
            check_fn=lambda: CheckResult(passed=False, message="Missing"),
        )

        report = run_doctor(checks=[core_check, optional_check])

        assert report.all_passed is False  # Because ffmpeg failed
        assert report.critical_failures == []  # But no core failures

    def test_run_doctor_with_reporter(self) -> None:
        """Given mock ProgressReporter → asserts start_phase, advance, complete_phase called."""
        mock_reporter = MagicMock()
        check = DoctorCheck(
            name="test",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="OK"),
        )

        run_doctor(checks=[check], reporter=mock_reporter)

        mock_reporter.start_phase.assert_called_once_with("doctor", total=1)
        mock_reporter.advance.assert_called_once_with(1)
        mock_reporter.complete_phase.assert_called_once()
