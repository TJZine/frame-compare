"""Unit tests for diagnostic checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
    assert result.hint is not None
    assert "32-character hexadecimal" in result.hint


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
    assert result.hint is not None
    assert "32-character hexadecimal" in result.hint


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
    assert legacy_result.hint is not None
    assert "FRAME_COMPARE_TMDB__API_KEY" in legacy_result.hint
    assert "legacy" in legacy_result.hint.lower()


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
