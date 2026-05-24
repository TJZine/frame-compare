"""Unit tests for probe cache keying logic and I/O."""

from pathlib import Path
from unittest.mock import patch

import tomli_w

from frame_compare.orchestration.probing.probe_cache import (
    load_clip_probe_cache,
)


def test_load_clip_probe_cache_returns_empty_dict_on_missing_file(tmp_path: Path):
    """Missing file -> empty dict."""
    cache = load_clip_probe_cache(tmp_path / "missing.toml")
    assert cache == {}


def test_load_clip_probe_cache_skips_entry_with_non_array_tonemap_prop_keys(tmp_path: Path):
    """Malformed tonemap key containers still trigger warn-and-skip handling."""
    f = tmp_path / "invalid_tonemap_shape.toml"
    f.write_text(
        """
version = "1"

[bad_key]
path = "video.mkv"
size_bytes = 100
mtime_ns = 100
width = 1920
height = 1080
num_frames = 100
fps_num = 24
fps_den = 1
is_hdr = false
tonemap_prop_keys = "not-an-array"
""",
        encoding="utf-8",
    )

    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_returns_empty_dict_on_version_mismatch(tmp_path: Path):
    """Wrong version -> empty dict."""
    f = tmp_path / "version.toml"
    with f.open("wb") as out:
        tomli_w.dump({"version": "2", "foo": {}}, out)

    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_ignores_unknown_fields_and_skips_invalid_entries(tmp_path: Path):
    """Robustness test for partial validity."""
    f = tmp_path / "mixed.toml"
    data = {
        "version": "1",
        "valid_key": {
            "path": "video.mkv",
            "size_bytes": 100,
            "mtime_ns": 100,
            "width": 100,
            "height": 100,
            "num_frames": 100,
            "fps_num": 24,
            "fps_den": 1,
            "is_hdr": False,
            "extra_field": "ignore me",  # Unknown field
        },
        "invalid_key": {
            "path": "video.mkv",
            # Missing size_bytes etc.
        },
    }
    with f.open("wb") as out:
        tomli_w.dump(data, out)

    with patch("frame_compare.orchestration.probing.probe_cache.log.warning") as warning:
        cache = load_clip_probe_cache(f)

    assert len(cache) == 1
    assert "valid_key" in cache
    assert cache["valid_key"].width == 100
    warning.assert_called_once()
    assert warning.call_args.args[0] == "probe_cache_invalid_entry"
    assert warning.call_args.kwargs["key"] == "invalid_key"


def test_load_clip_probe_cache_skips_entry_with_non_table_preserved_frame_props(tmp_path: Path):
    """Malformed preserved props containers still trigger warn-and-skip handling."""
    f = tmp_path / "invalid_props_shape.toml"
    f.write_text(
        """
version = "1"

[bad_key]
path = "video.mkv"
size_bytes = 100
mtime_ns = 100
width = 1920
height = 1080
num_frames = 100
fps_num = 24
fps_den = 1
is_hdr = false
preserved_frame_props = "not-a-table"
""",
        encoding="utf-8",
    )

    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_sanitizes_nested_hdr_metadata_values(tmp_path: Path):
    """Invalid nested HDR value types fall back to safe defaults instead of surviving unchanged."""
    f = tmp_path / "hdr_value_sanitize.toml"
    f.write_text(
        """
version = "1"

[hdr_key]
path = "hdr.mkv"
size_bytes = 100
mtime_ns = 100
width = 3840
height = 2160
num_frames = 240
fps_num = 24
fps_den = 1
is_hdr = true

[hdr_key.hdr_metadata]
mastering_display = 123
max_cll = "1000"
max_fall = 99.5
color_primaries = "9"
transfer = 16
matrix = true
""",
        encoding="utf-8",
    )

    cache = load_clip_probe_cache(f)

    hdr = cache["hdr_key"].hdr_metadata
    assert hdr is not None
    assert hdr.mastering_display is None
    assert hdr.max_cll is None
    assert hdr.max_fall is None
    assert hdr.color_primaries == 2
    assert hdr.transfer == 16
    assert hdr.matrix == 2


def test_load_clip_probe_cache_returns_empty_dict_on_missing_version(tmp_path: Path):
    """Missing version -> empty dict."""
    f = tmp_path / "missing_version.toml"
    with f.open("wb") as out:
        tomli_w.dump({"foo": {}}, out)

    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_sanitizes_preserved_props_and_tonemap_keys(tmp_path: Path):
    """Mixed-shape values are narrowed before entering the typed snapshot."""
    f = tmp_path / "sanitize_values.toml"
    f.write_text(
        """
version = "1"

[valid_key]
path = "video.mkv"
size_bytes = 100
mtime_ns = 100
width = 1920
height = 1080
num_frames = 100
fps_num = 24
fps_den = 1
is_hdr = false
tonemap_prop_keys = ["keep_me", 42, true]

[valid_key.preserved_frame_props]
keep_str = "value"
keep_int = 7
keep_float = 1.5
drop_bool = true
drop_array = [1, 2]
""",
        encoding="utf-8",
    )

    cache = load_clip_probe_cache(f)
    snapshot = cache["valid_key"]

    assert snapshot.preserved_frame_props == {
        "keep_str": "value",
        "keep_int": 7,
        "keep_float": 1.5,
    }
    assert snapshot.tonemap_prop_keys == ("keep_me",)


def test_load_clip_probe_cache_returns_empty_dict_on_read_os_error(tmp_path: Path):
    """Plain filesystem read failures degrade like corrupt generated state."""
    f = tmp_path / "unreadable.toml"
    f.write_text('version = "1"', encoding="utf-8")

    with (
        patch("pathlib.Path.open", side_effect=OSError("permission denied")),
        patch("frame_compare.orchestration.probing.probe_cache.log.warning") as warning,
    ):
        cache = load_clip_probe_cache(f)

    assert cache == {}
    warning.assert_called_once()
    assert warning.call_args.args[0] == "probe_cache_read_error"


def test_load_clip_probe_cache_returns_empty_dict_on_parse_error(tmp_path: Path):
    """Invalid TOML -> empty dict."""
    f = tmp_path / "invalid.toml"
    f.write_text("invalid [ toml", encoding="utf-8")
    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_skips_entry_with_non_table_hdr_metadata(tmp_path: Path):
    """HDR entries with malformed nested metadata tables are skipped."""
    f = tmp_path / "invalid_hdr_shape.toml"
    data = {
        "version": "1",
        "bad_hdr": {
            "path": "hdr.mkv",
            "size_bytes": 100,
            "mtime_ns": 100,
            "width": 3840,
            "height": 2160,
            "num_frames": 240,
            "fps_num": 24,
            "fps_den": 1,
            "is_hdr": True,
            "hdr_metadata": "not-a-table",
        },
    }
    with f.open("wb") as out:
        tomli_w.dump(data, out)

    cache = load_clip_probe_cache(f)
    assert cache == {}
