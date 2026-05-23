"""Preflight validation for Frame Compare.

This module handles pre-run validation including configuration loading,
workspace path resolution, and input verification.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.config.loader import load_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import (
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


def resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths:
    """Resolve all workspace paths from config."""
    paths = config.paths
    resolved_root = root.resolve()
    config_dir = _resolve_path(paths.config_dir, resolved_root)

    return WorkspacePaths(
        root=resolved_root,
        input_dir=_resolve_path(paths.input_dir, resolved_root),
        run_dir=None,  # Legacy mode: run folder disabled
        screenshots_dir=_resolve_path(paths.screenshots_dir, resolved_root),
        generated_dir=_resolve_path(paths.generated_dir, resolved_root),
        config_dir=config_dir,
        config_file=config_dir / "config.toml",
    )


def _resolve_paths_with_config_file(
    config: ConfigSchema, root: Path, config_file: Path
) -> WorkspacePaths:
    """Internal: Resolve paths with explicit config_file (for prepare_preflight)."""
    paths = config.paths
    resolved_root = root.resolve()

    return WorkspacePaths(
        root=resolved_root,
        input_dir=_resolve_path(paths.input_dir, resolved_root),
        run_dir=None,  # Legacy mode: run folder disabled
        screenshots_dir=_resolve_path(paths.screenshots_dir, resolved_root),
        generated_dir=_resolve_path(paths.generated_dir, resolved_root),
        config_dir=_resolve_path(paths.config_dir, resolved_root),
        config_file=config_file,
    )


def discover_inputs(input_dir: Path, patterns: list[str] | None = None) -> list[Path]:
    """Discover video files in input directory."""
    import fnmatch

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
        if not config_path.exists():
            raise ConfigNotFoundError(config_path)
        resolved_config_path = config_path.resolve()
        resolved_root = root.resolve() if root else resolved_config_path.parent.parent
    else:
        resolved_root = resolve_workspace(root)
        resolved_config_path = resolved_root / "config" / "config.toml"
        if not resolved_config_path.exists():
            raise ConfigNotFoundError(resolved_config_path)

    config = load_config(resolved_config_path, overrides=overrides)

    workspace = _resolve_paths_with_config_file(config, resolved_root, resolved_config_path)

    if not workspace.input_dir.exists():
        raise DirectoryNotFoundError(workspace.input_dir)

    discover_inputs(workspace.input_dir)

    return PreflightResult(
        config=config,
        workspace=workspace,
        warnings=warnings,
    )
