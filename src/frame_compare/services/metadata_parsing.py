"""Filename metadata parsing helpers."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

import anitopy
import structlog
from guessit import guessit

from frame_compare.config.text_validation import is_control_character
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


def _first_text(parser_result: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        raw_value = cast(object, parser_result.get(key))
        for value in _field_values(raw_value):
            if isinstance(value, str) and value.strip():
                return value
    return None


def _field_values(value: object) -> tuple[object, ...]:
    if isinstance(value, list):
        return tuple(cast(list[object], value))
    if isinstance(value, tuple):
        return cast(tuple[object, ...], value)
    return (value,)


def _first_int(parser_result: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        raw_value = cast(object, parser_result.get(key))
        for value in _field_values(raw_value):
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
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
        service=_keep_existing(
            current.service,
            _first_text(parser_result, "streaming_service"),
        ),
    )


def _parse_fields(
    filename: str,
    parser_priority: ParserPriority,
    alternate_policy: AlternateParserPolicy,
) -> _ParsedFilenameFields:
    if not filename:
        return _ParsedFilenameFields()
    parsers = _ordered_parsers(filename, parser_priority)
    fields = _merge_parser_metadata(_ParsedFilenameFields(), parsers[0](filename))
    if alternate_policy == "merge" or not _has_usable_title(fields.title):
        if alternate_policy == "fallback":
            fields = replace(fields, title=None)
        fields = _merge_parser_metadata(fields, parsers[1](filename))
    return fields


def _ordered_parsers(
    filename: str, parser_priority: ParserPriority
) -> tuple[FilenameMetadataParser, FilenameMetadataParser]:
    use_anitopy_first = parser_priority == "anitopy" or (
        parser_priority == "auto" and filename.startswith("[")
    )
    return (
        (_apply_anitopy if use_anitopy_first else _apply_guessit),
        (_apply_guessit if use_anitopy_first else _apply_anitopy),
    )


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
    return _parsed_metadata(filename, fields)


def _parsed_metadata(filename: str, fields: _ParsedFilenameFields) -> ParsedMetadata:
    """Build the historical canonical filename metadata shape."""

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
    "netflix": "NF",
    "amazon": "AMZN",
    "amazon prime": "AMZN",
    "paramount+": "PMTP",
    "disney+": "DSNP",
    "hbo max": "MAX",
    "max": "MAX",
    "hulu": "HULU",
    "peacock": "PCOK",
    "movies anywhere": "MA",
    "apple tv": "ATV",
    "apple tv+": "ATV",
}

_SERVICE_TOKEN_ALIASES = {
    "ATV": (("ATV",), ("APPLETV",), ("APPLE", "TV"), ("APPLE", "TV+")),
    "PMTP": (("PMTP",), ("PARAMOUNT",), ("PARAMOUNT+",)),
    "DSNP": (("DSNP",), ("DISNEY",), ("DISNEY+",)),
    "HULU": (("HULU",),),
    "PCOK": (("PCOK",), ("PEACOCK",)),
    "MAX": (("HMAX",), ("MAX",), ("HBO", "MAX")),
    "AMZN": (("AMZN",), ("AMAZON",), ("AMAZON", "PRIME")),
    "NF": (("NF",), ("NETFLIX",)),
    "MA": (("MA",), ("MOVIES", "ANYWHERE")),
}

_SOURCE_PATTERNS = (
    (r"UHD[. _-]*BluRay[. _-]*REMUX", "UHD BluRay REMUX"),
    (r"BluRay[. _-]*REMUX", "BluRay REMUX"),
    (r"UHD[. _-]*BluRay", "UHD BluRay"),
    (r"WEB[. _-]*DL", "WEB-DL"),
    (r"WEB[. _-]*Rip", "WEBRip"),
)


def parse_release_identity(
    filename: str,
    parser_priority: ParserPriority = "auto",
    *,
    alternate_policy: AlternateParserPolicy = "merge",
) -> ReleaseIdentity:
    """Parse presentation-only filename claims, failing open to the filename stem."""
    fields = _parse_fields(filename, parser_priority, alternate_policy)
    return _release_identity(filename, fields)


def parse_filename_with_release_identity(
    filename: str,
    parser_priority: ParserPriority = "auto",
) -> tuple[ParsedMetadata, ReleaseIdentity]:
    """Parse canonical-label and merged release metadata with one backend pass."""
    if not filename:
        fields = _ParsedFilenameFields()
        return ParsedMetadata(title=""), _release_identity(filename, fields)

    primary_parser, alternate_parser = _ordered_parsers(filename, parser_priority)
    primary_result = primary_parser(filename)
    alternate_result = alternate_parser(filename)
    canonical_fields = _merge_parser_metadata(_ParsedFilenameFields(), primary_result)
    if not _has_usable_title(canonical_fields.title):
        canonical_fields = _merge_parser_metadata(
            replace(canonical_fields, title=None), alternate_result
        )
    release_fields = _merge_parser_metadata(_ParsedFilenameFields(), primary_result)
    release_fields = _merge_parser_metadata(release_fields, alternate_result)
    return _parsed_metadata(filename, canonical_fields), _release_identity(filename, release_fields)


def _release_identity(filename: str, fields: _ParsedFilenameFields) -> ReleaseIdentity:
    stem = Path(filename).stem
    title = _normalize_release_text(re.sub(r"[._\-]", " ", fields.title or stem))
    resolution = _normalize_optional_release_text(fields.resolution)
    source_type = _source_type(filename, fields.source)
    release_suffix = _release_suffix(stem, resolution, source_type)
    release_tokens = _release_tokens(release_suffix)
    return ReleaseIdentity(
        content=ContentIdentity(
            title or "comparison",
            fields.year,
            fields.season,
            fields.episode,
            _normalize_optional_release_text(fields.episode_title),
            "parsed" if fields.title else "fallback",
        ),
        resolution=resolution,
        service=_service(fields.service, release_tokens),
        source_type=source_type,
        dynamic_range_claims=_dynamic_range_claims(release_tokens),
        release_group=_normalize_optional_release_text(fields.release_group),
        revision_tags=_revision_tags(release_suffix),
        variant_tags=_variant_tags(release_suffix),
    )


def _normalize_release_text(value: str) -> str:
    without_controls = "".join(
        " " if is_control_character(character) else character for character in value
    )
    return " ".join(without_controls.split())


def _normalize_optional_release_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_release_text(value) or None


def _release_tokens(value: str) -> tuple[str, ...]:
    return tuple(token.upper() for token in re.split(r"[^A-Za-z0-9+]+", value) if token)


def _contains_tokens(tokens: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    size = len(expected)
    return any(tokens[index : index + size] == expected for index in range(len(tokens) - size + 1))


def _service(parsed_service: str | None, tokens: tuple[str, ...]) -> str | None:
    parsed = _SERVICE_ALIASES.get((parsed_service or "").strip().casefold())
    if parsed is not None:
        return parsed
    return next(
        (
            code
            for code, aliases in _SERVICE_TOKEN_ALIASES.items()
            if any(_contains_tokens(tokens, alias) for alias in aliases)
        ),
        None,
    )


def _dynamic_range_claims(tokens: tuple[str, ...]) -> tuple[str, ...]:
    aliases = {
        "DV": (("DV",), ("DOVI",), ("DOLBY", "VISION")),
        "HDR10+": (("HDR10+",), ("HDR10PLUS",)),
        "HDR10": (("HDR10",),),
        "HLG": (("HLG",),),
        "HDR": (("HDR",),),
        "SDR": (("SDR",),),
    }
    return tuple(
        label
        for label, spellings in aliases.items()
        if any(_contains_tokens(tokens, spelling) for spelling in spellings)
    )


def _has_release_tag(value: str, expression: str) -> bool:
    return bool(re.search(rf"(?i)(?:^|[. _\-]){expression}(?:$|[. _\-])", value))


def _revision_tags(release_suffix: str) -> tuple[str, ...]:
    tags: list[str] = []
    if _has_release_tag(release_suffix, "REPACK2"):
        tags.append("REPACK2")
    elif _has_release_tag(release_suffix, "REPACK"):
        tags.append("REPACK")
    if _has_release_tag(release_suffix, r"REAL[. _\-]+PROPER"):
        tags.append("REAL PROPER")
    elif _has_release_tag(release_suffix, "PROPER"):
        tags.append("PROPER")
    return tuple(tags)


def _variant_tags(release_suffix: str) -> tuple[str, ...]:
    patterns = (
        ("HYBRID", "HYBRID"),
        ("IMAX", "IMAX"),
        ("Extended", "EXTENDED"),
        ("Director's Cut", r"DIRECTOR'?S?[. _\-]+CUT"),
        ("Criterion", "CRITERION"),
    )
    return tuple(
        label for label, expression in patterns if _has_release_tag(release_suffix, expression)
    )


def _release_suffix(stem: str, resolution: str | None, source_type: str | None) -> str:
    starts: list[int] = []
    if resolution:
        match = re.search(rf"(?i)(?:^|[. _\-]){re.escape(resolution)}(?:$|[. _\-])", stem)
        if match is not None:
            starts.append(match.start())
    for pattern, label in _SOURCE_PATTERNS:
        if source_type == label and (match := re.search(pattern, stem, re.IGNORECASE)) is not None:
            starts.append(match.start())
    if source_type in {"HDTV", "DVD"}:
        match = re.search(rf"(?i)(?:^|[. _\-]){source_type}(?:$|[. _\-])", stem)
        if match is not None:
            starts.append(match.start())
    return stem[min(starts) :] if starts else ""


def _source_type(filename: str, parsed_source: str | None) -> str | None:
    stem = Path(filename).stem
    for pattern, label in _SOURCE_PATTERNS:
        if re.search(rf"(?i)(?:^|[. _-]){pattern}(?:$|[. _-])", stem):
            return label
    normalized = {"Blu-ray": "BluRay", "HDTV": "HDTV", "DVD": "DVD"}
    return normalized.get((parsed_source or "").strip())


def _has_usable_title(title: str | None) -> bool:
    if title is None:
        return False
    return bool(re.sub(r"[._\-]", " ", title).strip())
