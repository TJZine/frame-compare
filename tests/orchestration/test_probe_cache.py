"""Unit tests for probe cache keying logic."""

from pathlib import Path

from frame_compare.orchestration.context import ClipFingerprint
from frame_compare.orchestration.probe_cache import compute_probe_cache_key


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
