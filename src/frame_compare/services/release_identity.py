"""Typed, presentation-only identities derived from release filenames."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from frame_compare.config.text_validation import (
    is_control_character,
    show_bidi_formatting_controls,
)

if TYPE_CHECKING:
    from frame_compare.services.types import TmdbMetadata

_STEM_TOKEN = re.compile(r"[^.\-_ ]+")


@dataclass(frozen=True, slots=True)
class ContentIdentity:
    """Identity of the work being compared, independent of a particular release."""

    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None
    title_origin: Literal["parsed", "fallback"] = "parsed"


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    """Filename-claimed release facts used only for presentation."""

    content: ContentIdentity
    resolution: str | None = None
    service: str | None = None
    source_type: str | None = None
    dynamic_range_claims: tuple[str, ...] = ()
    release_group: str | None = None
    revision_tags: tuple[str, ...] = ()
    variant_tags: tuple[str, ...] = ()
    has_terminal_release_group: bool = False


def format_content_identity(content: ContentIdentity) -> str:
    """Format a stable content label."""
    label = content.title
    if content.year is not None:
        label += f" ({content.year})"
    if content.season is not None and content.episode is not None:
        label += f" S{content.season:02d}E{content.episode:02d}"
    elif content.season is not None:
        label += f" S{content.season:02d}"
    elif content.episode is not None:
        label += f" E{content.episode:02d}"
    return label


def clip_role(index: int) -> str:
    """Return the stable presentation role for an ordered clip."""
    return "Reference" if index == 0 else f"Comparison {index}"


def comparison_title(
    identities: Sequence[ReleaseIdentity | None], metadata: TmdbMetadata | None
) -> str | None:
    """Return the resolved or shared content title, before surface-specific fallbacks."""
    if metadata is not None and metadata.title.strip():
        reference = identities[0] if identities else None
        content = reference.content if reference is not None else None
        return format_content_identity(
            ContentIdentity(
                metadata.title,
                year=(metadata.year or (content.year if content is not None else None))
                if metadata.media_type == "movie"
                else None,
                season=content.season
                if content is not None and metadata.media_type == "tv"
                else None,
                episode=content.episode
                if content is not None and metadata.media_type == "tv"
                else None,
            )
        )
    common = common_content_identity(identities)
    return format_content_identity(common) if common is not None else None


def _usable_release_group(identity: ReleaseIdentity) -> str | None:
    return identity.release_group if identity.has_terminal_release_group else None


def format_release_descriptor(
    identity: ReleaseIdentity, separator: str = " | ", *, short_name: str = ""
) -> str:
    """Format release facts without repeating content identity."""
    source = " ".join(part for part in (identity.service, identity.source_type) if part)
    parts = [identity.resolution, source or None]
    parts.extend((" ".join(identity.dynamic_range_claims) or None,))
    parts.extend(identity.revision_tags)
    parts.extend(identity.variant_tags)
    descriptor = separator.join(part for part in parts if part)
    ending = _usable_release_group(identity) or short_name.replace(" · ", separator)
    if ending and not (descriptor == ending or descriptor.endswith(separator + ending)):
        return separator.join(part for part in (descriptor, ending) if part)
    return descriptor


def format_compact_identity(
    identity: ReleaseIdentity, separator: str = " | ", *, short_name: str = ""
) -> str:
    """Format content and release facts in one compact line."""
    return separator.join(
        part
        for part in (
            format_content_identity(identity.content),
            format_release_descriptor(identity, separator, short_name=short_name),
        )
        if part
    )


def format_micro_descriptor(
    identity: ReleaseIdentity, separator: str = " | ", *, include_group: bool = True
) -> str:
    """Format the smallest useful release descriptor for constrained surfaces."""
    source = " ".join(part for part in (identity.service, identity.source_type) if part)
    return separator.join(
        part
        for part in (
            source or None,
            " ".join(identity.dynamic_range_claims) or None,
            *identity.revision_tags,
            _usable_release_group(identity) if include_group else None,
        )
        if part
    )


def normalize_release_text(value: str) -> str:
    """Normalize filename-derived presentation text."""
    without_controls = "".join(
        " " if is_control_character(character) else character for character in value
    )
    return " ".join(without_controls.split())


@dataclass(frozen=True, slots=True)
class ShortNameSource:
    """Per-source facts needed for a short presentation name."""

    identity: ReleaseIdentity | None
    label: str
    label_is_explicit: bool
    stem: str


def short_source_names(
    sources: Sequence[ShortNameSource],
    *,
    show_bidi_controls: bool = False,
) -> list[str]:
    """Prefer explicit labels, unique usable groups, micro descriptors, then filename text."""
    groups = [
        _usable_release_group(source.identity) if source.identity is not None else None
        for source in sources
    ]
    stems = [normalize_release_text(source.stem) for source in sources]
    tokens = [tuple(_STEM_TOKEN.finditer(stem)) for stem in stems]
    token_values = [tuple(token[0].casefold() for token in matches) for matches in tokens]
    prefix, suffix = _shared_stem_edges(token_values)
    names: list[str] = []
    protected: list[bool] = []
    for index, (source, group) in enumerate(zip(sources, groups, strict=True)):
        label = source.label.strip()
        if source.label_is_explicit and label:
            names.append(source.label)
            protected.append(True)
            continue
        if group and _release_group_is_unique(group, groups):
            names.append(group)
            protected.append(False)
            continue
        micro = (
            format_micro_descriptor(
                source.identity, separator=" · ", include_group=group is not None
            )
            if source.identity is not None
            else ""
        )
        start = prefix
        end = len(tokens[index]) - suffix
        if prefix == suffix == 0 and source.identity is not None:
            start = _verified_title_prefix(source.identity.content, token_values[index])
        differing = (
            stems[index][tokens[index][start].start() : tokens[index][end - 1].end()]
            if start < end
            else ""
        )
        names.append(micro or differing or label)
        protected.append(False)
    roles = [clip_role(index) for index in range(len(sources))]
    if show_bidi_controls:
        names = [show_bidi_formatting_controls(name) for name in names]
    return unique_presentation_names(names, roles=list(roles), protected=protected)


def _shared_stem_edges(token_values: Sequence[tuple[str, ...]]) -> tuple[int, int]:
    if len(token_values) < 2:
        return 0, 0
    prefix = _matching_token_count(token_values)
    suffix = _matching_token_count([tokens[prefix:][::-1] for tokens in token_values])
    return prefix, suffix


def _matching_token_count(token_values: Sequence[tuple[str, ...]]) -> int:
    for index, aligned in enumerate(zip(*token_values, strict=False)):
        if len(set(aligned)) > 1:
            return index
    return min(map(len, token_values))


def _verified_title_prefix(content: ContentIdentity, tokens: tuple[str, ...]) -> int:
    if content.title_origin == "parsed":
        title = tuple(token.casefold() for token in _STEM_TOKEN.findall(content.title))
        if len(title) < len(tokens) and tokens[: len(title)] == title:
            return len(title)
    return 0


def _release_group_is_unique(group: str, groups: Sequence[str | None]) -> bool:
    """Return whether no other source claims the same release group."""
    folded = group.casefold()
    return sum(1 for other in groups if other is not None and other.casefold() == folded) == 1


def unique_presentation_names(
    names: list[str],
    *,
    roles: list[str],
    protected: list[bool] | None = None,
    collision_key: Callable[[str], str] = str,
) -> list[str]:
    """Resolve display-only collisions deterministically without changing identities."""
    if len(names) != len(roles):
        raise ValueError("names and roles must have equal lengths")
    protected = [False] * len(names) if protected is None else protected
    if len(names) != len(protected):
        raise ValueError("names and protected must have equal lengths")
    counts = Counter(collision_key(name) for name in names)
    resolved = [
        f"{roles[index]} | {name}"
        if counts[collision_key(name)] > 1 and not protected[index]
        else name
        for index, name in enumerate(names)
    ]
    used = {collision_key(name) for index, name in enumerate(resolved) if protected[index]}
    for index, name in enumerate(resolved):
        if protected[index]:
            continue
        suffix = 2
        while collision_key(resolved[index]) in used:
            resolved[index] = f"{name} ({suffix})"
            suffix += 1
        used.add(collision_key(resolved[index]))
    return resolved


def common_content_identity(identities: Sequence[ReleaseIdentity | None]) -> ContentIdentity | None:
    """Return safely shared content identity, or None when content conflicts."""
    contents = [item.content for item in identities if item is not None]
    if len(contents) != len(identities) or not any(
        content.title_origin == "parsed" for content in contents
    ):
        return None
    if len({" ".join(item.title.casefold().split()) for item in contents}) != 1:
        return None
    for field in ("year", "season", "episode"):
        values = {getattr(item, field) for item in contents if getattr(item, field) is not None}
        if len(values) > 1:
            return None
    return ContentIdentity(
        title=contents[0].title,
        year=_shared_value(contents, "year"),
        season=_shared_value(contents, "season"),
        episode=_shared_value(contents, "episode"),
        title_origin="parsed",
    )


def _shared_value(
    contents: list[ContentIdentity], field: Literal["year", "season", "episode"]
) -> int | None:
    return next((value for item in contents if (value := getattr(item, field)) is not None), None)


__all__ = [
    "ContentIdentity",
    "ReleaseIdentity",
    "ShortNameSource",
    "common_content_identity",
    "format_compact_identity",
    "format_content_identity",
    "format_micro_descriptor",
    "format_release_descriptor",
    "clip_role",
    "comparison_title",
    "short_source_names",
    "unique_presentation_names",
]
