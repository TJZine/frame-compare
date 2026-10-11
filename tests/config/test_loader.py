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
    get_default_config,
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


@pytest.mark.parametrize(
    ("raw", "filename", "content", "error_type", "message"),
    [
        (False, "non_existent.toml", None, ConfigNotFoundError, "Configuration file not found"),
        (False, "bad.toml", "invalid = [", ConfigParseError, "Failed to parse"),
        (True, "missing.toml", None, ConfigNotFoundError, None),
    ],
)
def test_config_load_rejects_missing_or_malformed_files(
    tmp_path: Path,
    raw: bool,
    filename: str,
    content: str | None,
    error_type: type[ConfigNotFoundError] | type[ConfigParseError],
    message: str | None,
) -> None:
    path = tmp_path / filename
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(error_type) as exc:
        if raw:
            load_raw_config(path)
        else:
            load_config(config_path=path)
    if message is not None:
        assert message in str(exc.value)
    else:
        assert isinstance(exc.value, ConfigNotFoundError)
        assert exc.value.path == path


def test_toml_with_utf8_bom_is_accepted(tmp_path: Path) -> None:
    """UTF-8 BOM-prefixed TOML should load (common on Windows)."""
    config_file = tmp_path / "bom.toml"
    config_file.write_bytes(b"\xef\xbb\xbf[analysis]\nrandom_frame_count = 20\n")

    config = load_config(config_path=config_file)
    assert config.analysis.random_frame_count == 20


def test_config_with_invalid_utf8_raises_config_parse_error(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid-encoding.toml"
    config_file.write_bytes(b"[analysis]\nrandom_frame_count = 20\n\xff")

    with pytest.raises(ConfigParseError, match="not valid UTF-8"):
        load_config(config_path=config_file)


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


def test_nested_runtime_memory_limit_environment_value_is_decoded_without_relaxing_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "[runtime]\nmemory_limit_mb = 1024\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME__MEMORY_LIMIT_MB", "2048")

    config = load_config(config_path=config_file)

    assert config.runtime.memory_limit_mb == 2048

    with pytest.raises(ConfigValidationError):
        load_config(
            config_path=config_file,
            overrides={"runtime": {"memory_limit_mb": "2048"}},
        )

    monkeypatch.delenv("FRAME_COMPARE_RUNTIME__MEMORY_LIMIT_MB")
    config_file.write_text(
        '[runtime]\nmemory_limit_mb = "2048"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigValidationError):
        load_config(config_path=config_file)


@pytest.mark.parametrize(
    "value",
    ["511", "512.0", "true", "not-an-integer", "9" * 5000],
    ids=["below-minimum", "float", "bool", "non-integer", "overlong-decimal"],
)
def test_invalid_nested_runtime_memory_limit_environment_value_is_typed_failure(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME__MEMORY_LIMIT_MB", value)

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config()

    assert exc_info.value.validation_errors


def test_raw_config_ignores_runtime_memory_limit_environment_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("[runtime]\nmemory_limit_mb = 1024\n", encoding="utf-8")
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME__MEMORY_LIMIT_MB", "not-an-integer")

    document = load_raw_config(config_file)

    assert document.payload["runtime"] == {"memory_limit_mb": 1024}
    assert document.config.runtime.memory_limit_mb == 1024


def test_default_config_ignores_runtime_memory_limit_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME__MEMORY_LIMIT_MB", "2048")

    assert get_default_config().runtime.memory_limit_mb is None


@pytest.mark.parametrize(
    ("environment", "section", "field", "expected"),
    [
        ({"TMDB_API_KEY": "legacy_key"}, "tmdb", "api_key", None),
        (
            {"TMDB_API_KEY": "legacy_key", "FRAME_COMPARE_TMDB__API_KEY": "sentinel-tmdb-api-key"},
            "tmdb",
            "api_key",
            "sentinel-tmdb-api-key",
        ),
        ({"FRAME_COMPARE_LOG_LEVEL": "DEBUG"}, "logging", "level", "INFO"),
    ],
)
def test_config_environment_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    section: str,
    field: str,
    expected: object,
) -> None:
    monkeypatch.chdir(tmp_path)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    config = load_config()
    assert getattr(getattr(config, section), field) == expected
