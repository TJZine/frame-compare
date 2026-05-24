from typing import get_args

import httpx
import pytest

import frame_compare.services.tmdb_lookup as tmdb_lookup
from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.metadata import lookup_tmdb
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata


def test_tmdb_metadata_media_type_is_closed_domain() -> None:
    assert set(get_args(TmdbMetadata.__dataclass_fields__["media_type"].type)) == {"movie", "tv"}


@pytest.mark.anyio
async def test_tmdb_lookup_direct_module_maps_request_and_response_with_mock_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.themoviedb.org"
        assert request.url.params["api_key"] == "b" * 32
        assert request.url.params["query"] == "Arrival"
        assert request.url.params["year"] == "2016"
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
                        "media_type": "movie",
                        "poster_path": "/poster.jpg",
                        "backdrop_path": None,
                    },
                    {
                        "id": 123,
                        "name": "Ignored Person",
                        "media_type": "person",
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await tmdb_lookup.lookup_tmdb(
            ParsedMetadata(title="Arrival", year=2016),
            MetadataConfig(api_key="b" * 32, timeout_seconds=3.5),
            client,
        )

    assert requests
    assert result == TmdbMetadata(
        tmdb_id=329865,
        title="Arrival",
        original_title="Arrival",
        year=2016,
        media_type="movie",
        poster_url="https://image.tmdb.org/t/p/original/poster.jpg",
        backdrop_url=None,
    )
    assert lookup_tmdb is tmdb_lookup.lookup_tmdb


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
