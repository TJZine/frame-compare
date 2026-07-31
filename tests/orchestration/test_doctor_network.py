"""Unit tests for diagnostic checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from frame_compare.orchestration.doctor import (
    collect_checks,
)


def _clear_tmdb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__ENABLED", raising=False)


def test_check_tmdb_api_key_fails_with_malformed_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-backed TMDB keys should use the same format rule as runtime lookup."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    monkeypatch.chdir(tmp_path)
    _clear_tmdb_env(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "not-a-valid-key")

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key has invalid format"
    assert result.hint == ("Replace the TMDB credential with a 32-character hexadecimal API key")


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

    @pytest.mark.parametrize("status_code", [404, 500])
    def test_check_slowpics_fails_on_http_error_status(self, status_code: int) -> None:
        mock_response = MagicMock()
        mock_response.status_code = status_code

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.head = MagicMock(return_value=mock_response)

        checks = collect_checks()
        slowpics_check = next(c for c in checks if c.name == "slowpics")

        with patch("httpx.Client", return_value=mock_client):
            result = slowpics_check.check_fn()

        assert result.passed is False
        assert str(status_code) in result.message
        assert result.hint == "Review the returned HTTP status before retrying"

    def test_check_slowpics_timeout_has_timeout_specific_next_action(self) -> None:
        slowpics_check = next(c for c in collect_checks() if c.name == "slowpics")

        with patch("httpx.Client", side_effect=httpx.ReadTimeout("timed out")):
            result = slowpics_check.check_fn()

        assert result.passed is False
        assert result.message == "slow.pics connection timed out"
        assert result.hint == "Check network access to slow.pics, then retry"
        assert result.details == {"timeout": 5.0}

    def test_check_slowpics_request_failure_has_transport_specific_next_action(self) -> None:
        slowpics_check = next(c for c in collect_checks() if c.name == "slowpics")

        with patch("httpx.Client", side_effect=httpx.ConnectError("DNS failed")):
            result = slowpics_check.check_fn()

        assert result.passed is False
        assert result.message == "slow.pics connection failed: DNS failed"
        assert result.hint == (
            "Review the request failure and network path to slow.pics before retrying"
        )

    def test_check_slowpics_protocol_failure_uses_evidence_neutral_next_action(self) -> None:
        slowpics_check = next(c for c in collect_checks() if c.name == "slowpics")

        with patch(
            "httpx.Client",
            side_effect=httpx.RemoteProtocolError("server disconnected"),
        ):
            result = slowpics_check.check_fn()

        assert result.passed is False
        assert result.message == "slow.pics connection failed: server disconnected"
        assert result.hint == (
            "Review the request failure and network path to slow.pics before retrying"
        )


def test_check_tmdb_api_key_missing_mentions_workspace_config_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing TMDB config should point users at config/config.toml."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    monkeypatch.chdir(tmp_path)
    _clear_tmdb_env(monkeypatch)

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
    _clear_tmdb_env(monkeypatch)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key not configured"
    assert result.hint is not None
    assert "FRAME_COMPARE_TMDB__API_KEY" in result.hint


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
    _clear_tmdb_env(monkeypatch)

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
    _clear_tmdb_env(monkeypatch)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB API key has invalid format"
    assert result.hint == ("Replace the TMDB credential with a 32-character hexadecimal API key")


def test_check_tmdb_api_key_legacy_alias_remains_warning_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy TMDB_API_KEY alone should fail with guidance to use the canonical path."""
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")

    monkeypatch.chdir(tmp_path)
    _clear_tmdb_env(monkeypatch)

    monkeypatch.setenv("TMDB_API_KEY", "legacy_key")
    legacy_result = tmdb_check.check_fn()

    assert legacy_result.passed is False
    assert legacy_result.message == "TMDB API key configured via legacy variable"
    assert legacy_result.hint == (
        "Move the credential to FRAME_COMPARE_TMDB__API_KEY and remove TMDB_API_KEY"
    )


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
    _clear_tmdb_env(monkeypatch)

    result = tmdb_check.check_fn()

    assert result.passed is True
    assert result.message == "TMDB metadata lookup disabled"
    assert result.hint is None
    assert result.details == {"enabled": False}


def test_check_tmdb_parse_failure_points_to_config_syntax(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("[tmdb\nenabled = true", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _clear_tmdb_env(monkeypatch)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB configuration could not be loaded"
    assert result.hint == "Fix config/config.toml syntax, then rerun doctor"
    assert result.details["exception_type"] == "ConfigParseError"


def test_check_tmdb_validation_failure_does_not_guess_a_credential_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("[tmdb]\nunknown = true", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _clear_tmdb_env(monkeypatch)

    result = tmdb_check.check_fn()

    assert result.passed is False
    assert result.message == "TMDB configuration could not be loaded"
    assert result.hint == (
        "Fix the reported config/environment validation errors, then rerun doctor"
    )
    assert result.details["exception_type"] == "ConfigValidationError"
    assert "API_KEY" not in result.hint
