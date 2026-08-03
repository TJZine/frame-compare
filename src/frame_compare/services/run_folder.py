"""Run folder naming utilities for Frame Compare.

This module provides functions for deriving filesystem-safe run folder names
from video metadata (TMDB, guessit) with collision handling.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from frame_compare.errors import PathEscapesRootError
from frame_compare.services.errors import GeneratedDataReservationError
from frame_compare.services.metadata import parse_filename
from frame_compare.services.types import ParsedMetadata, TmdbMetadata
from frame_compare.utils.paths import require_managed_immediate_child

_UNNAMED_RUN_BASE = "unnamed_run"
_MAX_FOLDER_NAME_LENGTH = 64
_NUMERIC_COLLISION_ATTEMPTS = 100
_WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

# Characters illegal in Windows filenames (also avoid on Unix for portability)
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Collapse multiple spaces/underscores
_MULTI_SPACE = re.compile(r"[\s_]+")

log = logging.getLogger(__name__)

type RunFolderNamingSource = Literal["tmdb", "parsed_metadata", "filename_stems", "unnamed"]


@dataclass(frozen=True, slots=True)
class RunFolderReservation:
    path: Path
    folder_name: str
    base_name: str
    naming_source: RunFolderNamingSource


def sanitize_folder_name(name: str) -> str:
    """Remove/replace characters illegal in Windows/Unix paths."""
    if not name:
        return _UNNAMED_RUN_BASE

    sanitized = _ILLEGAL_CHARS.sub(" ", name)
    sanitized = _MULTI_SPACE.sub(" ", sanitized).strip()
    sanitized = sanitized.rstrip(". ")

    if not sanitized:
        return _UNNAMED_RUN_BASE

    # Limit length (Windows MAX_PATH considerations)
    if len(sanitized) > _MAX_FOLDER_NAME_LENGTH:
        truncated = sanitized[:_MAX_FOLDER_NAME_LENGTH]
        sanitized = truncated.rstrip(". ")
        if not sanitized:
            fallback = truncated.replace(".", "").replace(" ", "")
            sanitized = fallback if fallback else _UNNAMED_RUN_BASE

    sanitized = _avoid_windows_reserved_filename(sanitized)

    return sanitized


def _avoid_windows_reserved_filename(name: str) -> str:
    if _windows_reserved_filename(name):
        safe_name = f"{name.replace('.', ' ')} run"
        safe_name = _MULTI_SPACE.sub(" ", safe_name).strip().rstrip(". ")
        if len(safe_name) > _MAX_FOLDER_NAME_LENGTH:
            safe_name = safe_name[:_MAX_FOLDER_NAME_LENGTH].rstrip(". ")
        return (
            safe_name
            if safe_name and not _windows_reserved_filename(safe_name)
            else _UNNAMED_RUN_BASE
        )
    return name


def _windows_reserved_filename(name: str) -> bool:
    stem = name.split(".", maxsplit=1)[0].upper()
    return stem in _WINDOWS_RESERVED_FILENAMES


def find_common_metadata(filenames: list[str]) -> tuple[str | None, int | None]:
    """Find title/year shared by all non-empty parsed values."""
    if not filenames:
        return None, None

    parsed_results: list[ParsedMetadata] = []
    for filename in filenames:
        parsed_results.append(parse_filename(filename))

    if len(parsed_results) == 1:
        pm = parsed_results[0]
        return pm.title if pm.title else None, pm.year

    titles = [p.title.lower().strip() for p in parsed_results if p.title]
    common_title: str | None = None
    if titles and len(set(titles)) == 1:
        common_title = next(p.title for p in parsed_results if p.title)

    # Find common year
    years = [p.year for p in parsed_results if p.year is not None]
    common_year: int | None = None
    if years and len(set(years)) == 1:
        common_year = years[0]

    return common_title, common_year


def _combine_filename_stems(filenames: list[str]) -> str:
    """Create a combined name from filename stems."""
    if not filenames:
        return _UNNAMED_RUN_BASE

    stems: list[str] = []
    for filename in filenames:
        stem = Path(filename).stem
        # Truncate long stems
        if len(stem) > 30:
            stem = stem[:30]
        stems.append(sanitize_folder_name(stem))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_stems: list[str] = []
    for stem in stems:
        if stem.lower() not in seen:
            seen.add(stem.lower())
            unique_stems.append(stem)

    # Limit to first 2 stems to avoid excessively long names
    combined = " + ".join(unique_stems[:2])
    if len(unique_stems) > 2:
        combined += f" +{len(unique_stems) - 2} more"

    return sanitize_folder_name(combined)


def _append_collision_suffix(folder_name: str, suffix: str) -> str:
    """Append a suffix while keeping the result inside the path length budget."""
    allowed = _MAX_FOLDER_NAME_LENGTH - (len(suffix) + 1)
    if allowed < 1:
        allowed = 1
    trimmed = folder_name[:allowed].rstrip(". ")
    if not trimmed:
        trimmed = _UNNAMED_RUN_BASE[:allowed]
    return f"{trimmed}_{suffix}"


def _derive_base_folder_name(
    filenames: list[str],
    tmdb_metadata: TmdbMetadata | None = None,
) -> tuple[str, RunFolderNamingSource]:
    """Derive the canonical base run-folder name before collision handling."""
    if not filenames:
        return _UNNAMED_RUN_BASE, "unnamed"

    base_name: str | None = None

    if tmdb_metadata is not None:
        title = tmdb_metadata.title
        year = tmdb_metadata.year
        if title:
            base_name = f"{title} ({year})" if year and year > 0 else title
            return sanitize_folder_name(base_name), "tmdb"

    common_title, common_year = find_common_metadata(filenames)
    if common_title:
        base_name = f"{common_title} ({common_year})" if common_year else common_title
        return sanitize_folder_name(base_name), "parsed_metadata"

    combined = _combine_filename_stems(filenames)
    if combined == _UNNAMED_RUN_BASE:
        return combined, "unnamed"
    return combined, "filename_stems"


def reserve_run_folder(
    input_dir: Path,
    filenames: list[str],
    tmdb_metadata: TmdbMetadata | None = None,
) -> RunFolderReservation:
    """Derive and atomically reserve a unique run folder name by creating it.

    It derives the base folder name, then claims input_dir / candidate
    with mkdir(parents=True, exist_ok=False), retrying with numeric suffixes on collision.

    Args:
        input_dir: Directory where the run folder should be created
        filenames: List of video filenames (not full paths)
        tmdb_metadata: Optional TMDB metadata from lookup

    Returns:
        Reservation facts for the reserved run folder
    """
    base_name, naming_source = _derive_base_folder_name(filenames, tmdb_metadata)

    def _reservation(candidate_name: str) -> RunFolderReservation:
        return RunFolderReservation(
            path=input_dir / candidate_name,
            folder_name=candidate_name,
            base_name=base_name,
            naming_source=naming_source,
        )

    reservation = _reservation(base_name)

    # Try creating base folder name
    try:
        _reserve_candidate(input_dir, reservation.path)
        return reservation
    except FileExistsError:
        log.debug(
            "Run folder collision on base path; will retry with suffixes. Path: %s",
            reservation.path,
        )

    # Loop over compact numeric suffix candidates to resolve collisions.
    for attempt in range(2, _NUMERIC_COLLISION_ATTEMPTS + 2):
        suffix_name = _append_collision_suffix(base_name, str(attempt))
        suffix_reservation = _reservation(suffix_name)
        try:
            _reserve_candidate(input_dir, suffix_reservation.path)
            return suffix_reservation
        except FileExistsError:
            continue

    # Ultimate fallback with uuid
    random_suffix = uuid.uuid4().hex[:8]
    fallback_name = _append_collision_suffix(base_name, random_suffix)
    fallback_reservation = _reservation(fallback_name)
    _reserve_candidate(input_dir, fallback_reservation.path)
    return fallback_reservation


def _reserve_candidate(owner: Path, candidate: Path) -> None:
    """Validate and atomically claim one immediate child of ``owner``."""
    try:
        require_managed_immediate_child(owner, candidate)
        candidate.mkdir(parents=True, exist_ok=False)
    except (FileExistsError, PathEscapesRootError):
        raise
    except (OSError, RuntimeError) as exc:
        raise GeneratedDataReservationError(owner, exc) from exc
