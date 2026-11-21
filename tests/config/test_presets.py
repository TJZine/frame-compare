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


def test_load_preset_with_invalid_utf8_raises_preset_error(tmp_path: Path) -> None:
    preset_path = tmp_path / "invalid-encoding.toml"
    preset_path.write_bytes(b"[analysis]\nrandom_frame_count = 20\n\xff")

    with pytest.raises(PresetInvalidError, match="Invalid preset file"):
        load_preset("invalid-encoding", presets_dir=tmp_path)


@pytest.mark.parametrize(
    ("name", "content", "error_type", "message"),
    [
        ("missing", None, PresetNotFoundError, "Preset not found"),
        ("bad", "invalid = [", PresetInvalidError, "Invalid preset file"),
    ],
)
def test_load_preset_rejects_missing_or_invalid_toml(
    tmp_path: Path,
    name: str,
    content: str | None,
    error_type: type[PresetNotFoundError] | type[PresetInvalidError],
    message: str,
) -> None:
    if content is not None:
        (tmp_path / f"{name}.toml").write_text(content, encoding="utf-8")
    with pytest.raises(error_type) as exc:
        load_preset(name, presets_dir=tmp_path)
    assert message in str(exc.value)


def test_load_preset_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(PresetNameInvalidError):
        load_preset("../escape", presets_dir=tmp_path)


@pytest.mark.parametrize("operation", ["load", "save", "apply"])
def test_preset_operations_reject_empty_names(tmp_path: Path, operation: str) -> None:
    from frame_compare.config.loader import get_default_config

    with pytest.raises(PresetNameInvalidError):
        if operation == "load":
            load_preset("", presets_dir=tmp_path)
        elif operation == "save":
            save_preset("", get_default_config(), presets_dir=tmp_path)
        else:
            apply_preset(get_default_config(), "", presets_dir=tmp_path)


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
    tmdb = data["tmdb"]
    assert isinstance(tmdb, dict)
    assert "api_key" not in tmdb
    preset_text = (tmp_path / "safe.toml").read_text(encoding="utf-8")
    assert "secret-token" not in preset_text
    assert "sentinel-tmdb-api-key" not in preset_text


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
    for field in ("target_nits", "tone_curve", "gamma_lift", "contrast_recovery"):
        del expected_data["color"][field]

    save_preset("roundtrip", original_config, presets_dir=tmp_path)
    loaded_data = load_preset("roundtrip", presets_dir=tmp_path)

    assert loaded_data == expected_data
    color_data = loaded_data["color"]
    assert isinstance(color_data, dict)
    assert color_data["tonemap_speed"] == "quality"


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


def test_save_preset_deterministic_output(tmp_path: Path) -> None:
    """Saving the same config twice produces identical file contents."""
    from frame_compare.config.loader import get_default_config

    config = get_default_config()

    path1 = save_preset("test1", config, presets_dir=tmp_path)
    path2 = save_preset("test2", config, presets_dir=tmp_path)

    assert path1.read_text(encoding="utf-8") == path2.read_text(encoding="utf-8")


@pytest.mark.parametrize("generated_dir", ["generated", "/Volumes/review/generated"])
def test_save_preset_preserves_authored_generated_directory(
    tmp_path: Path,
    generated_dir: str,
) -> None:
    from frame_compare.config.loader import get_default_config

    config = get_default_config()
    config.paths.generated_dir = generated_dir

    save_preset("authored-generated", config, presets_dir=tmp_path)

    persisted = load_preset("authored-generated", presets_dir=tmp_path)
    paths = persisted["paths"]
    assert isinstance(paths, dict)
    assert paths["generated_dir"] == generated_dir
    assert "screenshots_dir" not in paths
    assert "use_run_folders" not in paths
    report = persisted.get("report")
    assert isinstance(report, dict)
    assert "output_dir" not in report


@pytest.mark.parametrize("failure", ["directory", "read_denied", "read_missing"])
def test_preset_acquisition_failure_is_typed_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    path = tmp_path / "selected.toml"
    if failure == "directory":
        path.mkdir()
    else:
        path.write_text("[analysis]\nrandom_frame_count = 12\n")

        def fail_read(*_args: object, **_kwargs: object) -> str:
            if failure == "read_missing":
                raise FileNotFoundError("sentinel-read-detail")
            raise PermissionError("sentinel-read-detail")

        monkeypatch.setattr(Path, "read_text", fail_read)
    error_type = PresetNotFoundError if failure == "read_missing" else PresetInvalidError
    with pytest.raises(error_type) as exc_info:
        load_preset("selected", presets_dir=tmp_path)
    assert "sentinel-read-detail" not in str(exc_info.value.context.to_dict())
    assert exc_info.value.__cause__ is None


def test_preset_acquisition_follows_symlinked_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "selected.toml").write_bytes(b"\xef\xbb\xbf[analysis]\nrandom_frame_count = 12\n")
    link = tmp_path / "presets"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable on this host")
    assert load_preset("selected", presets_dir=link)["analysis"] == {"random_frame_count": 12}


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("x = " + "{x=" * 1500 + "0" + "}" * 1500, id="deep"),
        pytest.param("x = " + "1" * 5000, id="integer-limit"),
    ],
)
def test_preset_parser_limits_are_typed(tmp_path: Path, content: str) -> None:
    (tmp_path / "limited.toml").write_text(content, encoding="utf-8")
    with pytest.raises(PresetInvalidError) as exc:
        load_preset("limited", presets_dir=tmp_path)
    assert exc.value.context.details is not None
    assert exc.value.context.details["parse_error"] == "configuration exceeds TOML parser limits"
