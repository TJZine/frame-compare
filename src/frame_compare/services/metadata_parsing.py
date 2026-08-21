"""Filename metadata parsing helpers."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

import anitopy
import structlog
from guessit import guessit

from frame_compare.services.release_identity import ContentIdentity, ReleaseIdentity
from frame_compare.services.types import ParsedMetadata

log = structlog.get_logger()

type FilenameMetadataParser = Callable[[str], dict[str, object]]
type _ParsedField = str | int
type ParserPriority = Literal["auto", "guessit", "anitopy"]
type AlternateParserPolicy = Literal["merge", "fallback"]


@dataclass(frozen=True)
class _ParsedFilenameFields:
    title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None
    release_group: str | None = None
    source: str | None = None
    resolution: str | None = None
    service: str | None = None
    other: tuple[str, ...] = ()
    edition: tuple[str, ...] = ()


def _first_text(parser_result: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = parser_result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _texts(parser_result: dict[str, object], *keys: str) -> tuple[str, ...]:
    values: list[str] = []
    for key in keys:
        value = parser_result.get(key)
        candidates = cast(list[object], value) if isinstance(value, list) else [value]
        values.extend(item.strip() for item in candidates if isinstance(item, str) and item.strip())
    return tuple(values)


def _first_int(parser_result: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        value = parser_result.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], int)
            and not isinstance(value[0], bool)
            and value[0] >= 0
        ):
            return value[0]
    return None


def _keep_existing[TParsedField: _ParsedField](
    existing: TParsedField | None,
    parsed: TParsedField | None,
) -> TParsedField | None:
    return existing if existing is not None else parsed


def _merge_parser_metadata(
    current: _ParsedFilenameFields,
    parser_result: dict[str, object],
) -> _ParsedFilenameFields:
    return _ParsedFilenameFields(
        title=_keep_existing(
            current.title,
            _first_text(parser_result, "anime_title", "title"),
        ),
        year=_keep_existing(current.year, _first_int(parser_result, "year")),
        season=_keep_existing(current.season, _first_int(parser_result, "season")),
        episode=_keep_existing(
            current.episode,
            _first_int(parser_result, "anime_episode", "episode"),
        ),
        episode_title=_keep_existing(
            current.episode_title,
            _first_text(parser_result, "episode_title", "anime_episode_title"),
        ),
        release_group=_keep_existing(
            current.release_group,
            _first_text(parser_result, "release_group"),
        ),
        source=_keep_existing(current.source, _first_text(parser_result, "source")),
        resolution=_keep_existing(
            current.resolution,
            _first_text(parser_result, "screen_size", "video_resolution"),
        ),
        service=_keep_existing(current.service, _first_text(parser_result, "streaming_service")),
        other=current.other
        + tuple(value for value in _texts(parser_result, "other") if value not in current.other),
        edition=current.edition
        + tuple(
            value for value in _texts(parser_result, "edition") if value not in current.edition
        ),
    )


def _parse_fields(
    filename: str,
    parser_priority: ParserPriority,
    alternate_policy: AlternateParserPolicy,
) -> _ParsedFilenameFields:
    if not filename:
        return _ParsedFilenameFields()
    use_anitopy_first = parser_priority == "anitopy" or (
        parser_priority == "auto" and filename.startswith("[")
    )

    parsers: list[FilenameMetadataParser] = [
        (_apply_anitopy if use_anitopy_first else _apply_guessit),
        (_apply_guessit if use_anitopy_first else _apply_anitopy),
    ]
    fields = _merge_parser_metadata(_ParsedFilenameFields(), parsers[0](filename))
    if alternate_policy == "merge" or not _has_usable_title(fields.title):
        if alternate_policy == "fallback":
            fields = replace(fields, title=None)
        fields = _merge_parser_metadata(fields, parsers[1](filename))
    return fields


def _log_parser_exception(parser_name: str, name: str, exc: Exception) -> None:
    log.debug(
        "filename_metadata_parser_failed",
        parser=parser_name,
        filename_stem=Path(name).stem,
        exception_type=type(exc).__name__,
        error=str(exc),
    )


def _normalize_parser_result(result: object) -> dict[str, object]:
    if not isinstance(result, Mapping):
        return {}
    return {
        key: value
        for key, value in cast(Mapping[object, object], result).items()
        if isinstance(key, str)
    }


def _apply_anitopy(name: str) -> dict[str, object]:
    try:
        return _normalize_parser_result(anitopy.parse(name))
    except Exception as exc:
        _log_parser_exception("anitopy", name, exc)
        return {}


def _apply_guessit(name: str) -> dict[str, object]:
    try:
        return _normalize_parser_result(guessit(name))
    except Exception as exc:
        _log_parser_exception("guessit", name, exc)
        return {}


def parse_filename(
    filename: str,
    parser_priority: ParserPriority = "auto",
    *,
    alternate_policy: AlternateParserPolicy = "merge",
) -> ParsedMetadata:
    """
    Extract metadata from filename using GuessIt + Anitopy.

    Parser selection:
    1. If filename starts with '[' (bracketed group), use Anitopy first
    2. Otherwise, try GuessIt for western media
    3. In fallback mode, try the alternate parser only when the primary parser
       returns no usable title. Merge mode preserves the historical behavior of
       filling missing primary fields from the alternate parser.

    Fallback behavior:
    - If both parsers fail to extract a title, use the filename stem
      (filename without extension) as the title
    - All other fields default to None when not extracted

    Normalization:
    - Title separators (., _, -) are normalized to spaces
    - Leading/trailing whitespace is stripped from title

    Args:
        filename: Video filename (not full path)
        parser_priority: Primary parser selection policy.
        alternate_policy: Whether the alternate parser always fills missing
            fields or runs only when the primary has no usable title.

    Returns:
        ParsedMetadata with extracted fields (always returns, never raises)
    """
    if not filename:
        return ParsedMetadata(title="")

    fields = _parse_fields(filename, parser_priority, alternate_policy)

    title = fields.title or Path(filename).stem

    # Normalization
    title = re.sub(r"[._\-]", " ", title).strip()

    return ParsedMetadata(
        title=title,
        year=fields.year,
        season=fields.season,
        episode=fields.episode,
        episode_title=fields.episode_title,
        release_group=fields.release_group,
        source=fields.source,
        resolution=fields.resolution,
    )


_SERVICE_ALIASES = {
    "Netflix": "NF",
    "Amazon Prime": "AMZN",
    "Paramount+": "PMTP",
    "Disney+": "DSNP",
    "HBO Max": "MAX",
    "Hulu": "HULU",
    "Peacock": "PCOK",
    "Movies Anywhere": "MA",
    "Apple TV+": "ATV",
}


def parse_release_identity(
    filename: str,
    parser_priority: ParserPriority = "auto",
    *,
    alternate_policy: AlternateParserPolicy = "merge",
) -> ReleaseIdentity:
    """Parse presentation-only filename claims, failing open to the filename stem."""
    fields = _parse_fields(filename, parser_priority, alternate_policy)
    title = re.sub(r"[._\-]", " ", fields.title or Path(filename).stem).strip()
    tokens = {token.upper() for token in re.split(r"[^A-Za-z0-9+]+", Path(filename).stem) if token}
    source_type = _source_type(filename, fields.source)
    has_release_context = fields.resolution is not None or source_type is not None
    service = _SERVICE_ALIASES.get(fields.service or "")
    if service is None:
        service = next(
            (
                code
                for code in (
                    "ATV",
                    "PMTP",
                    "DSNP",
                    "HULU",
                    "PCOK",
                    "HMAX",
                    "MAX",
                    "AMZN",
                    "NF",
                    "MA",
                )
                if has_release_context and code in tokens
            ),
            None,
        )
        if service == "HMAX":
            service = "MAX"
    observed = {value.casefold() for value in fields.other}
    raw_claims: set[str] = tokens if has_release_context else set()
    claims = tuple(
        label
        for label in (
            "DV",
            "HDR10+",
            "HDR10",
            "HLG",
            "HDR",
            "SDR",
        )
        if label.upper() in raw_claims
        or (label == "DV" and "DOLBY" in raw_claims and "VISION" in raw_claims)
    )
    revisions = tuple(
        tag
        for tag in ("REPACK2", "REPACK", "REAL PROPER", "PROPER")
        if has_release_context
        and re.search(
            rf"(?i)(?:^|[. _\-]){tag.replace(' ', r'[. _\-]+')}(?:$|[. _\-])", Path(filename).stem
        )
    )
    variants = tuple(
        tag
        for tag in ("HYBRID", "IMAX", "Extended", "Director's Cut", "Criterion")
        if has_release_context
        and (
            tag.casefold() in observed
            or any(tag.casefold() == value.casefold() for value in fields.edition)
            or re.search(rf"(?i)(?:^|[. _\-]){re.escape(tag)}(?:$|[. _\-])", Path(filename).stem)
        )
    )
    return ReleaseIdentity(
        content=ContentIdentity(
            title,
            fields.year,
            fields.season,
            fields.episode,
            fields.episode_title,
            "parsed" if fields.title else "fallback",
        ),
        resolution=fields.resolution,
        service=service,
        source_type=source_type,
        dynamic_range_claims=claims,
        release_group=fields.release_group,
        revision_tags=revisions,
        variant_tags=variants,
    )


def _source_type(filename: str, parsed_source: str | None) -> str | None:
    stem = Path(filename).stem
    patterns = (
        (r"UHD[. _-]*BluRay[. _-]*REMUX", "UHD BluRay REMUX"),
        (r"BluRay[. _-]*REMUX", "BluRay REMUX"),
        (r"UHD[. _-]*BluRay", "UHD BluRay"),
        (r"WEB[. _-]*DL", "WEB-DL"),
        (r"WEB[. _-]*Rip", "WEBRip"),
    )
    for pattern, label in patterns:
        if re.search(rf"(?i)(?:^|[. _-]){pattern}(?:$|[. _-])", stem):
            return label
    normalized = {"Blu-ray": "BluRay", "HDTV": "HDTV", "DVD": "DVD"}
    return normalized.get(parsed_source or "")


def _has_usable_title(title: str | None) -> bool:
    if title is None:
        return False
    return bool(re.sub(r"[._\-]", " ", title).strip())
