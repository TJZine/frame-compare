"""Metadata parsing and override helper utilities shared by the runner and CLI."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Mapping, MutableSequence, Optional, Sequence, TypeVar

from src.datatypes import NamingConfig
from src.utils import parse_filename_metadata

OverrideValue = TypeVar("OverrideValue")

_VERSION_PATTERN = re.compile(r"(?:^|[^0-9A-Za-z])(?P<tag>v\d{1,3})(?!\d)", re.IGNORECASE)


def parse_metadata(files: Sequence[Path], naming_cfg: NamingConfig) -> list[dict[str, str]]:
    """
    Extract naming metadata for each clip using the configured heuristics.

    The helper mirrors the legacy `_parse_metadata` behavior but now lives in a
    standalone module so the runner and CLI can share the logic outside of
    ``src.frame_compare.core``.
    """

    metadata: list[dict[str, str]] = []
    for file in files:
        info = parse_filename_metadata(
            file.name,
            prefer_guessit=naming_cfg.prefer_guessit,
            always_full_filename=naming_cfg.always_full_filename,
        )
        metadata.append(info)
    dedupe_labels(metadata, files, naming_cfg.always_full_filename)
    return metadata


def dedupe_labels(
    metadata: MutableSequence[dict[str, str]],
    files: Sequence[Path],
    prefer_full_name: bool,
) -> None:
    """Guarantee unique metadata labels by appending version hints when required."""

    counts = Counter((meta.get("label") or "") for meta in metadata)
    duplicate_groups: dict[str, list[int]] = defaultdict(list)
    for idx, meta in enumerate(metadata):
        label = meta.get("label") or ""
        if not label:
            metadata[idx]["label"] = files[idx].name
            continue
        if counts[label] > 1:
            duplicate_groups[label].append(idx)

    if prefer_full_name:
        for indices in duplicate_groups.values():
            for idx in indices:
                metadata[idx]["label"] = files[idx].name
        return

    for label, indices in duplicate_groups.items():
        for idx in indices:
            version = _extract_version_suffix(files[idx])
            if version:
                metadata[idx]["label"] = f"{label} {version}".strip()

        temp_counts = Counter(metadata[idx].get("label") or "" for idx in indices)
        for idx in indices:
            resolved = metadata[idx].get("label") or label
            if temp_counts[resolved] <= 1:
                continue
            order = indices.index(idx) + 1
            metadata[idx]["label"] = f"{label} #{order}"


def _extract_version_suffix(file_path: Path) -> str | None:
    """Return a version suffix (for example ``v2``) from *file_path* stem."""

    match = _VERSION_PATTERN.search(file_path.stem)
    if not match:
        return None
    tag = match.group("tag")
    return tag.upper() if tag else None


def normalise_override_mapping(raw: Mapping[str, OverrideValue]) -> Dict[str, OverrideValue]:
    """Lowercase override keys and drop empty entries."""

    normalised: Dict[str, OverrideValue] = {}
    for key, value in raw.items():
        key_str = str(key).strip().lower()
        if key_str:
            normalised[key_str] = value
    return normalised


def match_override(
    index: int,
    file: Path,
    metadata: Mapping[str, str],
    mapping: Mapping[str, OverrideValue],
) -> Optional[OverrideValue]:
    """Return the override value matching *index*, filenames, or metadata labels."""

    candidates = [
        str(index),
        file.name,
        file.stem,
        metadata.get("release_group", ""),
        metadata.get("file_name", ""),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        value = mapping.get(candidate.lower())
        if value is not None:
            return value
    return None


__all__ = [
    "OverrideValue",
    "parse_metadata",
    "dedupe_labels",
    "normalise_override_mapping",
    "match_override",
]
