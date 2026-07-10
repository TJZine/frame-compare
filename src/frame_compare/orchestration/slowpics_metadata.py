"""Pure slow.pics collection-title and TMDB association policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from frame_compare.config.schema_models import SlowpicsConfig
from frame_compare.config.slowpics import (
    SlowpicsTitleTemplateContext,
    render_slowpics_title_template,
)
from frame_compare.orchestration.source_labels import normalize_derived_display_text
from frame_compare.services.types import (
    ParsedMetadata,
    SlowpicsCollectionMetadata,
    TmdbMetadata,
)


@dataclass(frozen=True)
class SlowpicsMetadataResolution:
    """Resolved collection metadata plus sanitized policy warnings."""

    metadata: SlowpicsCollectionMetadata
    warnings: tuple[str, ...] = ()


def resolve_slowpics_collection_metadata(
    *,
    config: SlowpicsConfig,
    reference_path: Path,
    reference_label: str,
    parsed_reference: ParsedMetadata,
    resolved_tmdb: TmdbMetadata | None,
) -> SlowpicsMetadataResolution:
    """Resolve one immutable metadata value for upload and post-upload naming."""
    explicit_pair = (
        (config.tmdb_id, config.tmdb_media_type)
        if config.tmdb_id is not None and config.tmdb_media_type is not None
        else None
    )
    resolved_pair = (
        (resolved_tmdb.tmdb_id, resolved_tmdb.media_type) if resolved_tmdb is not None else None
    )
    mismatch = (
        explicit_pair is not None and resolved_pair is not None and explicit_pair != resolved_pair
    )
    matching_tmdb = None if mismatch else resolved_tmdb
    association = explicit_pair or resolved_pair

    context = _template_context(
        reference_path=reference_path,
        reference_label=reference_label,
        parsed_reference=parsed_reference,
        matching_tmdb=matching_tmdb,
        association=association,
    )
    base_title = _base_title(
        config=config,
        context=context,
        reference_path=reference_path,
        parsed_reference=parsed_reference,
        matching_tmdb=matching_tmdb,
    )
    title = f"{base_title} {config.title_suffix}" if config.title_suffix else base_title
    warnings = (
        (
            (
                "slow.pics: explicit TMDB association differs from resolved metadata; "
                "automatic title metadata was not combined with the explicit association"
            ),
        )
        if mismatch
        else ()
    )
    return SlowpicsMetadataResolution(
        metadata=SlowpicsCollectionMetadata(
            title=title,
            tmdb_id=association[0] if association is not None else None,
            tmdb_media_type=association[1] if association is not None else None,
        ),
        warnings=warnings,
    )


def _template_context(
    *,
    reference_path: Path,
    reference_label: str,
    parsed_reference: ParsedMetadata,
    matching_tmdb: TmdbMetadata | None,
    association: tuple[int, str] | None,
) -> SlowpicsTitleTemplateContext:
    title = matching_tmdb.title if matching_tmdb is not None else parsed_reference.title
    original_title = matching_tmdb.original_title if matching_tmdb is not None else ""
    year = matching_tmdb.year if matching_tmdb is not None else parsed_reference.year
    original_language = matching_tmdb.original_language if matching_tmdb is not None else None
    return {
        "Title": normalize_derived_display_text(title, fallback=""),
        "OriginalTitle": normalize_derived_display_text(original_title, fallback=""),
        "Year": str(year) if year is not None and year > 0 else "",
        "TMDBId": str(association[0]) if association is not None else "",
        "TMDBCategory": association[1].upper() if association is not None else "",
        "OriginalLanguage": normalize_derived_display_text(original_language or "", fallback=""),
        "Filename": normalize_derived_display_text(reference_path.stem, fallback=""),
        "FileName": normalize_derived_display_text(reference_path.name, fallback=""),
        "Label": normalize_derived_display_text(reference_label, fallback=""),
    }


def _base_title(
    *,
    config: SlowpicsConfig,
    context: SlowpicsTitleTemplateContext,
    reference_path: Path,
    parsed_reference: ParsedMetadata,
    matching_tmdb: TmdbMetadata | None,
) -> str:
    if config.title:
        return config.title
    if config.title_template:
        rendered = normalize_derived_display_text(
            render_slowpics_title_template(config.title_template, context),
            fallback="",
        )
        if rendered:
            return rendered
    if matching_tmdb is not None:
        candidate = _title_with_optional_year(matching_tmdb.title, matching_tmdb.year)
        if candidate:
            return candidate
    if parsed_reference.title:
        candidate = _title_with_optional_year(parsed_reference.title, parsed_reference.year)
        if candidate:
            return candidate
    stem = normalize_derived_display_text(reference_path.stem, fallback="")
    return stem or "Frame Comparison"


def _title_with_optional_year(title: str, year: int | None) -> str:
    normalized = normalize_derived_display_text(title, fallback="")
    if not normalized:
        return ""
    return f"{normalized} ({year})" if year is not None and year > 0 else normalized


__all__ = [
    "SlowpicsMetadataResolution",
    "resolve_slowpics_collection_metadata",
]
