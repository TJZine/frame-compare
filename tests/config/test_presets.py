"""Tests for preset management."""

from pathlib import Path

import pytest

from frame_compare.config.errors import (
    PresetInvalidError,
    PresetNameInvalidError,
    PresetNotFoundError,
)
from frame_compare.config.presets import (
    apply_preset,
    list_presets,
    load_preset,
    save_preset,
)


def test_list_presets_empty_dir(tmp_path: Path) -> None:
    """Test listing presets from empty or missing directory."""
    presets = list_presets(presets_dir=tmp_path)
    assert presets == []

    # Missing dir
    presets = list_presets(presets_dir=tmp_path / "missing")
    assert presets == []


def test_list_presets_finds_toml_files(tmp_path: Path) -> None:
    """Test listing finds TOML files."""
    (tmp_path / "a.toml").touch()
    (tmp_path / "b.toml").touch()
    (tmp_path / "c.txt").touch()  # Should be ignored

    presets = list_presets(presets_dir=tmp_path)
    assert presets == ["a", "b"]


def test_load_preset_success(tmp_path: Path) -> None:
    """Test loading a valid preset."""
    (tmp_path / "test.toml").write_text('key = "value"', encoding="utf-8")

    data = load_preset("test", presets_dir=tmp_path)
    assert data == {"key": "value"}


def test_load_preset_not_found_raises(tmp_path: Path) -> None:
    """Test that missing preset raises PresetNotFoundError."""
    with pytest.raises(PresetNotFoundError) as exc:
        load_preset("missing", presets_dir=tmp_path)
    assert "Preset not found" in str(exc.value)


def test_load_preset_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(PresetNameInvalidError):
        load_preset("../escape", presets_dir=tmp_path)


def test_load_preset_rejects_empty_name(tmp_path: Path) -> None:
    with pytest.raises(PresetNameInvalidError):
        load_preset("", presets_dir=tmp_path)


def test_preset_invalid_toml_raises_parse_error(tmp_path: Path) -> None:
    """Test that invalid TOML preset raises PresetInvalidError."""
    (tmp_path / "bad.toml").write_text("invalid = [", encoding="utf-8")

    with pytest.raises(PresetInvalidError) as exc:
        load_preset("bad", presets_dir=tmp_path)
    assert "Invalid preset file" in str(exc.value)


def test_save_preset_creates_file(tmp_path: Path) -> None:
    """Test saving a preset creates the file."""
    from frame_compare.config.loader import get_default_config

    config = get_default_config()
    save_preset("my_preset", config, presets_dir=tmp_path)

    assert (tmp_path / "my_preset.toml").exists()


def test_save_preset_omits_generated_secrets(tmp_path: Path) -> None:
    from frame_compare.config.loader import get_default_config

    config = get_default_config()
    config.slowpics.title = "Secret-safe preset"
    config.slowpics.webhook_url = "https://discord.com/api/webhooks/id/secret-token"
    config.tmdb.api_key = "sentinel-tmdb-api-key"

    save_preset("safe", config, presets_dir=tmp_path)

    data = load_preset("safe", presets_dir=tmp_path)
    slowpics = data["slowpics"]
    assert isinstance(slowpics, dict)
    assert slowpics["title"] == "Secret-safe preset"
    assert "webhook_url" not in slowpics
    assert "api_key" not in data["tmdb"]
    preset_text = (tmp_path / "safe.toml").read_text(encoding="utf-8")
    assert "secret-token" not in preset_text
    assert "sentinel-tmdb-api-key" not in preset_text


def test_save_preset_uses_atomic_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from frame_compare.config.loader import get_default_config

    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.config.presets.write_text_atomic", _fake_write)

    config = get_default_config()
    saved = save_preset("atomic", config, presets_dir=tmp_path)

    assert calls == [saved]


def test_save_preset_rejects_empty_name(tmp_path: Path) -> None:
    from frame_compare.config.loader import get_default_config

    config = get_default_config()
    with pytest.raises(PresetNameInvalidError):
        save_preset("", config, presets_dir=tmp_path)


def test_save_preset_roundtrip(tmp_path: Path) -> None:
    """Save a config as preset, load it, and verify data equality.

    Uses exclude_none=True because TOML cannot represent None.
    """
    from frame_compare.config.loader import get_default_config

    original_config = get_default_config()
    original_config.sources.label_mode = "filename"
    original_config.slowpics.title = "Preset Title"
    original_config.slowpics.title_suffix = "[Preset]"
    original_config.slowpics.tmdb_id = 42
    original_config.slowpics.tmdb_media_type = "movie"
    original_config.slowpics.remove_after_days = 90
    # This is what save_preset serializes (excludes None values)
    expected_data = original_config.model_dump(mode="json", exclude_none=True)

    save_preset("roundtrip", original_config, presets_dir=tmp_path)
    loaded_data = load_preset("roundtrip", presets_dir=tmp_path)

    assert loaded_data == expected_data


def test_save_preset_apply_restores_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Applying a saved preset restores the full config with defaults.

    Uses monkeypatch.chdir(tmp_path) so that apply_preset() loads from
    the relative DEFAULT_PRESETS_DIR path (config/presets) within tmp_path.
    """
    from frame_compare.config.loader import get_default_config

    # Change CWD to tmp_path so DEFAULT_PRESETS_DIR resolves to tmp_path/config/presets
    monkeypatch.chdir(tmp_path)

    original_config = get_default_config()

    # Save preset with no presets_dir argument (uses DEFAULT_PRESETS_DIR = config/presets)
    # config/presets will be created inside tmp_path
    save_preset("defaults", original_config)

    # Start with a fresh default config
    base_config = get_default_config()

    # apply_preset loads from DEFAULT_PRESETS_DIR (now tmp_path/config/presets)
    restored_config = apply_preset(base_config, "defaults")

    # The restored config should equal the original (defaults fill missing keys)
    assert restored_config.model_dump(mode="json") == original_config.model_dump(mode="json")


def test_apply_preset_merges_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test applying a preset merges values."""
    from frame_compare.config.loader import get_default_config

    monkeypatch.chdir(tmp_path)

    # Create a preset manually
    presets_dir = tmp_path / "config/presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    (presets_dir / "custom.toml").write_text(
        """
        [analysis]
        random_frame_count = 50
        """,
        encoding="utf-8",
    )

    config = get_default_config()
    new_config = apply_preset(config, "custom")

    assert new_config.analysis.random_frame_count == 50
    assert new_config.paths.input_dir == "comparison_videos"  # Unchanged


def test_apply_preset_rejects_empty_name(tmp_path: Path) -> None:
    from frame_compare.config.loader import get_default_config

    config = get_default_config()
    with pytest.raises(PresetNameInvalidError):
        apply_preset(config, "", presets_dir=tmp_path)


def test_save_preset_deterministic_output(tmp_path: Path) -> None:
    """Saving the same config twice produces identical file contents."""
    from frame_compare.config.loader import get_default_config

    config = get_default_config()

    path1 = save_preset("test1", config, presets_dir=tmp_path)
    path2 = save_preset("test2", config, presets_dir=tmp_path)

    assert path1.read_text(encoding="utf-8") == path2.read_text(encoding="utf-8")
