"""Preflight validation for Frame Compare.

This module handles pre-run validation including configuration loading,
workspace path resolution, and input verification.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.config.loader import load_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import PathEscapesRootError
from frame_compare.orchestration.errors import (
    DirectoryNotFoundError,
    InputDiscoveryError,
    NoVideosFoundError,
)
from frame_compare.utils.types import WorkspacePaths

# Canonical video patterns
_VIDEO_PATTERNS: list[str] = ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """Result of preflight validation."""

    config: ConfigSchema
    workspace: WorkspacePaths
    warnings: list[str] = field(default_factory=lambda: [])


def resolve_workspace(root: Path | None) -> Path:
    """Resolve workspace root directory."""
    # Priority 1: explicit root
    if root is not None:
        return root.resolve()

    cwd = Path.cwd()
    sentinel = Path("config") / "config.toml"

    # Priority 2: CWD if sentinel exists
    if (cwd / sentinel).exists():
        return cwd

    # Priority 3: search upward
    current = cwd
    while current != current.parent:
        if (current / sentinel).exists():
            return current
        current = current.parent

    # Priority 4: fallback to CWD
    return cwd


def _resolve_path(path_str: str, root: Path) -> Path:
    """Expand env vars and resolve relative to root."""
    expanded = os.path.expandvars(path_str)
    path = Path(expanded)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def resolve_contained_path(path_value: str | Path, root: Path) -> Path:
    """Resolve a path and require its final target to remain under ``root``."""
    resolved_root = root.resolve()
    expanded = os.path.expandvars(str(path_value))
    candidate = Path(expanded)
    resolved_path = (
        candidate.resolve() if candidate.is_absolute() else (resolved_root / candidate).resolve()
    )
    if not resolved_path.is_relative_to(resolved_root):
        raise PathEscapesRootError(resolved_path, resolved_root)
    return resolved_path


def _windows_portable_state_config_path() -> Path | None:
    """Return the installed Windows shim's sole external config destination."""
    if os.name != "nt":
        return None
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    state_dir = (Path(local_app_data) / "Programs" / "FrameCompare" / "state").resolve()
    return state_dir / "config.toml"


def resolve_selected_config_path(path_value: str | Path, root: Path) -> Path:
    """Resolve a selected config, including the one Windows portable exception."""
    resolved_root = root.resolve()
    expanded = os.path.expandvars(str(path_value))
    candidate = Path(expanded)
    resolved_path = (
        candidate.resolve() if candidate.is_absolute() else (resolved_root / candidate).resolve()
    )
    if resolved_path.is_relative_to(resolved_root):
        return resolved_path

    portable_state_config = _windows_portable_state_config_path()
    if portable_state_config is not None and resolved_path == portable_state_config:
        return resolved_path
    raise PathEscapesRootError(resolved_path, resolved_root)


def validate_and_normalize_config_paths(
    config: ConfigSchema,
    root: Path,
) -> ConfigSchema:
    """Validate contained config paths without mutating the supplied config."""
    resolved_root = root.resolve()
    resolve_contained_path(config.paths.config_dir, resolved_root)
    resolve_contained_path(config.paths.screenshots_dir, resolved_root)
    resolve_contained_path(config.paths.generated_dir, resolved_root)

    if config.report.output_dir is None:
        return config

    output_dir = resolve_contained_path(config.report.output_dir, resolved_root)
    return config.model_copy(
        update={"report": config.report.model_copy(update={"output_dir": str(output_dir)})}
    )


def resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths:
    """Resolve all workspace paths from config."""
    resolved_root = root.resolve()
    validated_config = validate_and_normalize_config_paths(config, resolved_root)
    paths = validated_config.paths
    config_dir = resolve_contained_path(paths.config_dir, resolved_root)
    generated_dir = resolve_contained_path(paths.generated_dir, resolved_root)

    return WorkspacePaths(
        root=resolved_root,
        input_dir=_resolve_path(paths.input_dir, resolved_root),
        run_dir=None,  # Legacy mode: run folder disabled
        screenshots_dir=resolve_contained_path(paths.screenshots_dir, resolved_root),
        generated_dir=generated_dir,
        config_dir=config_dir,
        config_file=config_dir / "config.toml",
        analysis_cache_dir=generated_dir / "cache" / "analysis",
        alignment_cache_dir=generated_dir / "cache" / "alignment",
    )


def _resolve_paths_with_config_file(
    config: ConfigSchema, root: Path, config_file: Path
) -> WorkspacePaths:
    """Internal: Resolve paths with explicit config_file (for prepare_preflight)."""
    resolved_root = root.resolve()
    validated_config = validate_and_normalize_config_paths(config, resolved_root)
    paths = validated_config.paths
    generated_dir = resolve_contained_path(paths.generated_dir, resolved_root)

    return WorkspacePaths(
        root=resolved_root,
        input_dir=_resolve_path(paths.input_dir, resolved_root),
        run_dir=None,  # Legacy mode: run folder disabled
        screenshots_dir=resolve_contained_path(paths.screenshots_dir, resolved_root),
        generated_dir=generated_dir,
        config_dir=resolve_contained_path(paths.config_dir, resolved_root),
        config_file=config_file,
        analysis_cache_dir=generated_dir / "cache" / "analysis",
        alignment_cache_dir=generated_dir / "cache" / "alignment",
    )


def discover_inputs(input_dir: Path, patterns: list[str] | None = None) -> list[Path]:
    """Discover video files in input directory."""
    effective_patterns = _VIDEO_PATTERNS if patterns is None else patterns
    normalized_patterns = [pattern.lower() for pattern in effective_patterns]
    recursive = any("/" in pattern or "**" in pattern for pattern in effective_patterns)

    try:
        candidates = input_dir.rglob("*") if recursive else input_dir.iterdir()
        videos: list[Path] = []
        for path in candidates:
            try:
                if not path.is_file():
                    continue
                if recursive:
                    candidate = path.relative_to(input_dir).as_posix().lower()
                else:
                    candidate = path.name.lower()
                if any(fnmatch.fnmatch(candidate, pattern) for pattern in normalized_patterns):
                    videos.append(path)
            except OSError as exc:
                raise InputDiscoveryError(input_dir, exc) from exc
    except OSError as exc:
        raise InputDiscoveryError(input_dir, exc) from exc

    # Stable ordering: case-insensitive lexicographic sort by filename
    ordered = sorted(videos, key=lambda p: p.name.lower())
    if not ordered:
        raise NoVideosFoundError(input_dir.resolve(), patterns=effective_patterns)
    return ordered


def prepare_preflight(
    root: Path | None = None,
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> PreflightResult:
    """Validate configuration and resolve workspace paths."""
    warnings: list[str] = []

    if config_path is not None:
        expanded_config_path = Path(os.path.expandvars(str(config_path)))
        if root is not None and not expanded_config_path.is_absolute():
            config_candidate = root.resolve() / expanded_config_path
        else:
            config_candidate = expanded_config_path
        resolved_candidate = config_candidate.resolve()
        resolved_root = root.resolve() if root else resolved_candidate.parent.parent
        resolved_config_path = resolve_selected_config_path(resolved_candidate, resolved_root)
        if not resolved_config_path.exists():
            raise ConfigNotFoundError(resolved_config_path)
    else:
        resolved_root = resolve_workspace(root)
        resolved_config_path = resolve_selected_config_path(
            resolved_root / "config" / "config.toml",
            resolved_root,
        )
        if not resolved_config_path.exists():
            raise ConfigNotFoundError(resolved_config_path)

    loaded_config = load_config(resolved_config_path, overrides=overrides)
    config = validate_and_normalize_config_paths(loaded_config, resolved_root)

    workspace = _resolve_paths_with_config_file(config, resolved_root, resolved_config_path)

    if not workspace.input_dir.exists():
        raise DirectoryNotFoundError(workspace.input_dir)

    discover_inputs(workspace.input_dir)

    return PreflightResult(
        config=config,
        workspace=workspace,
        warnings=warnings,
    )
