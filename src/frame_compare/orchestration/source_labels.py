"""Pre-probe source display-label resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.config.text_validation import is_control_character
from frame_compare.orchestration.errors import SourceSelectionError
from frame_compare.services.metadata_parsing import parse_filename
from frame_compare.services.release_identity import ReleaseIdentity
from frame_compare.services.types import ParsedMetadata

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class _LabelCandidate:
    path: Path
    label: str
    explicit: bool
    source_index: int


@dataclass(frozen=True, slots=True)
class ResolvedSourceLabel:
    """Canonical label plus the explicit-label provenance needed by presentation."""

    value: str
    explicit: bool


def resolve_source_labels(
    *,
    ordered_paths: list[Path],
    overrides_by_path: dict[Path, SourceOverrideConfig],
    label_mode: Literal["stem", "filename", "parsed"],
    label_parser: Literal["auto", "guessit", "anitopy"],
    release_identities_by_path: dict[Path, ReleaseIdentity] | None = None,
) -> dict[Path, str]:
    """Resolve unique presentation labels without changing source identity."""
    return {
        path: label.value
        for path, label in resolve_source_label_details(
            ordered_paths=ordered_paths,
            overrides_by_path=overrides_by_path,
            label_mode=label_mode,
            label_parser=label_parser,
            release_identities_by_path=release_identities_by_path,
        ).items()
    }


def resolve_source_label_details(
    *,
    ordered_paths: list[Path],
    overrides_by_path: dict[Path, SourceOverrideConfig],
    label_mode: Literal["stem", "filename", "parsed"],
    label_parser: Literal["auto", "guessit", "anitopy"],
    release_identities_by_path: dict[Path, ReleaseIdentity] | None = None,
) -> dict[Path, ResolvedSourceLabel]:
    """Resolve canonical labels while retaining explicit-label provenance."""
    candidates = [
        _label_candidate(
            path=path,
            override=overrides_by_path.get(path),
            label_mode=label_mode,
            label_parser=label_parser,
            source_index=index,
            release_identity=(release_identities_by_path or {}).get(path),
        )
        for index, path in enumerate(ordered_paths)
    ]
    _reject_duplicate_explicit_labels(candidates)

    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.label] = counts.get(candidate.label, 0) + 1

    qualified = [
        _qualify_derived_collision(candidate)
        if not candidate.explicit and counts[candidate.label] > 1
        else candidate
        for candidate in candidates
    ]

    resolved: dict[Path, ResolvedSourceLabel] = {}
    used = {candidate.label for candidate in qualified if candidate.explicit}
    for candidate in qualified:
        if candidate.explicit:
            resolved[candidate.path] = ResolvedSourceLabel(candidate.label, True)
            continue
        label = candidate.label
        if label in used:
            base = label
            suffix = candidate.source_index + 1
            label = f"{base} ({suffix})"
            while label in used:
                suffix += 1
                label = f"{base} ({suffix})"
        used.add(label)
        resolved[candidate.path] = ResolvedSourceLabel(label, False)
    return resolved


def normalize_derived_display_text(value: str, *, fallback: str = "comparison") -> str:
    """Replace unsafe runtime control text and collapse whitespace."""
    without_controls = "".join(
        " " if is_control_character(character) else character for character in value
    )
    normalized = _WHITESPACE_RE.sub(" ", without_controls).strip()
    return normalized or fallback


def _label_candidate(
    *,
    path: Path,
    override: SourceOverrideConfig | None,
    label_mode: Literal["stem", "filename", "parsed"],
    label_parser: Literal["auto", "guessit", "anitopy"],
    source_index: int,
    release_identity: ReleaseIdentity | None,
) -> _LabelCandidate:
    if override is not None and override.label is not None:
        return _LabelCandidate(path, override.label, True, source_index)
    if label_mode == "filename":
        label = normalize_derived_display_text(path.name)
    elif label_mode == "parsed":
        parsed = (
            ParsedMetadata(
                title=release_identity.content.title,
                year=release_identity.content.year,
                season=release_identity.content.season,
                episode=release_identity.content.episode,
                episode_title=release_identity.content.episode_title,
                release_group=release_identity.release_group,
                source=release_identity.source_type,
                resolution=release_identity.resolution,
            )
            if release_identity is not None
            else parse_filename(
                path.name,
                parser_priority=label_parser,
                alternate_policy="fallback",
            )
        )
        label = _parsed_label(parsed, fallback=path.stem)
    else:
        label = normalize_derived_display_text(path.stem)
    return _LabelCandidate(path, label, False, source_index)


def _parsed_label(parsed: ParsedMetadata, *, fallback: str) -> str:
    parts: list[str] = []
    if parsed.release_group:
        release_group = normalize_derived_display_text(parsed.release_group, fallback="")
        if release_group:
            parts.append(f"[{release_group}]")
    if parsed.title:
        parts.append(normalize_derived_display_text(parsed.title))
    marker = _episode_marker(parsed)
    if marker:
        parts.append(marker)
    label = " ".join(parts)
    if parsed.episode_title:
        episode_title = normalize_derived_display_text(parsed.episode_title, fallback="")
        if episode_title:
            label = f"{label} – {episode_title}" if label else episode_title
    return normalize_derived_display_text(label, fallback=normalize_derived_display_text(fallback))


def _episode_marker(parsed: ParsedMetadata) -> str:
    if parsed.season is not None and parsed.episode is not None:
        return f"S{parsed.season:02d}E{parsed.episode:02d}"
    if parsed.season is not None:
        return f"S{parsed.season:02d}"
    if parsed.episode is not None:
        return f"E{parsed.episode:02d}"
    return ""


def _reject_duplicate_explicit_labels(candidates: list[_LabelCandidate]) -> None:
    paths_by_label: dict[str, list[Path]] = {}
    for candidate in candidates:
        if candidate.explicit:
            paths_by_label.setdefault(candidate.label, []).append(candidate.path)
    for label, paths in paths_by_label.items():
        if len(paths) > 1:
            raise SourceSelectionError(
                selector=label,
                reason="duplicate explicit source label",
                role="sources.overrides",
                matches=paths,
            )


def _qualify_derived_collision(candidate: _LabelCandidate) -> _LabelCandidate:
    stem = normalize_derived_display_text(candidate.path.stem)
    return _LabelCandidate(
        candidate.path,
        f"{candidate.label} [{stem}]",
        False,
        candidate.source_index,
    )


__all__ = [
    "ResolvedSourceLabel",
    "normalize_derived_display_text",
    "resolve_source_label_details",
    "resolve_source_labels",
]
