"""Unit tests for probe cache keying logic and I/O."""

from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w

from frame_compare.orchestration.context import ClipFingerprint
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
)


def _entry(
    *,
    path: object = "video.mkv",
    size_bytes: int = 100,
    mtime_ns: int = 100,
    width: int = 1920,
    height: int = 1080,
    num_frames: int = 100,
    fps_num: int = 24,
    fps_den: int = 1,
) -> tuple[str, dict[str, object]]:
    fingerprint_path = Path(path) if isinstance(path, str) else Path("video.mkv")
    fingerprint = ClipFingerprint(fingerprint_path, size_bytes, mtime_ns)
    return compute_probe_cache_key(fingerprint), {
        "path": path,
        "size_bytes": size_bytes,
        "mtime_ns": mtime_ns,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "fps_num": fps_num,
        "fps_den": fps_den,
        "is_hdr": False,
    }


@pytest.mark.parametrize(
    "content", [None, {"version": "2", "foo": {}}], ids=["missing-file", "version-mismatch"]
)
def test_load_clip_probe_cache_miss(tmp_path: Path, content: dict[str, object] | None) -> None:
    path = tmp_path / ("missing.toml" if content is None else "version.toml")
    if content is not None:
        with path.open("wb") as output:
            tomli_w.dump(content, output)
    assert load_clip_probe_cache(path) == {}


def test_load_clip_probe_cache_ignores_unknown_fields_and_skips_invalid_entries(tmp_path: Path):
    """Robustness test for partial validity."""
    f = tmp_path / "mixed.toml"
    valid_key, valid_entry = _entry()
    data = {
        "version": "1",
        valid_key: {**valid_entry, "extra_field": "ignore me"},  # Unknown field
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
    assert valid_key in cache
    assert cache[valid_key].width == 1920
    warning.assert_called_once()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 0),
        ("height", -1),
        ("num_frames", 0),
        ("fps_num", 0),
        ("fps_num", -24),
        ("fps_den", -1),
        ("path", 42),
        ("size_bytes", -1),
    ],
)
def test_load_clip_probe_cache_skips_invalid_probe_facts(
    tmp_path: Path, field: str, value: object
) -> None:
    key, entry = _entry()
    entry[field] = value
    path = tmp_path / f"invalid_{field}_{value}.toml"
    with path.open("wb") as output:
        tomli_w.dump({"version": "1", key: entry}, output)

    assert load_clip_probe_cache(path) == {}


def test_load_clip_probe_cache_allows_pre_epoch_mtime(tmp_path: Path) -> None:
    key, entry = _entry(mtime_ns=-1)
    path = tmp_path / "pre_epoch.toml"
    with path.open("wb") as output:
        tomli_w.dump({"version": "1", key: entry}, output)

    loaded = load_clip_probe_cache(path)

    assert loaded[key].fingerprint.mtime_ns == -1


def test_load_clip_probe_cache_rejects_key_for_different_fingerprint(tmp_path: Path) -> None:
    key, entry = _entry()
    entry["path"] = "different.mkv"
    path = tmp_path / "mismatched_key.toml"
    with path.open("wb") as output:
        tomli_w.dump({"version": "1", key: entry}, output)

    assert load_clip_probe_cache(path) == {}


def test_load_clip_probe_cache_invalid_utf8_is_a_miss(tmp_path: Path) -> None:
    path = tmp_path / "invalid_utf8.toml"
    path.write_bytes(b"\xff")

    assert load_clip_probe_cache(path) == {}


def test_load_clip_probe_cache_sanitizes_nested_hdr_metadata_values(tmp_path: Path):
    """Invalid nested HDR value types fall back to safe defaults instead of surviving unchanged."""
    f = tmp_path / "hdr_value_sanitize.toml"
    key, entry = _entry(path="hdr.mkv", width=3840, height=2160, num_frames=240)
    entry["is_hdr"] = True
    entry["hdr_metadata"] = {
        "mastering_display": 123,
        "max_cll": "1000",
        "max_fall": 99.5,
        "color_primaries": "9",
        "transfer": 16,
        "matrix": True,
    }
    with f.open("wb") as output:
        tomli_w.dump({"version": "1", key: entry}, output)

    cache = load_clip_probe_cache(f)

    hdr = cache[key].hdr_metadata
    assert hdr is not None
    assert hdr.mastering_display is None
    assert hdr.max_cll is None
    assert hdr.max_fall is None
    assert hdr.color_primaries == 2
    assert hdr.transfer == 16
    assert hdr.matrix == 2


def test_load_clip_probe_cache_sanitizes_preserved_props_and_tonemap_keys(tmp_path: Path):
    """Mixed-shape values are narrowed before entering the typed snapshot."""
    f = tmp_path / "sanitize_values.toml"
    key, entry = _entry()
    entry["tonemap_prop_keys"] = ["keep_me", 42, True]
    entry["preserved_frame_props"] = {
        "keep_str": "value",
        "keep_int": 7,
        "keep_float": 1.5,
        "drop_bool": True,
        "drop_array": [1, 2],
    }
    with f.open("wb") as output:
        tomli_w.dump({"version": "1", key: entry}, output)

    cache = load_clip_probe_cache(f)
    snapshot = cache[key]

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
