import frame_compare.services.metadata_parsing as metadata_parsing
from frame_compare.services.metadata import parse_filename
from frame_compare.services.types import ParsedMetadata


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
