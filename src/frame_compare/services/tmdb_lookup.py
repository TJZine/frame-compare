"""TMDB metadata lookup service."""

import re
from typing import Any, cast

import httpx

from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

TMDB_API_URL = "https://api.themoviedb.org/3/search/multi"
TMDB_IMAGE_ORIGINAL_BASE_URL = "https://image.tmdb.org/t/p/original"
TMDB_KEY_REGEX = re.compile(r"^[0-9a-fA-F]{32}$")


def _build_search_params(parsed: ParsedMetadata, api_key: str) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "api_key": api_key,
        "query": parsed.title,
        "language": "en-US",
        "page": 1,
        "include_adult": "false",
    }
    if parsed.year:
        params["year"] = parsed.year
    return params


async def _request_tmdb_search(
    params: dict[str, str | int],
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> httpx.Response:
    return await client.get(
        TMDB_API_URL,
        params=params,
        timeout=config.timeout_seconds,
    )


def _raise_for_tmdb_response(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise TmdbError("Invalid API key")
    if response.status_code == 429:
        raise TmdbRateLimitedError()
    if response.status_code >= 500:
        raise TmdbError(f"TMDB service error: {response.status_code}")

    response.raise_for_status()


def _decode_tmdb_json(response: httpx.Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


def _tmdb_image_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{TMDB_IMAGE_ORIGINAL_BASE_URL}{path}"


def _tmdb_result_year(item: dict[str, Any], media_type: str) -> int:
    if media_type == "movie":
        year_str = str(item.get("release_date", ""))[:4]
    else:
        year_str = str(item.get("first_air_date", ""))[:4]

    return int(year_str) if year_str.isdigit() else 0


def _map_tmdb_result(item: dict[str, Any]) -> TmdbMetadata | None:
    media_type_raw = item.get("media_type", "movie")
    if media_type_raw == "movie":
        media_type = "movie"
    elif media_type_raw == "tv":
        media_type = "tv"
    else:
        return None

    return TmdbMetadata(
        tmdb_id=int(item["id"]),
        title=str(item.get("title") or item.get("name", "Unknown")),
        original_title=str(item.get("original_title") or item.get("original_name", "Unknown")),
        year=_tmdb_result_year(item, media_type),
        media_type=media_type,
        poster_url=_tmdb_image_url(cast(str | None, item.get("poster_path"))),
        backdrop_url=_tmdb_image_url(cast(str | None, item.get("backdrop_path"))),
    )


def _map_tmdb_results(data: dict[str, Any]) -> list[TmdbMetadata]:
    results_raw = cast(list[dict[str, Any]], data.get("results", []))
    mapped_results: list[TmdbMetadata] = []

    for item in results_raw:
        result = _map_tmdb_result(item)
        if result is not None:
            mapped_results.append(result)

    return mapped_results


def is_valid_tmdb_api_key(api_key: str) -> bool:
    """Return whether a TMDB API key matches the API v3 key format."""
    return TMDB_KEY_REGEX.fullmatch(api_key) is not None


async def _search_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbMetadata]:
    """Internal search helper that returns all results."""
    if config.api_key is None:
        return []

    if not is_valid_tmdb_api_key(config.api_key):
        raise TmdbError("Invalid API key format")

    params = _build_search_params(parsed, config.api_key)

    try:
        response = await _request_tmdb_search(params, config, client)
        _raise_for_tmdb_response(response)
        data = _decode_tmdb_json(response)
    except httpx.TimeoutException as e:
        raise TmdbError("Request timed out") from e
    except httpx.RequestError as e:
        # Avoid including the request URL (which can contain the API key) in error messages.
        raise TmdbError("Request failed") from e
    except httpx.HTTPStatusError as e:
        raise TmdbError(f"HTTP error occurred: {e.response.status_code}") from e
    except Exception as e:
        if isinstance(e, TmdbError | TmdbRateLimitedError):
            raise
        # Avoid leaking request details (e.g., query params) via exception stringification.
        raise TmdbError("Unexpected error during TMDB lookup") from e

    return _map_tmdb_results(data)


search_tmdb = _search_tmdb


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
