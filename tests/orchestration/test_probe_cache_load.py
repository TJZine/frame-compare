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
    fingerprint = ClipFingerprint(fingerprint_path, size_bytes, mtime_ns, source_token="a" * 64)
    return compute_probe_cache_key(fingerprint), {
        "path": path,
        "source_token": "a" * 64,
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
        ("fps_num", 2**63),
        ("fps_den", -1),
        ("fps_den", 2**63),
        ("num_frames", 2**31),
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


def test_load_clip_probe_cache_rejects_negative_fps_components(tmp_path: Path) -> None:
    key, entry = _entry(fps_num=-1, fps_den=-1)
    path = tmp_path / "negative_fps_pair.toml"
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


def test_load_clip_probe_cache_skips_oversized_entry_and_keeps_valid_sibling(
    tmp_path: Path,
) -> None:
    valid_key, valid_entry = _entry(path="valid.mkv", mtime_ns=-1)
    invalid_fps_key, invalid_fps_entry = _entry(path="negative-fps.mkv", fps_num=-1, fps_den=-1)
    overflowing_frame_key, overflowing_frame_entry = _entry(
        path="overflowing-frame-count.mkv", num_frames=10**350
    )
    huge_hex = "f" * 4000
    path = tmp_path / "oversized_sibling.toml"
    path.write_text(
        tomli_w.dumps(
            {
                "version": "1",
                valid_key: valid_entry,
                invalid_fps_key: invalid_fps_entry,
                overflowing_frame_key: overflowing_frame_entry,
            }
        )
        + f"""\n["oversized"]\npath = "oversized.mkv"\nsize_bytes = 0x{huge_hex}\nmtime_ns = 100\nwidth = 1920\nheight = 1080\nnum_frames = 100\nfps_num = 24\nfps_den = 1\nis_hdr = false\n""",
        encoding="utf-8",
    )

    loaded = load_clip_probe_cache(path)

    assert set(loaded) == {valid_key}
    assert loaded[valid_key].fingerprint.mtime_ns == -1


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


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("x = " + "{x=" * 1500 + "0" + "}" * 1500, id="deep"),
        pytest.param("x = " + "1" * 5000, id="integer-limit"),
    ],
)
def test_parser_limits_read_as_miss(tmp_path: Path, content: str) -> None:
    path = tmp_path / "probe.toml"
    path.write_text(content, encoding="utf-8")
    with patch("frame_compare.orchestration.probing.probe_cache.log.warning") as warning:
        assert load_clip_probe_cache(path) == {}
    warning.assert_called_once()


@pytest.mark.parametrize("token", [None, "", "a" * 63, "a" * 65, "z" * 64, 42])
def test_legacy_or_malformed_source_token_cannot_authorize_reuse(
    tmp_path: Path, token: object
) -> None:
    key, entry = _entry()
    if token is None:
        entry.pop("source_token")
    else:
        entry["source_token"] = token
    path = tmp_path / "legacy.toml"
    path.write_text(tomli_w.dumps({"version": "1", key: entry}), encoding="utf-8")
    assert load_clip_probe_cache(path) == {}


def test_schema_three_key_cannot_reauthorize_snapshot(tmp_path: Path) -> None:
    import hashlib
    import json

    from frame_compare.vs.runtime_contract import media_runtime_fingerprint

    _, entry = _entry()
    old_payload = {
        "path": entry["path"],
        "size_bytes": entry["size_bytes"],
        "mtime_ns": entry["mtime_ns"],
        "schema_version": 3,
        "media_runtime_fingerprint": media_runtime_fingerprint("probe"),
    }
    old_key = hashlib.blake2s(
        json.dumps(old_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "schema-three.toml"
    path.write_text(tomli_w.dumps({"version": "1", old_key: entry}), encoding="utf-8")
    assert load_clip_probe_cache(path) == {}
