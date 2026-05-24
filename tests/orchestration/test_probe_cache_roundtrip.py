"""Unit tests for probe cache keying logic and I/O."""

import tomllib
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.vs.types import HDRMetadata


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
