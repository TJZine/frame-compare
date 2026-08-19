import frame_compare.services.metadata_parsing as metadata_parsing
from frame_compare.services.metadata import parse_filename
from frame_compare.services.types import ParsedMetadata


def test_guessit_dependency_parses_supported_episode_filename() -> None:
    result = metadata_parsing.parse_filename(
        "Example.Show.S02E03.Episode.Title.1080p.WEB-DL-GROUP.mkv",
        parser_priority="guessit",
        alternate_policy="fallback",
    )

    assert result == ParsedMetadata(
        title="Example Show",
        season=2,
        episode=3,
        episode_title="Episode Title",
        release_group="GROUP",
        source="Web",
        resolution="1080p",
    )


def test_metadata_parsing_direct_module_merges_guessit_and_anitopy_fallback(mocker) -> None:
    """Direct parser module keeps primary fields while filling missing alternate fields."""
    mocker.patch(
        "frame_compare.services.metadata_parsing.guessit",
        return_value={
            "title": "Movie.Name",
            "year": "2024",
            "screen_size": "2160p",
        },
    )
    mocker.patch(
        "frame_compare.services.metadata_parsing.anitopy.parse",
        return_value={
            "anime_title": "Alternate Title",
            "anime_episode": "07",
            "release_group": "SubsPlease",
        },
    )

    result = metadata_parsing.parse_filename("Movie.Name.2024.E07.2160p.mkv")

    assert result == ParsedMetadata(
        title="Movie Name",
        year=2024,
        episode=7,
        release_group="SubsPlease",
        resolution="2160p",
    )
    assert parse_filename is metadata_parsing.parse_filename


def test_metadata_parsing_direct_module_uses_anitopy_first_for_bracketed_names(
    mocker,
) -> None:
    def fake_anitopy_parse(filename: str) -> dict[str, object]:
        assert filename == "[Group] Anime_Title - 03.mkv"
        return {
            "anime_title": "Anime_Title",
            "anime_episode": 3,
            "release_group": "Group",
        }

    def fake_guessit(filename: str) -> dict[str, object]:
        assert filename == "[Group] Anime_Title - 03.mkv"
        return {
            "title": "Western Title",
            "year": 2022,
            "release_group": "Wrong Group",
            "source": "Blu-ray",
            "screen_size": "1080p",
        }

    mocker.patch("frame_compare.services.metadata_parsing.anitopy.parse", fake_anitopy_parse)
    mocker.patch("frame_compare.services.metadata_parsing.guessit", fake_guessit)

    result = metadata_parsing.parse_filename("[Group] Anime_Title - 03.mkv")

    assert result.title == "Anime Title"
    assert result.year == 2022
    assert result.episode == 3
    assert result.release_group == "Group"
    assert result.source == "Blu-ray"
    assert result.resolution == "1080p"


def test_metadata_parsing_fallback_policy_stops_after_successful_primary(mocker) -> None:
    calls: list[str] = []

    def fake_anitopy(_filename: str) -> dict[str, object]:
        calls.append("anitopy")
        return {
            "anime_title": "Anime",
            "anime_episode": 4,
            "episode_title": "The Arrival",
        }

    def fake_guessit(_filename: str) -> dict[str, object]:
        calls.append("guessit")
        return {"title": "Fallback", "season": 1}

    mocker.patch("frame_compare.services.metadata_parsing.anitopy.parse", fake_anitopy)
    mocker.patch("frame_compare.services.metadata_parsing.guessit", fake_guessit)

    result = metadata_parsing.parse_filename("show.mkv", parser_priority="anitopy")

    assert calls == ["anitopy", "guessit"]
    assert result.title == "Anime"
    assert result.season == 1
    assert result.episode == 4
    assert result.episode_title == "The Arrival"

    calls.clear()
    result = metadata_parsing.parse_filename(
        "show.mkv",
        parser_priority="anitopy",
        alternate_policy="fallback",
    )

    assert calls == ["anitopy"]
    assert result.title == "Anime"
    assert result.season is None
    assert result.episode == 4
    assert result.episode_title == "The Arrival"


def test_metadata_parsing_fallback_policy_uses_alternate_for_missing_primary_title(
    mocker,
) -> None:
    calls: list[str] = []

    def fake_anitopy(_filename: str) -> dict[str, object]:
        calls.append("anitopy")
        return {"anime_episode": 4}

    def fake_guessit(_filename: str) -> dict[str, object]:
        calls.append("guessit")
        return {"title": "Fallback", "season": 1}

    mocker.patch("frame_compare.services.metadata_parsing.anitopy.parse", fake_anitopy)
    mocker.patch("frame_compare.services.metadata_parsing.guessit", fake_guessit)

    result = metadata_parsing.parse_filename(
        "show.mkv",
        parser_priority="anitopy",
        alternate_policy="fallback",
    )

    assert calls == ["anitopy", "guessit"]
    assert result.title == "Fallback"
    assert result.season == 1
    assert result.episode == 4


def test_metadata_parsing_fallback_policy_replaces_unusable_primary_title(mocker) -> None:
    mocker.patch(
        "frame_compare.services.metadata_parsing.anitopy.parse",
        return_value={"anime_title": "---", "anime_episode": 4},
    )
    mocker.patch(
        "frame_compare.services.metadata_parsing.guessit",
        return_value={"title": "Fallback"},
    )

    result = metadata_parsing.parse_filename(
        "show.mkv",
        parser_priority="anitopy",
        alternate_policy="fallback",
    )

    assert result.title == "Fallback"
    assert result.episode == 4


def test_metadata_parsing_fallback_policy_rejects_malformed_primary_fields(mocker) -> None:
    calls: list[str] = []

    def fake_anitopy(_filename: str) -> dict[str, object]:
        calls.append("anitopy")
        return {
            "anime_title": {"unexpected": "mapping"},
            "anime_episode": True,
            "release_group": ["unexpected"],
        }

    def fake_guessit(_filename: str) -> dict[str, object]:
        calls.append("guessit")
        return {"title": "Fallback", "episode": 2, "release_group": "Group"}

    mocker.patch("frame_compare.services.metadata_parsing.anitopy.parse", fake_anitopy)
    mocker.patch("frame_compare.services.metadata_parsing.guessit", fake_guessit)

    result = metadata_parsing.parse_filename(
        "show.mkv",
        parser_priority="anitopy",
        alternate_policy="fallback",
    )

    assert calls == ["anitopy", "guessit"]
    assert result.title == "Fallback"
    assert result.episode == 2
    assert result.release_group == "Group"


def test_metadata_parsing_fallback_policy_recovers_from_primary_exception(mocker) -> None:
    def fake_anitopy(_filename: str) -> dict[str, object]:
        raise RuntimeError("parser failed")

    mocker.patch("frame_compare.services.metadata_parsing.anitopy.parse", fake_anitopy)
    mocker.patch(
        "frame_compare.services.metadata_parsing.guessit",
        return_value={"title": "Fallback"},
    )

    result = metadata_parsing.parse_filename(
        "show.mkv",
        parser_priority="anitopy",
        alternate_policy="fallback",
    )

    assert result.title == "Fallback"
