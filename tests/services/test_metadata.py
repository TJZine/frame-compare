from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

import frame_compare.services.metadata as metadata
from frame_compare.services.errors import MetadataError
from frame_compare.services.metadata import parse_filename, resolve_metadata
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata


@pytest.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    """Provide an httpx.AsyncClient for async tests."""
    async with httpx.AsyncClient() as client:
        yield client


@dataclass(frozen=True)
class ResolutionOutcome:
    selected: TmdbMetadata | None
    candidates: list[TmdbMetadata]


def _movie(
    tmdb_id: int,
    title: str,
    year: int,
    *,
    original_title: str | None = None,
) -> TmdbMetadata:
    return TmdbMetadata(
        tmdb_id=tmdb_id,
        title=title,
        original_title=title if original_title is None else original_title,
        year=year,
        media_type="movie",
        poster_url=None,
        backdrop_url=None,
    )


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
        "frame_compare.services.metadata_parsing.guessit",
        side_effect=Exception("guessit error"),
    )
    mocker.patch(
        "frame_compare.services.metadata_parsing.anitopy.parse",
        side_effect=Exception("anitopy error"),
    )
    debug_log = mocker.patch("frame_compare.services.metadata_parsing.log.debug")

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


# ─── Resolve Metadata Facade Tests ────────────────────────────────────────────


@pytest.mark.anyio
async def test_resolve_metadata_returns_none_for_empty_filenames(
    async_client: httpx.AsyncClient,
) -> None:
    config = MetadataConfig(api_key="a" * 32)

    result = await resolve_metadata([], config, async_client)

    assert result is None


@pytest.mark.anyio
async def test_resolve_metadata_parses_only_first_filename(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    parsed = ParsedMetadata(title="Fight Club", year=1999)
    selected = _movie(550, "Fight Club", 1999)
    parse_mock = Mock(return_value=parsed)
    resolve_mock = AsyncMock(
        return_value=ResolutionOutcome(selected=selected, candidates=[selected])
    )
    config = MetadataConfig(api_key="a" * 32)

    monkeypatch.setattr(metadata, "parse_filename", parse_mock)
    monkeypatch.setattr(metadata, "resolve_tmdb_match", resolve_mock)

    result = await resolve_metadata(
        ["Fight.Club.1999.mkv", "Ignored.File.Name.mkv"],
        config,
        async_client,
    )

    assert result == selected
    parse_mock.assert_called_once_with("Fight.Club.1999.mkv")
    resolve_mock.assert_awaited_once_with(parsed, config, async_client)


@pytest.mark.anyio
async def test_resolve_metadata_returns_selected_vvitch_match_over_first_candidate(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    wrong_plain_title = _movie(41484, "The Witch", 2006)
    vvitch_release = _movie(
        310131,
        "The Witch",
        2015,
        original_title="The VVitch: A New-England Folktale",
    )
    resolve_mock = AsyncMock(
        return_value=ResolutionOutcome(
            selected=vvitch_release,
            candidates=[wrong_plain_title, vvitch_release],
        )
    )
    callback = Mock(side_effect=AssertionError("prompt_callback should not be used"))
    config = MetadataConfig(api_key="a" * 32)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="The VVitch", year=2015)),
    )
    monkeypatch.setattr(metadata, "resolve_tmdb_match", resolve_mock)

    result = await resolve_metadata(
        ["The.VVitch.2015.1080p.BluRay.mkv"],
        config,
        async_client,
        prompt_callback=callback,
    )

    assert result == vvitch_release
    callback.assert_not_called()


@pytest.mark.anyio
async def test_resolve_metadata_plain_title_alias_case_returns_vvitch_release(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    plain_title_match = _movie(79091, "The Witch", 2016)
    vvitch_release = _movie(
        310131,
        "The Witch",
        2015,
        original_title="The VVitch: A New-England Folktale",
    )
    config = MetadataConfig(api_key="a" * 32)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="The Witch", year=2015)),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(
            return_value=ResolutionOutcome(
                selected=vvitch_release,
                candidates=[plain_title_match, vvitch_release],
            )
        ),
    )

    result = await resolve_metadata(["The.Witch.2015.mkv"], config, async_client)

    assert result == vvitch_release


@pytest.mark.anyio
async def test_resolve_metadata_returns_none_for_unresolved_results_in_unattended_mode(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    candidates = [_movie(10, "The Witch", 2015), _movie(11, "The Witch", 2016)]
    callback = Mock(side_effect=AssertionError("prompt_callback should not be used"))
    config = MetadataConfig(api_key="a" * 32, unattended=True)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="The Witch", year=2015)),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(return_value=ResolutionOutcome(selected=None, candidates=candidates)),
    )

    result = await resolve_metadata(
        ["The.Witch.2015.mkv"],
        config,
        async_client,
        prompt_callback=callback,
    )

    assert result is None
    callback.assert_not_called()


@pytest.mark.anyio
async def test_resolve_metadata_returns_none_for_unresolved_results_without_callback(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    candidates = [_movie(10, "The Witch", 2015), _movie(11, "The Witch", 2016)]
    config = MetadataConfig(api_key="a" * 32, unattended=False)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="The Witch", year=2015)),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(return_value=ResolutionOutcome(selected=None, candidates=candidates)),
    )

    result = await resolve_metadata(["The.Witch.2015.mkv"], config, async_client)

    assert result is None


@pytest.mark.anyio
async def test_resolve_metadata_high_confidence_match_auto_accepts(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    exact_match = _movie(329865, "Arrival", 2016)
    callback = Mock(side_effect=AssertionError("prompt_callback should not be used"))
    config = MetadataConfig(api_key="a" * 32, unattended=False)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="Arrival", year=2016)),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(
            return_value=ResolutionOutcome(selected=exact_match, candidates=[exact_match])
        ),
    )

    result = await resolve_metadata(
        ["Arrival.2016.2160p.mkv"],
        config,
        async_client,
        prompt_callback=callback,
    )

    assert result == exact_match
    callback.assert_not_called()


@pytest.mark.anyio
async def test_resolve_metadata_with_callback_uses_ranked_candidates(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    first = _movie(1, "Result 1", 2020)
    second = _movie(2, "Result 2", 2021)
    config = MetadataConfig(api_key="a" * 32, unattended=False)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="Multi")),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(return_value=ResolutionOutcome(selected=None, candidates=[first, second])),
    )

    def callback(results: list[TmdbMetadata]) -> int:
        assert results == [first, second]
        return 1

    result = await resolve_metadata(
        ["Multi.mkv"],
        config,
        async_client,
        prompt_callback=callback,
    )

    assert result == second


@pytest.mark.anyio
async def test_resolve_metadata_returns_none_when_resolver_has_no_match_or_candidates(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    config = MetadataConfig(api_key="a" * 32)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="Unknown")),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(return_value=ResolutionOutcome(selected=None, candidates=[])),
    )

    result = await resolve_metadata(["Unknown.mkv"], config, async_client)

    assert result is None


@pytest.mark.anyio
async def test_resolve_metadata_invalid_callback_index(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    candidates = [_movie(1, "Result 1", 2020), _movie(2, "Result 2", 2021)]
    config = MetadataConfig(api_key="a" * 32, unattended=False)

    monkeypatch.setattr(
        metadata,
        "parse_filename",
        Mock(return_value=ParsedMetadata(title="Multi")),
    )
    monkeypatch.setattr(
        metadata,
        "resolve_tmdb_match",
        AsyncMock(return_value=ResolutionOutcome(selected=None, candidates=candidates)),
    )

    def callback(results: list[TmdbMetadata]) -> int:
        assert results == candidates
        return 99

    with pytest.raises(MetadataError, match="invalid selection index"):
        await resolve_metadata(
            ["Multi.mkv"],
            config,
            async_client,
            prompt_callback=callback,
        )
