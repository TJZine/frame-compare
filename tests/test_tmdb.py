import asyncio
from typing import Dict, List

import httpx
import pytest

from src import tmdb as tmdb_module
from src.tmdb import (
    MOVIE,
    TV,
    TMDBCandidate,
    TMDBConfig,
    TMDBResolutionError,
    resolve_tmdb,
)


@pytest.fixture(autouse=True)
def clear_tmdb_cache() -> None:
    original_max = tmdb_module._CACHE._max_entries
    tmdb_module._CACHE.clear()
    yield
    tmdb_module._CACHE.configure(max_entries=original_max)
    tmdb_module._CACHE.clear()


def test_tmdb_cache_enforces_max_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    tmdb_module._CACHE.configure(max_entries=2)
    monotonic_values = [100.0]

    def fake_monotonic() -> float:
        return monotonic_values[0]

    monkeypatch.setattr(tmdb_module.time, "monotonic", fake_monotonic)

    tmdb_module._CACHE.set(("/path/a", ()), {"id": 1}, ttl_seconds=30)
    monotonic_values[0] += 1
    tmdb_module._CACHE.set(("/path/b", ()), {"id": 2}, ttl_seconds=30)
    monotonic_values[0] += 1
    tmdb_module._CACHE.set(("/path/c", ()), {"id": 3}, ttl_seconds=30)

    assert len(tmdb_module._CACHE._data) == 2
    assert ("/path/a", ()) not in tmdb_module._CACHE._data
    assert tmdb_module._CACHE.get(("/path/b", ()), 30) == {"id": 2}


def test_tmdb_cache_expires_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    tmdb_module._CACHE.configure(max_entries=4)
    monotonic_values = [200.0]

    def fake_monotonic() -> float:
        return monotonic_values[0]

    monkeypatch.setattr(tmdb_module.time, "monotonic", fake_monotonic)

    tmdb_module._CACHE.set(("/path/d", ()), {"id": 4}, ttl_seconds=5)
    monotonic_values[0] += 6

    assert tmdb_module._CACHE.get(("/path/d", ()), 5) is None
    assert ("/path/d", ()) not in tmdb_module._CACHE._data


def test_resolve_requires_api_key() -> None:
    cfg = TMDBConfig(api_key="")
    with pytest.raises(TMDBResolutionError):
        asyncio.run(resolve_tmdb("Example.mkv", config=cfg))


def test_external_id_respects_preference() -> None:
    calls: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "movie_results": [
                    {
                        "id": 1,
                        "title": "Example Movie",
                        "release_date": "2000-01-01",
                        "popularity": 10.0,
                    }
                ],
                "tv_results": [
                    {
                        "id": 2,
                        "name": "Example Show",
                        "first_air_date": "2000-01-01",
                        "popularity": 12.0,
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token", category_preference="TV")
    result = asyncio.run(
        resolve_tmdb(
            "Example.mkv",
            config=cfg,
            imdb_id="tt1234567",
            http_transport=transport,
        )
    )
    assert result is not None
    assert result.category == TV
    assert result.tmdb_id == "2"
    assert calls == ["/3/find/tt1234567"]


def test_filename_search_year_similarity() -> None:
    calls: List[Dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append({"path": request.url.path, "query": params.get("query", "")})
        if request.url.path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 603,
                            "title": "The Matrix",
                            "release_date": "1999-03-31",
                            "popularity": 15.0,
                        },
                        {
                            "id": 604,
                            "title": "The Matrix Reloaded",
                            "release_date": "2003-05-15",
                            "popularity": 12.0,
                        },
                    ]
                },
            )
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token", year_tolerance=2)
    result = asyncio.run(
        resolve_tmdb(
            "The.Matrix.1999.mkv",
            config=cfg,
            year=1999,
            http_transport=transport,
        )
    )
    assert result is not None
    assert result.category == MOVIE
    assert result.tmdb_id == "603"
    assert any(call["query"] for call in calls)


def test_roman_numeral_fallback() -> None:
    queries: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        queries.append(query)
        if query.strip().lower() == "rocky 2":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 42,
                            "title": "Rocky II",
                            "release_date": "1979-06-15",
                            "popularity": 8.0,
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token")
    result = asyncio.run(
        resolve_tmdb(
            "Rocky.II.1979.mkv",
            config=cfg,
            http_transport=transport,
        )
    )
    assert result is not None
    assert result.tmdb_id == "42"
    assert any(query.strip().lower() == "rocky 2" for query in queries if query)


def test_anime_parsing_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tmdb_module, "_call_guessit", lambda filename: {})
    monkeypatch.setattr(
        tmdb_module,
        "_call_anitopy",
        lambda filename: {"anime_title": "Chainsaw Man"},
    )

    queries: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        queries.append(query)
        if query == "Chainsaw Man":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 321,
                            "name": "Chainsaw Man",
                            "first_air_date": "2022-10-12",
                            "popularity": 20.0,
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token")
    result = asyncio.run(
        resolve_tmdb(
            "[SubsPlease] Chainsaw Man - 01.mkv",
            config=cfg,
            http_transport=transport,
        )
    )
    assert result is not None
    assert result.tmdb_id == "321"
    assert "Chainsaw Man" in queries


def test_vvitch_alternative_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tmdb_module,
        "_call_guessit",
        lambda filename: {"title": "The VVitch: A New-England Folktale", "year": 2015},
    )

    queries: List[str] = []
    alias_calls: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        if query:
            queries.append(query)
        if request.url.path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 526667,
                            "title": "The Witch",
                            "original_title": "The Witch",
                            "release_date": "2015-01-23",
                            "popularity": 35.0,
                        },
                        {
                            "id": 310131,
                            "title": "The Witch",
                            "original_title": "The Witch",
                            "release_date": "2016-02-19",
                            "popularity": 30.0,
                        },
                    ]
                },
            )
        if "alternative_titles" in request.url.path:
            alias_calls.append(request.url.path)
            if request.url.path.endswith("/movie/310131/alternative_titles"):
                return httpx.Response(
                    200,
                    json={"titles": [{"title": "The VVitch: A New-England Folktale"}]},
                )
            return httpx.Response(200, json={"titles": [{"title": "The Witch"}]})
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token")
    result = asyncio.run(
        resolve_tmdb(
            "The.VVitch.A.New-England.Folktale.2015.2160p.mkv",
            config=cfg,
            http_transport=transport,
        )
    )

    assert result is not None
    assert result.tmdb_id == "310131"
    assert any("vvitch" in query.lower() for query in queries)
    assert any(path.endswith("/movie/310131/alternative_titles") for path in alias_calls)


def test_vvitch_plain_title_prefers_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tmdb_module,
        "_call_guessit",
        lambda filename: {"title": "The Witch", "year": 2015},
    )

    queries: List[str] = []
    alias_calls: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        if query:
            queries.append(query)
        if request.url.path.endswith("/search/movie"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 526667,
                            "title": "The Witch",
                            "original_title": "The Witch",
                            "release_date": "2015-01-23",
                            "popularity": 35.0,
                        },
                        {
                            "id": 310131,
                            "title": "The Witch",
                            "original_title": "The Witch",
                            "release_date": "2016-02-19",
                            "popularity": 30.0,
                        },
                    ]
                },
            )
        if "alternative_titles" in request.url.path:
            alias_calls.append(request.url.path)
            if request.url.path.endswith("/movie/310131/alternative_titles"):
                return httpx.Response(
                    200,
                    json={"titles": [{"title": "The VVitch: A New-England Folktale"}]},
                )
            return httpx.Response(200, json={"titles": [{"title": "The Witch"}]})
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token")
    result = asyncio.run(
        resolve_tmdb(
            "The.Witch.2015.2160p.UHD.BDRip.DV.HDR10.x265.DTS-HD.MA.5.1-Kira.Clip.mkv",
            config=cfg,
            http_transport=transport,
        )
    )

    assert result is not None
    assert result.tmdb_id == "310131"
    assert any(path.endswith("/movie/310131/alternative_titles") for path in alias_calls)
    # Ensure the fallback title without the alias text was used for the search
    assert any(query.lower().startswith("the witch") for query in queries)


def test_tmdb_backoff_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: List[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(tmdb_module.asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if attempts["count"] == 0:
            attempts["count"] += 1
            return httpx.Response(429, json={"status_code": 429})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 55,
                        "title": "Cache Test",
                        "release_date": "2020-01-01",
                        "popularity": 6.0,
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    cfg = TMDBConfig(api_key="token")
    first = asyncio.run(
        resolve_tmdb(
            "Cache.Test.2020.mkv",
            config=cfg,
            http_transport=transport,
        )
    )
    second = asyncio.run(
        resolve_tmdb(
            "Cache.Test.2020.mkv",
            config=cfg,
            http_transport=transport,
        )
    )
    assert first is not None and second is not None
    assert first.tmdb_id == "55"
    assert second.tmdb_id == "55"
    assert sleep_calls  # backoff triggered at least once
    # Only two HTTP calls should have been made (429 + success); cache served the second resolve
    assert attempts["count"] == 1
