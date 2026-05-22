"""Unit tests for diagnostic checks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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

        with (
            patch("frame_compare.orchestration.doctor.register_windows_dll_dirs") as register_dirs,
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
                "frame_compare.orchestration.doctor._candidate_lsmas_plugin_paths",
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


class TestCheckVSPreview:
    """Tests for the optional VSPreview diagnostic check."""

    def test_check_vspreview_probe_failure_is_optional_status(self) -> None:
        checks = collect_checks()
        vspreview_check = next(c for c in checks if c.name == "vspreview")

        with patch(
            "frame_compare.vspreview.adapter.is_vspreview_available",
            side_effect=RuntimeError("broken import metadata"),
        ):
            result = vspreview_check.check_fn()

        assert result.passed is True
        assert "probe failed" in result.message
        assert result.details["exception_type"] == "RuntimeError"
        assert result.details["exception"] == "broken import metadata"


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


def test_check_tmdb_api_key_passes_with_workspace_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TMDB check should honor config/config.toml discovered from the workspace cwd."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        """
        [tmdb]
        api_key = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        """,
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)

    result = tmdb_check.check_fn()

    assert result.passed is True
    assert result.message == "TMDB API key configured"


def test_check_tmdb_api_key_fails_with_malformed_workspace_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """File-backed TMDB keys should use the same format rule as runtime lookup."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        """
        [tmdb]
        api_key = "config_key"
        """,
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key has invalid format"
    assert result.hint is not None
    assert "32-character hexadecimal" in result.hint


def test_check_tmdb_api_key_fails_with_malformed_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-backed TMDB keys should use the same format rule as runtime lookup."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "not-a-valid-key")

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key has invalid format"
    assert result.hint is not None
    assert "32-character hexadecimal" in result.hint


def test_check_tmdb_api_key_legacy_alias_remains_warning_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy TMDB_API_KEY alone should fail with guidance to use the canonical path."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)

    monkeypatch.setenv("TMDB_API_KEY", "legacy_key")
    legacy_result = tmdb_check.check_fn()

    assert legacy_result.passed is False
    assert legacy_result.message == "TMDB API key configured via legacy variable"
    assert legacy_result.hint is not None
    assert "FRAME_COMPARE_TMDB__API_KEY" in legacy_result.hint
    assert "legacy" in legacy_result.hint.lower()


def test_check_tmdb_api_key_missing_mentions_workspace_config_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing TMDB config should point users at config/config.toml."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key not configured"
    assert result.hint is not None
    assert "tmdb.api_key in config/config.toml" in result.hint


def test_check_tmdb_api_key_enabled_without_key_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicitly enabled TMDB still requires credentials."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        """
        [tmdb]
        enabled = true
        """,
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key not configured"
    assert result.hint is not None
    assert "FRAME_COMPARE_TMDB__API_KEY" in result.hint


def test_check_tmdb_api_key_disabled_without_key_is_non_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disabled TMDB should not require credentials."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        """
        [tmdb]
        enabled = false
        """,
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)

    result = tmdb_check.check_fn()

    assert result.passed is True
    assert result.message == "TMDB metadata lookup disabled"
    assert result.hint is None
    assert result.details == {"enabled": False}


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
