"""TMDB metadata lookup service."""

import re
from collections.abc import Mapping
from typing import Literal, cast

import httpx

from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

type _TmdbMediaType = Literal["movie", "tv"]


TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_MULTI_SEARCH_URL = f"{TMDB_API_BASE_URL}/search/multi"
TMDB_MOVIE_SEARCH_URL = f"{TMDB_API_BASE_URL}/search/movie"
TMDB_TV_SEARCH_URL = f"{TMDB_API_BASE_URL}/search/tv"
TMDB_IMAGE_ORIGINAL_BASE_URL = "https://image.tmdb.org/t/p/original"
TMDB_KEY_REGEX = re.compile(r"^[0-9a-fA-F]{32}$")


def _build_search_params(
    parsed: ParsedMetadata,
    api_key: str,
    *,
    year_param_name: str = "year",
) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "api_key": api_key,
        "query": parsed.title,
        "language": "en-US",
        "page": 1,
        "include_adult": "false",
    }
    if parsed.year:
        params[year_param_name] = parsed.year
    return params


async def _request_tmdb_search(
    url: str,
    params: Mapping[str, str | int],
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> httpx.Response:
    return await client.get(
        url,
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


def _decode_tmdb_json(response: httpx.Response) -> object:
    return response.json()


def _tmdb_image_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{TMDB_IMAGE_ORIGINAL_BASE_URL}{path}"


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _tmdb_result_year(item: Mapping[str, object], media_type: _TmdbMediaType) -> int:
    if media_type == "movie":
        date_value = _optional_str(item.get("release_date"))
    else:
        date_value = _optional_str(item.get("first_air_date"))

    year_str = "" if date_value is None else date_value[:4]

    return int(year_str) if year_str.isdigit() else 0


def _normalize_media_type(value: object) -> _TmdbMediaType | None:
    if value == "movie":
        return "movie"
    if value == "tv":
        return "tv"
    return None


def _map_tmdb_result(
    item: Mapping[str, object],
    endpoint_media_type: _TmdbMediaType | None = None,
) -> TmdbMetadata | None:
    media_type = endpoint_media_type or _normalize_media_type(item.get("media_type"))
    if media_type is None:
        return None

    tmdb_id_raw = item.get("id")
    if isinstance(tmdb_id_raw, bool):
        return None
    if isinstance(tmdb_id_raw, int):
        tmdb_id = tmdb_id_raw
    elif isinstance(tmdb_id_raw, str) and tmdb_id_raw.isdigit():
        tmdb_id = int(tmdb_id_raw)
    else:
        return None

    title = _optional_str(item.get("title")) or _optional_str(item.get("name")) or "Unknown"
    original_title = (
        _optional_str(item.get("original_title"))
        or _optional_str(item.get("original_name"))
        or "Unknown"
    )

    return TmdbMetadata(
        tmdb_id=tmdb_id,
        title=title,
        original_title=original_title,
        year=_tmdb_result_year(item, media_type),
        media_type=media_type,
        original_language=_optional_str(item.get("original_language")),
        poster_url=_tmdb_image_url(_optional_str(item.get("poster_path"))),
        backdrop_url=_tmdb_image_url(_optional_str(item.get("backdrop_path"))),
    )


def _map_tmdb_results(
    data: object,
    *,
    endpoint_media_type: _TmdbMediaType | None = None,
) -> list[TmdbMetadata]:
    if not isinstance(data, dict):
        raise TmdbError("Malformed TMDB response")

    data_dict = cast(dict[str, object], data)
    results_raw = data_dict.get("results", [])
    if not isinstance(results_raw, list):
        raise TmdbError("Malformed TMDB response")

    mapped_results: list[TmdbMetadata] = []
    for item in cast(list[object], results_raw):
        if not isinstance(item, dict):
            continue
        metadata = _map_tmdb_result(
            cast(dict[str, object], item), endpoint_media_type=endpoint_media_type
        )
        if metadata is not None:
            mapped_results.append(metadata)
    return mapped_results


def _map_tmdb_results_with_cacheability(
    data: object,
    *,
    endpoint_media_type: _TmdbMediaType | None = None,
) -> tuple[list[TmdbMetadata], bool]:
    """Map results and report whether the response was structurally complete."""
    mapped_results = _map_tmdb_results(data, endpoint_media_type=endpoint_media_type)
    if not isinstance(data, dict):
        return mapped_results, False
    results_raw = cast(dict[str, object], data).get("results")
    if not isinstance(results_raw, list):
        return mapped_results, False
    cacheable = all(
        _tmdb_result_is_cacheable(item, endpoint_media_type)
        for item in cast(list[object], results_raw)
    )
    return mapped_results, cacheable


def _tmdb_result_is_cacheable(
    item: object,
    endpoint_media_type: _TmdbMediaType | None,
) -> bool:
    if not isinstance(item, dict):
        return False
    typed_item = cast(dict[str, object], item)
    if endpoint_media_type is None and typed_item.get("media_type") == "person":
        person_id = typed_item.get("id")
        name = typed_item.get("name")
        has_valid_id = (isinstance(person_id, int) and not isinstance(person_id, bool)) or (
            isinstance(person_id, str) and person_id.isdigit()
        )
        return has_valid_id and isinstance(name, str) and bool(name.strip())
    return _map_tmdb_result(typed_item, endpoint_media_type=endpoint_media_type) is not None


def _map_tmdb_alternative_titles(
    data: object,
    media_type: _TmdbMediaType,
) -> list[str]:
    if not isinstance(data, dict):
        return []

    data_dict = cast(dict[str, object], data)
    key = "titles" if media_type == "movie" else "results"
    titles_raw = data_dict.get(key, [])
    if not isinstance(titles_raw, list):
        return []

    titles: list[str] = []
    for item in cast(list[object], titles_raw):
        if not isinstance(item, dict):
            continue
        title = _optional_str(cast(dict[str, object], item).get("title"))
        if title:
            titles.append(title)

    return titles


def _map_tmdb_alternative_titles_with_cacheability(
    data: object,
    media_type: _TmdbMediaType,
) -> tuple[list[str], bool]:
    """Map alternative titles and reject incomplete containers for caching."""
    titles = _map_tmdb_alternative_titles(data, media_type)
    if not isinstance(data, dict):
        return titles, False
    key = "titles" if media_type == "movie" else "results"
    titles_raw = cast(dict[str, object], data).get(key)
    if not isinstance(titles_raw, list):
        return titles, False
    cacheable = all(
        isinstance(item, dict)
        and isinstance(cast(dict[str, object], item).get("title"), str)
        and bool(cast(dict[str, object], item).get("title"))
        for item in cast(list[object], titles_raw)
    )
    return titles, cacheable


def _build_alternative_titles_url(tmdb_id: int, media_type: _TmdbMediaType) -> str:
    return f"{TMDB_API_BASE_URL}/{media_type}/{tmdb_id}/alternative_titles"


def _validate_tmdb_api_key(config: MetadataConfig) -> str | None:
    api_key = config.api_key
    if api_key is None:
        return None

    if not is_valid_tmdb_api_key(api_key):
        raise TmdbError("Invalid API key format")

    return api_key


async def _request_tmdb_json(
    url: str,
    params: Mapping[str, str | int],
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> object:
    try:
        response = await _request_tmdb_search(url, params, config, client)
        _raise_for_tmdb_response(response)
        return _decode_tmdb_json(response)
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


async def _search_tmdb_endpoint(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    url: str,
    endpoint_media_type: _TmdbMediaType | None = None,
    cache: TmdbCache | None = None,
) -> list[TmdbMetadata]:
    api_key = _validate_tmdb_api_key(config)
    if api_key is None:
        return []

    year_param_name = "first_air_date_year" if endpoint_media_type == "tv" else "year"
    params = _build_search_params(parsed, api_key, year_param_name=year_param_name)
    if cache is not None:
        cached = cache.get_search(url, params)
        if cached is not None:
            return cached
    data = await _request_tmdb_json(url, params, config, client)
    results, cacheable = _map_tmdb_results_with_cacheability(
        data,
        endpoint_media_type=endpoint_media_type,
    )
    if cache is not None and cacheable:
        await cache.store_search(url, params, results)
    return results


async def search_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> list[TmdbMetadata]:
    return await _search_tmdb_endpoint(
        parsed,
        config,
        client,
        url=TMDB_MULTI_SEARCH_URL,
        cache=cache,
    )


async def search_tmdb_movie(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> list[TmdbMetadata]:
    return await _search_tmdb_endpoint(
        parsed,
        config,
        client,
        url=TMDB_MOVIE_SEARCH_URL,
        endpoint_media_type="movie",
        cache=cache,
    )


async def search_tmdb_tv(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> list[TmdbMetadata]:
    return await _search_tmdb_endpoint(
        parsed,
        config,
        client,
        url=TMDB_TV_SEARCH_URL,
        endpoint_media_type="tv",
        cache=cache,
    )


async def fetch_tmdb_alternative_titles(
    tmdb_id: int,
    media_type: _TmdbMediaType,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> list[str]:
    api_key = _validate_tmdb_api_key(config)
    if api_key is None:
        return []

    url = _build_alternative_titles_url(tmdb_id, media_type)
    params = {"api_key": api_key}
    if cache is not None:
        cached = cache.get_alternative_titles(url, params)
        if cached is not None:
            return cached
    data = await _request_tmdb_json(url, params, config, client)
    titles, cacheable = _map_tmdb_alternative_titles_with_cacheability(data, media_type)
    if cache is not None and cacheable:
        await cache.store_alternative_titles(url, params, titles)
    return titles


def is_valid_tmdb_api_key(api_key: str) -> bool:
    """Return whether a TMDB API key matches the API v3 key format."""
    return TMDB_KEY_REGEX.fullmatch(api_key) is not None


async def lookup_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
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
    if cache is None:
        results = await search_tmdb(parsed, config, client)
    else:
        results = await search_tmdb(parsed, config, client, cache=cache)
    return results[0] if results else None
