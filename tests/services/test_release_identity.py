"""Structured release identity corpus and formatter tests."""

from pathlib import Path

import pytest

from frame_compare.services.metadata_parsing import (
    parse_filename_with_release_identity,
)
from frame_compare.services.release_identity import (
    ContentIdentity,
    ReleaseIdentity,
    ShortNameSource,
    format_compact_identity,
    format_micro_descriptor,
    format_release_descriptor,
    short_source_names,
    unique_presentation_names,
)
from frame_compare.services.types import ParsedMetadata


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
        (
            "The.Odyssey.2026.2160p.UHD.BluRay.DTS-HD.MA.5.1.HDR.x265-RandomBytes.mkv",
            (None, "UHD BluRay", ("HDR",), (), "RandomBytes"),
        ),
        ("Film.2020.1080p.WEB-DL.DTS.HD.MA.5.1-GROUP.mkv", (None, "WEB-DL", (), (), "GROUP")),
        ("Film.2020.1080p.WEB-DL.DTSHD.MA.5.1-GROUP.mkv", (None, "WEB-DL", (), (), "GROUP")),
        (
            "Film.2020.1080p.MA.WEB-DL.DTS-HD.MA.5.1-GROUP.mkv",
            ("MA", "WEB-DL", (), (), "GROUP"),
        ),
        ("Film.2020.1080p.AppleTV.WEB-DL-GROUP.mkv", ("ATV", "WEB-DL", (), (), "GROUP")),
    ],
)
def test_real_parser_corpus(filename: str, expected: tuple[object, ...]) -> None:
    _, identity = parse_filename_with_release_identity(filename)
    assert (
        identity.service,
        identity.source_type,
        identity.dynamic_range_claims,
        identity.revision_tags,
        identity.release_group,
    ) == expected


@pytest.mark.parametrize("code_token", ["CC", "PLAY", "HBO", "HMAX", "iT", "MAX", "SHO", "STAN"])
def test_needs_web_services_without_web_next_give_no_service(code_token: str) -> None:
    _, identity = parse_filename_with_release_identity(
        f"Show.S01E01.1080p.{code_token}.DDP5.1.H.264-GRP.mkv"
    )
    assert identity.service is None


def test_hbo_max_without_web_next_gives_no_service() -> None:
    _, identity = parse_filename_with_release_identity(
        "Show.S01E01.1080p.HBO.MAX.DDP5.1.H.264-GRP.mkv"
    )
    assert identity.service is None


def test_it_without_web_next_gives_no_service() -> None:
    _, identity = parse_filename_with_release_identity("Show.S01E01.1080p.IT.DDP5.1.H.264-GRP.mkv")
    assert identity.service is None


def test_screenshots_it_file_descriptor() -> None:
    identity = ReleaseIdentity(
        ContentIdentity("Show", 2024),
        "2160p",
        "iT",
        "WEB-DL",
        ("DV", "HDR"),
        "ThisBlockHasProblems",
        has_terminal_release_group=True,
    )
    assert (
        format_release_descriptor(identity, short_name="")
        == "2160p | iT WEB-DL | DV HDR | ThisBlockHasProblems"
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

    _, identity = parse_filename_with_release_identity("Show.mkv")

    assert identity.service == expected


def test_hlg_claim_is_not_duplicated_in_release_descriptor() -> None:
    identity = ReleaseIdentity(
        ContentIdentity("Show", season=1, episode=5),
        "1080p",
        "AMZN",
        "WEBRip",
        ("HLG",),
        "GROUP",
        has_terminal_release_group=True,
    )

    assert format_release_descriptor(identity, short_name="") == "1080p | AMZN WEBRip | HLG | GROUP"


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
    _, identity = parse_filename_with_release_identity(filename)
    assert identity.dynamic_range_claims == claims
    assert identity.revision_tags == revisions


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

    _, identity = parse_filename_with_release_identity("Movie.1080p.WEB-DL-GROUP.mkv")

    assert identity.content.title == "Movie Title"
    assert identity.release_group == "GROUP EVIL"
    assert "\n" not in format_compact_identity(identity, short_name="")
    assert "\x1b" not in format_compact_identity(identity, short_name="")


@pytest.mark.parametrize(
    ("filename", "expected_canonical", "expected_year", "expected_episode"),
    [
        (
            "[Group] Movie.2024.1080p.NF.WEB-DL.HDR10.mkv",
            ParsedMetadata(title="Movie 2024", release_group="Group", resolution="1080p"),
            2024,
            None,
        ),
        (
            "[SubsPlease] Show - 03 (1080p) [ABC].mkv",
            ParsedMetadata(
                title="Show",
                episode=3,
                release_group="SubsPlease",
                resolution="1080p",
            ),
            None,
            3,
        ),
    ],
)
def test_combined_parse_preserves_canonical_fallback_and_merged_release_facts(
    filename: str,
    expected_canonical: ParsedMetadata,
    expected_year: int | None,
    expected_episode: int | None,
) -> None:
    canonical, release = parse_filename_with_release_identity(filename, parser_priority="auto")

    assert canonical == expected_canonical
    assert release.content.year == expected_year
    assert release.content.episode == expected_episode


def test_formatters_and_common_content() -> None:
    content = ContentIdentity("Avatar Aang The Last Airbender", 2026)
    first = ReleaseIdentity(
        content,
        "2160p",
        "PMTP",
        "WEB-DL",
        ("DV", "HDR10+"),
        "Kitsune",
        has_terminal_release_group=True,
    )
    second = ReleaseIdentity(
        content,
        "2160p",
        "ATV",
        "WEB-DL",
        ("DV", "HDR10+"),
        "Kitsune",
        ("REPACK",),
        has_terminal_release_group=True,
    )
    assert (
        format_release_descriptor(first, short_name="")
        == "2160p | PMTP WEB-DL | DV HDR10+ | Kitsune"
    )
    assert format_compact_identity(second, short_name="").startswith(
        "Avatar Aang The Last Airbender (2026) | 2160p"
    )
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
        has_terminal_release_group=True,
    )
    assert format_release_descriptor(identity, separator=" · ", short_name="") == (
        "2160p · ATV WEB-DL · DV HDR10+ · Kitsune"
    )
    assert format_micro_descriptor(identity, separator=" · ") == (
        "ATV WEB-DL · DV HDR10+ · Kitsune"
    )
    compact = format_compact_identity(identity, separator=" · ", short_name="")
    assert compact == "Example (2026) · 2160p · ATV WEB-DL · DV HDR10+ · Kitsune"
    assert "|" not in compact


def _short_name_identity(
    service: str | None = None,
    group: str | None = None,
    dynamic_range: tuple[str, ...] = (),
    revision: tuple[str, ...] = (),
) -> ReleaseIdentity:
    return ReleaseIdentity(
        ContentIdentity("Example", year=2026),
        resolution="2160p",
        service=service,
        source_type="WEB-DL" if service is not None else None,
        dynamic_range_claims=dynamic_range,
        release_group=group,
        revision_tags=revision,
        has_terminal_release_group=group is not None,
    )


def _short_name_source(
    identity: ReleaseIdentity | None,
    label: str,
    *,
    explicit: bool = False,
) -> ShortNameSource:
    return ShortNameSource(identity=identity, label=label, label_is_explicit=explicit, stem="")


@pytest.mark.parametrize(
    ("sources", "expected"),
    [
        pytest.param(
            [
                _short_name_source(_short_name_identity("AMZN", "SCOPE", ("HDR",)), "a.mkv"),
                _short_name_source(
                    _short_name_identity("iT", "ThisBlockHasProblems", ("DV", "HDR")),
                    "b.mkv",
                ),
                _short_name_source(
                    _short_name_identity("MA", "TheEndOfTheFuckingWorld", ("DV", "HDR")),
                    "c.mkv",
                ),
            ],
            [
                "SCOPE",
                "ThisBlockHasProblems",
                "TheEndOfTheFuckingWorld",
            ],
            id="use_unique_release_groups",
        ),
        pytest.param(
            [
                _short_name_source(_short_name_identity("AMZN", "SCOPE", ("HDR",)), "a.mkv"),
                _short_name_source(_short_name_identity("iT", "scope", ("DV", "HDR")), "b.mkv"),
            ],
            [
                "AMZN WEB-DL · HDR · SCOPE",
                "iT WEB-DL · DV HDR · scope",
            ],
            id="fall_back_to_compact_name_on_shared_group",
        ),
        pytest.param(
            [
                _short_name_source(
                    _short_name_identity("AMZN", "SCOPE", ("HDR",)), "My Cut", explicit=True
                ),
                _short_name_source(_short_name_identity("iT", "OTHER", ("DV", "HDR")), "b.mkv"),
            ],
            [
                "My Cut",
                "OTHER",
            ],
            id="use_explicit_labels_as_given",
        ),
        pytest.param(
            [
                _short_name_source(None, "reference.mkv"),
                _short_name_source(_short_name_identity("iT", "OTHER", ("DV", "HDR")), "b.mkv"),
            ],
            [
                "reference.mkv",
                "OTHER",
            ],
            id="without_identity_fall_back_to_label",
        ),
        pytest.param(
            [
                _short_name_source(_short_name_identity("AMZN", "SCOPE", ("HDR",)), "a.mkv"),
                _short_name_source(_short_name_identity("AMZN", "SCOPE", ("HDR",)), "b.mkv"),
            ],
            [
                "Reference | AMZN WEB-DL · HDR · SCOPE",
                "Comparison 1 | AMZN WEB-DL · HDR · SCOPE",
            ],
            id="resolve_remaining_collisions",
        ),
    ],
)
def test_short_names(sources: list[ShortNameSource], expected: list[str]) -> None:
    assert short_source_names(sources) == expected


_EBP = "Black.Sails.S01E08.1080p.Bluray.DD5.1.x264-EbP.mkv"
_GNOME = "Black.Sails.S01E08.VIII.1080p.AMZN.WEB-DL.DDP.5.1.H.264-GNOME.mkv"
_NOGRP = "Black.Sails.S01E08.VIII.1080p.BluRay.REMUX.AVC.DTS-HD.MA.5.1-NOGRP.mkv"
_DEMON_SLAYER = "Constructed.DemonSlayer-Kitsune.english-dub-only.mkv"
_DEMON_SLAYER_COPY = "Constructed.DemonSlayer-Kitsune.english-dub-only-copy.mkv"


@pytest.mark.parametrize(
    ("filenames", "expected", "descriptors"),
    [
        ([_EBP, _GNOME, _NOGRP], ["EbP", "GNOME", "NOGRP"], None),
        ([_EBP, _DEMON_SLAYER], ["EbP", "english-dub-only"], None),
        (
            [_EBP, _DEMON_SLAYER_COPY, _DEMON_SLAYER],
            ["EbP", "english-dub-only-copy", "english-dub-only"],
            None,
        ),
        (
            [
                "Constructed.Witch-Kira.audio-delay-500ms.mkv",
                "Constructed.Witch-Kira.audio-starts-500ms-in-sync.mkv",
            ],
            ["delay-500ms", "starts-500ms-in-sync"],
            None,
        ),
        (
            ["Movie.x264-Group.mkv", "Movie.1080p.BluRay-Group-copy.mkv"],
            ["Group", "Group-copy"],
            None,
        ),
        (
            ["Movie.1080p.BluRay.x264-D-Z0N3.mkv", "Movie.1080p.x264-EbP.mkv"],
            ["D-Z0N3", "EbP"],
            None,
        ),
        (["Movie.cutA.final.mkv", "Movie.cutB.final.mkv"], ["cutA", "cutB"], None),
        (["Movie.mkv", "Movie.alternate.mkv"], ["Canonical 1", "alternate"], None),
        (
            ["Movie.2010.1080p.BluRay.x264.crf18.mkv", "Movie.2010.1080p.BluRay.x264.crf20.mkv"],
            ["crf18", "crf20"],
            ["1080p · BluRay · crf18", "1080p · BluRay · crf20"],
        ),
        (
            ["Movie.2010.1080p.BluRay.HYBRID.x264.mkv", "Movie.2010.1080p.WEB-DL.x264.mkv"],
            ["BluRay", "WEB-DL"],
            ["1080p · BluRay · HYBRID", "1080p · WEB-DL"],
        ),
        (
            [
                "Movie.2010.crf18.2160p.AMZN.WEB-DL.H.265-FLUX.mkv",
                "Movie.2010.crf20.2160p.AMZN.WEB-DL.H.265-FLUX.mkv",
            ],
            ["crf18", "crf20"],
            ["2160p · AMZN WEB-DL · FLUX", "2160p · AMZN WEB-DL · FLUX"],
        ),
    ],
)
def test_short_names_for_real_filenames(
    filenames: list[str], expected: list[str], descriptors: list[str] | None
) -> None:
    sources = [
        ShortNameSource(
            identity=parse_filename_with_release_identity(filename)[1],
            label=f"Canonical {index}",
            label_is_explicit=False,
            stem=Path(filename).stem,
        )
        for index, filename in enumerate(filenames, start=1)
    ]
    assert short_source_names(sources) == expected
    actual_descriptors = []
    for source, short in zip(sources, expected, strict=True):
        assert source.identity is not None
        descriptor = format_release_descriptor(source.identity, separator=" · ", short_name=short)
        actual_descriptors.append(descriptor)
        assert format_compact_identity(source.identity, separator=" · ", short_name=short).endswith(
            descriptor
        )
        if not source.identity.has_terminal_release_group:
            assert format_micro_descriptor(
                source.identity, include_group=True
            ) == format_micro_descriptor(source.identity, include_group=False)
    if descriptors is not None:
        assert actual_descriptors == descriptors


def test_malformed_name_fails_open_to_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("frame_compare.services.metadata_parsing.guessit", lambda _name: 42)
    monkeypatch.setattr("frame_compare.services.metadata_parsing.anitopy.parse", lambda _name: None)
    _, identity = parse_filename_with_release_identity("odd_name.mkv")
    assert identity.content == ContentIdentity("odd name", title_origin="fallback")
