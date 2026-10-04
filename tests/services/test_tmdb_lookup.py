from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Literal

import httpx
import pytest
import structlog

import frame_compare.services.tmdb_lookup as tmdb_lookup
from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata
from frame_compare.utils.logging import configure_logging


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("media_type", "key", "title", "payload", "expected"),
    [
        (
            "movie",
            "b" * 32,
            "Arrival",
            {
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
            [
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
            ],
        ),
        (
            "tv",
            "c" * 32,
            "Severance",
            {
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
            [
                TmdbMetadata(
                    tmdb_id=95396,
                    title="Severance",
                    original_title="Severance",
                    year=2022,
                    media_type="tv",
                    poster_url="https://image.tmdb.org/t/p/original/poster.jpg",
                    backdrop_url="https://image.tmdb.org/t/p/original/backdrop.jpg",
                )
            ],
        ),
    ],
)
async def test_search_tmdb_endpoint_mapping(
    media_type: Literal["movie", "tv"],
    key: str,
    title: str,
    payload: object,
    expected: list[TmdbMetadata],
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == f"/3/search/{media_type}"
        assert request.url.params["api_key"] == key
        assert request.url.params["query"] == title
        assert request.url.params["include_adult"] == "false"
        return httpx.Response(200, json=payload)

    search = tmdb_lookup.search_tmdb_movie if media_type == "movie" else tmdb_lookup.search_tmdb_tv
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await search(
            ParsedMetadata(title=title), MetadataConfig(api_key=key, timeout_seconds=3.5), client
        )
    assert requests
    assert results == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("media_type", "tmdb_id", "key", "payload", "expected"),
    [
        (
            "movie",
            329865,
            "d" * 32,
            {
                "titles": [
                    {"iso_3166_1": "US", "title": "Story of Your Life"},
                    {"iso_3166_1": "GB", "title": "Arrival"},
                ]
            },
            ["Story of Your Life", "Arrival"],
        ),
        (
            "tv",
            95396,
            "e" * 32,
            {
                "results": [
                    {"iso_3166_1": "US", "title": "Severance"},
                    {"iso_3166_1": "JP", "title": "Severance JP"},
                ]
            },
            ["Severance", "Severance JP"],
        ),
        (
            "movie",
            42,
            "f" * 32,
            {
                "titles": [
                    "bad-entry",
                    {"title": "Alias 1"},
                    {"title": 123},
                    {"iso_3166_1": "US"},
                    {"title": "Alias 2"},
                ]
            },
            ["Alias 1", "Alias 2"],
        ),
        (
            "tv",
            43,
            "f" * 32,
            {
                "results": [
                    "bad-entry",
                    {"title": "Alias 1"},
                    {"title": 123},
                    {"iso_3166_1": "US"},
                    {"title": "Alias 2"},
                ]
            },
            ["Alias 1", "Alias 2"],
        ),
        ("movie", 44, "f" * 32, {}, []),
        ("tv", 45, "f" * 32, {}, []),
    ],
)
async def test_fetch_tmdb_alternative_title_mapping(
    media_type: Literal["movie", "tv"], tmdb_id: int, key: str, payload: object, expected: list[str]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.themoviedb.org"
        assert request.url.path == f"/3/{media_type}/{tmdb_id}/alternative_titles"
        if key != "f" * 32:
            assert request.url.params["api_key"] == key
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        titles = await tmdb_lookup.fetch_tmdb_alternative_titles(
            tmdb_id,
            media_type,
            MetadataConfig(api_key=key, timeout_seconds=3.5 if key != "f" * 32 else 10.0),
            client,
        )
    assert titles == expected


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
            await tmdb_lookup.search_tmdb(
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
        result = await tmdb_lookup.search_tmdb(
            ParsedMetadata(title="Valid Show"),
            MetadataConfig(api_key="a" * 32),
            client,
        )

    assert result == [
        TmdbMetadata(
            tmdb_id=42,
            title="Valid Show",
            original_title="Valid Show Original",
            year=0,
            media_type="tv",
            poster_url=None,
            backdrop_url=None,
        )
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [[], {"results": {}}, {"results": "not-a-list"}])
async def test_tmdb_lookup_malformed_top_level_payload_raises_domain_error(
    payload: object,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(TmdbError) as excinfo:
            await tmdb_lookup.search_tmdb(
                ParsedMetadata(title="No Results"),
                MetadataConfig(api_key="a" * 32),
                client,
            )

    assert excinfo.value.context.details == {"reason": "Malformed TMDB response"}


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
@pytest.mark.parametrize("failure", [401, 429, 500, "timeout", "transport", "json"])
async def test_search_failures_never_create_cache_file(tmp_path: Path, failure: int | str) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.TimeoutException("slow", request=request)
        if failure == "transport":
            raise httpx.ConnectError("failed", request=request)
        if isinstance(failure, int):
            return httpx.Response(failure)
        return httpx.Response(200, content=b"not-json")

    errors = (TmdbError, TmdbRateLimitedError) if isinstance(failure, int) else TmdbError
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(errors):
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
