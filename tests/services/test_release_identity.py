"""Structured release identity corpus and formatter tests."""

import pytest

from frame_compare.services.metadata_parsing import parse_release_identity
from frame_compare.services.release_identity import (
    ContentIdentity,
    ReleaseIdentity,
    common_content_identity,
    format_compact_identity,
    format_micro_descriptor,
    format_release_descriptor,
    unique_presentation_names,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        (
            "Avatar.Aang.The.Last.Airbender.2026.2160p.PMTP.WEB-DL.DV.HDR10+.H.265-Kitsune.mkv",
            ("PMTP", "WEB-DL", ("DV", "HDR10+"), (), "Kitsune"),
        ),
        (
            "Avatar.Aang.The.Last.Airbender.2026.2160p.ATV.WEB-DL.DV.HDR10+.REPACK.H.265-Kitsune.mkv",
            ("ATV", "WEB-DL", ("DV", "HDR10+"), ("REPACK",), "Kitsune"),
        ),
        (
            "Movie.2024.2160p.NF.WEB-DL.HDR10.REPACK2-GROUP.mkv",
            ("NF", "WEB-DL", ("HDR10",), ("REPACK2",), "GROUP"),
        ),
        (
            "Show.S01E05.1080p.AMZN.WEBRip.HLG-GROUP.mkv",
            ("AMZN", "WEBRip", ("HLG",), (), "HLG-GROUP"),
        ),
        (
            "Film.2020.2160p.UHD.BluRay.REMUX.DV.HDR-GROUP.mkv",
            (None, "UHD BluRay REMUX", ("DV", "HDR"), (), "GROUP"),
        ),
        (
            "Film.2020.1080p.BluRay.REMUX.HDR10-GROUP.mkv",
            (None, "BluRay REMUX", ("HDR10",), (), "GROUP"),
        ),
        ("Film.2020.1080p.HDTV.SDR-GROUP.mkv", (None, "HDTV", ("SDR",), (), "GROUP")),
        ("Film.2020.DVD.PROPER-GROUP.mkv", (None, "DVD", (), ("PROPER",), "GROUP")),
        ("Film.2020.2160p.DSNP.WEB-DL.HYBRID.IMAX-GROUP.mkv", ("DSNP", "WEB-DL", (), (), "GROUP")),
        ("Film.2020.1080p.HULU.WEB-DL-GROUP.mkv", ("HULU", "WEB-DL", (), (), "GROUP")),
        ("Film.2020.1080p.PCOK.WEB-DL-GROUP.mkv", ("PCOK", "WEB-DL", (), (), "GROUP")),
        ("Film.2020.1080p.HMAX.WEB-DL-GROUP.mkv", ("MAX", "WEB-DL", (), (), "GROUP")),
        ("Film.2020.1080p.MA.BluRay-GROUP.mkv", ("MA", "BluRay", (), (), "GROUP")),
    ],
)
def test_real_parser_corpus(filename: str, expected: tuple[object, ...]) -> None:
    identity = parse_release_identity(filename)
    assert (
        identity.service,
        identity.source_type,
        identity.dynamic_range_claims,
        identity.revision_tags,
        identity.release_group,
    ) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "Ma.2024.mkv",
        "Max.Payne.2008.mkv",
        "The.Web.2020.mkv",
        "A.Proper.Man.2024.mkv",
        "HDR.The.Story.2023.mkv",
        "Studio-Canal.mkv",
        "Class.of.2160.mkv",
        "Movie.x264.mkv",
    ],
)
def test_title_tokens_are_not_release_false_positives(filename: str) -> None:
    identity = parse_release_identity(filename)
    assert identity.service is None
    assert identity.source_type is None
    assert not identity.dynamic_range_claims
    assert not identity.revision_tags


def test_formatters_and_common_content() -> None:
    content = ContentIdentity("Avatar Aang The Last Airbender", 2026)
    first = ReleaseIdentity(content, "2160p", "PMTP", "WEB-DL", ("DV", "HDR10+"), "Kitsune")
    second = ReleaseIdentity(
        content, "2160p", "ATV", "WEB-DL", ("DV", "HDR10+"), "Kitsune", ("REPACK",)
    )
    assert format_release_descriptor(first) == "2160p | PMTP WEB-DL | DV HDR10+ | Kitsune"
    assert format_compact_identity(second).startswith(
        "Avatar Aang The Last Airbender (2026) | 2160p"
    )
    assert common_content_identity([first, second]) == content
    assert format_micro_descriptor(second) == "ATV WEB-DL | DV HDR10+ | REPACK | Kitsune"
    assert unique_presentation_names(["same", "same"], roles=["Reference", "Comparison 1"]) == [
        "Reference | same",
        "Comparison 1 | same",
    ]
    assert unique_presentation_names(
        ["My Encode", "My Encode"],
        roles=["Reference", "Comparison 1"],
        protected=[True, False],
    ) == ["My Encode", "Comparison 1 | My Encode"]


def test_malformed_name_fails_open_to_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("frame_compare.services.metadata_parsing.guessit", lambda _name: 42)
    monkeypatch.setattr("frame_compare.services.metadata_parsing.anitopy.parse", lambda _name: None)
    identity = parse_release_identity("odd_name.mkv")
    assert identity.content == ContentIdentity("odd name", title_origin="fallback")


def test_anime_unicode_and_variant_fields() -> None:
    anime = parse_release_identity("[SubsPlease] 葬送のフリーレン - 03 (1080p) [ABC123].mkv")
    assert anime.content.episode == 3
    assert anime.release_group == "SubsPlease"

    variant = parse_release_identity(
        "Film.2020.2160p.DSNP.WEB-DL.HYBRID.IMAX.Extended.Criterion-GROUP.mkv"
    )
    assert variant.variant_tags == ("HYBRID", "IMAX", "Extended", "Criterion")
