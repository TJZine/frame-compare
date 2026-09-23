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
            ("AMZN", "WEBRip", ("HLG",), (), "GROUP"),
        ),
        (
            "Show.S01E05.1080p.AMZN.WEBRip.HLG.HEVC-HLG-GROUP.mkv",
            ("AMZN", "WEBRip", ("HLG",), (), "HLG-GROUP"),
        ),
        ("Film.2024.2160p.WEB-DL-MAX.mkv", (None, "WEB-DL", (), (), "MAX")),
        ("Film.2024.2160p.WEB-DL-HDR.mkv", (None, "WEB-DL", (), (), "HDR")),
        ("Film.2024.2160p.WEB-DL-PROPER.mkv", (None, "WEB-DL", (), (), "PROPER")),
        ("Film.2024.2160p.WEB-DL-IMAX.mkv", (None, "WEB-DL", (), (), "IMAX")),
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
        ("Film.2020.1080p.HMAX.WEB-DL-GROUP.mkv", ("HMAX", "WEB-DL", (), (), "GROUP")),
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
    ("code_token", "expected"),
    [
        ("AMZN", "AMZN"),
        ("ATV", "ATV"),
        ("ATVP", "ATVP"),
        ("APTV", "ATVP"),
        ("CC", "CC"),
        ("DCU", "DCU"),
        ("DSNP", "DSNP"),
        ("PLAY", "PLAY"),
        ("HBO", "HBO"),
        ("HMAX", "HMAX"),
        ("HULU", "HULU"),
        ("iT", "iT"),
        ("MAX", "MAX"),
        ("MA", "MA"),
        ("NF", "NF"),
        ("PMTP", "PMTP"),
        ("PCOK", "PCOK"),
        ("ROKU", "ROKU"),
        ("SHO", "SHO"),
        ("STAN", "STAN"),
        ("SYFY", "SYFY"),
        ("ABEMA", "ABEMA"),
        ("ADN", "ADN"),
        ("B-Global", "B-Global"),
        ("Bilibili", "Bilibili"),
        ("CR", "CR"),
        ("FUNI", "FUNI"),
        ("HIDIVE", "HIDIVE"),
        ("VRV", "VRV"),
        ("WKN", "WKN"),
    ],
)
def test_streaming_service_codes_from_realistic_filenames(code_token: str, expected: str) -> None:
    identity = parse_release_identity(f"Show.S01E01.1080p.{code_token}.WEB-DL.DDP5.1.H.264-GRP.mkv")
    assert identity.service == expected


@pytest.mark.parametrize(
    ("alias_tokens", "expected"),
    [
        ("AMAZON", "AMZN"),
        ("AMAZONHD", "AMZN"),
        ("AMAZON.PRIME", "AMZN"),
        ("APPLETV", "ATV"),
        ("APPLE.TV", "ATV"),
        ("APPLE.TV+", "ATVP"),
        ("DC.UNIVERSE", "DCU"),
        ("DSNY", "DSNP"),
        ("DISNEY", "DSNP"),
        ("DISNEY+", "DSNP"),
        ("HBOM", "HMAX"),
        ("HBOMAX", "HMAX"),
        ("ITUNES", "iT"),
        ("MOVIES.ANYWHERE", "MA"),
        ("NETFLIX", "NF"),
        ("NETFLIXHD", "NF"),
        ("NETFLIXUHD", "NF"),
        ("PARAMOUNT", "PMTP"),
        ("PARAMOUNT+", "PMTP"),
        ("PEACOCK", "PCOK"),
        ("PEACOCK.TV", "PCOK"),
        ("SHOWTIME", "SHO"),
        ("ABEMATV", "ABEMA"),
        ("ABEMA.TV", "ABEMA"),
        ("BGLOBAL", "B-Global"),
        ("B.GLOBAL", "B-Global"),
        ("BILI", "Bilibili"),
        ("CRUNCHYROLL", "CR"),
        ("CRUNCHY.ROLL", "CR"),
        ("FUNIMATION", "FUNI"),
        ("HIDI", "HIDIVE"),
        ("WAKA", "WKN"),
        ("WAKANIM", "WKN"),
    ],
)
def test_streaming_service_alias_spellings_from_realistic_filenames(
    alias_tokens: str, expected: str
) -> None:
    identity = parse_release_identity(
        f"Show.S01E01.1080p.{alias_tokens}.WEB-DL.DDP5.1.H.264-GRP.mkv"
    )
    assert identity.service == expected


@pytest.mark.parametrize("code_token", ["CC", "PLAY", "HBO", "HMAX", "iT", "MAX", "SHO", "STAN"])
def test_needs_web_services_without_web_next_give_no_service(code_token: str) -> None:
    identity = parse_release_identity(f"Show.S01E01.1080p.{code_token}.DDP5.1.H.264-GRP.mkv")
    assert identity.service is None


def test_hbo_max_without_web_next_gives_no_service() -> None:
    identity = parse_release_identity("Show.S01E01.1080p.HBO.MAX.DDP5.1.H.264-GRP.mkv")
    assert identity.service is None


def test_it_title_and_service_from_realistic_filename() -> None:
    identity = parse_release_identity("It.2017.2160p.iT.WEB-DL.DDP5.1.H.264-GRP.mkv")
    assert identity.content.title == "It"
    assert identity.service == "iT"


def test_it_without_web_next_gives_no_service() -> None:
    identity = parse_release_identity("Show.S01E01.1080p.IT.DDP5.1.H.264-GRP.mkv")
    assert identity.service is None


def test_hbo_max_gives_hmax_and_hbo_alone_gives_hbo() -> None:
    combined = parse_release_identity("Show.S01E01.1080p.HBO.MAX.WEB-DL.DDP5.1.H.264-GRP.mkv")
    assert combined.service == "HMAX"
    alone = parse_release_identity("Show.S01E01.1080p.HBO.WEB-DL.DDP5.1.H.264-GRP.mkv")
    assert alone.service == "HBO"


def test_screenshots_it_file_descriptor() -> None:
    identity = parse_release_identity(
        "Show.2024.2160p.iT.WEB-DL.DV.HDR.H.265-ThisBlockHasProblems.mkv"
    )
    assert (
        format_release_descriptor(identity) == "2160p | iT WEB-DL | DV HDR | ThisBlockHasProblems"
    )


@pytest.mark.parametrize(
    ("guessit_name", "expected"),
    [
        ("Apple TV+", "ATVP"),
        ("HBO Max", "HMAX"),
        ("iTunes", "iT"),
        ("Comedy Central", "CC"),
        ("DC Universe", "DCU"),
        ("Disney", "DSNP"),
        ("HBO Go", "HBO"),
        ("The Roku Channel", "ROKU"),
        ("Showtime", "SHO"),
        ("Stan", "STAN"),
        ("Syfy", "SYFY"),
        ("Crunchy Roll", "CR"),
        ("Anime Digital Network", "ADN"),
        ("Peacock", "PCOK"),
    ],
)
def test_guessit_streaming_service_names_map_to_display_codes(
    monkeypatch: pytest.MonkeyPatch, guessit_name: str, expected: str
) -> None:
    monkeypatch.setattr(
        "frame_compare.services.metadata_parsing.guessit",
        lambda _name: {"title": "Show", "streaming_service": guessit_name},
    )
    monkeypatch.setattr("frame_compare.services.metadata_parsing.anitopy.parse", lambda _name: {})

    identity = parse_release_identity("Show.mkv")

    assert identity.service == expected


def test_embedded_source_text_does_not_start_the_release_suffix() -> None:
    identity = parse_release_identity("The.WebRipples.PROPER.Man.2024.1080p.WEBRip-GROUP.mkv")

    assert identity.source_type == "WEBRip"
    assert identity.revision_tags == ()
    assert identity.release_group == "GROUP"


def test_hlg_claim_is_not_duplicated_in_release_descriptor() -> None:
    identity = parse_release_identity("Show.S01E05.1080p.AMZN.WEBRip.HLG-GROUP.mkv")

    assert format_release_descriptor(identity) == "1080p | AMZN WEBRip | HLG | GROUP"


def test_hlg_group_correction_normalizes_the_remaining_group() -> None:
    identity = parse_release_identity("Show.S01E05.1080p.AMZN.WEBRip.HLG-\x1bGROUP.mkv")

    assert identity.release_group == "GROUP"


def test_hdr10plus_group_correction_preserves_the_claim() -> None:
    identity = parse_release_identity("Film.2024.2160p.WEB-DL.HDR10Plus-GROUP.mkv")

    assert identity.dynamic_range_claims == ("HDR10+",)
    assert identity.release_group == "GROUP"


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


def test_normalized_empty_parser_title_uses_stem_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "frame_compare.services.metadata_parsing.guessit",
        lambda _name: {"title": "\x01\x02"},
    )
    monkeypatch.setattr("frame_compare.services.metadata_parsing.anitopy.parse", lambda _name: {})

    identity = parse_release_identity("Meaningful.Movie.mkv")

    assert identity.content == ContentIdentity(
        "Meaningful Movie",
        title_origin="fallback",
    )


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


def test_separator_keyword_applies_to_inner_and_outer_joins() -> None:
    """The B1 separator flows into the nested release join, not just the outer one."""
    identity = ReleaseIdentity(
        ContentIdentity("Example", year=2026),
        resolution="2160p",
        service="ATV",
        source_type="WEB-DL",
        dynamic_range_claims=("DV", "HDR10+"),
        release_group="Kitsune",
    )
    assert format_release_descriptor(identity, separator=" · ") == (
        "2160p · ATV WEB-DL · DV HDR10+ · Kitsune"
    )
    assert format_micro_descriptor(identity, separator=" · ") == (
        "ATV WEB-DL · DV HDR10+ · Kitsune"
    )
    compact = format_compact_identity(identity, separator=" · ")
    assert compact == "Example (2026) · 2160p · ATV WEB-DL · DV HDR10+ · Kitsune"
    assert "|" not in compact


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
