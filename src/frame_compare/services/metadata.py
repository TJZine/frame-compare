"""Filename parsing and TMDB lookup service."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

import anitopy
import httpx
import structlog
from guessit import guessit

from frame_compare.services.errors import MetadataError, TmdbError, TmdbRateLimitedError
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

TMDB_API_URL = "https://api.themoviedb.org/3/search/multi"
TMDB_IMAGE_ORIGINAL_BASE_URL = "https://image.tmdb.org/t/p/original"
TMDB_KEY_REGEX = re.compile(r"^[0-9a-fA-F]{32}$")
log = structlog.get_logger()

type FilenameMetadataParser = Callable[[str], dict[str, object]]
type _ParsedField = str | int
_TParsedField = TypeVar("_TParsedField", bound=_ParsedField)


@dataclass(frozen=True)
class _ParsedFilenameFields:
    title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    release_group: str | None = None
    source: str | None = None
    resolution: str | None = None


def is_valid_tmdb_api_key(api_key: str) -> bool:
    """Return whether a TMDB API key matches the API v3 key format."""
    return TMDB_KEY_REGEX.fullmatch(api_key) is not None


def _first_text(parser_result: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = parser_result.get(key)
        if value:
            return str(value)
    return None


def _first_int(parser_result: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        value = parser_result.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        if isinstance(value, list) and value and isinstance(value[0], int):
            return value[0]
    return None


def _keep_existing(
    existing: _TParsedField | None,
    parsed: _TParsedField | None,
) -> _TParsedField | None:
    return existing if existing is not None else parsed


def _merge_parser_metadata(
    current: _ParsedFilenameFields,
    parser_result: dict[str, object],
) -> _ParsedFilenameFields:
    return _ParsedFilenameFields(
        title=_keep_existing(
            current.title,
            _first_text(parser_result, "anime_title", "title"),
        ),
        year=_keep_existing(current.year, _first_int(parser_result, "year")),
        season=_keep_existing(current.season, _first_int(parser_result, "season")),
        episode=_keep_existing(
            current.episode,
            _first_int(parser_result, "anime_episode", "episode"),
        ),
        release_group=_keep_existing(
            current.release_group,
            _first_text(parser_result, "release_group"),
        ),
        source=_keep_existing(current.source, _first_text(parser_result, "source")),
        resolution=_keep_existing(
            current.resolution,
            _first_text(parser_result, "screen_size", "video_resolution"),
        ),
    )


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

    def _log_parser_exception(parser_name: str, name: str, exc: Exception) -> None:
        log.debug(
            "filename_metadata_parser_failed",
            parser=parser_name,
            filename_stem=Path(name).stem,
            exception_type=type(exc).__name__,
            error=str(exc),
        )

    def _normalize_parser_result(result: object) -> dict[str, object]:
        if not isinstance(result, Mapping):
            return {}
        parser_mapping = cast(Mapping[object, object], result)
        return {key: value for key, value in parser_mapping.items() if isinstance(key, str)}

    def _apply_anitopy(name: str) -> dict[str, object]:
        try:
            return _normalize_parser_result(anitopy.parse(name))
        except Exception as exc:
            _log_parser_exception("anitopy", name, exc)
            return {}

    def _apply_guessit(name: str) -> dict[str, object]:
        try:
            return _normalize_parser_result(guessit(name))
        except Exception as exc:
            _log_parser_exception("guessit", name, exc)
            return {}

    parsers: list[FilenameMetadataParser] = [
        (_apply_anitopy if use_anitopy_first else _apply_guessit),
        (_apply_guessit if use_anitopy_first else _apply_anitopy),
    ]

    fields = _ParsedFilenameFields()

    for parser in parsers:
        fields = _merge_parser_metadata(fields, parser(filename))

    title = fields.title or Path(filename).stem

    # Normalization
    title = re.sub(r"[._\-]", " ", title).strip()

    return ParsedMetadata(
        title=title,
        year=fields.year,
        season=fields.season,
        episode=fields.episode,
        release_group=fields.release_group,
        source=fields.source,
        resolution=fields.resolution,
    )


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

    results_raw = cast(list[dict[str, Any]], data.get("results", []))
    mapped_results: list[TmdbMetadata] = []

    for item in results_raw:
        media_type_raw = item.get("media_type", "movie")
        if media_type_raw == "movie":
            media_type = "movie"
        elif media_type_raw == "tv":
            media_type = "tv"
        else:
            continue

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
            return f"{TMDB_IMAGE_ORIGINAL_BASE_URL}{path}"

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
