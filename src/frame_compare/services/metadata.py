"""Metadata resolution workflow and compatibility facade."""

from collections.abc import Callable

import httpx

from frame_compare.services.errors import MetadataError
from frame_compare.services.metadata_parsing import parse_filename
from frame_compare.services.tmdb_lookup import (
    is_valid_tmdb_api_key,
    lookup_tmdb,
    search_tmdb,
)
from frame_compare.services.types import MetadataConfig, TmdbMetadata

__all__ = [
    "is_valid_tmdb_api_key",
    "lookup_tmdb",
    "parse_filename",
    "resolve_metadata",
]


async def resolve_metadata(
    filenames: list[str],
    config: MetadataConfig,
    client: httpx.AsyncClient,
    prompt_callback: Callable[[list[TmdbMetadata]], int] | None = None,
) -> TmdbMetadata | None:
    """
    Full metadata resolution workflow.

    Steps:
    1. Parse first filename
    2. Search TMDB
    3. If multiple results, config.unattended is false, and prompt_callback is
       provided, call prompt_callback; otherwise fall back to the first result
    4. Return selected metadata

    Selection behavior:
    - If no results: return None
    - If single result or config.unattended=True: return first result
    - If multiple results and prompt_callback is None: return first result (index 0)
    - If multiple results and prompt_callback provided: call it and use returned index
    - If prompt_callback returns an invalid index (< 0 or >= len(results)):
      raise MetadataError with message containing "invalid selection index"

    Args:
        filenames: List of filenames to try parsing
        config: TMDB configuration
        client: HTTP client (injected, not owned)
        prompt_callback: Optional callback for interactive selection

    Returns:
        TmdbMetadata if found and selected, None otherwise

    Raises:
        MetadataError: If prompt_callback returns invalid index
        TmdbError: If TMDB lookup fails
    """
    if not filenames:
        return None

    parsed = parse_filename(filenames[0])
    results = await search_tmdb(parsed, config, client)

    if not results:
        return None

    if len(results) == 1 or config.unattended:
        return results[0]

    if prompt_callback is None:
        return results[0]

    idx = prompt_callback(results)
    if idx < 0 or idx >= len(results):
        raise MetadataError("invalid selection index")

    return results[idx]
