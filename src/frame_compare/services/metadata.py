"""Metadata resolution workflow and compatibility facade."""

from typing import TYPE_CHECKING

import httpx

from frame_compare.services.metadata_parsing import parse_filename
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.tmdb_lookup import is_valid_tmdb_api_key
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

if TYPE_CHECKING:
    from frame_compare.services.tmdb_resolution import TmdbResolutionOutcome

__all__ = [
    "is_valid_tmdb_api_key",
    "parse_filename",
    "resolve_metadata",
]


async def resolve_tmdb_match(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> "TmdbResolutionOutcome":
    from frame_compare.services.tmdb_resolution import resolve_tmdb_match as _resolve_tmdb_match

    return await _resolve_tmdb_match(parsed, config, client, cache=cache)


async def resolve_metadata(
    filenames: list[str],
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> TmdbMetadata | None:
    """
    Full metadata resolution workflow.

    Steps:
    1. Parse the first filename
    2. Delegate TMDB ranking to the resolver
    3. Return the resolver's selected match when available
    4. Otherwise return no match

    Args:
        filenames: List of filenames to try parsing
        config: TMDB configuration
        client: HTTP client (injected, not owned)

    Returns:
        TmdbMetadata if found and selected, None otherwise

    Raises:
        TmdbError: If TMDB lookup fails
    """
    if not filenames:
        return None

    parsed = parse_filename(filenames[0])
    if cache is None:
        outcome = await resolve_tmdb_match(parsed, config, client)
    else:
        outcome = await resolve_tmdb_match(parsed, config, client, cache=cache)

    if outcome.selected is not None:
        return outcome.selected

    if not outcome.candidates:
        return None

    if config.unattended:
        return None

    return None
