import pytest

from src.datatypes import NamingConfig
import src.utils as utils


def test_parse_guessit_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    naming = NamingConfig(always_full_filename=False, prefer_guessit=True)
    monkeypatch.setattr(utils, "GUESSIT_AVAILABLE", True, raising=False)

    def fake_guessit(name: str):
        return {
            "title": "Show",
            "episode": [1, 2],
            "episode_title": "Pilot",
            "release_group": "Team",
        }

    monkeypatch.setattr(utils, "_guessit", fake_guessit, raising=False)
    meta = utils.parse_filename_metadata("Example.mkv", naming=naming)
    assert meta["anime_title"] == "Show"
    assert meta["episode_number"] == "1-2"
    assert meta["display_name"] == "Team"


def test_parse_anitopy_fallback_brackets(monkeypatch: pytest.MonkeyPatch) -> None:
    naming = NamingConfig(always_full_filename=True, prefer_guessit=False)
    monkeypatch.setattr(utils, "GUESSIT_AVAILABLE", False, raising=False)

    class FakeAni:
        @staticmethod
        def parse(name: str):
            return {
                "anime_title": "Title",
                "episode_number": [3],
                "episode_title": "Arc",
                "release_group": "",
            }

    monkeypatch.setattr(utils, "ani", FakeAni, raising=False)
    meta = utils.parse_filename_metadata("[Grp] Title - 03.mkv", naming=naming)
    assert meta["release_group"] == "Grp"
    assert meta["episode_number"] == "3"
    assert meta["display_name"] == "[Grp] Title - 03.mkv"


def test_parse_prefer_guessit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    naming = NamingConfig(always_full_filename=False, prefer_guessit=True)
    monkeypatch.setattr(utils, "GUESSIT_AVAILABLE", True, raising=False)

    def exploding_guessit(_: str):
        raise AssertionError("guessit should not be called")

    monkeypatch.setattr(utils, "_guessit", exploding_guessit, raising=False)

    class FakeAni:
        @staticmethod
        def parse(name: str):
            return {"release_group": "Grp"}

    monkeypatch.setattr(utils, "ani", FakeAni, raising=False)
    meta = utils.parse_filename_metadata("[Grp] Title - 01.mkv", naming=naming, prefer_guessit=False)
    assert meta["release_group"] == "Grp"
    assert meta["display_name"] == "Grp"
