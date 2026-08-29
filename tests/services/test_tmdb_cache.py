from __future__ import annotations

import tomllib
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from structlog.testing import capture_logs

import frame_compare.services.tmdb_cache as tmdb_cache
from frame_compare.services.tmdb_cache import TmdbCache, cache_key_for_request
from frame_compare.services.types import TmdbMetadata


def _movie(tmdb_id: int, title: str) -> TmdbMetadata:
    return TmdbMetadata(
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=2020,
        media_type="movie",
    )


def _search_params(query: str, api_key: str = "a" * 32) -> dict[str, str | int]:
    return {
        "api_key": api_key,
        "query": query,
        "language": "en-US",
        "page": 1,
        "include_adult": "false",
    }


@pytest.mark.anyio
async def test_cache_preserves_order_and_separates_search_and_alias_entries(
    tmp_path: Path,
) -> None:
    cache = TmdbCache(tmp_path / "cache" / "tmdb.toml")
    endpoint = "https://api.example.test/search/movie"
    params = _search_params("The Witch")

    await cache.store_search(endpoint, params, [_movie(2, "Second"), _movie(1, "First")])
    await cache.store_alternative_titles(
        "https://api.example.test/movie/2/alternative_titles",
        {"api_key": "a" * 32},
        ["Zed", "Alpha", "Zed"],
    )

    assert cache.get_search(endpoint, _search_params("The Witch", "b" * 32)) == [
        _movie(2, "Second"),
        _movie(1, "First"),
    ]
    assert cache.get_alternative_titles(
        "https://api.example.test/movie/2/alternative_titles",
        {"api_key": "c" * 32},
    ) == ["Zed", "Alpha", "Zed"]


@pytest.mark.anyio
async def test_empty_alternative_titles_round_trip(tmp_path: Path) -> None:
    cache = TmdbCache(tmp_path / "tmdb.toml")
    endpoint = "https://api.example.test/movie/1/alternative_titles"
    params = {"api_key": "a" * 32}

    await cache.store_alternative_titles(endpoint, params, [])

    assert cache.get_alternative_titles(endpoint, params) == []


@pytest.mark.anyio
async def test_empty_entries_are_cacheable_through_the_ttl_boundary(tmp_path: Path) -> None:
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    cache = TmdbCache(tmp_path / "tmdb.toml", clock=lambda: now[0])
    endpoint = "https://api.example.test/movie/1/alternative_titles"
    params = {"api_key": "a" * 32}

    await cache.store_alternative_titles(endpoint, params, [])
    now[0] += timedelta(days=1)
    assert cache.get_alternative_titles(endpoint, params) == []

    now[0] += timedelta(seconds=1)
    assert cache.get_alternative_titles(endpoint, params) is None


@pytest.mark.anyio
async def test_positive_entries_expire_after_thirty_days(tmp_path: Path) -> None:
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    cache = TmdbCache(tmp_path / "tmdb.toml", clock=lambda: now[0])
    endpoint = "https://api.example.test/search/movie"
    params = _search_params("Known")

    await cache.store_search(endpoint, params, [_movie(1, "Known")])
    now[0] += timedelta(days=30)
    assert cache.get_search(endpoint, params) == [_movie(1, "Known")]

    now[0] += timedelta(seconds=1)
    assert cache.get_search(endpoint, params) is None


@pytest.mark.anyio
async def test_future_dated_entry_is_not_reused(tmp_path: Path) -> None:
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    cache = TmdbCache(tmp_path / "tmdb.toml", clock=lambda: now[0])
    endpoint = "https://api.example.test/search/movie"
    params = _search_params("Known")

    now[0] += timedelta(days=1)
    await cache.store_search(endpoint, params, [_movie(1, "Known")])
    now[0] -= timedelta(days=1)

    assert cache.get_search(endpoint, params) is None


@pytest.mark.anyio
async def test_cache_key_hashes_query_and_excludes_api_key() -> None:
    endpoint = "https://api.example.test/search/movie"
    params = _search_params("Private title", "a" * 32)
    first = cache_key_for_request(
        "search",
        endpoint,
        params,
    )
    second = cache_key_for_request(
        "search",
        endpoint,
        {**params, "api_key": "b" * 32},
    )
    different_query = cache_key_for_request(
        "search",
        endpoint,
        {**params, "query": "Another title"},
    )

    assert first == second
    assert first != different_query
    assert first != cache_key_for_request("search", endpoint, {**params, "page": 2})
    assert first != cache_key_for_request("search", endpoint, {**params, "language": "fr-FR"})
    assert first != cache_key_for_request("search", endpoint + "/other", params)
    assert first != cache_key_for_request("alternative_titles", endpoint, params)
    assert len(first) == 64
    assert "Private title" not in first
    assert "a" * 32 not in first


@pytest.mark.anyio
async def test_cache_file_does_not_persist_query_or_api_key(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache" / "tmdb.toml"
    cache = TmdbCache(cache_path)
    api_key = "a" * 32

    await cache.store_search(
        "https://api.example.test/search/multi",
        _search_params("Private title", api_key),
        [],
    )

    content = cache_path.read_text(encoding="utf-8")
    assert "Private title" not in content
    assert api_key not in content


@pytest.mark.anyio
async def test_cache_prunes_oldest_entries_by_count_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tmdb_cache, "TMDB_CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(tmdb_cache, "TMDB_CACHE_MAX_BYTES", 10_000)
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path, clock=lambda: now[0])
    endpoint = "https://api.example.test/search/movie"
    params = [_search_params(f"Title {index}") for index in range(3)]

    for index, request_params in enumerate(params):
        await cache.store_search(endpoint, request_params, [_movie(index + 1, "Same")])
        now[0] += timedelta(seconds=1)

    data = tomllib.loads(cache_path.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert isinstance(entries, dict)
    keys = [cache_key_for_request("search", endpoint, request_params) for request_params in params]
    assert list(entries) == sorted(entries)
    assert set(entries) == {keys[1], keys[2]}


@pytest.mark.anyio
async def test_cache_prunes_oldest_entries_by_serialized_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tmdb_cache, "TMDB_CACHE_MAX_ENTRIES", 10)
    monkeypatch.setattr(tmdb_cache, "TMDB_CACHE_MAX_BYTES", 10_000)
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)
    endpoint = "https://api.example.test/search/movie"
    first_params = _search_params("First")
    second_params = _search_params("Second")

    await cache.store_search(endpoint, first_params, [_movie(1, "Same")])
    one_entry_size = cache_path.stat().st_size
    monkeypatch.setattr(tmdb_cache, "TMDB_CACHE_MAX_BYTES", one_entry_size + 1)
    await cache.store_search(endpoint, second_params, [_movie(2, "Same")])

    first_key = cache_key_for_request("search", endpoint, first_params)
    second_key = cache_key_for_request("search", endpoint, second_params)
    data = tomllib.loads(cache_path.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert isinstance(entries, dict)
    assert set(entries) == {second_key}
    assert first_key not in entries
    assert cache_path.stat().st_size <= one_entry_size + 1


@pytest.mark.anyio
async def test_independent_writers_merge_entries_under_the_file_lock(tmp_path: Path) -> None:
    cache_path = tmp_path / "tmdb.toml"
    endpoint = "https://api.example.test/search/movie"
    first_params = _search_params("First")
    second_params = _search_params("Second")

    await TmdbCache(cache_path).store_search(endpoint, first_params, [_movie(1, "First")])
    await TmdbCache(cache_path).store_search(endpoint, second_params, [_movie(2, "Second")])

    reader = TmdbCache(cache_path)
    assert reader.get_search(endpoint, first_params) == [_movie(1, "First")]
    assert reader.get_search(endpoint, second_params) == [_movie(2, "Second")]


@pytest.mark.anyio
async def test_corrupt_wrong_version_or_malformed_entry_degrades_to_miss(tmp_path: Path) -> None:
    cache_path = tmp_path / "tmdb.toml"
    endpoint = "https://api.example.test/search/movie"
    params = _search_params("Known")

    cache_path.write_text("not = [valid", encoding="utf-8")
    assert TmdbCache(cache_path).get_search(endpoint, params) is None

    cache_path.write_text('version = "999"\n[entries]\n', encoding="utf-8")
    assert TmdbCache(cache_path).get_search(endpoint, params) is None

    key = cache_key_for_request("search", endpoint, params)
    cache_path.write_text(
        f'''version = "{tmdb_cache.TMDB_CACHE_VERSION}"

[entries."{key}"]
kind = "search"
stored_at = "2026-01-01T00:00:00Z"
results = ["not metadata"]
''',
        encoding="utf-8",
    )
    assert TmdbCache(cache_path).get_search(endpoint, params) is None


@pytest.mark.anyio
async def test_locked_atomic_write_failure_is_warning_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "tmdb.toml"
    cache = TmdbCache(cache_path)
    events: list[str] = []

    @contextmanager
    def fake_lock(path: Path) -> Generator[None]:
        assert path == cache.lock_path
        events.append("lock_enter")
        try:
            yield
        finally:
            events.append("lock_exit")

    def fail_write(_path: Path, _content: bytes) -> None:
        assert events == ["lock_enter"]
        events.append("write")
        raise OSError("write blocked")

    monkeypatch.setattr(tmdb_cache, "exclusive_file_lock", fake_lock)
    monkeypatch.setattr(tmdb_cache, "write_bytes_atomic", fail_write)
    endpoint = "https://api.example.test/search/movie"
    params = _search_params("Private title", "a" * 32)

    with capture_logs() as logs:
        await cache.store_search(endpoint, params, [_movie(1, "Known")])

    assert events == ["lock_enter", "write", "lock_exit"]
    warnings = [entry for entry in logs if entry.get("event") == "tmdb_cache_write_failed"]
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["entry_key"] == cache_key_for_request("search", endpoint, params)
    assert "Private title" not in repr(warning)
    assert "a" * 32 not in repr(warning)
    assert not cache_path.exists()
