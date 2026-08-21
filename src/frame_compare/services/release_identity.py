"""Typed, presentation-only identities derived from release filenames."""

from collections import Counter
from dataclasses import dataclass
from typing import Literal


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


def format_release_descriptor(identity: ReleaseIdentity) -> str:
    """Format release facts without repeating content identity."""
    source = " ".join(part for part in (identity.service, identity.source_type) if part)
    parts = [identity.resolution, source or None]
    parts.extend((" ".join(identity.dynamic_range_claims) or None,))
    parts.extend(identity.revision_tags)
    parts.extend(identity.variant_tags)
    parts.append(identity.release_group)
    return " | ".join(part for part in parts if part)


def format_compact_identity(identity: ReleaseIdentity) -> str:
    """Format content and release facts in one compact line."""
    return " | ".join(
        part
        for part in (format_content_identity(identity.content), format_release_descriptor(identity))
        if part
    )


def format_micro_descriptor(identity: ReleaseIdentity) -> str:
    """Format the smallest useful release descriptor for constrained surfaces."""
    source = " ".join(part for part in (identity.service, identity.source_type) if part)
    return " | ".join(
        part
        for part in (
            source or None,
            " ".join(identity.dynamic_range_claims) or None,
            *identity.revision_tags,
            identity.release_group,
        )
        if part
    )


def unique_presentation_names(names: list[str], *, roles: list[str]) -> list[str]:
    """Resolve display-only collisions deterministically without changing identities."""
    if len(names) != len(roles):
        raise ValueError("names and roles must have equal lengths")
    counts = Counter(names)
    resolved = [
        f"{roles[index]} | {name}" if counts[name] > 1 else name for index, name in enumerate(names)
    ]
    used: dict[str, int] = {}
    for index, name in enumerate(resolved):
        used[name] = used.get(name, 0) + 1
        if used[name] > 1:
            resolved[index] = f"{name} ({used[name]})"
    return resolved


def common_content_identity(identities: list[ReleaseIdentity]) -> ContentIdentity | None:
    """Return safely shared content identity, or None when content conflicts."""
    if not identities or not any(item.content.title_origin == "parsed" for item in identities):
        return None
    contents = [item.content for item in identities]
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
    "common_content_identity",
    "format_compact_identity",
    "format_content_identity",
    "format_micro_descriptor",
    "format_release_descriptor",
    "unique_presentation_names",
]
