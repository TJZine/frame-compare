"""Run folder naming utilities for Frame Compare.

This module provides functions for deriving filesystem-safe run folder names
from video metadata (TMDB, guessit) with collision handling.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from frame_compare.services.metadata import parse_filename
from frame_compare.services.types import ParsedMetadata, TmdbMetadata

# Characters illegal in Windows filenames (also avoid on Unix for portability)
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Collapse multiple spaces/underscores
_MULTI_SPACE = re.compile(r"[\s_]+")


def sanitize_folder_name(name: str) -> str:
    """Remove/replace characters illegal in Windows/Unix paths.

    Args:
        name: Raw folder name

    Returns:
        Filesystem-safe folder name
    """
    if not name:
        return "unnamed_run"

    # Replace illegal characters with space
    sanitized = _ILLEGAL_CHARS.sub(" ", name)
    # Collapse multiple spaces
    sanitized = _MULTI_SPACE.sub(" ", sanitized).strip()
    # Remove trailing periods/spaces (Windows restriction)
    sanitized = sanitized.rstrip(". ")

    if not sanitized:
        return "unnamed_run"

    # Limit length (Windows MAX_PATH considerations)
    max_len = 100
    if len(sanitized) > max_len:
        truncated = sanitized[:max_len]
        sanitized = truncated.rstrip(". ")
        if not sanitized:
            fallback = truncated.replace(".", "").replace(" ", "")
            sanitized = fallback if fallback else "unnamed_run"

    return sanitized


def find_common_metadata(filenames: list[str]) -> tuple[str | None, int | None]:
    """Find title/year shared by all non-empty parsed values.

    Parses each filename and finds metadata values that match across available
    parsed fields. Missing/empty fields are ignored to keep graceful fallback
    behavior for partially parseable filenames.

    Args:
        filenames: List of video filenames to compare

    Returns:
        Tuple of (common_title, common_year). Either may be None if no match found.
    """
    if not filenames:
        return None, None

    parsed_results: list[ParsedMetadata] = []
    for filename in filenames:
        parsed_results.append(parse_filename(filename))

    if len(parsed_results) == 1:
        pm = parsed_results[0]
        return pm.title if pm.title else None, pm.year

    # Find common title (case-insensitive comparison across non-empty titles)
    titles = [p.title.lower().strip() for p in parsed_results if p.title]
    common_title: str | None = None
    if titles and len(set(titles)) == 1:
        # All non-empty titles match - preserve original casing from first contributor.
        common_title = next(p.title for p in parsed_results if p.title)

    # Find common year
    years = [p.year for p in parsed_results if p.year is not None]
    common_year: int | None = None
    if years and len(set(years)) == 1:
        common_year = years[0]

    return common_title, common_year


def _combine_filename_stems(filenames: list[str]) -> str:
    """Create a combined name from filename stems.

    Args:
        filenames: List of video filenames

    Returns:
        Combined folder name from sanitized stems
    """
    if not filenames:
        return "unnamed_run"

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


def derive_run_folder_name(
    filenames: list[str],
    tmdb_metadata: TmdbMetadata | None = None,
    existing_folders: list[str] | None = None,
) -> str:
    """Derive a filesystem-safe run folder name from video metadata.

    Priority:
    1. TMDB metadata: "{title} ({year})"
    2. Guessit: find common title/year across filenames
    3. Fallback: combine sanitized filename stems

    Collision handling:
    - If name exists in existing_folders, append timestamp

    Args:
        filenames: List of video filenames (not full paths)
        tmdb_metadata: Optional TMDB metadata from lookup
        existing_folders: Optional list of existing folder names for collision check

    Returns:
        Filesystem-safe folder name
    """
    if not filenames:
        return f"unnamed_run_{_format_timestamp()}"

    base_name: str | None = None

    # Priority 1: TMDB metadata
    if tmdb_metadata is not None:
        title = tmdb_metadata.title
        year = tmdb_metadata.year
        if title:
            base_name = f"{title} ({year})" if year and year > 0 else title

    # Priority 2: Common metadata from guessit
    if base_name is None:
        common_title, common_year = find_common_metadata(filenames)
        if common_title:
            base_name = f"{common_title} ({common_year})" if common_year else common_title

    # Priority 3: Fallback to combined stems
    if base_name is None:
        base_name = _combine_filename_stems(filenames)

    # Sanitize the name
    folder_name = sanitize_folder_name(base_name)

    # Check for collisions
    if existing_folders:
        existing_lower = {f.lower() for f in existing_folders}
        if folder_name.lower() in existing_lower:
            ts = _format_timestamp()
            max_len = 100
            allowed = max_len - (len(ts) + 1)
            if allowed < 1:
                allowed = 1
            folder_name = f"{folder_name[:allowed]}_{ts}"

    return folder_name


def get_existing_run_folders(input_dir: Path) -> list[str]:
    """Get list of existing run folder names in input directory.

    Filters to only include directories (not files).

    Args:
        input_dir: Path to input directory (e.g., comparison_videos/)

    Returns:
        List of existing folder names
    """
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
    import time
    import uuid

    if not filenames:
        base_name = "unnamed_run"
    else:
        base_name = None

        # Priority 1: TMDB metadata
        if tmdb_metadata is not None:
            title = tmdb_metadata.title
            year = tmdb_metadata.year
            if title:
                base_name = f"{title} ({year})" if year and year > 0 else title

        # Priority 2: Common metadata from guessit
        if base_name is None:
            common_title, common_year = find_common_metadata(filenames)
            if common_title:
                base_name = f"{common_title} ({common_year})" if common_year else common_title

        # Priority 3: Fallback to combined stems
        if base_name is None:
            base_name = _combine_filename_stems(filenames)

    folder_name = sanitize_folder_name(base_name)
    candidate_path = input_dir / folder_name

    # Try creating base folder name
    try:
        candidate_path.mkdir(parents=True, exist_ok=False)
        return candidate_path
    except FileExistsError:
        pass

    # Loop over suffix candidates with timestamp + sequence index to resolve collisions
    for attempt in range(10):
        ts = _format_timestamp()
        if attempt > 0:
            ts += f"-{attempt}"
        max_len = 100
        allowed = max_len - (len(ts) + 1)
        if allowed < 1:
            allowed = 1
        suffix_name = f"{folder_name[:allowed]}_{ts}"
        suffix_path = input_dir / suffix_name
        try:
            suffix_path.mkdir(parents=True, exist_ok=False)
            return suffix_path
        except FileExistsError:
            time.sleep(0.1)

    # Ultimate fallback with uuid
    random_suffix = uuid.uuid4().hex[:8]
    fallback_name = f"{folder_name[:80]}_{random_suffix}"
    fallback_path = input_dir / fallback_name
    fallback_path.mkdir(parents=True, exist_ok=False)
    return fallback_path
