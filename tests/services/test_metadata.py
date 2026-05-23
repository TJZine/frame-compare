from collections.abc import AsyncIterator
from typing import get_args

import httpx
import pytest
import respx

from frame_compare.errors import MetadataError
from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.metadata import lookup_tmdb, parse_filename, resolve_metadata
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata


@pytest.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    """Provide an httpx.AsyncClient for async tests."""
    async with httpx.AsyncClient() as client:
        yield client


MOCK_TMDB_MOVIE = {
    "results": [
        {
            "id": 550,
            "title": "Fight Club",
            "original_title": "Fight Club",
            "release_date": "1999-10-15",
            "media_type": "movie",
            "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
            "backdrop_path": "/hZkgoQYus5vegHoetLkCJzb17zJ.jpg",
        }
    ]
}

MOCK_TMDB_TV = {
    "results": [
        {
            "id": 1399,
            "name": "Game of Thrones",
            "original_name": "Game of Thrones",
            "first_air_date": "2011-04-17",
            "media_type": "tv",
            "poster_path": "/1XS1oqL89opfnbLl8WnZY1O1uJx.jpg",
            "backdrop_path": "/suopoADq0k8YZr4dQXcU6pToj6s.jpg",
        }
    ]
}

MOCK_TMDB_MULTI = {
    "results": [
        {
            "id": 1,
            "title": "Result 1",
            "release_date": "2020-01-01",
            "media_type": "movie",
        },
        {
            "id": 2,
            "title": "Result 2",
            "release_date": "2021-01-01",
            "media_type": "movie",
        },
    ]
}

MOCK_TMDB_MULTI_WITH_PERSON = {
    "results": [
        {
            "id": 1,
            "title": "Result 1",
            "release_date": "2020-01-01",
            "media_type": "movie",
        },
        {
            "id": 999,
            "name": "Some Actor",
            "media_type": "person",
        },
    ]
}

# ─── Filename Parsing Tests ───────────────────────────────────────────────────


def test_parse_filename_western_movie() -> None:
    result = parse_filename("Movie.Name.2024.BluRay.1080p.mkv")
    assert result.title == "Movie Name"
    assert result.year == 2024
    assert result.source == "Blu-ray"
    assert result.resolution == "1080p"


def test_parse_filename_anime_with_group() -> None:
    result = parse_filename("[SubGroup] Anime Title - 01 [1080p].mkv")
    assert result.title == "Anime Title"
    assert result.episode == 1
    assert result.release_group == "SubGroup"


def test_parse_filename_tv_show() -> None:
    result = parse_filename("Show.Name.S01E05.720p.WEB-DL.mkv")
    assert result.title == "Show Name"
    assert result.season == 1
    assert result.episode == 5


def test_parse_filename_minimal() -> None:
    result = parse_filename("video.mkv")
    assert result.title == "video"
    assert result.year is None
    assert result.season is None
    assert result.episode is None


def test_parse_filename_empty() -> None:
    result = parse_filename("")
    assert result.title == ""
    assert result.year is None


def test_parse_filename_parsers_raise_falls_back_to_stem(mocker) -> None:
    """When both parsers raise, fall back to filename stem."""
    mocker.patch(
        "frame_compare.services.metadata.guessit",
        side_effect=Exception("guessit error"),
    )
    mocker.patch(
        "frame_compare.services.metadata.anitopy.parse",
        side_effect=Exception("anitopy error"),
    )
    debug_log = mocker.patch("frame_compare.services.metadata.log.debug")

    result = parse_filename("Movie.Name.2024.BluRay.1080p.mkv")

    assert result.title == "Movie Name 2024 BluRay 1080p"
    assert result.year is None
    assert result.season is None
    assert result.episode is None
    assert result.release_group is None
    assert result.source is None
    assert result.resolution is None
    assert debug_log.call_count == 2
    debug_log.assert_any_call(
        "filename_metadata_parser_failed",
        parser="guessit",
        filename_stem="Movie.Name.2024.BluRay.1080p",
        exception_type="Exception",
        error="guessit error",
    )
    debug_log.assert_any_call(
        "filename_metadata_parser_failed",
        parser="anitopy",
        filename_stem="Movie.Name.2024.BluRay.1080p",
        exception_type="Exception",
        error="anitopy error",
    )


# ─── TMDB Lookup Tests ────────────────────────────────────────────────────────


def test_tmdb_metadata_media_type_is_closed_domain() -> None:
    assert set(get_args(TmdbMetadata.__dataclass_fields__["media_type"].type)) == {"movie", "tv"}


@pytest.mark.anyio
async def test_lookup_tmdb_returns_metadata(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_MOVIE)
    )
    parsed = ParsedMetadata(title="Fight Club", year=1999)
    config = MetadataConfig(api_key="a" * 32)

    result = await lookup_tmdb(parsed, config, async_client)

    assert result is not None
    assert result.tmdb_id == 550
    assert result.title == "Fight Club"
    assert result.year == 1999
    assert result.media_type == "movie"
    assert (
        result.poster_url == "https://image.tmdb.org/t/p/original/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg"
    )


@pytest.mark.anyio
async def test_lookup_tmdb_skips_person_results(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_MULTI_WITH_PERSON)
    )
    parsed = ParsedMetadata(title="Fight Club", year=1999)
    config = MetadataConfig(api_key="a" * 32)

    result = await lookup_tmdb(parsed, config, async_client)

    assert result is not None
    assert result.media_type in {"movie", "tv"}


@pytest.mark.anyio
async def test_lookup_tmdb_tv_uses_first_air_date(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_TV)
    )
    parsed = ParsedMetadata(title="Game of Thrones")
    config = MetadataConfig(api_key="a" * 32)

    result = await lookup_tmdb(parsed, config, async_client)

    assert result is not None
    assert result.tmdb_id == 1399
    assert result.year == 2011
    assert result.media_type == "tv"


@pytest.mark.anyio
async def test_lookup_tmdb_no_results(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    parsed = ParsedMetadata(title="Unknown Movie")
    config = MetadataConfig(api_key="a" * 32)

    result = await lookup_tmdb(parsed, config, async_client)
    assert result is None


@pytest.mark.anyio
async def test_lookup_tmdb_api_key_none(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    parsed = ParsedMetadata(title="Fight Club")
    config = MetadataConfig(api_key=None)

    result = await lookup_tmdb(parsed, config, async_client)

    assert result is None
    assert respx_mock.calls.call_count == 0


@pytest.mark.anyio
async def test_lookup_tmdb_invalid_api_key_format(async_client: httpx.AsyncClient) -> None:
    parsed = ParsedMetadata(title="Fight Club")
    config = MetadataConfig(api_key="short")

    with pytest.raises(TmdbError, match="Invalid API key format"):
        await lookup_tmdb(parsed, config, async_client)


@pytest.mark.anyio
async def test_lookup_tmdb_rejects_non_hex_api_key(async_client: httpx.AsyncClient) -> None:
    parsed = ParsedMetadata(title="Fight Club")
    config = MetadataConfig(api_key="g" * 32)

    with pytest.raises(TmdbError, match="Invalid API key format"):
        await lookup_tmdb(parsed, config, async_client)


@pytest.mark.anyio
async def test_lookup_tmdb_rate_limited(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(429)
    )
    parsed = ParsedMetadata(title="Fight Club")
    config = MetadataConfig(api_key="a" * 32)

    with pytest.raises(TmdbRateLimitedError):
        await lookup_tmdb(parsed, config, async_client)


@pytest.mark.anyio
async def test_lookup_tmdb_server_error(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(500)
    )
    parsed = ParsedMetadata(title="Fight Club")
    config = MetadataConfig(api_key="a" * 32)

    with pytest.raises(TmdbError, match="500"):
        await lookup_tmdb(parsed, config, async_client)


# ─── Resolve Metadata Tests ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_resolve_metadata_single_result(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_MOVIE)
    )
    config = MetadataConfig(api_key="a" * 32)

    result = await resolve_metadata(["Fight.Club.mkv"], config, async_client)

    assert result is not None
    assert result.tmdb_id == 550


@pytest.mark.anyio
async def test_resolve_metadata_no_results(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    config = MetadataConfig(api_key="a" * 32)

    result = await resolve_metadata(["Unknown.mkv"], config, async_client)
    assert result is None


@pytest.mark.anyio
async def test_resolve_metadata_unattended_mode(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_MULTI)
    )
    config = MetadataConfig(api_key="a" * 32, unattended=True)

    # Callback should not be called in unattended mode
    callback_called = False

    def callback(results: list[TmdbMetadata]) -> int:
        nonlocal callback_called
        callback_called = True
        return 1

    result = await resolve_metadata(["Multi.mkv"], config, async_client, prompt_callback=callback)

    assert result is not None
    assert result.tmdb_id == 1
    assert not callback_called


@pytest.mark.anyio
async def test_resolve_metadata_with_callback(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_MULTI)
    )
    config = MetadataConfig(api_key="a" * 32, unattended=False)

    def callback(results: list[TmdbMetadata]) -> int:
        assert len(results) == 2
        return 1  # Select second result

    result = await resolve_metadata(["Multi.mkv"], config, async_client, prompt_callback=callback)

    assert result is not None
    assert result.tmdb_id == 2


@pytest.mark.anyio
async def test_resolve_metadata_invalid_callback_index(
    respx_mock: respx.MockRouter, async_client: httpx.AsyncClient
) -> None:
    respx_mock.get(url__startswith="https://api.themoviedb.org/3/search/multi").mock(
        return_value=httpx.Response(200, json=MOCK_TMDB_MULTI)
    )
    config = MetadataConfig(api_key="a" * 32, unattended=False)

    def callback(results: list[TmdbMetadata]) -> int:
        return 99  # Invalid index

    with pytest.raises(MetadataError, match="invalid selection index"):
        await resolve_metadata(["Multi.mkv"], config, async_client, prompt_callback=callback)
