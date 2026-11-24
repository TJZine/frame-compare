"""Durable, low-level cache for successful TMDB lookup responses.

The resolver deliberately owns candidate selection and never persists its final
decision.  This module only stores the ordered response values returned by the
TMDB search and alternative-title endpoints.  Cache keys are opaque hashes of
the request semantics with the API key excluded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal, NotRequired, TypedDict, cast

import structlog
import tomli_w
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidateAs,
    field_validator,
)

from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES

log = structlog.get_logger()

TMDB_CACHE_VERSION = "2"
TMDB_CACHE_MAX_ENTRIES = 2000
TMDB_CACHE_MAX_BYTES = 5 * 1024 * 1024
TMDB_CACHE_POSITIVE_TTL = timedelta(days=30)
TMDB_CACHE_EMPTY_TTL = timedelta(days=1)

type TmdbCacheEntryKind = Literal["search", "alternative_titles"]
type _CacheValue = str | int | float | bool | None
type _StoredValues = tuple[TmdbMetadata, ...] | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _StoredEntry:
    kind: TmdbCacheEntryKind
    stored_at: datetime
    values: _StoredValues


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return _normalise_datetime(value).isoformat().replace("+00:00", "Z")


def _validate_serializable_tmdb_id(value: int) -> int:
    # tomli_w uses str() to serialize integers when merging cached entries.
    str(value)
    return value


class _CachedMetadata(TypedDict):
    tmdb_id: Annotated[StrictInt, AfterValidator(_validate_serializable_tmdb_id)]
    title: StrictStr
    original_title: StrictStr
    year: Annotated[StrictInt, Field(ge=0, le=9999)]
    media_type: Literal["movie", "tv"]
    original_language: NotRequired[StrictStr | None]
    poster_url: NotRequired[StrictStr | None]
    backdrop_url: NotRequired[StrictStr | None]


class _CachedEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stored_at: AwareDatetime

    @field_validator("stored_at", mode="before")
    @classmethod
    def parse_stored_at(cls, value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError("stored_at must be an ISO datetime string")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))


class _CachedSearch(_CachedEntry):
    kind: Literal["search"]
    results: tuple[
        Annotated[TmdbMetadata, ValidateAs(_CachedMetadata, lambda data: TmdbMetadata(**data))],
        ...,
    ]


class _CachedAlternativeTitles(_CachedEntry):
    kind: Literal["alternative_titles"]
    titles: tuple[StrictStr, ...]


_ENTRY_ADAPTER = TypeAdapter(
    Annotated[_CachedSearch | _CachedAlternativeTitles, Field(discriminator="kind")]
)


def _metadata_table(metadata: TmdbMetadata) -> dict[str, object]:
    result: dict[str, object] = {
        "tmdb_id": metadata.tmdb_id,
        "title": metadata.title,
        "original_title": metadata.original_title,
        "year": metadata.year,
        "media_type": metadata.media_type,
    }
    for field in ("original_language", "poster_url", "backdrop_url"):
        value = getattr(metadata, field)
        if value is not None:
            result[field] = value
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def cache_key_for_request(
    kind: TmdbCacheEntryKind,
    endpoint: str,
    params: Mapping[str, _CacheValue],
) -> str:
    """Return an opaque key for one exact request, excluding the API key.

    Search query text is represented by a SHA-256 digest rather than being
    included in either the persisted key or any cache diagnostic.  Parameter
    types and all non-secret values remain part of the identity, so semantically
    different endpoint requests cannot share entries.
    """
    request_params: dict[str, _CacheValue] = {}
    query_hash: str | None = None
    query_present = False
    for name, value in params.items():
        if name.casefold() == "api_key":
            continue
        if name == "query":
            query_present = True
            query_hash = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
            continue
        request_params[name] = value

    identity: dict[str, object] = {
        "kind": kind,
        "endpoint": endpoint,
        "params": request_params,
    }
    if query_present:
        identity["query_sha256"] = query_hash
    serialized = _canonical_json(identity)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _entry_table(entry: _StoredEntry) -> dict[str, object]:
    output: dict[str, object] = {
        "kind": entry.kind,
        "stored_at": _format_datetime(entry.stored_at),
    }
    if entry.kind == "search":
        output["results"] = [
            _metadata_table(item) for item in cast(tuple[TmdbMetadata, ...], entry.values)
        ]
    else:
        output["titles"] = list(cast(tuple[str, ...], entry.values))
    return output


def _serialize_entries(entries: Mapping[str, _StoredEntry]) -> bytes:
    ordered_entries: dict[str, object] = {
        key: _entry_table(entries[key]) for key in sorted(entries)
    }
    return tomli_w.dumps({"version": TMDB_CACHE_VERSION, "entries": ordered_entries}).encode(
        "utf-8"
    )


def _bounded_entries(entries: Mapping[str, _StoredEntry]) -> tuple[dict[str, _StoredEntry], bytes]:
    oldest_first = sorted(
        entries,
        key=lambda key: (_normalise_datetime(entries[key].stored_at), key),
    )
    bounded = dict(entries)
    excess = max(0, len(bounded) - TMDB_CACHE_MAX_ENTRIES)
    for key in oldest_first[:excess]:
        bounded.pop(key)
    oldest_first = oldest_first[excess:]

    while bounded:
        serialized = _serialize_entries(bounded)
        if len(serialized) <= TMDB_CACHE_MAX_BYTES:
            return bounded, serialized
        remove_count = max(1, len(bounded) // 10)
        for key in oldest_first[:remove_count]:
            bounded.pop(key)
        oldest_first = oldest_first[remove_count:]
    return {}, _serialize_entries({})


class TmdbCache:
    """Owner for one shared durable TMDB cache file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._clock = _utc_now
        self._state_lock = Lock()
        self._loaded = False
        self._entries: dict[str, _StoredEntry] | None = None

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.lock")

    def _now(self) -> datetime:
        return _normalise_datetime(self._clock())

    def _load_entries(self) -> dict[str, _StoredEntry] | None:
        try:
            with self.path.open("rb") as handle:
                data = tomllib.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, *SERIALIZED_DECODE_FAILURES):
            log.warning(
                "tmdb_cache_read_failed",
                cache_path=str(self.path),
                error_type="filesystem_or_toml",
                action="network_lookup_without_cache",
            )
            return None

        if data.get("version") != TMDB_CACHE_VERSION:
            log.warning(
                "tmdb_cache_version_mismatch",
                cache_path=str(self.path),
                expected_version=TMDB_CACHE_VERSION,
                action="network_lookup_without_cache",
            )
            return None

        entries_raw = data.get("entries")
        if not isinstance(entries_raw, Mapping):
            log.warning(
                "tmdb_cache_invalid_entries_container",
                cache_path=str(self.path),
                action="network_lookup_without_cache",
            )
            return None

        entries: dict[str, _StoredEntry] = {}
        for key, raw_entry in cast(Mapping[str, object], entries_raw).items():
            if len(key) != 64 or any(digit not in "0123456789abcdef" for digit in key):
                log.warning(
                    "tmdb_cache_invalid_entry",
                    cache_path=str(self.path),
                    entry_key="<invalid>",
                    action="ignore_entry",
                    error_type="invalid_key",
                )
                continue
            try:
                entry = _ENTRY_ADAPTER.validate_python(raw_entry)
                entries[key] = _StoredEntry(
                    kind=entry.kind,
                    stored_at=entry.stored_at.astimezone(UTC),
                    values=entry.results if isinstance(entry, _CachedSearch) else entry.titles,
                )
            except (TypeError, ValueError, OverflowError, RecursionError):
                log.warning(
                    "tmdb_cache_invalid_entry",
                    cache_path=str(self.path),
                    entry_key=key,
                    action="ignore_entry",
                    error_type="malformed_entry",
                )
        return entries

    def _get(
        self, kind: TmdbCacheEntryKind, endpoint: str, params: Mapping[str, _CacheValue]
    ) -> _StoredValues | None:
        key = cache_key_for_request(kind, endpoint, params)
        with self._state_lock:
            if not self._loaded:
                self._entries = self._load_entries()
                self._loaded = True
            entry = None if self._entries is None else self._entries.get(key)
        if entry is None or entry.kind != kind:
            return None
        ttl = TMDB_CACHE_EMPTY_TTL if not entry.values else TMDB_CACHE_POSITIVE_TTL
        age = self._now() - entry.stored_at
        if age < timedelta(0) or age > ttl:
            return None
        return entry.values

    def get_search(
        self,
        endpoint: str,
        params: Mapping[str, _CacheValue],
    ) -> list[TmdbMetadata] | None:
        """Return a fresh cached ordered search response, or ``None`` on miss."""
        values = self._get("search", endpoint, params)
        if values is None:
            return None
        return list(cast(tuple[TmdbMetadata, ...], values))

    def get_alternative_titles(
        self,
        endpoint: str,
        params: Mapping[str, _CacheValue],
    ) -> list[str] | None:
        """Return a fresh cached ordered alternative-title response, or ``None``."""
        values = self._get("alternative_titles", endpoint, params)
        if values is None:
            return None
        return list(cast(tuple[str, ...], values))

    def _store(
        self,
        kind: TmdbCacheEntryKind,
        endpoint: str,
        params: Mapping[str, _CacheValue],
        values: _StoredValues,
    ) -> None:
        key = cache_key_for_request(kind, endpoint, params)
        entry = _StoredEntry(kind=kind, stored_at=self._now(), values=values)
        try:
            with exclusive_file_lock(self.lock_path):
                existing = self._load_entries()
                merged = {} if existing is None else existing
                merged[key] = entry
                bounded, serialized = _bounded_entries(merged)
                write_bytes_atomic(self.path, serialized)
                with self._state_lock:
                    self._entries = bounded
                    self._loaded = True
        except (OSError, TypeError, ValueError):
            log.warning(
                "tmdb_cache_write_failed",
                cache_path=str(self.path),
                entry_key=key,
                action="network_lookup_without_cache",
                error_type="filesystem_or_serialization",
            )

    async def store_search(
        self,
        endpoint: str,
        params: Mapping[str, _CacheValue],
        results: Sequence[TmdbMetadata],
    ) -> None:
        """Store one successful ordered search response off the event loop."""
        await asyncio.to_thread(
            self._store,
            "search",
            endpoint,
            params,
            tuple(results),
        )

    async def store_alternative_titles(
        self,
        endpoint: str,
        params: Mapping[str, _CacheValue],
        titles: Sequence[str],
    ) -> None:
        """Store one successful ordered alternative-title response off the event loop."""
        await asyncio.to_thread(
            self._store,
            "alternative_titles",
            endpoint,
            params,
            tuple(titles),
        )


__all__ = [
    "TmdbCache",
    "cache_key_for_request",
]
