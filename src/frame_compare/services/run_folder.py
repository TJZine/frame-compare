"""Run folder naming utilities for Frame Compare.

This module provides functions for deriving filesystem-safe run folder names
from video metadata (TMDB, guessit) with collision handling.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from frame_compare.services.metadata import parse_filename
from frame_compare.services.types import ParsedMetadata, TmdbMetadata

_UNNAMED_RUN_BASE = "unnamed_run"
_MAX_FOLDER_NAME_LENGTH = 100

# Characters illegal in Windows filenames (also avoid on Unix for portability)
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Collapse multiple spaces/underscores
_MULTI_SPACE = re.compile(r"[\s_]+")

log = logging.getLogger(__name__)


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

    return sanitized


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


def _format_timestamp() -> str:
    """Format current timestamp for folder name suffix."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _append_collision_suffix(folder_name: str, suffix: str) -> str:
    """Append a suffix while keeping the result inside the path length budget."""
    allowed = _MAX_FOLDER_NAME_LENGTH - (len(suffix) + 1)
    if allowed < 1:
        allowed = 1
    return f"{folder_name[:allowed]}_{suffix}"


def _resolve_existing_folder_collision(
    base_name: str,
    existing_folders: list[str] | None,
    *,
    initial_candidate: str | None = None,
    collision_timestamp: str | None = None,
) -> str:
    """Resolve a unique folder name against a caller-provided existing-folder snapshot."""
    candidate = base_name if initial_candidate is None else initial_candidate
    if not existing_folders:
        return candidate

    existing_lower = {folder.lower() for folder in existing_folders}
    if candidate.lower() not in existing_lower:
        return candidate

    timestamp = _format_timestamp() if collision_timestamp is None else collision_timestamp
    attempt = 0
    while True:
        suffix = timestamp if attempt == 0 else f"{timestamp}-{attempt}"
        candidate = _append_collision_suffix(base_name, suffix)
        if candidate.lower() not in existing_lower:
            return candidate
        attempt += 1


def _derive_base_folder_name(
    filenames: list[str],
    tmdb_metadata: TmdbMetadata | None = None,
) -> str:
    """Derive the canonical base run-folder name before collision handling."""
    if not filenames:
        return _UNNAMED_RUN_BASE

    base_name: str | None = None

    if tmdb_metadata is not None:
        title = tmdb_metadata.title
        year = tmdb_metadata.year
        if title:
            base_name = f"{title} ({year})" if year and year > 0 else title

    if base_name is None:
        common_title, common_year = find_common_metadata(filenames)
        if common_title:
            base_name = f"{common_title} ({common_year})" if common_year else common_title

    if base_name is None:
        return _combine_filename_stems(filenames)

    return sanitize_folder_name(base_name)


def derive_run_folder_name(
    filenames: list[str],
    tmdb_metadata: TmdbMetadata | None = None,
    existing_folders: list[str] | None = None,
) -> str:
    """Derive a filesystem-safe run folder name from video metadata."""
    if not filenames:
        timestamp = _format_timestamp()
        unnamed_candidate = _append_collision_suffix(_UNNAMED_RUN_BASE, timestamp)
        return _resolve_existing_folder_collision(
            _UNNAMED_RUN_BASE,
            existing_folders,
            initial_candidate=unnamed_candidate,
            collision_timestamp=timestamp,
        )

    folder_name = _derive_base_folder_name(filenames, tmdb_metadata)
    return _resolve_existing_folder_collision(folder_name, existing_folders)


def get_existing_run_folders(input_dir: Path) -> list[str]:
    """Get list of existing run folder names in input directory, filtering to only include directories."""
    if not input_dir.exists():
        return []
    if not input_dir.is_dir():
        return []

    return [p.name for p in input_dir.iterdir() if p.is_dir()]


def reserve_run_folder(
    input_dir: Path,
    filenames: list[str],
    tmdb_metadata: TmdbMetadata | None = None,
) -> Path:
    """Derive and atomically reserve a unique run folder name by creating it.

    It derives the base folder name, then claims input_dir / candidate
    with mkdir(parents=True, exist_ok=False), retrying with timestamp suffixes on collision.

    Args:
        input_dir: Directory where the run folder should be created
        filenames: List of video filenames (not full paths)
        tmdb_metadata: Optional TMDB metadata from lookup

    Returns:
        Path to the reserved run folder
    """
    folder_name = _derive_base_folder_name(filenames, tmdb_metadata)
    candidate_path = input_dir / folder_name

    # Try creating base folder name
    try:
        candidate_path.mkdir(parents=True, exist_ok=False)
        return candidate_path
    except FileExistsError:
        log.debug(
            "Run folder collision on base path; will retry with suffixes. Path: %s",
            candidate_path,
        )

    # Loop over suffix candidates with timestamp + sequence index to resolve collisions
    for attempt in range(10):
        ts = _format_timestamp()
        if attempt > 0:
            ts += f"-{attempt}"
        suffix_name = _append_collision_suffix(folder_name, ts)
        suffix_path = input_dir / suffix_name
        try:
            suffix_path.mkdir(parents=True, exist_ok=False)
            return suffix_path
        except FileExistsError:
            time.sleep(0.1)

    # Ultimate fallback with uuid
    random_suffix = uuid.uuid4().hex[:8]
    fallback_name = _append_collision_suffix(folder_name[:80], random_suffix)
    fallback_path = input_dir / fallback_name
    fallback_path.mkdir(parents=True, exist_ok=False)
    return fallback_path
