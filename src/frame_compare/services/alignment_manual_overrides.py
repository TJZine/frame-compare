"""Manual alignment override schema and run-scoped persistence.

This module provides persistence for user-provided alignment overrides
stored in `{cache_dir}/manual_overrides.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import structlog
import tomli_w

from frame_compare.utils.atomic_write import write_bytes_atomic

MANUAL_OVERRIDES_VERSION = "1"
MANUAL_OVERRIDES_FILE = "manual_overrides.toml"

log = structlog.get_logger()


@dataclass(frozen=True)
class ManualOverride:
    """User-confirmed alignment override from an interactive review session.

    Attributes:
        reference_clip: Path stem of reference clip
        comparison_clip: Path stem of comparison clip
        frame_offset: User-confirmed signed frame offset (comparison-relative-to-reference)
        timestamp: ISO 8601 timestamp when override was recorded
        confirmed: True if user explicitly confirmed computed offset
    """

    reference_clip: str
    comparison_clip: str
    frame_offset: int
    timestamp: str
    confirmed: bool = True


def load_manual_overrides(cache_dir: Path) -> dict[str, ManualOverride]:
    """Load valid persisted manual overrides from cache."""
    cache_path = cache_dir / MANUAL_OVERRIDES_FILE
    data = _read_manual_overrides(cache_path)

    if data is None:
        return {}

    if not _has_supported_manual_override_version(data, cache_path):
        return {}

    result: dict[str, ManualOverride] = {}
    for key, entry in data.items():
        if key == "version":
            continue
        if not isinstance(entry, dict):
            continue

        try:
            result[key] = _manual_override_from_entry(cast(dict[str, object], entry))
        except (TypeError, KeyError) as e:
            log.warning(
                "manual_overrides_entry_invalid",
                key=key,
                error=str(e),
            )

    return result


def _read_manual_overrides(cache_path: Path) -> dict[str, object] | None:
    try:
        if not cache_path.exists():
            return None
        with cache_path.open("rb") as f:
            return cast(dict[str, object], tomllib.load(f))
    except OSError as e:
        log.warning(
            "manual_overrides_read_error",
            path=str(cache_path),
            error=str(e),
        )
        return None
    except tomllib.TOMLDecodeError as e:
        log.warning(
            "manual_overrides_parse_error",
            path=str(cache_path),
            error=str(e),
        )
        return None


def _has_supported_manual_override_version(data: dict[str, object], cache_path: Path) -> bool:
    version = data.get("version")
    if version == MANUAL_OVERRIDES_VERSION:
        return True

    log.warning(
        "manual_overrides_version_mismatch",
        path=str(cache_path),
        found=version,
        expected=MANUAL_OVERRIDES_VERSION,
    )
    return False


def _manual_override_from_entry(entry: dict[str, object]) -> ManualOverride:
    ref_clip = entry.get("reference_clip")
    comp_clip = entry.get("comparison_clip")
    frame_off = entry.get("frame_offset")
    ts = entry.get("timestamp")
    conf = entry.get("confirmed", True)

    if not isinstance(ref_clip, str):
        raise TypeError("reference_clip must be str")
    if not isinstance(comp_clip, str):
        raise TypeError("comparison_clip must be str")
    if not isinstance(frame_off, int) or isinstance(frame_off, bool):
        raise TypeError("frame_offset must be int")
    if not isinstance(ts, str):
        raise TypeError("timestamp must be str")
    if not isinstance(conf, bool):
        raise TypeError("confirmed must be bool")

    return ManualOverride(
        reference_clip=ref_clip,
        comparison_clip=comp_clip,
        frame_offset=frame_off,
        timestamp=ts,
        confirmed=conf,
    )


def save_manual_override(cache_dir: Path, override: ManualOverride) -> None:
    """Persist one manual override, merging with valid existing entries."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.warning(
            "manual_overrides_write_error",
            path=str(cache_dir / MANUAL_OVERRIDES_FILE),
            error=str(e),
        )
        return

    cache_path = cache_dir / MANUAL_OVERRIDES_FILE

    data: dict[str, object] = {"version": MANUAL_OVERRIDES_VERSION}
    try:
        cache_exists = cache_path.exists()
    except OSError as e:
        log.warning(
            "manual_overrides_read_existing_error",
            path=str(cache_path),
            error=str(e),
        )
        cache_exists = False
    if cache_exists:
        try:
            with cache_path.open("rb") as f:
                existing = tomllib.load(f)
                if existing.get("version") == MANUAL_OVERRIDES_VERSION:
                    data.update(existing)
        except OSError as e:
            log.warning(
                "manual_overrides_read_existing_error",
                path=str(cache_path),
                error=str(e),
            )
        except tomllib.TOMLDecodeError:
            log.warning(
                "manual_overrides_corrupt_on_write",
                path=str(cache_path),
            )

    key = f"{override.reference_clip}:{override.comparison_clip}"
    entry = {
        "reference_clip": override.reference_clip,
        "comparison_clip": override.comparison_clip,
        "frame_offset": override.frame_offset,
        "timestamp": override.timestamp,
        "confirmed": override.confirmed,
    }
    data[key] = entry

    ordered: dict[str, object] = {"version": MANUAL_OVERRIDES_VERSION}
    for k in sorted(key for key in data if key != "version"):
        ordered[k] = data[k]

    try:
        write_bytes_atomic(cache_path, tomli_w.dumps(ordered).encode("utf-8"))
    except OSError as e:
        log.warning(
            "manual_overrides_write_error",
            path=str(cache_path),
            error=str(e),
        )
