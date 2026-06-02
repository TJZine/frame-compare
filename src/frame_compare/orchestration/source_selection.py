"""Source selector resolution for discovered input clips."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from frame_compare.config.schema_models import SourceOverrideConfig, SourcesConfig
from frame_compare.orchestration.errors import DuplicateSourceStemError, SourceSelectionError

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class SourceSelection:
    """Resolved source ordering and per-path overrides."""

    ordered_paths: list[Path]
    overrides_by_path: dict[Path, SourceOverrideConfig]


def resolve_source_selection(
    *,
    input_dir: Path,
    discovered_paths: list[Path],
    config: SourcesConfig,
) -> SourceSelection:
    """Resolve configured source selectors against discovered inputs."""
    _ensure_unique_stems(discovered_paths)
    if not discovered_paths:
        return SourceSelection(ordered_paths=[], overrides_by_path={})

    reference_path = discovered_paths[0]
    if config.reference is not None:
        reference_path = _resolve_selector(
            selector=config.reference,
            input_dir=input_dir,
            paths=discovered_paths,
            role="sources.reference",
        )

    ordered_paths = [reference_path, *(path for path in discovered_paths if path != reference_path)]
    overrides_by_path: dict[Path, SourceOverrideConfig] = {}
    selectors_by_path: dict[Path, str] = {}
    for selector, override in config.overrides.items():
        path = _resolve_selector(
            selector=selector,
            input_dir=input_dir,
            paths=discovered_paths,
            role="sources.overrides",
        )
        existing = selectors_by_path.get(path)
        if existing is not None:
            raise SourceSelectionError(
                selector=selector,
                reason=f"duplicates override selector {existing!r}",
                role="sources.overrides",
                matches=[path],
            )
        selectors_by_path[path] = selector
        overrides_by_path[path] = override

    return SourceSelection(ordered_paths=ordered_paths, overrides_by_path=overrides_by_path)


def reference_cache_domain_token(override: SourceOverrideConfig | None) -> str | None:
    """Return source override data that affects the reference analysis frame domain."""
    if override is None:
        return None
    if (
        override.trim_start_frames == 0
        and override.trim_end_frames == 0
        and override.effective_fps is None
    ):
        return None
    return (
        f"trim_start={override.trim_start_frames}|"
        f"trim_end={override.trim_end_frames}|"
        f"effective_fps={_format_effective_fps_token(override.effective_fps)}"
    )


def _format_effective_fps_token(effective_fps: Fraction | None) -> str:
    if effective_fps is None:
        return ""
    return f"{effective_fps.numerator}/{effective_fps.denominator}"


def _ensure_unique_stems(paths: list[Path]) -> None:
    by_stem: dict[str, list[Path]] = {}
    for path in paths:
        by_stem.setdefault(path.stem, []).append(path)
    for stem, matches in by_stem.items():
        if len(matches) > 1:
            raise DuplicateSourceStemError(stem=stem, matches=matches)


def _resolve_selector(
    *,
    selector: str,
    input_dir: Path,
    paths: list[Path],
    role: str,
) -> Path:
    normalized = _normalize_selector(selector, role=role)
    for match_type, matches in (
        (
            "relative path",
            [path for path in paths if _relative_path(path, input_dir) == normalized],
        ),
        ("filename", [path for path in paths if path.name == normalized]),
        ("stem", [path for path in paths if path.stem == normalized]),
    ):
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SourceSelectionError(
                selector=selector,
                reason=f"ambiguous {match_type}",
                role=role,
                matches=matches,
            )
    raise SourceSelectionError(selector=selector, reason="no matching source", role=role)


def _normalize_selector(selector: str, *, role: str) -> str:
    if selector == "":
        raise SourceSelectionError(selector=selector, reason="empty selector", role=role)
    if _WINDOWS_DRIVE.match(selector):
        raise SourceSelectionError(selector=selector, reason="absolute path", role=role)

    normalized = selector.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        raise SourceSelectionError(selector=selector, reason="absolute path", role=role)

    segments = normalized.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise SourceSelectionError(
            selector=selector,
            reason="empty, current-directory, or parent-directory path segment",
            role=role,
        )
    return normalized


def _relative_path(path: Path, input_dir: Path) -> str:
    try:
        return path.relative_to(input_dir).as_posix()
    except ValueError:
        return path.name
