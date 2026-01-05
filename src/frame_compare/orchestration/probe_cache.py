"""Probe snapshot cache keying logic and I/O."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import structlog
import tomli_w

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.vs.types import HDRMetadata

log = structlog.get_logger()


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


def load_clip_probe_cache(cache_path: Path) -> dict[str, ClipProbeSnapshot]:
    """Load probe cache from TOML file.

    Returns empty dict on missing file, parse error, or version mismatch (warn-only).
    Skips invalid entries (warn-only).
    """
    if not cache_path.exists():
        return {}

    try:
        with cache_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        log.warning("probe_cache_parse_error", path=str(cache_path), error=str(e))
        return {}

    if str(data.get("version")) != "1":
        log.warning(
            "probe_cache_version_mismatch",
            path=str(cache_path),
            found=data.get("version"),
            expected="1",
        )
        return {}

    snapshots: dict[str, ClipProbeSnapshot] = {}

    for key, entry_raw in data.items():
        if key == "version":
            continue

        if not isinstance(entry_raw, dict):
            continue

        entry = cast(dict[str, Any], entry_raw)

        try:
            # Reconstruct fingerprint (needed for snapshot)
            fingerprint = ClipFingerprint(
                path=Path(str(entry["path"])),
                size_bytes=int(entry["size_bytes"]),
                mtime_ns=int(entry["mtime_ns"]),
            )

            # Reconstruct HDR metadata if present (from nested hdr_metadata table per SSOT)
            hdr_metadata: HDRMetadata | None = None
            if entry.get("is_hdr"):
                hdr_table_raw = entry.get("hdr_metadata")
                if isinstance(hdr_table_raw, dict):
                    # Cast for type safety; load from nested table per SSOT §3.5.1
                    hdr_table = cast(dict[str, Any], hdr_table_raw)
                    hdr_metadata = HDRMetadata(
                        mastering_display=cast(str | None, hdr_table.get("mastering_display")),
                        max_cll=cast(int | None, hdr_table.get("max_cll")),
                        max_fall=cast(int | None, hdr_table.get("max_fall")),
                        color_primaries=int(hdr_table.get("color_primaries", 2)),
                        transfer=int(hdr_table.get("transfer", 2)),
                        matrix=int(hdr_table.get("matrix", 2)),
                    )

            snapshots[key] = ClipProbeSnapshot(
                fingerprint=fingerprint,
                width=int(entry["width"]),
                height=int(entry["height"]),
                num_frames=int(entry["num_frames"]),
                fps=Fraction(int(entry["fps_num"]), int(entry["fps_den"])),
                is_hdr=bool(entry["is_hdr"]),
                hdr_metadata=hdr_metadata,
                preserved_frame_props=cast(
                    dict[str, str | int | float], entry.get("preserved_frame_props", {})
                ),
                tonemap_prop_keys=tuple(cast(list[str], entry.get("tonemap_prop_keys", []))),
            )
        except (KeyError, TypeError, ValueError) as e:
            log.warning("probe_cache_invalid_entry", key=key, error=str(e))
            continue

    return snapshots


def save_clip_probe_cache(
    cache_path: Path, entries_by_key: Mapping[str, ClipProbeSnapshot]
) -> None:
    """Save probe cache to TOML file (overwrites).

    Enforces stable ordering and primitive-only preserved props.
    """
    output: dict[str, Any] = {"version": "1"}

    # Sort keys for deterministic output
    for key in sorted(entries_by_key.keys()):
        snapshot = entries_by_key[key]
        fp = snapshot.fingerprint

        # Invariant check
        if snapshot.is_hdr and snapshot.hdr_metadata is None:
            raise ValueError(f"Snapshot {key} is_hdr=True but hdr_metadata is None")

        entry: dict[str, Any] = {
            "path": str(fp.path),
            "size_bytes": fp.size_bytes,
            "mtime_ns": fp.mtime_ns,
            "width": snapshot.width,
            "height": snapshot.height,
            "num_frames": snapshot.num_frames,
            "fps_num": snapshot.fps.numerator,
            "fps_den": snapshot.fps.denominator,
            "is_hdr": snapshot.is_hdr,
            "tonemap_prop_keys": list(snapshot.tonemap_prop_keys),
        }

        # Sanitize preserved_frame_props (str|int|float only)
        # We perform runtime validation to ensure only TOML-safe primitives are persisted,
        # even if the in-memory type hint was bypassed.
        safe_props: dict[str, str | int | float] = {}
        for k, v in snapshot.preserved_frame_props.items():
            # Use cast to Any to avoid "Unnecessary isinstance" warning while being defensive
            if isinstance(cast(Any, v), str | int | float):
                safe_props[k] = v
        entry["preserved_frame_props"] = safe_props

        # Per SSOT §3.5.1: is_hdr=true → nested hdr_metadata table; is_hdr=false → omit
        if snapshot.is_hdr and snapshot.hdr_metadata:
            md = snapshot.hdr_metadata
            entry["hdr_metadata"] = {
                "mastering_display": md.mastering_display,
                "max_cll": md.max_cll,
                "max_fall": md.max_fall,
                "color_primaries": md.color_primaries,
                "transfer": md.transfer,
                "matrix": md.matrix,
            }

        output[key] = entry

    # SSOT §3.5.1: This helper MUST create parent directories if missing
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with cache_path.open("wb") as f:
        tomli_w.dump(output, f)
