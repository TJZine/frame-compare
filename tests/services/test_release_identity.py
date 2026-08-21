"""Structured release identity corpus and formatter tests."""

import pytest

from frame_compare.services.metadata_parsing import (
    parse_filename,
    parse_filename_with_release_identity,
    parse_release_identity,
)
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
        ("Film.2020.1080p.AppleTV.WEB-DL-GROUP.mkv", ("ATV", "WEB-DL", (), (), "GROUP")),
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
        "Ma.2024.1080p.WEB-DL-GROUP.mkv",
        "Max.Payne.2008.1080p.WEB-DL-GROUP.mkv",
        "The.Web.2020.1080p.BluRay-GROUP.mkv",
        "A.Proper.Man.2024.1080p.WEB-DL-GROUP.mkv",
        "HDR.The.Story.2023.1080p.WEB-DL-GROUP.mkv",
        "DV.2024.1080p.WEB-DL-GROUP.mkv",
        "Studio-Canal.mkv",
        "Class.of.2160.mkv",
        "Movie.x264.mkv",
    ],
)
def test_title_tokens_are_not_release_false_positives(filename: str) -> None:
    identity = parse_release_identity(filename)
    assert identity.service is None
    assert not identity.dynamic_range_claims
    assert not identity.revision_tags


@pytest.mark.parametrize(
    ("filename", "claims", "revisions"),
    [
        ("Film.2024.2160p.WEB-DL.DoVi-GROUP.mkv", ("DV",), ()),
        ("Film.2024.2160p.WEB-DL.HDR10Plus-GROUP.mkv", ("HDR10+",), ()),
        ("Film.2024.2160p.WEB-DL.REAL.PROPER-GROUP.mkv", (), ("REAL PROPER",)),
    ],
)
def test_compact_aliases_and_specific_revision_precedence(
    filename: str,
    claims: tuple[str, ...],
    revisions: tuple[str, ...],
) -> None:
    identity = parse_release_identity(filename)
    assert identity.dynamic_range_claims == claims
    assert identity.revision_tags == revisions


def test_parser_field_shapes_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "frame_compare.services.metadata_parsing.guessit",
        lambda _name: {
            "title": ["Example"],
            "year": ["2024"],
            "screen_size": ["2160p"],
            "source": ["Web"],
            "streaming_service": ["Netflix"],
            "release_group": ["GROUP"],
        },
    )
    monkeypatch.setattr("frame_compare.services.metadata_parsing.anitopy.parse", lambda _name: {})

    identity = parse_release_identity("Example.2024.2160p.NF.WEB-DL.DoVi.HDR10+-GROUP.mkv")

    assert identity.content == ContentIdentity("Example", year=2024)
    assert identity.resolution == "2160p"
    assert identity.service == "NF"
    assert identity.source_type == "WEB-DL"
    assert identity.release_group == "GROUP"
    assert identity.dynamic_range_claims == ("DV", "HDR10+")


def test_parser_derived_controls_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "frame_compare.services.metadata_parsing.guessit",
        lambda _name: {
            "title": "Movie\nTitle",
            "screen_size": "1080p",
            "source": "Web",
            "release_group": "GROUP\x1bEVIL",
        },
    )
    monkeypatch.setattr("frame_compare.services.metadata_parsing.anitopy.parse", lambda _name: {})

    identity = parse_release_identity("Movie.1080p.WEB-DL-GROUP.mkv")

    assert identity.content.title == "Movie Title"
    assert identity.release_group == "GROUP EVIL"
    assert "\n" not in format_compact_identity(identity)
    assert "\x1b" not in format_compact_identity(identity)


@pytest.mark.parametrize(
    ("filename", "expected_year", "expected_episode"),
    [
        ("[Group] Movie.2024.1080p.NF.WEB-DL.HDR10.mkv", 2024, None),
        ("[SubsPlease] Show - 03 (1080p) [ABC].mkv", None, 3),
    ],
)
def test_combined_parse_preserves_canonical_fallback_and_merged_release_facts(
    filename: str,
    expected_year: int | None,
    expected_episode: int | None,
) -> None:
    canonical, release = parse_filename_with_release_identity(filename, parser_priority="auto")

    assert canonical == parse_filename(
        filename,
        parser_priority="auto",
        alternate_policy="fallback",
    )
    assert release.content.year == expected_year
    assert release.content.episode == expected_episode


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
