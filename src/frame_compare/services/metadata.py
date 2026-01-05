"""Filename parsing and TMDB lookup service."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import anitopy
import httpx
from guessit import guessit  # type: ignore

from frame_compare.errors import MetadataError, TmdbError, TmdbRateLimitedError
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

TMDB_API_URL = "https://api.themoviedb.org/3/search/multi"
TMDB_KEY_REGEX = re.compile(r"^[0-9a-fA-F]{32}$")


def parse_filename(filename: str) -> ParsedMetadata:
    """
    Extract metadata from filename using GuessIt + Anitopy.

    Parser selection:
    1. If filename starts with '[' (bracketed group), use Anitopy first
    2. Otherwise, try GuessIt for western media
    3. If primary parser returns no title, try the alternate parser

    Fallback behavior:
    - If both parsers fail to extract a title, use the filename stem
      (filename without extension) as the title
    - All other fields default to None when not extracted

    Normalization:
    - Title separators (., _, -) are normalized to spaces
    - Leading/trailing whitespace is stripped from title

    Args:
        filename: Video filename (not full path)

    Returns:
        ParsedMetadata with extracted fields (always returns, never raises)
    """
    if not filename:
        return ParsedMetadata(title="")

    # Determine primary parser
    use_anitopy_first = filename.startswith("[")

    title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    release_group: str | None = None
    source: str | None = None
    resolution: str | None = None

    def _apply_anitopy(name: str) -> dict[str, Any]:
        try:
            result = anitopy.parse(name)  # type: ignore
            return cast(dict[str, Any], result) if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _apply_guessit(name: str) -> dict[str, Any]:
        try:
            result = guessit(name)  # type: ignore
            return dict(cast(dict[Any, Any], result)) if result else {}
        except Exception:
            return {}

    parsers = [
        (_apply_anitopy if use_anitopy_first else _apply_guessit),
        (_apply_guessit if use_anitopy_first else _apply_anitopy),
    ]

    for parser in parsers:
        res = parser(filename)
        # title extraction
        t = res.get("anime_title") or res.get("title")
        if t and not title:
            title = str(t)

        # year
        if year is None:
            y = res.get("year")
            if isinstance(y, int):
                year = y
            elif isinstance(y, str) and y.isdigit():
                year = int(y)

        # season
        if season is None:
            s = res.get("season")
            if isinstance(s, int):
                season = s
            elif isinstance(s, str) and s.isdigit():
                season = int(s)

        # episode
        if episode is None:
            e = res.get("anime_episode") or res.get("episode")
            if isinstance(e, int):
                episode = e
            elif isinstance(e, str) and e.isdigit():
                episode = int(e)
            elif isinstance(e, list) and e and isinstance(e[0], int):
                episode = e[0]

        # release_group
        if release_group is None:
            rg = res.get("release_group")
            if rg:
                release_group = str(rg)

        # source
        if source is None:
            src = res.get("source")
            if src:
                source = str(src)

        # resolution
        if resolution is None:
            res_val = res.get("screen_size") or res.get("video_resolution")
            if res_val:
                resolution = str(res_val)

    # Fallback to stem if no title found
    if not title:
        title = Path(filename).stem

    # Normalization
    title = re.sub(r"[._\-]", " ", title).strip()

    return ParsedMetadata(
        title=title,
        year=year,
        season=season,
        episode=episode,
        release_group=release_group,
        source=source,
        resolution=resolution,
    )


async def _search_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbMetadata]:
    """Internal search helper that returns all results."""
    if config.api_key is None:
        return []

    if not TMDB_KEY_REGEX.fullmatch(config.api_key):
        raise TmdbError("Invalid API key format")

    params: dict[str, str | int] = {
        "api_key": config.api_key,
        "query": parsed.title,
        "language": "en-US",
        "page": 1,
        "include_adult": "false",
    }
    if parsed.year:
        params["year"] = parsed.year

    try:
        response = await client.get(
            TMDB_API_URL,
            params=params,
            timeout=config.timeout_seconds,
        )

        if response.status_code == 401:
            raise TmdbError("Invalid API key")
        if response.status_code == 429:
            raise TmdbRateLimitedError()
        if response.status_code >= 500:
            raise TmdbError(f"TMDB service error: {response.status_code}")

        response.raise_for_status()
        data = cast(dict[str, Any], response.json())

    except httpx.TimeoutException as e:
        raise TmdbError("Request timed out") from e
    except httpx.HTTPStatusError as e:
        raise TmdbError(f"HTTP error occurred: {e}") from e
    except Exception as e:
        if isinstance(e, TmdbError | TmdbRateLimitedError):
            raise
        raise TmdbError(f"Unexpected error during TMDB lookup: {e}") from e

    results_raw = cast(list[dict[str, Any]], data.get("results", []))
    mapped_results: list[TmdbMetadata] = []

    for item in results_raw:
        media_type = str(item.get("media_type", "movie"))

        # Year extraction
        year_str = ""
        if media_type == "movie":
            year_str = str(item.get("release_date", ""))[:4]
        else:
            year_str = str(item.get("first_air_date", ""))[:4]

        year = int(year_str) if year_str.isdigit() else 0

        def _get_url(path: str | None) -> str | None:
            if not path:
                return None
            return f"https://image.tmdb.org/t/p/original{path}"

        mapped_results.append(
            TmdbMetadata(
                tmdb_id=int(item["id"]),
                title=str(item.get("title") or item.get("name", "Unknown")),
                original_title=str(
                    item.get("original_title") or item.get("original_name", "Unknown")
                ),
                year=year,
                media_type=media_type,
                poster_url=_get_url(cast(str | None, item.get("poster_path"))),
                backdrop_url=_get_url(cast(str | None, item.get("backdrop_path"))),
            )
        )

    return mapped_results


async def lookup_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> TmdbMetadata | None:
    """
    Look up media on TMDB.

    Preconditions:
    - If config.api_key is None, return None without making a request
    - If config.api_key is not a valid 32-character hex string, raise
      TmdbError with message containing "Invalid API key format"

    Args:
        parsed: Metadata from filename parsing
        config: TMDB configuration
        client: HTTP client (injected, not owned)

    Returns:
        TmdbMetadata if found, None otherwise

    Raises:
        TmdbError: If API key is invalid format, or API call fails
        TmdbRateLimitedError: If rate limited (HTTP 429)
    """
    results = await _search_tmdb(parsed, config, client)
    return results[0] if results else None


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
    3. If multiple results and not unattended, call prompt_callback
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
    results = await _search_tmdb(parsed, config, client)

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
