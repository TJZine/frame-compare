"""Unit tests for probe cache keying logic and I/O."""

import tomllib
from fractions import Fraction
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
import tomli_w

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.orchestration.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.vs.types import HDRMetadata

# ============================================================================
# Keying Tests
# ============================================================================


def test_compute_probe_cache_key_stable_for_same_fingerprint():
    """Verify that identical fingerprints produce the same key."""
    fp1 = ClipFingerprint(Path("video.mkv"), 1024, 5000)
    fp2 = ClipFingerprint(Path("video.mkv"), 1024, 5000)

    key1 = compute_probe_cache_key(fp1)
    key2 = compute_probe_cache_key(fp2)

    assert key1 == key2
    assert isinstance(key1, str)
    assert len(key1) > 0


def test_probe_cache_invalidates_on_fingerprint_change():
    """Verify that changing any fingerprint field changes the key."""
    base_fp = ClipFingerprint(Path("video.mkv"), 1024, 5000)
    base_key = compute_probe_cache_key(base_fp)

    # Change path
    fp_path = ClipFingerprint(Path("other.mkv"), 1024, 5000)
    assert compute_probe_cache_key(fp_path) != base_key

    # Change size
    fp_size = ClipFingerprint(Path("video.mkv"), 2048, 5000)
    assert compute_probe_cache_key(fp_size) != base_key

    # Change mtime
    fp_mtime = ClipFingerprint(Path("video.mkv"), 1024, 6000)
    assert compute_probe_cache_key(fp_mtime) != base_key


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_snapshot() -> ClipProbeSnapshot:
    """Return a standard SDR snapshot."""
    fp = ClipFingerprint(Path("video.mkv"), 1024, 5000)
    # Use cast to Any to bypass type checking for the test case that
    # intentionally provides "dirty" data for sanitization verification.
    return ClipProbeSnapshot(
        fingerprint=fp,
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24000, 1001),
        is_hdr=False,
        preserved_frame_props=cast(Any, {"some_prop": 1.0, "bad_prop": [1, 2]}),
        tonemap_prop_keys=("props",),
    )


@pytest.fixture
def hdr_snapshot() -> ClipProbeSnapshot:
    """Return a standard HDR snapshot."""
    fp = ClipFingerprint(Path("hdr.mkv"), 2048, 6000)
    metadata = HDRMetadata(
        mastering_display="G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)",
        max_cll=1000,
        max_fall=400,
        color_primaries=9,
        transfer=16,
        matrix=9,
    )
    return ClipProbeSnapshot(
        fingerprint=fp,
        width=3840,
        height=2160,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=True,
        hdr_metadata=metadata,
        preserved_frame_props={"scenecut": 1},
        tonemap_prop_keys=("masteringdisplay",),
    )


# ============================================================================
# Load Tests
# ============================================================================


def test_load_clip_probe_cache_returns_empty_dict_on_missing_file(tmp_path: Path):
    """Missing file -> empty dict."""
    cache = load_clip_probe_cache(tmp_path / "missing.toml")
    assert cache == {}


def test_load_clip_probe_cache_returns_empty_dict_on_parse_error(tmp_path: Path):
    """Invalid TOML -> empty dict."""
    f = tmp_path / "invalid.toml"
    f.write_text("invalid [ toml", encoding="utf-8")
    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_returns_empty_dict_on_read_os_error(tmp_path: Path):
    """Plain filesystem read failures degrade like corrupt generated state."""
    f = tmp_path / "unreadable.toml"
    f.write_text('version = "1"', encoding="utf-8")

    with (
        patch("pathlib.Path.open", side_effect=OSError("permission denied")),
        patch("frame_compare.orchestration.probe_cache.log.warning") as warning,
    ):
        cache = load_clip_probe_cache(f)

    assert cache == {}
    warning.assert_called_once()
    assert warning.call_args.args[0] == "probe_cache_read_error"


def test_load_clip_probe_cache_returns_empty_dict_on_version_mismatch(tmp_path: Path):
    """Wrong version -> empty dict."""
    f = tmp_path / "version.toml"
    with f.open("wb") as out:
        tomli_w.dump({"version": "2", "foo": {}}, out)

    cache = load_clip_probe_cache(f)
    assert cache == {}


def test_load_clip_probe_cache_returns_empty_dict_on_missing_version(tmp_path: Path):
    """Missing version -> empty dict."""
    f = tmp_path / "missing_version.toml"
    with f.open("wb") as out:
        tomli_w.dump({"foo": {}}, out)

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

    cache = load_clip_probe_cache(f)
    assert len(cache) == 1
    assert "valid_key" in cache
    assert cache["valid_key"].width == 100


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


# ============================================================================
# Save Tests
# ============================================================================


def test_save_clip_probe_cache_raises_when_is_hdr_true_but_hdr_metadata_missing(tmp_path: Path):
    """Invariant: is_hdr=True requires metadata."""
    fp = ClipFingerprint(Path("bad.mkv"), 0, 0)
    bad_snap = ClipProbeSnapshot(
        fingerprint=fp,
        width=1,
        height=1,
        num_frames=1,
        fps=Fraction(1, 1),
        is_hdr=True,
        hdr_metadata=None,
    )

    with pytest.raises(ValueError, match="is_hdr=True but hdr_metadata is None"):
        save_clip_probe_cache(tmp_path / "out.toml", {"key": bad_snap})


def test_save_clip_probe_cache_creates_parent_directories(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
):
    """SSOT §3.5.1: save_clip_probe_cache MUST create parent directories."""
    nested_path = tmp_path / "deep" / "nested" / "cache.toml"
    assert not nested_path.parent.exists()

    key = compute_probe_cache_key(sample_snapshot.fingerprint)
    save_clip_probe_cache(nested_path, {key: sample_snapshot})

    assert nested_path.exists()


def test_save_clip_probe_cache_writes_version_first_and_keys_sorted(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
):
    """Version header must be first and table keys must be sorted."""
    f = tmp_path / "ordering.toml"

    key_a = "a_key"
    key_b = "b_key"

    entries = {
        key_b: sample_snapshot,
        key_a: sample_snapshot,
    }

    save_clip_probe_cache(f, entries)

    contents = f.read_text(encoding="utf-8")
    lines = [line for line in contents.splitlines() if line.strip()]

    assert lines[0].startswith('version = "1"')
    assert contents.index(f"[{key_a}]") < contents.index(f"[{key_b}]")


def test_save_clip_probe_cache_logs_and_continues_on_write_os_error(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
) -> None:
    """Probe cache writes are best-effort generated-state acceleration."""
    f = tmp_path / "unwritable" / "cache.toml"
    key = compute_probe_cache_key(sample_snapshot.fingerprint)

    with (
        patch("pathlib.Path.open", side_effect=OSError("disk full")),
        patch("frame_compare.orchestration.probe_cache.log.warning") as warning,
    ):
        save_clip_probe_cache(f, {key: sample_snapshot})

    assert warning.call_args.args[0] == "probe_cache_write_error"


# ============================================================================
# Round-Trip Tests
# ============================================================================


def test_probe_cache_round_trip_toml(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot, hdr_snapshot: ClipProbeSnapshot
):
    """Full round-trip test."""
    f = tmp_path / "roundtrip.toml"

    key_sdr = compute_probe_cache_key(sample_snapshot.fingerprint)
    key_hdr = compute_probe_cache_key(hdr_snapshot.fingerprint)

    entries = {key_sdr: sample_snapshot, key_hdr: hdr_snapshot}

    save_clip_probe_cache(f, entries)
    loaded = load_clip_probe_cache(f)

    assert len(loaded) == 2

    # Verify SDR
    sdr = loaded[key_sdr]
    assert sdr.width == sample_snapshot.width
    assert sdr.fps == sample_snapshot.fps
    assert sdr.preserved_frame_props == {"some_prop": 1.0}  # List was dropped
    assert sdr.tonemap_prop_keys == sample_snapshot.tonemap_prop_keys

    # Verify HDR
    hdr = loaded[key_hdr]
    assert hdr.is_hdr is True
    assert hdr.hdr_metadata is not None
    assert hdr_snapshot.hdr_metadata is not None
    assert hdr.hdr_metadata.max_cll == 1000
    assert hdr.hdr_metadata.mastering_display == hdr_snapshot.hdr_metadata.mastering_display


def test_preserved_frame_props_are_toml_safe_primitives_only(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
):
    """Sanitization test."""
    f = tmp_path / "sanitize.toml"
    # sample_snapshot has a list in preserved_frame_props
    key = compute_probe_cache_key(sample_snapshot.fingerprint)
    save_clip_probe_cache(f, {key: sample_snapshot})

    loaded = load_clip_probe_cache(f)
    props = loaded[key].preserved_frame_props

    assert "some_prop" in props  # float is safe
    assert "bad_prop" not in props  # list is unsafe


def test_save_clip_probe_cache_drops_bool_preserved_frame_props(tmp_path: Path) -> None:
    """bool is an int subclass, but persisted frame props treat booleans as unsafe."""
    f = tmp_path / "bool_props.toml"
    snapshot = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path("video.mkv"), 1024, 5000),
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24000, 1001),
        is_hdr=False,
        preserved_frame_props=cast(Any, {"keep_int": 1, "drop_bool": True}),
        tonemap_prop_keys=(),
    )
    key = compute_probe_cache_key(snapshot.fingerprint)

    save_clip_probe_cache(f, {key: snapshot})
    loaded = load_clip_probe_cache(f)

    assert loaded[key].preserved_frame_props == {"keep_int": 1}


def test_hdr_metadata_persisted_as_nested_table(tmp_path: Path, hdr_snapshot: ClipProbeSnapshot):
    """SSOT §3.5.1: hdr_metadata MUST be a nested table, not flattened fields."""
    f = tmp_path / "hdr_nested.toml"
    key = compute_probe_cache_key(hdr_snapshot.fingerprint)

    save_clip_probe_cache(f, {key: hdr_snapshot})

    # Read raw TOML to verify structure
    with f.open("rb") as fh:
        raw_data = tomllib.load(fh)

    entry = raw_data[key]

    # MUST have nested hdr_metadata table
    assert "hdr_metadata" in entry
    assert isinstance(entry["hdr_metadata"], dict)

    # HDR fields MUST NOT be flattened at entry level
    assert "color_primaries" not in entry
    assert "transfer" not in entry
    assert "matrix" not in entry
    assert "mastering_display" not in entry
    assert "max_cll" not in entry
    assert "max_fall" not in entry

    # Nested table has correct values
    hdr_table = entry["hdr_metadata"]
    assert hdr_table["color_primaries"] == 9
    assert hdr_table["transfer"] == 16
    assert hdr_table["matrix"] == 9
    assert hdr_table["max_cll"] == 1000
    assert hdr_table["max_fall"] == 400


def test_hdr_metadata_with_optional_fields_none_is_toml_serializable(tmp_path: Path):
    """Regression test: TOML writer must never see None values (tomli_w cannot serialize None)."""
    fp = ClipFingerprint(Path("hdr_optional_none.mkv"), 1, 1)
    snapshot = ClipProbeSnapshot(
        fingerprint=fp,
        width=3840,
        height=2160,
        num_frames=1,
        fps=Fraction(24, 1),
        is_hdr=True,
        hdr_metadata=HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=2,
            transfer=2,
            matrix=2,
        ),
        preserved_frame_props={},
        tonemap_prop_keys=(),
    )

    f = tmp_path / "hdr_optional_none.toml"
    key = compute_probe_cache_key(snapshot.fingerprint)
    save_clip_probe_cache(f, {key: snapshot})

    with f.open("rb") as fh:
        raw_data = tomllib.load(fh)

    hdr_table = cast(dict[str, Any], raw_data[key]["hdr_metadata"])
    assert hdr_table["color_primaries"] == 2
    assert hdr_table["transfer"] == 2
    assert hdr_table["matrix"] == 2
    assert "mastering_display" not in hdr_table
    assert "max_cll" not in hdr_table
    assert "max_fall" not in hdr_table

    loaded = load_clip_probe_cache(f)[key]
    assert loaded.hdr_metadata is not None
    assert loaded.hdr_metadata.mastering_display is None
    assert loaded.hdr_metadata.max_cll is None
    assert loaded.hdr_metadata.max_fall is None
