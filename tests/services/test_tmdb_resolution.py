from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import anyio
import httpx
import pytest

import frame_compare.services.tmdb_resolution as tmdb_resolution
from frame_compare.services.errors import TmdbRateLimitedError
from frame_compare.services.metadata import resolve_metadata
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.tmdb_resolution import resolve_tmdb_match
from frame_compare.services.types import MetadataConfig, ParsedMetadata

type AsyncClientFactory = Callable[
    [httpx.MockTransport],
    AbstractAsyncContextManager[httpx.AsyncClient],
]


@asynccontextmanager
async def _client_for_transport(
    transport: httpx.MockTransport,
) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=transport) as client:
        yield client


@pytest.fixture
def async_client_factory() -> AsyncClientFactory:
    return _client_for_transport


def _movie_result(
    tmdb_id: int,
    title: str,
    release_date: str,
    *,
    original_title: str | None = None,
    media_type: str | None = "movie",
    popularity: float = 0.0,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": tmdb_id,
        "title": title,
        "original_title": title if original_title is None else original_title,
        "release_date": release_date,
        "popularity": popularity,
    }
    if media_type is not None:
        payload["media_type"] = media_type
    return payload


@pytest.mark.anyio
async def test_resolve_metadata_prefers_vvitch_alias_release(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(526667, "The Witch", "2015-01-23", popularity=35.0),
                        _movie_result(310131, "The Witch", "2016-02-19", popularity=30.0),
                    ]
                },
            )
        if path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(
                            526667,
                            "The Witch",
                            "2015-01-23",
                            media_type=None,
                            popularity=35.0,
                        ),
                        _movie_result(
                            310131,
                            "The Witch",
                            "2016-02-19",
                            media_type=None,
                            popularity=30.0,
                        ),
                    ]
                },
            )
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/movie/310131/alternative_titles"):
            return httpx.Response(
                200,
                json={"titles": [{"title": "The VVitch: A New-England Folktale"}]},
            )
        if path.endswith("/movie/526667/alternative_titles"):
            return httpx.Response(200, json={"titles": [{"title": "The Witch"}]})
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        result = await resolve_metadata(
            ["The.VVitch.A.New-England.Folktale.2015.2160p.mkv"],
            config,
            client,
        )

    assert result is not None
    assert result.tmdb_id == 310131


@pytest.mark.anyio
async def test_resolve_metadata_keeps_match_when_alias_enrichment_is_rate_limited(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/movie/329865/alternative_titles"):
            return httpx.Response(429)
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/search/multi") or path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={"results": [_movie_result(329865, "Arrival", "2016-11-10")]},
            )
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        result = await resolve_metadata(["Arrival.2016.2160p.mkv"], config, client)

    assert result is not None
    assert result.tmdb_id == 329865


@pytest.mark.anyio
async def test_resolve_metadata_plain_title_alias_case_prefers_vvitch_release(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(526667, "The Witch", "2015-01-23", popularity=35.0),
                        _movie_result(310131, "The Witch", "2016-02-19", popularity=30.0),
                    ]
                },
            )
        if path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(
                            526667,
                            "The Witch",
                            "2015-01-23",
                            media_type=None,
                            popularity=35.0,
                        ),
                        _movie_result(
                            310131,
                            "The Witch",
                            "2016-02-19",
                            media_type=None,
                            popularity=30.0,
                        ),
                    ]
                },
            )
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/movie/310131/alternative_titles"):
            return httpx.Response(
                200,
                json={"titles": [{"title": "The VVitch: A New-England Folktale"}]},
            )
        if path.endswith("/movie/526667/alternative_titles"):
            return httpx.Response(200, json={"titles": [{"title": "The Witch"}]})
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        result = await resolve_metadata(
            ["The.Witch.2015.2160p.UHD.BDRip.DV.HDR10.x265.mkv"],
            config,
            client,
        )

    assert result is not None
    assert result.tmdb_id == 310131


@pytest.mark.anyio
async def test_resolve_metadata_returns_none_for_ambiguous_unattended_match(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(10, "The Witch", "2015-01-01", popularity=20.0),
                        _movie_result(11, "The Witch", "2016-01-01", popularity=19.0),
                    ]
                },
            )
        if path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(10, "The Witch", "2015-01-01", media_type=None),
                        _movie_result(11, "The Witch", "2016-01-01", media_type=None),
                    ]
                },
            )
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/alternative_titles"):
            return httpx.Response(200, json={"titles": [{"title": "The Witch"}]})
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32, unattended=True)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        result = await resolve_metadata(["The.Witch.2015.mkv"], config, client)

    assert result is None


@pytest.mark.anyio
async def test_resolve_metadata_auto_accepts_high_confidence_exact_match(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={"results": [_movie_result(329865, "Arrival", "2016-11-10", popularity=40.0)]},
            )
        if path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(
                            329865, "Arrival", "2016-11-10", media_type=None, popularity=40.0
                        )
                    ]
                },
            )
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        result = await resolve_metadata(["Arrival.2016.2160p.mkv"], config, client)

    assert result is not None
    assert result.tmdb_id == 329865


@pytest.mark.anyio
async def test_resolve_tmdb_match_returns_ranked_candidates_when_unresolved(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(10, "The Witch", "2015-01-01", popularity=20.0),
                        _movie_result(11, "The Witch", "2016-01-01", popularity=19.0),
                    ]
                },
            )
        if path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        _movie_result(10, "The Witch", "2015-01-01", media_type=None),
                        _movie_result(11, "The Witch", "2016-01-01", media_type=None),
                    ]
                },
            )
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/alternative_titles"):
            return httpx.Response(200, json={"titles": [{"title": "The Witch"}]})
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    parsed = ParsedMetadata(title="The Witch", year=2015)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        outcome = await resolve_tmdb_match(parsed, config, client)

    assert outcome.selected is None
    assert [candidate.tmdb_id for candidate in outcome.candidates[:2]] == [10, 11]


@pytest.mark.anyio
async def test_resolve_tmdb_match_does_not_auto_select_movie_for_tv_hint(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={
                    "results": [_movie_result(2316, "The Office", "2005-01-01", popularity=25.0)]
                },
            )
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    parsed = ParsedMetadata(title="The Office", year=2005, season=1, episode=1)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        outcome = await resolve_tmdb_match(parsed, config, client)

    assert outcome.selected is None
    assert outcome.candidates
    assert outcome.candidates[0].media_type == "movie"


@pytest.mark.anyio
async def test_resolve_tmdb_match_auto_accepts_exact_tv_match_without_parsed_year(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search/tv"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 95396,
                            "name": "Severance",
                            "original_name": "Severance",
                            "first_air_date": "2022-02-18",
                        }
                    ]
                },
            )
        if path.endswith("/search/multi"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 95396,
                            "name": "Severance",
                            "original_name": "Severance",
                            "first_air_date": "2022-02-18",
                            "media_type": "tv",
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    parsed = ParsedMetadata(title="Severance", season=1, episode=1)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        outcome = await resolve_tmdb_match(parsed, config, client)

    assert outcome.selected is not None
    assert outcome.selected.tmdb_id == 95396


@pytest.mark.anyio
async def test_resolve_tmdb_match_searches_variants_with_bounded_concurrency(
    async_client_factory: AsyncClientFactory,
) -> None:
    active_requests = 0
    max_active_requests = 0
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_requests, max_active_requests, request_count
        del request
        active_requests += 1
        request_count += 1
        max_active_requests = max(max_active_requests, active_requests)
        await anyio.sleep(0.01)
        active_requests -= 1
        return httpx.Response(200, json={"results": []})

    config = MetadataConfig(api_key="a" * 32)
    parsed = ParsedMetadata(title="The VVitch IV: Chapter 2", year=2024)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        outcome = await resolve_tmdb_match(parsed, config, client)

    assert outcome.selected is None
    assert outcome.candidates == []
    assert request_count > tmdb_resolution.MAX_CONCURRENT_SEARCH_REQUESTS
    assert 1 < max_active_requests <= tmdb_resolution.MAX_CONCURRENT_SEARCH_REQUESTS


@pytest.mark.anyio
async def test_resolve_tmdb_match_preserves_results_when_search_variant_fails(
    async_client_factory: AsyncClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search/movie"):
            return httpx.Response(503)
        if request.url.path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        if request.url.path.endswith("/alternative_titles"):
            return httpx.Response(200, json={"titles": []})
        return httpx.Response(
            200,
            json={"results": [_movie_result(329865, "Arrival", "2016-11-10")]},
        )

    monkeypatch.setattr(
        tmdb_resolution.log,
        "warning",
        lambda event, **fields: warnings.append({"event": event, **fields}),
    )
    config = MetadataConfig(api_key="a" * 32)
    parsed = ParsedMetadata(title="Arrival", year=2016)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        outcome = await resolve_tmdb_match(parsed, config, client)

    assert outcome.selected is not None
    assert outcome.selected.tmdb_id == 329865
    assert warnings == [
        {
            "event": "tmdb_search_variants_degraded",
            "failed_request_count": 2,
            "total_request_count": 6,
            "error_types": ["TmdbError"],
        }
    ]


@pytest.mark.anyio
async def test_resolve_tmdb_match_raises_first_error_when_all_variants_fail(
    async_client_factory: AsyncClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search/multi") and request.url.params.get("year"):
            return httpx.Response(429)
        return httpx.Response(503)

    config = MetadataConfig(api_key="a" * 32)
    parsed = ParsedMetadata(title="Arrival", year=2016)
    async with async_client_factory(httpx.MockTransport(handler)) as client:
        with pytest.raises(TmdbRateLimitedError):
            await resolve_tmdb_match(parsed, config, client)


@pytest.mark.anyio
async def test_resolver_cache_replays_candidates_and_aliases_without_network(
    tmp_path: Path,
    async_client_factory: AsyncClientFactory,
) -> None:
    candidate = _movie_result(
        329865,
        "Arrival",
        "2016-11-10",
        popularity=25.0,
    )

    def first_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/alternative_titles"):
            return httpx.Response(200, json={"titles": []})
        if request.url.path.endswith("/search/tv"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"results": [candidate]})

    config = MetadataConfig(api_key="a" * 32, category_preference="movie")
    parsed = ParsedMetadata(title="Arrival", year=2016)
    cache = TmdbCache(tmp_path / "tmdb.toml")

    async with async_client_factory(httpx.MockTransport(first_handler)) as client:
        first = await resolve_tmdb_match(parsed, config, client, cache=cache)

    def unexpected_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected TMDB request: {request.url}")

    async with async_client_factory(httpx.MockTransport(unexpected_network)) as client:
        second = await resolve_tmdb_match(parsed, config, client, cache=cache)

    assert second == first
