"""Unit tests for probe cache keying logic and I/O."""

import os
from pathlib import Path

import frame_compare.orchestration.probing.probe_cache as probe_cache
from frame_compare.orchestration.context import ClipFingerprint
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
)


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


def test_live_probe_key_invalidates_same_size_and_mtime_replacement(tmp_path: Path) -> None:
    video = tmp_path / "video.mkv"
    fixed_mtime_ns = 1_704_067_200_000_000_000
    video.write_bytes(b"original")
    os.utime(video, ns=(fixed_mtime_ns, fixed_mtime_ns))
    original = probe_cache.live_probe_fingerprint(video).fingerprint
    video.write_bytes(b"replaced")
    os.utime(video, ns=(fixed_mtime_ns, fixed_mtime_ns))
    replaced = probe_cache.live_probe_fingerprint(video).fingerprint

    assert original.source_token is not None
    assert original.size_bytes == replaced.size_bytes
    assert original.mtime_ns == replaced.mtime_ns
    assert compute_probe_cache_key(original) != compute_probe_cache_key(replaced)


def test_probe_cache_key_changes_with_scoped_runtime_fingerprint(monkeypatch) -> None:
    fingerprint = ClipFingerprint(Path("video.mkv"), 1024, 5000)
    original = compute_probe_cache_key(fingerprint)

    observed_scopes: list[str] = []

    def _fingerprint(scope: str) -> str:
        observed_scopes.append(scope)
        return "f" * 64

    monkeypatch.setattr(probe_cache, "media_runtime_fingerprint", _fingerprint)

    assert compute_probe_cache_key(fingerprint) != original
    assert observed_scopes == ["probe"]
