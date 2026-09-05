from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Literal, get_args

import httpx
import pytest
import structlog

import frame_compare.services.tmdb_lookup as tmdb_lookup
from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.metadata import lookup_tmdb as metadata_lookup_tmdb
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata
from frame_compare.utils.logging import configure_logging


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
                        "original_language": "en",
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
            original_language="en",
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
@pytest.mark.parametrize("failure_kind", ["status", "request", "timeout", "decode"])
async def test_tmdb_failures_do_not_leak_api_key_through_json_tracebacks(
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    api_key = "d34db33fd34db33fd34db33fd34db33f"
    stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", stream)
    configure_logging(log_format="json")

    def handler(request: httpx.Request) -> httpx.Response:
        if failure_kind == "status":
            return httpx.Response(403)
        if failure_kind == "request":
            raise httpx.ConnectError("transport failed", request=request)
        if failure_kind == "timeout":
            raise httpx.TimeoutException("request timed out", request=request)
        return httpx.Response(200, content=f'{{"credential":"{api_key}"')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        try:
            await tmdb_lookup.lookup_tmdb(
                ParsedMetadata(title="Arrival"),
                MetadataConfig(api_key=api_key),
                client,
            )
        except TmdbError as exc:
            structlog.get_logger().warning("metadata_degraded", exc_info=exc)
            assert exc.__cause__ is None
            assert exc.__context__ is None
        else:
            pytest.fail("TMDB failure did not raise TmdbError")

    payload = json.loads(stream.getvalue())
    assert payload["exception"]
    assert api_key not in json.dumps(payload)


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


@pytest.mark.anyio
async def test_search_tmdb_cache_hit_reuses_ordered_response_across_api_keys(
    tmp_path: Path,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 2,
                        "title": "Second",
                        "original_title": "Second",
                        "release_date": "2020-01-01",
                    },
                    {
                        "id": 1,
                        "title": "First",
                        "original_title": "First",
                        "release_date": "2019-01-01",
                    },
                ]
            },
        )

    cache = TmdbCache(tmp_path / "tmdb.toml")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await tmdb_lookup.search_tmdb_movie(
            ParsedMetadata(title="Ordered"),
            MetadataConfig(api_key="a" * 32),
            client,
            cache=cache,
        )
        second = await tmdb_lookup.search_tmdb_movie(
            ParsedMetadata(title="Ordered"),
            MetadataConfig(api_key="b" * 32),
            client,
            cache=cache,
        )

    assert second == first
    assert [item.tmdb_id for item in second] == [2, 1]
    assert request_count == 1


@pytest.mark.anyio
async def test_search_tmdb_invalid_utf8_cache_falls_back_to_network(tmp_path: Path) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache_path.write_bytes(b"\xff")
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={"results": [{"id": 1, "title": "Known", "release_date": "2020-01-01"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await tmdb_lookup.search_tmdb_movie(
            ParsedMetadata(title="Known"),
            MetadataConfig(api_key="a" * 32),
            client,
            cache=TmdbCache(cache_path),
        )

    assert [item.tmdb_id for item in result] == [1]
    assert request_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "malformed_result",
    [
        "malformed-result",
        {"id": 1.5, "title": "Float ID", "release_date": "2020-01-01"},
        {"title": "Missing ID", "release_date": "2020-01-01"},
    ],
)
async def test_lookup_does_not_cache_malformed_success_response(
    tmp_path: Path,
    malformed_result: object,
) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "results": [
                    {"id": 1, "title": "Valid", "release_date": "2020-01-01"},
                    malformed_result,
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await tmdb_lookup.search_tmdb_movie(
            ParsedMetadata(title="Malformed"),
            MetadataConfig(api_key="a" * 32),
            client,
            cache=cache,
        )

    assert [item.tmdb_id for item in result] == [1]
    assert not cache_path.exists()


@pytest.mark.anyio
async def test_multi_search_can_cache_while_ignoring_person_results(tmp_path: Path) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "results": [
                    {"id": 9, "media_type": "person", "name": "Performer"},
                    {
                        "id": 1,
                        "media_type": "movie",
                        "title": "Known",
                        "release_date": "2020-01-01",
                    },
                ]
            },
        )

    cache = TmdbCache(tmp_path / "tmdb.toml")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await tmdb_lookup.search_tmdb(
            ParsedMetadata(title="Known"),
            MetadataConfig(api_key="a" * 32),
            client,
            cache=cache,
        )
        second = await tmdb_lookup.search_tmdb(
            ParsedMetadata(title="Known"),
            MetadataConfig(api_key="b" * 32),
            client,
            cache=cache,
        )

    assert second == first
    assert [item.tmdb_id for item in second] == [1]
    assert request_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "person_result",
    [
        {"media_type": "person", "name": "Missing ID"},
        {"id": 1.5, "media_type": "person", "name": "Float ID"},
        {"id": 9, "media_type": "person"},
        {"id": 9, "media_type": "person", "name": "  "},
    ],
)
async def test_multi_search_does_not_cache_malformed_person_results(
    tmp_path: Path,
    person_result: object,
) -> None:
    cache_path = tmp_path / "tmdb.toml"

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "results": [
                    person_result,
                    {
                        "id": 1,
                        "media_type": "movie",
                        "title": "Known",
                        "release_date": "2020-01-01",
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await tmdb_lookup.search_tmdb(
            ParsedMetadata(title="Known"),
            MetadataConfig(api_key="a" * 32),
            client,
            cache=TmdbCache(cache_path),
        )

    assert [item.tmdb_id for item in result] == [1]
    assert not cache_path.exists()


@pytest.mark.anyio
async def test_alternative_title_cache_preserves_empty_response_but_not_malformed_container(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(200, json={"titles": {}})
        return httpx.Response(200, json={"titles": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        malformed = await tmdb_lookup.fetch_tmdb_alternative_titles(
            1,
            "movie",
            MetadataConfig(api_key="a" * 32),
            client,
            cache=cache,
        )
        valid_empty = await tmdb_lookup.fetch_tmdb_alternative_titles(
            1,
            "movie",
            MetadataConfig(api_key="a" * 32),
            client,
            cache=cache,
        )
        cached_empty = await tmdb_lookup.fetch_tmdb_alternative_titles(
            1,
            "movie",
            MetadataConfig(api_key="b" * 32),
            client,
            cache=cache,
        )

    assert malformed == []
    assert valid_empty == []
    assert cached_empty == []
    assert requests == 2


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [401, 429, 500])
async def test_search_errors_never_create_cache_file(
    tmp_path: Path,
    status_code: int,
) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code))
    ) as client:
        with pytest.raises((TmdbError, TmdbRateLimitedError)):
            await tmdb_lookup.search_tmdb_movie(
                ParsedMetadata(title="Failure"),
                MetadataConfig(api_key="a" * 32),
                client,
                cache=cache,
            )

    assert not cache_path.exists()


@pytest.mark.anyio
@pytest.mark.parametrize("failure_kind", ["timeout", "transport", "json"])
async def test_transport_and_decode_errors_never_create_cache_file(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if failure_kind == "timeout":
            raise httpx.TimeoutException("slow", request=request)
        if failure_kind == "transport":
            raise httpx.ConnectError("failed", request=request)
        return httpx.Response(200, content=b"not-json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TmdbError):
            await tmdb_lookup.search_tmdb_movie(
                ParsedMetadata(title="Failure"),
                MetadataConfig(api_key="a" * 32),
                client,
                cache=cache,
            )

    assert not cache_path.exists()


@pytest.mark.anyio
async def test_missing_or_invalid_api_key_skips_cache_io(tmp_path: Path) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)

    async with httpx.AsyncClient() as client:
        assert (
            await tmdb_lookup.search_tmdb_movie(
                ParsedMetadata(title="No key"),
                MetadataConfig(api_key=None),
                client,
                cache=cache,
            )
            == []
        )
        with pytest.raises(TmdbError, match="Invalid API key format"):
            await tmdb_lookup.search_tmdb_movie(
                ParsedMetadata(title="Bad key"),
                MetadataConfig(api_key="not-a-key"),
                client,
                cache=cache,
            )

    assert not cache_path.exists()
