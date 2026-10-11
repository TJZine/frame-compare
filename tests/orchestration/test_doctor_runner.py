"""Unit tests for diagnostic checks."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from frame_compare.orchestration.doctor import (
    CheckResult,
    DoctorCheck,
    collect_checks,
    run_doctor,
)
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus


@pytest.fixture(autouse=True)
def _clear_tmdb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__ENABLED", raising=False)


class TestRunDoctor:
    """Tests for run_doctor function."""

    @pytest.mark.parametrize(
        ("checks", "all_passed", "critical_failures"),
        [
            pytest.param(
                [
                    DoctorCheck(
                        name="test_check",
                        category="core",
                        check_fn=lambda: CheckResult(passed=True, message="OK"),
                    )
                ],
                True,
                [],
                id="all-pass",
            ),
            pytest.param(
                [
                    DoctorCheck(
                        name="vapoursynth",
                        category="core",
                        check_fn=lambda: CheckResult(passed=False, message="Failed"),
                    )
                ],
                False,
                ["vapoursynth"],
                id="core-failure",
            ),
            pytest.param(
                [
                    DoctorCheck(
                        name="vapoursynth",
                        category="core",
                        check_fn=lambda: CheckResult(passed=True, message="OK"),
                    ),
                    DoctorCheck(
                        name="ffmpeg",
                        category="optional",
                        check_fn=lambda: CheckResult(passed=False, message="Missing"),
                    ),
                ],
                False,
                [],
                id="optional-failure",
            ),
        ],
    )
    def test_run_doctor_outcomes(
        self, checks: list[DoctorCheck], all_passed: bool, critical_failures: list[str]
    ) -> None:
        report = run_doctor(checks=checks)
        assert report.all_passed is all_passed
        assert report.critical_failures == critical_failures


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


class TestCheckVSView:
    """Tests for the optional VSView diagnostic check."""

    @pytest.mark.parametrize(
        ("availability", "available", "message", "message_fragment", "hint", "details"),
        [
            pytest.param(
                VSViewAvailability(status=VSViewAvailabilityStatus.AVAILABLE, message="available"),
                True,
                "VSView and the Frame Compare alignment panel are available",
                False,
                None,
                None,
                id="reports_native_panel_readiness",
            ),
            pytest.param(
                VSViewAvailability(
                    status=VSViewAvailabilityStatus.MISSING_PLUGIN,
                    message="Frame Compare alignment panel is not installed for VSView",
                    hint="Reinstall frame-compare[vsview] in this environment",
                ),
                False,
                None,
                False,
                "Reinstall frame-compare[vsview] in this environment",
                None,
                id="reports_missing_native_panel",
            ),
            pytest.param(
                VSViewAvailability(
                    status=VSViewAvailabilityStatus.PROBE_FAILED,
                    message="VSView availability probe failed",
                    error_details={
                        "exception_type": "RuntimeError",
                        "exception": "broken import metadata",
                    },
                ),
                None,
                "probe failed",
                True,
                None,
                {"exception_type": "RuntimeError"},
                id="probe_failure_is_optional_status",
            ),
        ],
    )
    def test_check_vsview_status(
        self,
        availability: VSViewAvailability,
        available: bool | None,
        message: str | None,
        message_fragment: bool,
        hint: str | None,
        details: dict[str, str] | None,
    ) -> None:
        checks = collect_checks()
        vsview_check = next(c for c in checks if c.name == "vsview")
        with patch(
            "frame_compare.vsview.adapter.check_vsview_availability", return_value=availability
        ):
            result = vsview_check.check_fn()
        assert result.passed is True
        if available is not None:
            assert result.available is available
        if message is not None:
            if message_fragment:
                assert message in result.message
            else:
                assert result.message == message
        if hint is not None:
            assert result.hint == hint
        if details is not None:
            assert result.details == details
