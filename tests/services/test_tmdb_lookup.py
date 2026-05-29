from __future__ import annotations

from typing import Literal, get_args

import httpx
import pytest

import frame_compare.services.tmdb_lookup as tmdb_lookup
from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.metadata import lookup_tmdb as metadata_lookup_tmdb
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata


def test_tmdb_metadata_media_type_is_closed_domain() -> None:
    assert set(get_args(TmdbMetadata.__dataclass_fields__["media_type"].type)) == {"movie", "tv"}


def test_metadata_lookup_tmdb_alias_identity() -> None:
    assert metadata_lookup_tmdb is tmdb_lookup.lookup_tmdb


@pytest.mark.anyio
async def test_search_tmdb_movie_maps_movie_endpoint_without_media_type() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == "/3/search/movie"
        assert request.url.params["api_key"] == "b" * 32
        assert request.url.params["query"] == "Arrival"
        assert request.url.params["include_adult"] == "false"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 329865,
                        "title": "Arrival",
                        "original_title": "Arrival",
                        "release_date": "2016-11-10",
                        "poster_path": "/poster.jpg",
                        "backdrop_path": None,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await tmdb_lookup.search_tmdb_movie(
            ParsedMetadata(title="Arrival"),
            MetadataConfig(api_key="b" * 32, timeout_seconds=3.5),
            client,
        )

    assert requests
    assert results == [
        TmdbMetadata(
            tmdb_id=329865,
            title="Arrival",
            original_title="Arrival",
            year=2016,
            media_type="movie",
            poster_url="https://image.tmdb.org/t/p/original/poster.jpg",
            backdrop_url=None,
        )
    ]


@pytest.mark.anyio
async def test_search_tmdb_tv_maps_tv_endpoint_without_media_type() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == "/3/search/tv"
        assert request.url.params["api_key"] == "c" * 32
        assert request.url.params["query"] == "Severance"
        assert request.url.params["include_adult"] == "false"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 95396,
                        "name": "Severance",
                        "original_name": "Severance",
                        "first_air_date": "2022-02-17",
                        "poster_path": "/poster.jpg",
                        "backdrop_path": "/backdrop.jpg",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await tmdb_lookup.search_tmdb_tv(
            ParsedMetadata(title="Severance"),
            MetadataConfig(api_key="c" * 32, timeout_seconds=3.5),
            client,
        )

    assert requests
    assert results == [
        TmdbMetadata(
            tmdb_id=95396,
            title="Severance",
            original_title="Severance",
            year=2022,
            media_type="tv",
            poster_url="https://image.tmdb.org/t/p/original/poster.jpg",
            backdrop_url="https://image.tmdb.org/t/p/original/backdrop.jpg",
        )
    ]


@pytest.mark.anyio
async def test_fetch_tmdb_alternative_titles_movie_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == "/3/movie/329865/alternative_titles"
        assert request.url.params["api_key"] == "d" * 32
        return httpx.Response(
            200,
            json={
                "titles": [
                    {"iso_3166_1": "US", "title": "Story of Your Life"},
                    {"iso_3166_1": "GB", "title": "Arrival"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        titles = await tmdb_lookup.fetch_tmdb_alternative_titles(
            329865,
            "movie",
            MetadataConfig(api_key="d" * 32, timeout_seconds=3.5),
            client,
        )

    assert titles == ["Story of Your Life", "Arrival"]


@pytest.mark.anyio
async def test_fetch_tmdb_alternative_titles_tv_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == "/3/tv/95396/alternative_titles"
        assert request.url.params["api_key"] == "e" * 32
        return httpx.Response(
            200,
            json={
                "results": [
                    {"iso_3166_1": "US", "title": "Severance"},
                    {"iso_3166_1": "JP", "title": "Severance JP"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        titles = await tmdb_lookup.fetch_tmdb_alternative_titles(
            95396,
            "tv",
            MetadataConfig(api_key="e" * 32, timeout_seconds=3.5),
            client,
        )

    assert titles == ["Severance", "Severance JP"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("media_type", "tmdb_id", "payload"),
    [
        (
            "movie",
            42,
            {
                "titles": [
                    "bad-entry",
                    {"title": "Alias 1"},
                    {"title": 123},
                    {"iso_3166_1": "US"},
                    {"title": "Alias 2"},
                ]
            },
        ),
        (
            "tv",
            43,
            {
                "results": [
                    "bad-entry",
                    {"title": "Alias 1"},
                    {"title": 123},
                    {"iso_3166_1": "US"},
                    {"title": "Alias 2"},
                ]
            },
        ),
        ("movie", 44, {}),
        ("tv", 45, {}),
    ],
)
async def test_fetch_tmdb_alternative_titles_ignores_malformed_or_missing_entries(
    media_type: Literal["movie", "tv"],
    tmdb_id: int,
    payload: object,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == f"/3/{media_type}/{tmdb_id}/alternative_titles"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        titles = await tmdb_lookup.fetch_tmdb_alternative_titles(
            tmdb_id,
            media_type,
            MetadataConfig(api_key="f" * 32),
            client,
        )

    expected = ["Alias 1", "Alias 2"] if isinstance(payload, dict) and payload else []
    assert titles == expected


@pytest.mark.anyio
async def test_tmdb_lookup_direct_module_classifies_http_and_transport_errors() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(401))
    ) as client:
        with pytest.raises(TmdbError) as excinfo:
            await tmdb_lookup.lookup_tmdb(
                ParsedMetadata(title="Arrival"),
                MetadataConfig(api_key="c" * 32),
                client,
            )

    assert excinfo.value.context.details == {"reason": "Invalid API key"}

    def raise_connect_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"leaked-key={'d' * 32}", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(raise_connect_error)) as client:
        with pytest.raises(TmdbError) as excinfo:
            await tmdb_lookup.lookup_tmdb(
                ParsedMetadata(title="Arrival"),
                MetadataConfig(api_key="d" * 32),
                client,
            )

    assert excinfo.value.context.details == {"reason": "Request failed"}
    assert "d" * 32 not in excinfo.value.context.message


@pytest.mark.anyio
async def test_tmdb_lookup_direct_module_classifies_rate_limit_and_timeout() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        with pytest.raises(TmdbRateLimitedError):
            await tmdb_lookup.lookup_tmdb(
                ParsedMetadata(title="Arrival"),
                MetadataConfig(api_key="e" * 32),
                client,
            )

    def raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(raise_timeout)) as client:
        with pytest.raises(TmdbError) as excinfo:
            await tmdb_lookup.lookup_tmdb(
                ParsedMetadata(title="Arrival"),
                MetadataConfig(api_key="f" * 32),
                client,
            )

    assert excinfo.value.context.details == {"reason": "Request timed out"}


def test_tmdb_lookup_direct_module_validates_api_key_shape() -> None:
    assert tmdb_lookup.is_valid_tmdb_api_key("0123456789abcdefABCDEF0123456789")
    assert not tmdb_lookup.is_valid_tmdb_api_key("g" * 32)


@pytest.mark.anyio
async def test_tmdb_lookup_skips_malformed_search_result_items() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "results": [
                        "not-a-dict",
                        {"id": "bad", "title": "Bad", "media_type": "movie"},
                        {"id": 42.9, "title": "Float ID", "media_type": "movie"},
                        {"id": 1, "title": "Person", "media_type": "person"},
                        {
                            "id": "42",
                            "name": "Valid Show",
                            "original_name": "Valid Show Original",
                            "first_air_date": 2020,
                            "media_type": "tv",
                            "poster_path": 123,
                        },
                    ]
                },
            )
        )
    ) as client:
        result = await tmdb_lookup.lookup_tmdb(
            ParsedMetadata(title="Valid Show"),
            MetadataConfig(api_key="a" * 32),
            client,
        )

    assert result == TmdbMetadata(
        tmdb_id=42,
        title="Valid Show",
        original_title="Valid Show Original",
        year=0,
        media_type="tv",
        poster_url=None,
        backdrop_url=None,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [[], {"results": {}}, {"results": "not-a-list"}])
async def test_tmdb_lookup_malformed_top_level_payload_raises_domain_error(
    payload: object,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(TmdbError) as excinfo:
            await tmdb_lookup.lookup_tmdb(
                ParsedMetadata(title="No Results"),
                MetadataConfig(api_key="a" * 32),
                client,
            )

    assert excinfo.value.context.details == {"reason": "Malformed TMDB response"}


@pytest.mark.anyio
async def test_tmdb_lookup_skips_float_id_without_truncating_to_int() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 42.9, "title": "Float ID", "media_type": "movie"},
                        {"id": 43, "title": "Integer ID", "media_type": "movie"},
                    ]
                },
            )
        )
    ) as client:
        result = await tmdb_lookup.lookup_tmdb(
            ParsedMetadata(title="Integer ID"),
            MetadataConfig(api_key="a" * 32),
            client,
        )

    assert result is not None
    assert result.tmdb_id == 43
    assert result.title == "Integer ID"
