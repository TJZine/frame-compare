"""Metadata resolution workflow and compatibility facade."""

from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx

from frame_compare.services.errors import MetadataError
from frame_compare.services.metadata_parsing import parse_filename
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.tmdb_lookup import is_valid_tmdb_api_key, lookup_tmdb
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

if TYPE_CHECKING:
    from frame_compare.services.tmdb_resolution import TmdbResolutionOutcome

__all__ = [
    "is_valid_tmdb_api_key",
    "lookup_tmdb",
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
    prompt_callback: Callable[[list[TmdbMetadata]], int] | None = None,
    *,
    cache: TmdbCache | None = None,
) -> TmdbMetadata | None:
    """
    Full metadata resolution workflow.

    Steps:
    1. Parse the first filename
    2. Delegate TMDB ranking to the resolver
    3. Return the resolver's selected match when available
    4. Otherwise, optionally prompt from unresolved ranked candidates

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

    if prompt_callback is None:
        return None

    idx = prompt_callback(outcome.candidates)
    if idx < 0 or idx >= len(outcome.candidates):
        raise MetadataError("invalid selection index")

    return outcome.candidates[idx]
