"""Probe snapshot cache keying logic."""

import hashlib
import json
from typing import Any

from frame_compare.orchestration.context import ClipFingerprint


def compute_probe_cache_key(fingerprint: ClipFingerprint) -> str:
    """Return a stable key for clip probe cache entries.

    The key is derived solely from the ClipFingerprint (path, size, mtime)
    and a schema version. It is independent of trim state.

    Serialization uses canonical JSON settings (sorted keys, no spaces)
    to ensure cross-platform determinism.
    """
    payload: dict[str, Any] = {
        "path": str(fingerprint.path),
        "size_bytes": fingerprint.size_bytes,
        "mtime_ns": fingerprint.mtime_ns,
        "schema_version": 1,
    }

    # SSOT: json.dumps(..., sort_keys=True, separators=(",", ":"))
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    # SSOT: blake2s hex digest of UTF-8 bytes
    return hashlib.blake2s(serialized.encode("utf-8")).hexdigest()
