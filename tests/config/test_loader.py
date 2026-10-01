"""Tests for configuration loading logic."""

from pathlib import Path
from typing import Any

import pytest

from frame_compare.config.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from frame_compare.config.loader import (
    load_config,
    load_raw_config,
)


def test_load_from_toml_file(tmp_path: Path) -> None:
    """Test loading config from a TOML file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [analysis]
        random_frame_count = 20

        [tmdb]
        api_key = "sentinel-tmdb-api-key"
        """,
        encoding="utf-8",
    )

    config = load_config(config_path=config_file)
    assert config.analysis.random_frame_count == 20
    assert config.tmdb.api_key == "sentinel-tmdb-api-key"
    # Other values remain defaults
    assert config.paths.input_dir == "comparison_videos"


def test_load_slowpics_naming_and_source_label_fields_from_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [sources]
        label_mode = "parsed"
        label_parser = "anitopy"

        [sources.overrides."reference.mkv"]
        label = "Reference Source"

        [slowpics]
        title_template = "${Title} (${Year})"
        title_suffix = "[Compare]"
        is_hentai = true
        tmdb_id = 7
        tmdb_media_type = "tv"
        remove_after_days = 30
        image_upload_timeout_seconds = 240.0
        """,
        encoding="utf-8",
    )

    config = load_config(config_path=config_file)
    assert config.sources.label_mode == "parsed"
    assert config.sources.label_parser == "anitopy"
    assert config.sources.overrides["reference.mkv"].label == "Reference Source"
    assert config.slowpics.title_template == "${Title} (${Year})"
    assert config.slowpics.title_suffix == "[Compare]"
    assert config.slowpics.is_hentai is True
    assert config.slowpics.tmdb_id == 7
    assert config.slowpics.tmdb_media_type == "tv"
    assert config.slowpics.remove_after_days == 30
    assert config.slowpics.image_upload_timeout_seconds == 240.0


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
    config_file.write_bytes(b"\xef\xbb\xbf[analysis]\nrandom_frame_count = 20\n")

    config = load_config(config_path=config_file)
    assert config.analysis.random_frame_count == 20


def test_validation_error_raises(tmp_path: Path) -> None:
    """Test that invalid config values raise ConfigValidationError."""
    config_file = tmp_path / "invalid.toml"
    config_file.write_text(
        """
        [analysis]
        random_frame_count = -1
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


def test_raw_config_load_ignores_environment_and_redacts_invalid_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[tmdb]\napi_key = "file-secret"\n[analysis]\nrandom_frame_count = 7\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "environment-secret")
    monkeypatch.setenv("FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD", "true")

    document = load_raw_config(config_file)

    assert document.payload["tmdb"] == {"api_key": "file-secret"}
    assert document.config.tmdb.api_key == "file-secret"
    assert document.config.analysis.random_frame_count == 7

    config_file.write_text('[paths]\ninput_dir = "comparison_videos"\n', encoding="utf-8")
    omitted_environment = load_raw_config(config_file)
    assert omitted_environment.config.tmdb.api_key is None
    assert omitted_environment.config.slowpics.auto_upload is False

    config_file.write_text(
        '[analysis]\nrandom_frame_count = "raw-secret"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        load_raw_config(config_file)
    validation_errors = exc_info.value.validation_errors
    assert validation_errors
    assert all(error.get("input") == "<redacted>" for error in validation_errors)
    assert "raw-secret" not in str(exc_info.value.context.to_dict())


def test_raw_config_load_missing_file_uses_config_not_found_error(tmp_path: Path) -> None:
    config_file = tmp_path / "missing.toml"

    with pytest.raises(ConfigNotFoundError) as exc_info:
        load_raw_config(config_file)

    assert exc_info.value.path == config_file


def test_empty_overrides_leave_defaults_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config(overrides={})
    assert config.analysis.random_frame_count == 10


def test_precedence_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full precedence order: Overrides > Env > TOML > Defaults."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [analysis]
        random_frame_count = 10  # TOML
        """,
        encoding="utf-8",
    )

    # Env
    monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__RANDOM_FRAME_COUNT", "20")

    # 1. Env overrides TOML
    config = load_config(config_path=config_file)
    assert config.analysis.random_frame_count == 20

    # 2. Explicit overrides override Env
    overrides: dict[str, Any] = {"analysis": {"random_frame_count": 30}}
    config = load_config(config_path=config_file, overrides=overrides)
    assert config.analysis.random_frame_count == 30


def test_tmdb_api_key_legacy_alias_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy TMDB_API_KEY alias is no longer supported."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TMDB_API_KEY", "legacy_key")

    config = load_config()
    assert config.tmdb.api_key is None


def test_tmdb_api_key_nested_var_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical TMDB nested var is used when both vars are set."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TMDB_API_KEY", "legacy_key")
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "sentinel-tmdb-api-key")

    config = load_config()
    assert config.tmdb.api_key == "sentinel-tmdb-api-key"


def test_log_level_legacy_alias_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy FRAME_COMPARE_LOG_LEVEL alias is no longer supported."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FRAME_COMPARE_LOG_LEVEL", "DEBUG")

    config = load_config()
    assert config.logging.level == "INFO"
