"""Probe snapshot cache keying logic and I/O."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, TypeGuard, cast

import structlog
import tomli_w

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.vs.runtime_contract import media_runtime_fingerprint
from frame_compare.vs.types import HDRMetadata

log = structlog.get_logger()

type PrimitiveFrameProp = str | int | float


@dataclass(frozen=True)
class _CacheEntryLoadOutcome:
    snapshot: ClipProbeSnapshot | None
    warning: str | None = None


@dataclass(frozen=True)
class _CacheWriteOutcome:
    error: str | None = None


class _ProbeCacheReadError(Exception):
    """Signal that a shared update must abort after a cache read failure."""


def _mapping_has_only_str_keys(mapping: Mapping[object, object]) -> bool:
    keys = list(mapping)
    return all(isinstance(key, str) for key in keys)


def _is_str_key_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    if not isinstance(value, Mapping):
        return False
    return _mapping_has_only_str_keys(cast(Mapping[object, object], value))


def _is_non_bool_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _sanitize_hdr_metadata(entry: Mapping[str, object]) -> HDRMetadata:
    mastering_display_raw = entry.get("mastering_display")
    mastering_display = mastering_display_raw if isinstance(mastering_display_raw, str) else None

    max_cll_raw = entry.get("max_cll")
    max_cll = max_cll_raw if _is_non_bool_int(max_cll_raw) else None

    max_fall_raw = entry.get("max_fall")
    max_fall = max_fall_raw if _is_non_bool_int(max_fall_raw) else None

    color_primaries_raw = entry.get("color_primaries")
    color_primaries = color_primaries_raw if _is_non_bool_int(color_primaries_raw) else 2

    transfer_raw = entry.get("transfer")
    transfer = transfer_raw if _is_non_bool_int(transfer_raw) else 2

    matrix_raw = entry.get("matrix")
    matrix = matrix_raw if _is_non_bool_int(matrix_raw) else 2

    return HDRMetadata(
        mastering_display=mastering_display,
        max_cll=max_cll,
        max_fall=max_fall,
        color_primaries=color_primaries,
        transfer=transfer,
        matrix=matrix,
    )


def _sanitize_preserved_frame_props(value: object) -> dict[str, PrimitiveFrameProp]:
    if value is None:
        return {}
    if not _is_str_key_mapping(value):
        raise TypeError("preserved_frame_props must be a table")

    sanitized: dict[str, PrimitiveFrameProp] = {}
    for key, prop_value in value.items():
        if isinstance(prop_value, str | float) or _is_non_bool_int(prop_value):
            sanitized[key] = prop_value
    return sanitized


def _sanitize_tonemap_prop_keys(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise TypeError("tonemap_prop_keys must be an array")

    sanitized: list[str] = []
    sequence = cast(Sequence[object], value)
    for item in sequence:
        if isinstance(item, str):
            sanitized.append(item)
    return tuple(sanitized)


def _require_int(entry: Mapping[str, object], field: str) -> int:
    value = entry[field]
    if not _is_non_bool_int(value):
        raise TypeError(f"{field} must be an integer")
    return value


def _require_bool(entry: Mapping[str, object], field: str) -> bool:
    value = entry[field]
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a boolean")
    return value


def _load_fps(entry: Mapping[str, object]) -> Fraction:
    fps_num = _require_int(entry, "fps_num")
    fps_den = _require_int(entry, "fps_den")
    if fps_den == 0:
        raise ValueError("fps_den must be non-zero")
    return Fraction(fps_num, fps_den)


def _load_cache_entry(entry_raw: object) -> _CacheEntryLoadOutcome:
    if not _is_str_key_mapping(entry_raw):
        return _CacheEntryLoadOutcome(
            snapshot=None,
            warning="entry must be a table",
        )
    entry = entry_raw

    try:
        fingerprint = ClipFingerprint(
            path=Path(str(entry["path"])),
            size_bytes=_require_int(entry, "size_bytes"),
            mtime_ns=_require_int(entry, "mtime_ns"),
        )

        is_hdr = _require_bool(entry, "is_hdr")
        hdr_metadata: HDRMetadata | None = None
        if is_hdr:
            hdr_table_raw = entry.get("hdr_metadata")
            if hdr_table_raw is None:
                raise TypeError("hdr_metadata must be a table when is_hdr is true")
            if not _is_str_key_mapping(hdr_table_raw):
                raise TypeError("hdr_metadata must be a table")
            hdr_metadata = _sanitize_hdr_metadata(hdr_table_raw)

        return _CacheEntryLoadOutcome(
            snapshot=ClipProbeSnapshot(
                fingerprint=fingerprint,
                width=_require_int(entry, "width"),
                height=_require_int(entry, "height"),
                num_frames=_require_int(entry, "num_frames"),
                fps=_load_fps(entry),
                is_hdr=is_hdr,
                hdr_metadata=hdr_metadata,
                preserved_frame_props=_sanitize_preserved_frame_props(
                    entry.get("preserved_frame_props")
                ),
                tonemap_prop_keys=_sanitize_tonemap_prop_keys(entry.get("tonemap_prop_keys")),
            )
        )
    except (KeyError, TypeError, ValueError) as e:
        return _CacheEntryLoadOutcome(snapshot=None, warning=str(e))


def compute_probe_cache_key(fingerprint: ClipFingerprint) -> str:
    """Return a stable key for clip probe cache entries.

    The key is derived from the ClipFingerprint (path, size, mtime), the
    probe-key schema, and the supported decoder runtime identity. It is
    independent of trim state and intentionally does not hash media contents.

    Serialization uses canonical JSON settings (sorted keys, no spaces)
    to ensure cross-platform determinism.
    """
    payload: dict[str, Any] = {
        "path": str(fingerprint.path),
        "size_bytes": fingerprint.size_bytes,
        "mtime_ns": fingerprint.mtime_ns,
        "schema_version": 2,
        "media_runtime_fingerprint": media_runtime_fingerprint("probe"),
    }

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return hashlib.blake2s(serialized.encode("utf-8")).hexdigest()


def _load_clip_probe_cache(
    cache_path: Path, *, abort_on_read_error: bool
) -> dict[str, ClipProbeSnapshot]:
    try:
        with cache_path.open("rb") as f:
            data: dict[str, object] = tomllib.load(f)
    except FileNotFoundError:
        return {}
    except OSError as e:
        log.warning("probe_cache_read_error", path=str(cache_path), error=str(e))
        if abort_on_read_error:
            raise _ProbeCacheReadError from e
        return {}
    except tomllib.TOMLDecodeError as e:
        log.warning("probe_cache_parse_error", path=str(cache_path), error=str(e))
        if abort_on_read_error:
            raise _ProbeCacheReadError("Malformed shared probe cache") from e
        return {}

    found_version = str(data.get("version"))
    if found_version != "1":
        log.warning(
            "probe_cache_version_mismatch",
            path=str(cache_path),
            found=data.get("version"),
            expected="1",
        )
        if abort_on_read_error:
            raise _ProbeCacheReadError(f"Unsupported shared probe cache version: {found_version!r}")
        return {}

    snapshots: dict[str, ClipProbeSnapshot] = {}

    for key, entry_raw in data.items():
        if key == "version":
            continue

        outcome = _load_cache_entry(entry_raw)
        if outcome.snapshot is None:
            log.warning("probe_cache_invalid_entry", key=key, error=outcome.warning)
            continue

        snapshots[key] = outcome.snapshot

    return snapshots


def load_clip_probe_cache(cache_path: Path) -> dict[str, ClipProbeSnapshot]:
    """Load probe cache from TOML file.

    Returns empty dict on missing file, parse error, or version mismatch (warn-only).
    Skips invalid entries (warn-only).
    """
    return _load_clip_probe_cache(cache_path, abort_on_read_error=False)


def _load_shared_clip_probe_cache_for_update(
    cache_path: Path,
) -> dict[str, ClipProbeSnapshot]:
    """Load shared entries, aborting when existing state cannot be read safely."""
    return _load_clip_probe_cache(cache_path, abort_on_read_error=True)


def _write_cache_file(cache_path: Path, output: Mapping[str, Any]) -> _CacheWriteOutcome:
    try:
        content = tomli_w.dumps(output).encode("utf-8")
        write_bytes_atomic(cache_path, content)
    except OSError as e:
        return _CacheWriteOutcome(error=str(e))

    return _CacheWriteOutcome()


def save_clip_probe_cache(
    cache_path: Path, entries_by_key: Mapping[str, ClipProbeSnapshot]
) -> None:
    """Save probe cache to TOML file (overwrites).

    Enforces stable ordering and primitive-only preserved props.
    """
    output: dict[str, Any] = {"version": "1"}

    for key in sorted(entries_by_key.keys()):
        snapshot = entries_by_key[key]
        fp = snapshot.fingerprint

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

        # We perform runtime validation to ensure only TOML-safe primitives are persisted,
        # even if the in-memory type hint was bypassed.
        safe_props: dict[str, str | int | float] = {}
        dropped_props: dict[str, str] = {}
        dropped_count = 0
        for k, v in snapshot.preserved_frame_props.items():
            raw_value = cast(Any, v)
            # Use cast to Any to avoid "Unnecessary isinstance" warning while being defensive.
            # bool is an int subclass, but frame-prop persistence treats booleans as non-numeric.
            if isinstance(raw_value, str | float) or (
                isinstance(raw_value, int) and not isinstance(raw_value, bool)
            ):
                safe_props[k] = v
            else:
                dropped_count += 1
                if len(dropped_props) < 10:
                    dropped_props[k] = type(v).__name__
        entry["preserved_frame_props"] = safe_props
        if dropped_count:
            log.warning(
                "probe_cache_props_dropped",
                cache_key=key,
                dropped_count=dropped_count,
                dropped_props=dropped_props,
            )

        # TOML doesn't support None values, so we only include non-None fields
        if snapshot.is_hdr and snapshot.hdr_metadata:
            md = snapshot.hdr_metadata
            hdr_dict: dict[str, Any] = {
                "color_primaries": md.color_primaries,
                "transfer": md.transfer,
                "matrix": md.matrix,
            }
            if md.mastering_display is not None:
                hdr_dict["mastering_display"] = md.mastering_display
            if md.max_cll is not None:
                hdr_dict["max_cll"] = md.max_cll
            if md.max_fall is not None:
                hdr_dict["max_fall"] = md.max_fall
            entry["hdr_metadata"] = hdr_dict

        output[key] = entry

    outcome = _write_cache_file(cache_path, output)
    if outcome.error is not None:
        log.warning("probe_cache_write_error", path=str(cache_path), error=outcome.error)


def merge_shared_clip_probe_cache(
    cache_path: Path, current_entries: Mapping[str, ClipProbeSnapshot]
) -> None:
    """Merge current entries into a shared cache under one locked transaction."""
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    try:
        with exclusive_file_lock(lock_path):
            entries_by_key = _load_shared_clip_probe_cache_for_update(cache_path)
            entries_by_key.update(current_entries)
            save_clip_probe_cache(cache_path, entries_by_key)
    except _ProbeCacheReadError:
        return
    except OSError as e:
        log.warning("probe_cache_write_error", path=str(cache_path), error=str(e))
