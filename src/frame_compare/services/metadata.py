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
    if not filenames:
        return None

    parsed = parse_filename(filenames[0])
    if cache is None:
        outcome = await resolve_tmdb_match(parsed, config, client)
    else:
        outcome = await resolve_tmdb_match(parsed, config, client, cache=cache)

    return outcome.selected
