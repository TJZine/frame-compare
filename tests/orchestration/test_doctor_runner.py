"""Unit tests for diagnostic checks."""

from __future__ import annotations

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
            name="vapoursynth",
            category="core",
            check_fn=lambda: CheckResult(passed=False, message="Failed"),
        )

        report = run_doctor(checks=[failing_check])

        assert report.all_passed is False
        assert "vapoursynth" in report.critical_failures

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


def test_run_doctor_survives_raising_check() -> None:
    def _boom() -> CheckResult:
        raise RuntimeError("secret path /private/boom")

    checks = [DoctorCheck(name="boom", category="optional", check_fn=_boom)]

    report = run_doctor(checks=checks)

    assert len(report.checks) == 1
    _, result = report.checks[0]
    assert result.passed is False
    assert result.message == "boom check failed"
    assert "secret path" not in result.message
    assert result.details == {"exception_type": "RuntimeError"}


class TestCollectChecks:
    """Tests for collect_checks function."""

    def test_collect_checks_returns_all_categories(self) -> None:
        """collect_checks() returns checks with core, optional, network categories."""
        checks = collect_checks()

        categories = {check.category for check in checks}
        assert "core" in categories
        assert "optional" in categories
        assert "network" in categories

        # Verify exact count and order for the current doctor contract.
        assert [check.name for check in checks] == [
            "vapoursynth",
            "lsmas",
            "vs_placebo",
            "ffms2",
            "ffmpeg",
            "vsview",
            "slowpics",
            "tmdb_api_key",
        ]
        assert checks[0].category == "core"
        assert checks[-1].category == "network"


class TestCheckVSView:
    """Tests for the optional VSView diagnostic check."""

    def test_check_vsview_probe_failure_is_optional_status(self) -> None:
        from frame_compare.vsview.adapter import (
            VSViewAvailability,
            VSViewAvailabilityStatus,
        )

        checks = collect_checks()
        vsview_check = next(c for c in checks if c.name == "vsview")

        with patch(
            "frame_compare.vsview.adapter.check_vsview_availability",
            return_value=VSViewAvailability(
                status=VSViewAvailabilityStatus.PROBE_FAILED,
                message="VSView availability probe failed",
                error_details={
                    "exception_type": "RuntimeError",
                    "exception": "broken import metadata",
                },
            ),
        ):
            result = vsview_check.check_fn()

        assert result.passed is True
        assert "probe failed" in result.message
        assert result.details == {"exception_type": "RuntimeError"}
