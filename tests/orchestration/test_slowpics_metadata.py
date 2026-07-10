"""Resolved slow.pics collection metadata policy tests."""

from pathlib import Path

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


def test_literal_template_and_suffix_paths_share_exact_final_title() -> None:
    assert _resolve(SlowpicsConfig(title="Literal", title_suffix="[X]")).metadata.title == (
        "Literal [X]"
    )
    result = _resolve(
        SlowpicsConfig(
            title_template="${Title} (${Year}) - ${Filename} - ${FileName} - ${Label} $$",
            title_suffix="[X]",
        )
    )
    assert result.metadata.title == (
        "Parsed Title (2020) - Reference.Source - Reference.Source.mkv - Reference Label $ [X]"
    )


def test_automatic_title_precedence_tmdb_parsed_stem_and_final_fallback() -> None:
    tmdb = TmdbMetadata(1, "TMDB Title", "Original", 2024, "movie")
    assert _resolve(tmdb=tmdb).metadata.title == "TMDB Title (2024)"
    assert _resolve(parsed=ParsedMetadata(title="Parsed", year=2021)).metadata.title == (
        "Parsed (2021)"
    )
    assert _resolve(parsed=ParsedMetadata(title=""), path=Path("Reference.mkv")).metadata.title == (
        "Reference"
    )
    assert _resolve(parsed=ParsedMetadata(title=""), path=Path("")).metadata.title == (
        "Frame Comparison"
    )


def test_zero_year_is_omitted_and_blank_template_continues_to_automatic_fallback() -> None:
    tmdb = TmdbMetadata(1, "TMDB Title", "Original", 0, "tv")
    assert _resolve(
        SlowpicsConfig(title_template="${OriginalLanguage}"), tmdb=tmdb
    ).metadata.title == ("TMDB Title")


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
