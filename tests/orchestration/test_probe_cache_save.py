"""Unit tests for probe cache keying logic and I/O."""

from fractions import Fraction
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    merge_shared_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.vs.types import HDRMetadata


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


def test_save_clip_probe_cache_atomic_write_failure_preserves_existing_cache(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
) -> None:
    """Probe cache writes are best-effort generated-state acceleration."""
    f = tmp_path / "cache.toml"
    existing = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path("existing.mkv"), 2048, 6000),
        width=1280,
        height=720,
        num_frames=50,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    existing_key = compute_probe_cache_key(existing.fingerprint)
    current_key = compute_probe_cache_key(sample_snapshot.fingerprint)
    save_clip_probe_cache(f, {existing_key: existing})

    with (
        patch(
            "frame_compare.orchestration.probing.probe_cache.write_bytes_atomic",
            side_effect=OSError("disk full"),
        ),
        patch("frame_compare.orchestration.probing.probe_cache.log.warning") as warning,
    ):
        save_clip_probe_cache(f, {current_key: sample_snapshot})

    assert warning.call_args.args[0] == "probe_cache_write_error"
    assert set(load_clip_probe_cache(f)) == {existing_key}


def test_merge_shared_clip_probe_cache_lock_failure_warns_without_replacing(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
) -> None:
    f = tmp_path / "cache.toml"
    existing = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path("existing.mkv"), 2048, 6000),
        width=1280,
        height=720,
        num_frames=50,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    existing_key = compute_probe_cache_key(existing.fingerprint)
    current_key = compute_probe_cache_key(sample_snapshot.fingerprint)
    save_clip_probe_cache(f, {existing_key: existing})

    with (
        patch(
            "frame_compare.orchestration.probing.probe_cache.exclusive_file_lock",
            side_effect=OSError("lock unavailable"),
        ),
        patch("frame_compare.orchestration.probing.probe_cache.log.warning") as warning,
    ):
        merge_shared_clip_probe_cache(f, {current_key: sample_snapshot})

    assert warning.call_args.args[0] == "probe_cache_write_error"
    assert set(load_clip_probe_cache(f)) == {existing_key}


def test_merge_shared_clip_probe_cache_read_failure_aborts_without_replacing(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
) -> None:
    f = tmp_path / "cache.toml"
    existing = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path("existing.mkv"), 2048, 6000),
        width=1280,
        height=720,
        num_frames=50,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    existing_key = compute_probe_cache_key(existing.fingerprint)
    current_key = compute_probe_cache_key(sample_snapshot.fingerprint)
    save_clip_probe_cache(f, {existing_key: existing})
    existing_bytes = f.read_bytes()

    with (
        patch(
            "frame_compare.orchestration.probing.probe_cache.tomllib.load",
            side_effect=PermissionError("temporarily unavailable"),
        ),
        patch("frame_compare.orchestration.probing.probe_cache.write_bytes_atomic") as atomic_write,
        patch("frame_compare.orchestration.probing.probe_cache.log.warning") as warning,
    ):
        merge_shared_clip_probe_cache(f, {current_key: sample_snapshot})

    assert f.read_bytes() == existing_bytes
    assert set(load_clip_probe_cache(f)) == {existing_key}
    assert warning.call_args_list[0].args[0] == "probe_cache_read_error"
    assert [call.args[0] for call in warning.call_args_list] == ["probe_cache_read_error"]
    atomic_write.assert_not_called()


@pytest.mark.parametrize(
    "existing_content",
    [
        pytest.param("invalid [ toml", id="malformed-toml"),
        pytest.param('version = "2"\n', id="version-mismatch"),
    ],
)
def test_merge_shared_clip_probe_cache_invalid_state_aborts_without_replacing(
    tmp_path: Path,
    sample_snapshot: ClipProbeSnapshot,
    existing_content: str,
) -> None:
    cache_path = tmp_path / "cache.toml"
    cache_path.write_text(existing_content, encoding="utf-8")
    existing_bytes = cache_path.read_bytes()
    current_key = compute_probe_cache_key(sample_snapshot.fingerprint)

    with patch(
        "frame_compare.orchestration.probing.probe_cache.write_bytes_atomic"
    ) as atomic_write:
        merge_shared_clip_probe_cache(cache_path, {current_key: sample_snapshot})

    assert cache_path.read_bytes() == existing_bytes
    atomic_write.assert_not_called()


def test_save_clip_probe_cache_creates_parent_directories(
    tmp_path: Path, sample_snapshot: ClipProbeSnapshot
):
    """SSOT §3.5.1: save_clip_probe_cache MUST create parent directories."""
    nested_path = tmp_path / "deep" / "nested" / "cache.toml"
    assert not nested_path.parent.exists()

    key = compute_probe_cache_key(sample_snapshot.fingerprint)
    save_clip_probe_cache(nested_path, {key: sample_snapshot})

    assert nested_path.exists()
