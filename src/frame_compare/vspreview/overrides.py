"""Manual override cache schema and persistence helpers.

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

MANUAL_OVERRIDES_VERSION = "1"
MANUAL_OVERRIDES_FILE = "manual_overrides.toml"

log = structlog.get_logger()


@dataclass(frozen=True)
class ManualOverride:
    """User-provided alignment override from VSPreview session.

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
    """Load persisted manual overrides from cache.

    Args:
        cache_dir: Directory containing manual_overrides.toml

    Returns:
        Dict mapping "{ref_stem}:{comp_stem}" -> ManualOverride
        Empty dict if file does not exist, has parse errors, or version mismatch
    """
    cache_path = cache_dir / MANUAL_OVERRIDES_FILE

    try:
        if not cache_path.exists():
            return {}
        with cache_path.open("rb") as f:
            data = tomllib.load(f)
    except OSError as e:
        log.warning(
            "manual_overrides_read_error",
            path=str(cache_path),
            error=str(e),
        )
        return {}
    except tomllib.TOMLDecodeError as e:
        log.warning(
            "manual_overrides_parse_error",
            path=str(cache_path),
            error=str(e),
        )
        return {}

    # Check version
    version = data.get("version")
    if version != MANUAL_OVERRIDES_VERSION:
        log.warning(
            "manual_overrides_version_mismatch",
            path=str(cache_path),
            found=version,
            expected=MANUAL_OVERRIDES_VERSION,
        )
        return {}

    result: dict[str, ManualOverride] = {}
    for key, entry in data.items():
        if key == "version":
            continue
        if not isinstance(entry, dict):
            continue

        typed_entry = cast(dict[str, object], entry)
        try:
            ref_clip = typed_entry.get("reference_clip")
            comp_clip = typed_entry.get("comparison_clip")
            frame_off = typed_entry.get("frame_offset")
            ts = typed_entry.get("timestamp")
            conf = typed_entry.get("confirmed", True)

            # Strict isinstance checks
            if not isinstance(ref_clip, str):
                raise TypeError("reference_clip must be str")
            if not isinstance(comp_clip, str):
                raise TypeError("comparison_clip must be str")
            # frame_offset must be int and not a boolean (isinstance(True, int) is True in Python)
            if not isinstance(frame_off, int) or isinstance(frame_off, bool):
                raise TypeError("frame_offset must be int")
            if not isinstance(ts, str):
                raise TypeError("timestamp must be str")
            if not isinstance(conf, bool):
                raise TypeError("confirmed must be bool")

            override = ManualOverride(
                reference_clip=ref_clip,
                comparison_clip=comp_clip,
                frame_offset=frame_off,
                timestamp=ts,
                confirmed=conf,
            )
            result[key] = override
        except (TypeError, KeyError) as e:
            log.warning(
                "manual_overrides_entry_invalid",
                key=key,
                error=str(e),
            )
            # Skip invalid entries, continue with others

    return result


def save_manual_override(cache_dir: Path, override: ManualOverride) -> None:
    """Persist a manual override to cache.

    Args:
        cache_dir: Directory for manual_overrides.toml
        override: Override to save

    Behavior:
        - Creates file if not exists
        - Merges with existing overrides
        - Overwrites existing entry for same key
        - Writes with stable ordering (version first, then sorted keys)
    """
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

    # Load existing data
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
                # Only merge if version matches
                if existing.get("version") == MANUAL_OVERRIDES_VERSION:
                    data.update(existing)
        except OSError as e:
            log.warning(
                "manual_overrides_read_existing_error",
                path=str(cache_path),
                error=str(e),
            )
        except tomllib.TOMLDecodeError:
            # If corrupt, we'll just overwrite
            log.warning(
                "manual_overrides_corrupt_on_write",
                path=str(cache_path),
            )

    # Build key and entry
    key = f"{override.reference_clip}:{override.comparison_clip}"
    entry = {
        "reference_clip": override.reference_clip,
        "comparison_clip": override.comparison_clip,
        "frame_offset": override.frame_offset,
        "timestamp": override.timestamp,
        "confirmed": override.confirmed,
    }
    data[key] = entry

    # Write with stable ordering: version first, then sorted entry keys
    ordered: dict[str, object] = {"version": MANUAL_OVERRIDES_VERSION}
    for k in sorted(key for key in data if key != "version"):
        ordered[k] = data[k]

    try:
        with cache_path.open("wb") as f:
            f.write(tomli_w.dumps(ordered).encode("utf-8"))
    except OSError as e:
        log.warning(
            "manual_overrides_write_error",
            path=str(cache_path),
            error=str(e),
        )
