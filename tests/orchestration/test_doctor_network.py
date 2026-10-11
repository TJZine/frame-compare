"""Unit tests for diagnostic checks."""

from __future__ import annotations

from pathlib import Path

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


@pytest.mark.parametrize(
    (
        "content",
        "passed",
        "message",
        "hint",
        "hint_fragment",
        "forbidden_hint",
        "details",
        "exact_details",
    ),
    [
        pytest.param(
            None,
            False,
            "TMDB API key not configured",
            "tmdb.api_key in config/config.toml",
            True,
            None,
            {},
            False,
            id="check_tmdb_api_key_missing_mentions_workspace_config_hint",
        ),
        pytest.param(
            "\n        [tmdb]\n        enabled = true\n        ",
            False,
            "TMDB API key not configured",
            "FRAME_COMPARE_TMDB__API_KEY",
            True,
            None,
            {},
            False,
            id="check_tmdb_api_key_enabled_without_key_still_fails",
        ),
        pytest.param(
            '\n        [tmdb]\n        api_key = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n        ',
            True,
            "TMDB API key configured",
            None,
            False,
            None,
            {},
            False,
            id="check_tmdb_api_key_passes_with_workspace_config",
        ),
        pytest.param(
            '\n        [tmdb]\n        api_key = "config_key"\n        ',
            False,
            "TMDB API key has invalid format",
            "Replace the TMDB credential with a 32-character hexadecimal API key",
            False,
            None,
            {},
            False,
            id="check_tmdb_api_key_fails_with_malformed_workspace_config",
        ),
        pytest.param(
            "\n        [tmdb]\n        enabled = false\n        ",
            True,
            "TMDB metadata lookup disabled",
            None,
            False,
            None,
            {"enabled": False},
            True,
            id="check_tmdb_api_key_disabled_without_key_is_non_failing",
        ),
        pytest.param(
            "[tmdb\nenabled = true",
            False,
            "TMDB configuration could not be loaded",
            "Fix config/config.toml syntax, then rerun doctor",
            False,
            None,
            {"exception_type": "ConfigParseError"},
            False,
            id="check_tmdb_parse_failure_points_to_config_syntax",
        ),
        pytest.param(
            "[tmdb]\nunknown = true",
            False,
            "TMDB configuration could not be loaded",
            "Fix the reported config/environment validation errors, then rerun doctor",
            False,
            "API_KEY",
            {"exception_type": "ConfigValidationError"},
            False,
            id="check_tmdb_validation_failure_does_not_guess_a_credential_fix",
        ),
    ],
)
def test_check_tmdb_workspace_config(
    content: str | None,
    passed: bool,
    message: str,
    hint: str | None,
    hint_fragment: bool,
    forbidden_hint: str | None,
    details: dict[str, object],
    exact_details: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmdb_check = next(c for c in collect_checks() if c.name == "tmdb_api_key")
    if content is not None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _clear_tmdb_env(monkeypatch)
    result = tmdb_check.check_fn()
    assert result.passed is passed
    assert result.message == message
    if hint_fragment:
        assert result.hint is not None
        assert hint is not None
        assert hint in result.hint
    else:
        assert result.hint == hint
    if forbidden_hint is not None:
        assert result.hint is not None
        assert forbidden_hint not in result.hint
    if exact_details:
        assert result.details == details
    else:
        for key, value in details.items():
            assert result.details[key] == value
