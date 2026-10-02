"""Resolved slow.pics collection metadata policy tests."""

from pathlib import Path

import pytest

from frame_compare.config.schema_models import SlowpicsConfig
from frame_compare.orchestration.slowpics_metadata import (
    resolve_slowpics_collection_metadata,
)
from frame_compare.services.types import ParsedMetadata, TmdbMetadata


def _resolve(
    config: SlowpicsConfig | None = None,
    *,
    parsed: ParsedMetadata | None = None,
    tmdb: TmdbMetadata | None = None,
    path: Path = Path("Reference.Source.mkv"),
):
    return resolve_slowpics_collection_metadata(
        config=config or SlowpicsConfig(),
        reference_path=path,
        reference_label="Reference Label",
        parsed_reference=parsed or ParsedMetadata(title="Parsed Title", year=2020),
        resolved_tmdb=tmdb,
    )


@pytest.mark.parametrize(
    ("config", "parsed", "tmdb", "path", "expected"),
    [
        pytest.param(
            SlowpicsConfig(title="Literal", title_suffix="[X]"),
            None,
            None,
            Path("Reference.Source.mkv"),
            "Literal [X]",
            id="literal_template_and_suffix_paths_share_exact_final_title-0",
        ),
        pytest.param(
            SlowpicsConfig(
                title_template="${Title} (${Year}) - ${Filename} - ${FileName} - ${Label} $$",
                title_suffix="[X]",
            ),
            None,
            None,
            Path("Reference.Source.mkv"),
            "Parsed Title (2020) - Reference.Source - Reference.Source.mkv - Reference Label $ [X]",
            id="literal_template_and_suffix_paths_share_exact_final_title-1",
        ),
        pytest.param(
            None,
            None,
            TmdbMetadata(1, "TMDB Title", "Original", 2024, "movie"),
            Path("Reference.Source.mkv"),
            "TMDB Title (2024)",
            id="automatic_title_precedence_tmdb_parsed_stem_and_final_fallback-0",
        ),
        pytest.param(
            None,
            ParsedMetadata(title="Parsed", year=2021),
            None,
            Path("Reference.Source.mkv"),
            "Parsed (2021)",
            id="automatic_title_precedence_tmdb_parsed_stem_and_final_fallback-1",
        ),
        pytest.param(
            None,
            ParsedMetadata(title=""),
            None,
            Path("Reference.mkv"),
            "Reference",
            id="automatic_title_precedence_tmdb_parsed_stem_and_final_fallback-2",
        ),
        pytest.param(
            None,
            ParsedMetadata(title=""),
            None,
            Path(""),
            "Frame Comparison",
            id="automatic_title_precedence_tmdb_parsed_stem_and_final_fallback-3",
        ),
        pytest.param(
            SlowpicsConfig(title_suffix="[X]"),
            ParsedMetadata(title="Parsed", year=2021),
            TmdbMetadata(1, "TMDB Title", "Original", 2024, "movie"),
            Path("Reference.mkv"),
            "TMDB Title (2024) [X]",
            id="suffix-0",
        ),
        pytest.param(
            SlowpicsConfig(title_suffix="[X]"),
            ParsedMetadata(title="Parsed", year=2021),
            None,
            Path("Reference.mkv"),
            "Parsed (2021) [X]",
            id="suffix-1",
        ),
        pytest.param(
            SlowpicsConfig(title_suffix="[X]"),
            ParsedMetadata(title=""),
            None,
            Path("Reference.mkv"),
            "Reference [X]",
            id="suffix-2",
        ),
        pytest.param(
            SlowpicsConfig(title_suffix="[X]"),
            ParsedMetadata(title=""),
            None,
            Path(""),
            "Frame Comparison [X]",
            id="suffix-3",
        ),
        pytest.param(
            SlowpicsConfig(title_template="${OriginalLanguage}"),
            None,
            TmdbMetadata(1, "TMDB Title", "Original", 0, "tv"),
            Path("Reference.Source.mkv"),
            "TMDB Title",
            id="zero_year_is_omitted_and_blank_template_continues_to_automatic_fallback-0",
        ),
    ],
)
def test_resolved_collection_title(
    config: SlowpicsConfig | None,
    parsed: ParsedMetadata | None,
    tmdb: TmdbMetadata | None,
    path: Path,
    expected: str,
) -> None:
    assert _resolve(config, parsed=parsed, tmdb=tmdb, path=path).metadata.title == expected


def test_auto_and_explicit_tmdb_association_are_typed() -> None:
    tmdb = TmdbMetadata(7, "Title", "Original", 2024, "tv", original_language="ja")
    automatic = _resolve(tmdb=tmdb).metadata
    assert (automatic.tmdb_id, automatic.tmdb_media_type) == (7, "tv")

    explicit = _resolve(
        SlowpicsConfig(tmdb_id=9, tmdb_media_type="movie"),
        tmdb=None,
    ).metadata
    assert (explicit.tmdb_id, explicit.tmdb_media_type) == (9, "movie")


def test_explicit_tmdb_mismatch_isolated_from_resolved_title_without_mutation() -> None:
    config = SlowpicsConfig(
        tmdb_id=9,
        tmdb_media_type="movie",
        title_template="${Title}|${OriginalTitle}|${Year}|${OriginalLanguage}|${TMDBCategory}_${TMDBId}",
    )
    tmdb = TmdbMetadata(7, "Wrong", "Wrong Original", 2024, "tv", original_language="ja")
    result = _resolve(
        config,
        parsed=ParsedMetadata(title="Parsed", year=2020),
        tmdb=tmdb,
    )

    assert result.metadata.title == "Parsed||2020||MOVIE_9"
    assert (result.metadata.tmdb_id, result.metadata.tmdb_media_type) == (9, "movie")
    assert result.warnings
    assert config.tmdb_id == 9
    assert tmdb.title == "Wrong"
