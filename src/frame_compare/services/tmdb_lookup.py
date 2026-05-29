"""TMDB metadata lookup service."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

import httpx

from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

type _TmdbMediaType = Literal["movie", "tv"]


@dataclass(frozen=True)
class TmdbSearchHit:
    metadata: TmdbMetadata
    popularity: float

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
    params: dict[str, str | int],
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


def _tmdb_result_popularity(item: Mapping[str, object]) -> float:
    popularity_raw = item.get("popularity")
    if isinstance(popularity_raw, bool):
        return 0.0
    if isinstance(popularity_raw, int | float):
        return float(popularity_raw)
    if isinstance(popularity_raw, str):
        try:
            return float(popularity_raw)
        except ValueError:
            return 0.0
    return 0.0


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
        poster_url=_tmdb_image_url(_optional_str(item.get("poster_path"))),
        backdrop_url=_tmdb_image_url(_optional_str(item.get("backdrop_path"))),
    )


def _map_tmdb_hit(
    item: Mapping[str, object],
    *,
    endpoint_media_type: _TmdbMediaType | None = None,
) -> TmdbSearchHit | None:
    metadata = _map_tmdb_result(item, endpoint_media_type)
    if metadata is None:
        return None
    return TmdbSearchHit(metadata=metadata, popularity=_tmdb_result_popularity(item))


def _map_tmdb_hits(
    data: object,
    *,
    endpoint_media_type: _TmdbMediaType | None = None,
) -> list[TmdbSearchHit]:
    if not isinstance(data, dict):
        raise TmdbError("Malformed TMDB response")

    data_dict = cast(dict[str, object], data)
    results_raw = data_dict.get("results", [])
    if not isinstance(results_raw, list):
        raise TmdbError("Malformed TMDB response")

    mapped_hits: list[TmdbSearchHit] = []
    for item in cast(list[object], results_raw):
        if not isinstance(item, dict):
            continue
        hit = _map_tmdb_hit(cast(dict[str, object], item), endpoint_media_type=endpoint_media_type)
        if hit is not None:
            mapped_hits.append(hit)
    return mapped_hits


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
    params: dict[str, str | int],
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
) -> list[TmdbMetadata]:
    hits = await _search_tmdb_endpoint_hits(
        parsed,
        config,
        client,
        url=url,
        endpoint_media_type=endpoint_media_type,
    )
    return [hit.metadata for hit in hits]


async def _search_tmdb_endpoint_hits(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    url: str,
    endpoint_media_type: _TmdbMediaType | None = None,
) -> list[TmdbSearchHit]:
    api_key = _validate_tmdb_api_key(config)
    if api_key is None:
        return []

    year_param_name = "first_air_date_year" if endpoint_media_type == "tv" else "year"
    params = _build_search_params(parsed, api_key, year_param_name=year_param_name)
    data = await _request_tmdb_json(url, params, config, client)
    return _map_tmdb_hits(data, endpoint_media_type=endpoint_media_type)


async def search_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbMetadata]:
    return await _search_tmdb_endpoint(
        parsed,
        config,
        client,
        url=TMDB_MULTI_SEARCH_URL,
    )


async def search_tmdb_multi_hits(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbSearchHit]:
    return await _search_tmdb_endpoint_hits(
        parsed,
        config,
        client,
        url=TMDB_MULTI_SEARCH_URL,
    )


async def search_tmdb_movie(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbMetadata]:
    return await _search_tmdb_endpoint(
        parsed,
        config,
        client,
        url=TMDB_MOVIE_SEARCH_URL,
        endpoint_media_type="movie",
    )


async def search_tmdb_movie_hits(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbSearchHit]:
    return await _search_tmdb_endpoint_hits(
        parsed,
        config,
        client,
        url=TMDB_MOVIE_SEARCH_URL,
        endpoint_media_type="movie",
    )


async def search_tmdb_tv(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbMetadata]:
    return await _search_tmdb_endpoint(
        parsed,
        config,
        client,
        url=TMDB_TV_SEARCH_URL,
        endpoint_media_type="tv",
    )


async def search_tmdb_tv_hits(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[TmdbSearchHit]:
    return await _search_tmdb_endpoint_hits(
        parsed,
        config,
        client,
        url=TMDB_TV_SEARCH_URL,
        endpoint_media_type="tv",
    )


async def fetch_tmdb_alternative_titles(
    tmdb_id: int,
    media_type: _TmdbMediaType,
    config: MetadataConfig,
    client: httpx.AsyncClient,
) -> list[str]:
    api_key = _validate_tmdb_api_key(config)
    if api_key is None:
        return []

    data = await _request_tmdb_json(
        _build_alternative_titles_url(tmdb_id, media_type),
        {"api_key": api_key},
        config,
        client,
    )
    return _map_tmdb_alternative_titles(data, media_type)


def is_valid_tmdb_api_key(api_key: str) -> bool:
    """Return whether a TMDB API key matches the API v3 key format."""
    return TMDB_KEY_REGEX.fullmatch(api_key) is not None


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
    results = await search_tmdb(parsed, config, client)
    return results[0] if results else None
