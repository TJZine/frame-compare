"""Tests for configuration loading logic."""

from pathlib import Path
from typing import Any

import pytest

from frame_compare.config.loader import (
    get_default_config,
    load_config,
    load_config_from_env,
)
from frame_compare.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)


def test_load_default_config() -> None:
    """Test loading default config without TOML or env."""
    config = get_default_config()
    assert config.analysis.frame_count == 10


def test_load_from_toml_file(tmp_path: Path) -> None:
    """Test loading config from a TOML file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [analysis]
        frame_count = 20
        """,
        encoding="utf-8",
    )

    config = load_config(config_path=config_file)
    assert config.analysis.frame_count == 20
    # Other values remain defaults
    assert config.paths.input_dir == "comparison_videos"


def test_toml_file_not_found_raises() -> None:
    """Test that missing config file raises ConfigNotFoundError."""
    with pytest.raises(ConfigNotFoundError) as exc:
        load_config(config_path=Path("non_existent.toml"))
    assert "Configuration file not found" in str(exc.value)


def test_toml_syntax_error_raises(tmp_path: Path) -> None:
    """Test that invalid TOML syntax raises ConfigParseError."""
    config_file = tmp_path / "bad.toml"
    config_file.write_text("invalid = [", encoding="utf-8")

    with pytest.raises(ConfigParseError) as exc:
        load_config(config_path=config_file)
    assert "Failed to parse" in str(exc.value)


def test_toml_with_utf8_bom_is_accepted(tmp_path: Path) -> None:
    """UTF-8 BOM-prefixed TOML should load (common on Windows)."""
    config_file = tmp_path / "bom.toml"
    config_file.write_bytes(b"\xef\xbb\xbf[analysis]\nframe_count = 20\n")

    config = load_config(config_path=config_file)
    assert config.analysis.frame_count == 20


def test_validation_error_raises(tmp_path: Path) -> None:
    """Test that invalid config values raise ConfigValidationError."""
    config_file = tmp_path / "invalid.toml"
    config_file.write_text(
        """
        [analysis]
        frame_count = -1
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as exc:
        load_config(config_path=config_file)

    assert "Invalid configuration" in str(exc.value)
    # Check context is available
    assert exc.value.context.details is not None
    errors = exc.value.context.details.get("validation_errors")
    assert isinstance(errors, list)
    assert len(errors) > 0


def test_config_validation_error_context_is_json_serializable(tmp_path: Path) -> None:
    """Test that validation error context can be serialized to JSON."""
    config_file = tmp_path / "invalid.toml"
    config_file.write_text(
        """
        [analysis]
        frame_count = -1
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as exc:
        load_config(config_path=config_file)

    # This should not raise
    import json

    json.dumps(exc.value.context.to_dict())


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test overriding config via environment variables."""
    monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__FRAME_COUNT", "30")

    config = load_config_from_env()
    assert config.analysis.frame_count == 30


def test_env_override_empty_string_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty-string env var should raise ConfigValidationError."""
    monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__FRAME_COUNT", "")

    with pytest.raises(ConfigValidationError):
        load_config_from_env()


def test_cli_override_takes_precedence(tmp_path: Path) -> None:
    """Test that CLI overrides take precedence over file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [analysis]
        frame_count = 20
        """,
        encoding="utf-8",
    )

    overrides: dict[str, Any] = {"analysis": {"frame_count": 50}}
    config = load_config(config_path=config_file, overrides=overrides)

    assert config.analysis.frame_count == 50


def test_load_config_none_path_with_empty_overrides_returns_config() -> None:
    config = load_config(config_path=None, overrides={})
    assert config.analysis.frame_count == 10


def test_empty_overrides_leave_defaults_intact() -> None:
    config = load_config(overrides={})
    assert config.analysis.frame_count == 10


def test_precedence_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full precedence order: Overrides > Env > TOML > Defaults."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [analysis]
        frame_count = 10  # TOML
        """,
        encoding="utf-8",
    )

    # Env
    monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__FRAME_COUNT", "20")

    # 1. Env overrides TOML
    config = load_config(config_path=config_file)
    assert config.analysis.frame_count == 20

    # 2. Explicit overrides override Env
    overrides: dict[str, Any] = {"analysis": {"frame_count": 30}}
    config = load_config(config_path=config_file, overrides=overrides)
    assert config.analysis.frame_count == 30


def test_tmdb_api_key_legacy_alias_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy TMDB_API_KEY alias is no longer supported."""
    monkeypatch.setenv("TMDB_API_KEY", "legacy_key")

    config = load_config()
    assert config.tmdb.api_key is None


def test_tmdb_api_key_nested_var_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Canonical TMDB nested var is used when both vars are set."""
    monkeypatch.setenv("TMDB_API_KEY", "legacy_key")
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "new_key")

    config = load_config()
    assert config.tmdb.api_key == "new_key"


def test_log_level_legacy_alias_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy FRAME_COMPARE_LOG_LEVEL alias is no longer supported."""
    monkeypatch.setenv("FRAME_COMPARE_LOG_LEVEL", "DEBUG")

    config = load_config()
    assert config.logging.level == "INFO"


def test_tone_curve_mobius_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAME_COMPARE_COLOR__TONE_CURVE", "mobius")

    with pytest.raises(ConfigValidationError) as excinfo:
        load_config_from_env()
    assert any(
        isinstance(loc, list) and any(str(part).lower() == "tone_curve" for part in loc)
        for loc in (err.get("loc") for err in excinfo.value.validation_errors)
    )


def test_tone_curve_linear_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAME_COMPARE_COLOR__TONE_CURVE", "linear")

    with pytest.raises(ConfigValidationError) as excinfo:
        load_config_from_env()
    assert any(
        isinstance(loc, list) and any(str(part).lower() == "tone_curve" for part in loc)
        for loc in (err.get("loc") for err in excinfo.value.validation_errors)
    )
