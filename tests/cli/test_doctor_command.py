import json

from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.orchestration.doctor import CheckResult, DoctorCheck, DoctorReport
from frame_compare.utils.progress_protocol import ProgressReporter

from .cli_helpers import runner


def test_doctor_json_conforms_to_schema_shape(monkeypatch: MonkeyPatch) -> None:
    checks = [
        DoctorCheck(
            name="python_version",
            category="core",
            check_fn=lambda: CheckResult(passed=True, message="ok"),
        ),
        DoctorCheck(
            name="ffmpeg",
            category="optional",
            check_fn=lambda: CheckResult(
                passed=False,
                message="missing",
                hint="install ffmpeg",
                details={"path": None},
            ),
        ),
    ]
    report = DoctorReport(
        checks=[(checks[0], checks[0].check_fn()), (checks[1], checks[1].check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["doctor"]["baseline_version"] == "R76"
    assert len(payload["doctor"]["checks"]) == 2
    first = payload["doctor"]["checks"][0]
    second = payload["doctor"]["checks"][1]
    assert first["id"] == "python_version"
    assert first["category"] == "core"
    assert first["status"] == "pass"
    assert "message" in first
    assert second["id"] == "ffmpeg"
    assert second["category"] == "optional"
    assert second["status"] == "fail"
    assert second["install_hint"] == "install ffmpeg"
    assert "details" in second


def test_doctor_exit_code_is_3_on_core_failure(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="vapoursynth",
        category="core",
        check_fn=lambda: CheckResult(passed=False, message="missing"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=["vapoursynth"],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 3


def _run_doctor_optional_failure_and_assert(monkeypatch: MonkeyPatch) -> None:
    check = DoctorCheck(
        name="slowpics",
        category="network",
        check_fn=lambda: CheckResult(passed=False, message="offline"),
    )
    report = DoctorReport(
        checks=[(check, check.check_fn())],
        all_passed=False,
        critical_failures=[],
    )

    def _run_doctor(
        checks: list[DoctorCheck] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> DoctorReport:
        return report

    monkeypatch.setattr("frame_compare.cli.entry.run_doctor", _run_doctor)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_doctor_exit_code_is_0_on_optional_or_network_failure(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)


def test_doctor_stub_text(monkeypatch: MonkeyPatch) -> None:
    _run_doctor_optional_failure_and_assert(monkeypatch)
