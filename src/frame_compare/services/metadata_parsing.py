"""Filename metadata parsing helpers."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import anitopy
import structlog
from guessit import guessit

from frame_compare.services.types import ParsedMetadata

log = structlog.get_logger()

type FilenameMetadataParser = Callable[[str], dict[str, object]]
type _ParsedField = str | int


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


def _first_text(parser_result: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = parser_result.get(key)
        if value:
            return str(value)
    return None


def _first_int(parser_result: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        value = parser_result.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        if isinstance(value, list) and value and isinstance(value[0], int):
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
    )


def parse_filename(
    filename: str,
    parser_priority: Literal["auto", "guessit", "anitopy"] = "auto",
) -> ParsedMetadata:
    """
    Extract metadata from filename using GuessIt + Anitopy.

    Parser selection:
    1. If filename starts with '[' (bracketed group), use Anitopy first
    2. Otherwise, try GuessIt for western media
    3. If primary parser returns no title, try the alternate parser

    Fallback behavior:
    - If both parsers fail to extract a title, use the filename stem
      (filename without extension) as the title
    - All other fields default to None when not extracted

    Normalization:
    - Title separators (., _, -) are normalized to spaces
    - Leading/trailing whitespace is stripped from title

    Args:
        filename: Video filename (not full path)

    Returns:
        ParsedMetadata with extracted fields (always returns, never raises)
    """
    if not filename:
        return ParsedMetadata(title="")

    # Determine primary parser
    use_anitopy_first = parser_priority == "anitopy" or (
        parser_priority == "auto" and filename.startswith("[")
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
        parser_mapping = cast(Mapping[object, object], result)
        return {key: value for key, value in parser_mapping.items() if isinstance(key, str)}

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

    parsers: list[FilenameMetadataParser] = [
        (_apply_anitopy if use_anitopy_first else _apply_guessit),
        (_apply_guessit if use_anitopy_first else _apply_anitopy),
    ]

    fields = _ParsedFilenameFields()

    for parser in parsers:
        fields = _merge_parser_metadata(fields, parser(filename))

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
