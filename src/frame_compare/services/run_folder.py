from __future__ import annotations

import logging
import ntpath
import re
import uuid
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from frame_compare.errors import PathEscapesRootError
from frame_compare.services.errors import GeneratedDataReservationError
from frame_compare.services.release_identity import (
    ShortNameSource,
    clip_role,
    comparison_title,
    format_content_identity,
    short_source_names,
    unique_presentation_names,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.paths import require_managed_immediate_child

_UNNAMED_RUN_BASE = "unnamed_run"
_MAX_FOLDER_NAME_LENGTH = 64
_TOKEN_SEPARATORS = " .-,"
_STEM_WORDS = re.compile(r"[^.\-_ ()]+")

# Characters illegal in Windows filenames (also avoid on Unix for portability)
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACE = re.compile(r"[\s_]+")

log = logging.getLogger(__name__)

type RunFolderNamingSource = Literal["tmdb", "parsed_metadata", "filename_stems", "unnamed"]


@dataclass(frozen=True, slots=True)
class RunFolderReservation:
    path: Path
    folder_name: str
    base_name: str
    naming_source: RunFolderNamingSource


def _clean_folder_text(value: str) -> str:
    return _MULTI_SPACE.sub(" ", _ILLEGAL_CHARS.sub(" ", value)).strip().rstrip(". ")


def _token_prefix(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if value[limit] in _TOKEN_SEPARATORS:
        return value[:limit].rstrip(_TOKEN_SEPARATORS)
    boundary = max(value.rfind(separator, 0, limit) for separator in _TOKEN_SEPARATORS)
    return value[:boundary].rstrip(_TOKEN_SEPARATORS) if boundary >= 0 else ""


def _avoid_windows_reserved_filename(name: str, limit: int) -> str:
    if ntpath.isreserved(name):
        safe_name = _clean_folder_text(f"{name.replace('.', ' ')} run")
        safe_name = _token_prefix(safe_name, limit)
        return safe_name if safe_name and not ntpath.isreserved(safe_name) else _UNNAMED_RUN_BASE
    return name


def _folder_title(
    sources: Sequence[ShortNameSource], tmdb_metadata: TmdbMetadata | None
) -> tuple[str, RunFolderNamingSource]:
    if not sources:
        return "", "unnamed"

    identities = [source.identity for source in sources]
    title = comparison_title(identities, tmdb_metadata)
    if title is not None:
        return title

    titles = list(
        dict.fromkeys(
            format_content_identity(identity.content)
            for identity in identities
            if identity is not None and identity.content.title_origin == "parsed"
        )
    )
    return " + ".join(titles[:2]), "filename_stems"


def _label_summary(labels: Sequence[str], kept: int) -> str:
    summary = ", ".join(labels[:kept])
    omitted = len(labels) - kept
    if omitted:
        summary = f"{summary} +{omitted}".strip()
    return summary


def _fit_folder_name(title: str, labels: Sequence[str], limit: int) -> str:
    if len(labels) == 1:
        budget = limit - (len(title) + 3 if title else 0)
        shortened = _token_prefix(labels[0], max(budget, 0))
        if shortened:
            return " - ".join(part for part in (title, shortened) if part)
    for kept in range(len(labels), -1, -1):
        summary = _label_summary(labels, kept)
        name = " - ".join(part for part in (title, summary) if part)
        if len(name) <= limit:
            return name or _UNNAMED_RUN_BASE

    summary = _label_summary(labels, 0)
    title_budget = limit - (len(summary) + 3 if summary else 0)
    shortened_title = _token_prefix(title, title_budget).removesuffix(" +")
    if not shortened_title:
        return _fit_folder_name("", labels, limit)
    return " - ".join(part for part in (shortened_title, summary) if part)


def reserve_run_folder(
    generated_root: Path,
    sources: Sequence[ShortNameSource],
    tmdb_metadata: TmdbMetadata | None = None,
    *,
    now: datetime,
) -> RunFolderReservation:
    raw_title, naming_source = _folder_title(sources, tmdb_metadata)
    title = _clean_folder_text(raw_title)
    cleaned_labels = [_clean_folder_text(name) for name in short_source_names(sources)]
    if not title and not any(cleaned_labels):
        naming_source = "unnamed"
    roles = [clip_role(index) for index in range(len(sources))]
    title_tokens = _STEM_WORDS.findall(title.casefold())
    for index, label in enumerate(cleaned_labels):
        label_tokens = _STEM_WORDS.findall(label.casefold())
        if label_tokens and set(label_tokens).issubset(title_tokens):
            cleaned_labels[index] = ""
    labels = [
        _clean_folder_text(label)
        for label in unique_presentation_names(
            [label or roles[index] for index, label in enumerate(cleaned_labels)],
            roles=roles,
        )
    ]

    def _candidate_name(suffix: str = "") -> str:
        limit = _MAX_FOLDER_NAME_LENGTH - len(suffix)
        name = _fit_folder_name(title, labels, limit)
        return _avoid_windows_reserved_filename(name, limit) + suffix

    base_name = _candidate_name()

    def _reserve(name: str) -> RunFolderReservation:
        path = generated_root / name
        _reserve_candidate(generated_root, path)
        return RunFolderReservation(path, name, base_name, naming_source)

    try:
        return _reserve(base_name)
    except FileExistsError:
        log.debug(
            "Run folder collision on base path; will retry with suffixes. Path: %s",
            generated_root / base_name,
        )

    local_time = now.astimezone()
    minute = local_time.strftime("%Y-%m-%d %H.%M")
    second = local_time.strftime("%Y-%m-%d %H.%M.%S")
    for stamp in (minute, second):
        try:
            return _reserve(_candidate_name(f" ({stamp})"))
        except FileExistsError:
            continue

    return _reserve(_candidate_name(f" ({second} {uuid.uuid4().hex[:8]})"))


def _reserve_candidate(owner: Path, candidate: Path) -> None:
    resolved_owner = _prepare_reservation_owner(owner)
    try:
        resolved_candidate = require_managed_immediate_child(resolved_owner, candidate)
        resolved_candidate.mkdir(exist_ok=False)
    except (FileExistsError, PathEscapesRootError):
        raise
    except (OSError, RuntimeError) as exc:
        raise GeneratedDataReservationError(resolved_owner, exc) from exc


def _prepare_reservation_owner(owner: Path) -> Path:
    try:
        if not owner.is_absolute():
            raise RuntimeError("generated-data root must be an absolute resolved path")
        resolved_owner_before_create = owner.resolve(strict=False)
        if resolved_owner_before_create != owner:
            raise RuntimeError(
                "generated-data root must be resolved before reservation: "
                f"{owner} -> {resolved_owner_before_create}"
            )

        for directory in (*reversed(owner.parents), owner):
            if directory.is_symlink() or directory.is_junction():
                raise RuntimeError(f"generated-data root ancestor is redirected: {directory}")
            if not directory.exists():
                with suppress(FileExistsError):
                    directory.mkdir()
            if directory.is_symlink() or directory.is_junction() or not directory.is_dir():
                raise NotADirectoryError(
                    f"generated-data root ancestor is not a real directory: {directory}"
                )

        resolved_owner = owner.resolve(strict=True)
        if resolved_owner != owner:
            raise RuntimeError(
                f"generated-data root changed during reservation: {owner} -> {resolved_owner}"
            )
        return resolved_owner
    except (OSError, RuntimeError) as exc:
        raise GeneratedDataReservationError(owner, exc) from exc
