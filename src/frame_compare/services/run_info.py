"""Root-level run identity persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict

import tomli_w

from frame_compare import __version__
from frame_compare.services.run_folder import RunFolderNamingSource
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.vs.runtime_contract import MediaRuntimeReport, supported_media_runtime_report

type RunInfoTmdbSkipReason = Literal["disabled", "skip_metadata", "no_http_client"]

# run_info.toml is a write-only provenance artifact. Version 1 predates the
# coordinated media-runtime identity and is intentionally unsupported rather
# than migrated or interpreted as current evidence.
RUN_INFO_SCHEMA_VERSION: Final = 2


class RunInfoTmdbPayload(TypedDict):
    enabled: bool
    attempted: bool
    resolved: bool
    failed: bool
    skip_reason: NotRequired[RunInfoTmdbSkipReason]
    error_type: NotRequired[str]
    tmdb_id: NotRequired[int]
    title: NotRequired[str]
    year: NotRequired[int]
    media_type: NotRequired[Literal["movie", "tv"]]


class RunInfoPayload(TypedDict):
    version: int
    created_at: str
    folder_name: str
    naming_source: RunFolderNamingSource
    source_filenames: list[str]
    frame_compare_version: str
    media_runtime: MediaRuntimeReport
    tmdb: NotRequired[RunInfoTmdbPayload]


@dataclass(frozen=True, slots=True)
class RunInfoTmdbPrefetchFacts:
    enabled: bool
    attempted: bool
    resolved: bool
    failed: bool
    skipped_reason: RunInfoTmdbSkipReason | None = None
    error_type: str | None = None
    tmdb_id: int | None = None
    title: str | None = None
    year: int | None = None
    media_type: Literal["movie", "tv"] | None = None


@dataclass(frozen=True, slots=True)
class RunInfo:
    created_at: datetime
    folder_name: str
    naming_source: RunFolderNamingSource
    source_filenames: list[str]
    tmdb: RunInfoTmdbPrefetchFacts | None = None
    frame_compare_version: str = __version__
    version: int = RUN_INFO_SCHEMA_VERSION


def _format_created_at(created_at: datetime) -> str:
    utc_created_at = created_at
    if utc_created_at.tzinfo is None:
        utc_created_at = utc_created_at.replace(tzinfo=UTC)
    else:
        utc_created_at = utc_created_at.astimezone(UTC)
    return utc_created_at.isoformat(timespec="seconds").replace("+00:00", "Z")


def _tmdb_table(facts: RunInfoTmdbPrefetchFacts) -> RunInfoTmdbPayload:
    table: RunInfoTmdbPayload = {
        "enabled": facts.enabled,
        "attempted": facts.attempted,
        "resolved": facts.resolved,
        "failed": facts.failed,
    }
    if facts.skipped_reason is not None:
        table["skip_reason"] = facts.skipped_reason
    if facts.error_type is not None:
        table["error_type"] = facts.error_type
    if facts.tmdb_id is not None:
        table["tmdb_id"] = facts.tmdb_id
    if facts.title is not None:
        table["title"] = facts.title
    if facts.year is not None:
        table["year"] = facts.year
    if facts.media_type is not None:
        table["media_type"] = facts.media_type
    return table


def serialize_run_info(info: RunInfo) -> str:
    """Serialize run identity as deterministic TOML without null placeholders."""
    payload: RunInfoPayload = {
        "version": info.version,
        "created_at": _format_created_at(info.created_at),
        "folder_name": info.folder_name,
        "naming_source": info.naming_source,
        "source_filenames": info.source_filenames,
        "frame_compare_version": info.frame_compare_version,
        "media_runtime": supported_media_runtime_report(),
    }
    if info.tmdb is not None:
        payload["tmdb"] = _tmdb_table(info.tmdb)
    return tomli_w.dumps(payload)


def write_run_info(path: Path, info: RunInfo) -> None:
    """Atomically write run_info.toml."""
    write_text_atomic(path, serialize_run_info(info), encoding="utf-8")
