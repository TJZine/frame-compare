"""Probe snapshot cache keying logic and I/O."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import isfinite
from pathlib import Path
from typing import Annotated, Any, Self

import structlog
import tomli_w
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.utils.atomic_write import write_bytes_atomic
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES
from frame_compare.vs.errors import SourceLoadError
from frame_compare.vs.props import parse_mastering_display_luminance
from frame_compare.vs.runtime_contract import media_runtime_fingerprint
from frame_compare.vs.source_admission import SourceAdmission, admit_source, source_identity
from frame_compare.vs.types import HDRMetadata

log = structlog.get_logger()

_CACHE_VERSION = "1"
_SOURCE_TOKEN_PATTERN = re.compile(r"\A[0-9a-fA-F]{64}\Z")

# Preview looks up each canonical property before its alias.
_PREVIEW_DECIMAL_PROP_KEYS = (
    ("_Matrix", "Matrix"),
    ("_Transfer", "Transfer"),
    ("_Primaries", "Primaries"),
    ("_Range",),
)

# R81's VSVideoInfo stores width, height and numFrames as signed 32-bit fields,
# and fpsNum/fpsDen as signed 64-bit fields.
type _Int64 = Annotated[StrictInt, Field(ge=-(2**63), le=2**63 - 1)]
type _PositiveInt32 = Annotated[StrictInt, Field(ge=1, le=2**31 - 1)]
type _PositiveInt64 = Annotated[StrictInt, Field(ge=1, le=2**63 - 1)]
type _HDRLightLevel = Annotated[StrictInt, Field(ge=0, le=2**31 - 1)]
type _FiniteFloat = Annotated[StrictFloat, Field(allow_inf_nan=False)]


def _reject_int_as_float(value: object) -> object:
    # StrictFloat accepts ints, even one rejected by the bounded integer branch.
    if isinstance(value, int):
        raise ValueError("Integer frame props must fit signed int64")
    return value


type _FramePropFloat = Annotated[_FiniteFloat, BeforeValidator(_reject_int_as_float)]


@dataclass(frozen=True)
class LiveProbeFingerprint:
    fingerprint: ClipFingerprint
    admission: SourceAdmission


def live_probe_fingerprint(path: Path) -> LiveProbeFingerprint:
    """Bind reusable probe facts to admitted source and probe runtime identities."""
    try:
        resolved = path.resolve(strict=True)
        admission = admit_source(resolved, abort_check=raise_if_cancelling)
        token = None
        try:
            identity = source_identity(resolved)
        except OSError:
            # An admitted private source remains usable without persisted authority.
            identity = None
        if identity is not None and admission.geometry_probe_token is not None:
            payload = (asdict(identity), admission.geometry_probe_token)
            token = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
            ).hexdigest()
        return LiveProbeFingerprint(
            ClipFingerprint(resolved, admission.stamp.size, admission.stamp.mtime_ns, token),
            admission,
        )
    except (OSError, ValueError, FFmpegError, FFmpegNotFoundError) as error:
        raise SourceLoadError(path, str(error)) from error


class _ProbeCacheReadError(Exception):
    """Signal that a shared update must abort after a cache read failure."""


class _StoredHDRMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mastering_display: StrictStr | None = None
    max_cll: _HDRLightLevel | None = None
    max_fall: _HDRLightLevel | None = None
    color_primaries: _Int64
    transfer: _Int64
    matrix: _Int64

    @field_validator("mastering_display")
    @classmethod
    def validate_mastering_display(cls, value: str | None) -> str | None:
        luminance = parse_mastering_display_luminance(value)
        if any(nits is not None and not isfinite(nits) for nits in luminance):
            raise ValueError("Mastering display luminance must be finite")
        return value

    def to_metadata(self) -> HDRMetadata:
        return HDRMetadata(
            mastering_display=self.mastering_display,
            max_cll=self.max_cll,
            max_fall=self.max_fall,
            color_primaries=self.color_primaries,
            transfer=self.transfer,
            matrix=self.matrix,
        )


class _StoredProbeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: StrictStr
    source_token: Annotated[StrictStr, Field(pattern=_SOURCE_TOKEN_PATTERN)]
    size_bytes: Annotated[StrictInt, Field(ge=0, le=2**63 - 1)]
    mtime_ns: _Int64
    width: _PositiveInt32
    height: _PositiveInt32
    num_frames: _PositiveInt32
    fps_num: _PositiveInt64
    fps_den: _PositiveInt64
    is_hdr: StrictBool
    hdr_metadata: _StoredHDRMetadata | None = None
    preserved_frame_props: dict[str, StrictStr | _Int64 | _FramePropFloat] = Field(
        default_factory=dict
    )

    @field_validator("preserved_frame_props")
    @classmethod
    def validate_preview_decimal_props(
        cls, props: dict[str, str | int | float]
    ) -> dict[str, str | int | float]:
        for keys in _PREVIEW_DECIMAL_PROP_KEYS:
            value = next((props[key] for key in keys if key in props), None)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.isdecimal():
                    int(stripped)
        return props

    @model_validator(mode="after")
    def require_hdr_metadata(self) -> Self:
        if self.is_hdr and self.hdr_metadata is None:
            raise ValueError("HDR entries require hdr_metadata")
        return self

    def to_snapshot(self) -> ClipProbeSnapshot:
        hdr_metadata = (
            self.hdr_metadata.to_metadata()
            if self.is_hdr and self.hdr_metadata is not None
            else None
        )
        return ClipProbeSnapshot(
            fingerprint=ClipFingerprint(
                path=Path(self.path),
                size_bytes=self.size_bytes,
                mtime_ns=self.mtime_ns,
                source_token=self.source_token,
            ),
            width=self.width,
            height=self.height,
            num_frames=self.num_frames,
            fps=Fraction(self.fps_num, self.fps_den),
            is_hdr=self.is_hdr,
            hdr_metadata=hdr_metadata,
            preserved_frame_props=self.preserved_frame_props,
        )


def compute_probe_cache_key(fingerprint: ClipFingerprint) -> str:
    """Return a stable key for clip probe cache entries.

    The key binds the strong source/probe token, path, size, mtime, probe-key
    schema, and supported decoder runtime identity. It is
    independent of trim state and intentionally does not hash media contents.

    Serialization uses canonical JSON settings (sorted keys, no spaces)
    to ensure cross-platform determinism.
    """
    payload: dict[str, Any] = {
        "path": str(fingerprint.path),
        "size_bytes": fingerprint.size_bytes,
        "mtime_ns": fingerprint.mtime_ns,
        "schema_version": 4,
        "source_token": fingerprint.source_token,
        "media_runtime_fingerprint": media_runtime_fingerprint("probe"),
    }

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return hashlib.blake2s(serialized.encode("utf-8")).hexdigest()


def _load_clip_probe_cache(
    cache_path: Path, *, abort_on_read_error: bool
) -> dict[str, ClipProbeSnapshot]:
    try:
        with cache_path.open("rb") as f:
            data: dict[str, object] = tomllib.load(f)
    except FileNotFoundError:
        return {}
    except OSError as e:
        log.warning("probe_cache_read_error", path=str(cache_path), error=type(e).__name__)
        if abort_on_read_error:
            raise _ProbeCacheReadError from e
        return {}
    except SERIALIZED_DECODE_FAILURES:
        log.warning("probe_cache_parse_error", path=str(cache_path))
        return {}

    if data.get("version") != _CACHE_VERSION:
        log.warning("probe_cache_version_mismatch", path=str(cache_path))
        return {}

    snapshots: dict[str, ClipProbeSnapshot] = {}

    for key, entry_raw in data.items():
        if key == "version":
            continue

        try:
            snapshot = _StoredProbeEntry.model_validate(entry_raw).to_snapshot()
            expected_key = compute_probe_cache_key(snapshot.fingerprint)
        except Exception as error:
            log.warning(
                "probe_cache_invalid_entry", path=str(cache_path), error=type(error).__name__
            )
            continue

        if key != expected_key:
            log.warning(
                "probe_cache_invalid_entry",
                path=str(cache_path),
                error="entry key does not match persisted fingerprint",
            )
            continue

        snapshots[key] = snapshot

    return snapshots


def load_clip_probe_cache(cache_path: Path) -> dict[str, ClipProbeSnapshot]:
    """Load probe cache from TOML file.

    Returns empty dict on missing file, parse error, or version mismatch (warn-only).
    Skips invalid entries (warn-only).
    """
    return _load_clip_probe_cache(cache_path, abort_on_read_error=False)


def save_clip_probe_cache(
    cache_path: Path, entries_by_key: Mapping[str, ClipProbeSnapshot]
) -> None:
    """Save probe cache to TOML file in stable key order (overwrites)."""
    output: dict[str, Any] = {"version": _CACHE_VERSION}

    for key in sorted(entries_by_key.keys()):
        snapshot = entries_by_key[key]
        fp = snapshot.fingerprint
        if fp.source_token is None or _SOURCE_TOKEN_PATTERN.fullmatch(fp.source_token) is None:
            continue

        if snapshot.is_hdr and snapshot.hdr_metadata is None:
            raise ValueError(f"Snapshot {key} is_hdr=True but hdr_metadata is None")

        entry: dict[str, Any] = {
            "path": str(fp.path),
            "source_token": fp.source_token,
            "size_bytes": fp.size_bytes,
            "mtime_ns": fp.mtime_ns,
            "width": snapshot.width,
            "height": snapshot.height,
            "num_frames": snapshot.num_frames,
            "fps_num": snapshot.fps.numerator,
            "fps_den": snapshot.fps.denominator,
            "is_hdr": snapshot.is_hdr,
            "preserved_frame_props": snapshot.preserved_frame_props,
        }

        # TOML doesn't support None values, so we only include non-None fields
        if snapshot.is_hdr and snapshot.hdr_metadata:
            md = snapshot.hdr_metadata
            hdr_dict: dict[str, Any] = {
                "color_primaries": md.color_primaries,
                "transfer": md.transfer,
                "matrix": md.matrix,
            }
            if md.mastering_display is not None:
                hdr_dict["mastering_display"] = md.mastering_display
            if md.max_cll is not None:
                hdr_dict["max_cll"] = md.max_cll
            if md.max_fall is not None:
                hdr_dict["max_fall"] = md.max_fall
            entry["hdr_metadata"] = hdr_dict

        output[key] = entry

    try:
        content = tomli_w.dumps(output).encode("utf-8")
        write_bytes_atomic(cache_path, content, publish_guard=raise_if_cancelling)
    except OSError as error:
        log.warning("probe_cache_write_error", path=str(cache_path), error=type(error).__name__)


def merge_shared_clip_probe_cache(
    cache_path: Path, current_entries: Mapping[str, ClipProbeSnapshot]
) -> None:
    """Merge current entries into a shared cache under one locked transaction."""
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    try:
        with exclusive_file_lock(lock_path, abort_check=raise_if_cancelling):
            entries_by_key = _load_clip_probe_cache(cache_path, abort_on_read_error=True)
            entries_by_key.update(current_entries)
            save_clip_probe_cache(cache_path, entries_by_key)
    except _ProbeCacheReadError:
        return
    except OSError as e:
        log.warning("probe_cache_write_error", path=str(cache_path), error=type(e).__name__)
