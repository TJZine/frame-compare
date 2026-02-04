"""Preflight validation for Frame Compare 2.0.

This module handles pre-run validation including configuration loading,
workspace path resolution, and input verification.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from frame_compare.config import ConfigSchema, load_config
from frame_compare.errors import (
    ConfigNotFoundError,
    DirectoryNotFoundError,
    NoVideosFoundError,
)
from frame_compare.utils.types import WorkspacePaths

# Canonical video patterns per SSOT §4.3.6
_VIDEO_PATTERNS: list[str] = ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """Result of preflight validation.

    Attributes:
        config: Loaded and validated configuration
        workspace: Resolved absolute workspace paths
        warnings: Non-fatal warnings collected during preflight
    """

    config: ConfigSchema
    workspace: WorkspacePaths
    warnings: list[str] = field(default_factory=lambda: [])


def resolve_workspace(root: Path | None) -> Path:
    """Resolve workspace root directory.

    Priority:
    1. Explicit root parameter
    2. Current working directory if config/config.toml exists
    3. Search upward from cwd for config/config.toml
    4. Current working directory (fallback)

    Args:
        root: Optional explicit root path

    Returns:
        Resolved absolute workspace root path
    """
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
        return path
    return (root / path).resolve()


def resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths:
    """Resolve all workspace paths from config.

    Applies:
    - Environment variable expansion
    - Relative path resolution from root

    Note: config_file is derived as root / config_dir / "config.toml" per SSOT.

    Args:
        config: Loaded configuration schema
        root: Workspace root directory

    Returns:
        WorkspacePaths with all paths resolved to absolute
    """
    paths = config.paths
    resolved_root = root.resolve()
    config_dir = _resolve_path(paths.config_dir, resolved_root)

    return WorkspacePaths(
        root=resolved_root,
        input_dir=_resolve_path(paths.input_dir, resolved_root),
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
        screenshots_dir=_resolve_path(paths.screenshots_dir, resolved_root),
        generated_dir=_resolve_path(paths.generated_dir, resolved_root),
        config_dir=_resolve_path(paths.config_dir, resolved_root),
        config_file=config_file,
    )


def discover_inputs(input_dir: Path, patterns: list[str] | None = None) -> list[Path]:
    """Discover video files in input directory.

    Args:
        input_dir: Directory to search
        patterns: Glob patterns to match (defaults to module patterns if None)

    Returns:
        Sorted list of video file paths (case-insensitive lexicographic by filename)
    """
    effective_patterns = _VIDEO_PATTERNS if patterns is None else patterns
    videos: list[Path] = []
    for pattern in effective_patterns:
        videos.extend(input_dir.glob(pattern))

    # Stable ordering: case-insensitive lexicographic sort by filename
    ordered = sorted(videos, key=lambda p: p.name.lower())
    if not ordered:
        raise NoVideosFoundError(input_dir.resolve(), patterns=effective_patterns)
    return ordered


def prepare_preflight(
    root: Path | None = None,
    config_path: Path | None = None,
) -> PreflightResult:
    """Validate configuration and resolve workspace paths.

    Steps:
    1. Resolve workspace root (explicit, cwd, or search upward)
    2. Load configuration file (explicit path or discovery)
    3. Validate configuration schema
    4. Resolve all workspace paths declared in ConfigSchema.paths
    5. Verify input directory exists and contains videos

    Args:
        root: Optional explicit workspace root
        config_path: Optional explicit config file path

    Returns:
        PreflightResult with config and workspace

    Raises:
        ConfigNotFoundError: Configuration file not found
        DirectoryNotFoundError: Input directory missing
        NoVideosFoundError: No video files match patterns
    """
    warnings: list[str] = []

    # Step 1-2: Resolve config path
    if config_path is not None:
        # Explicit config path provided
        if not config_path.exists():
            raise ConfigNotFoundError(config_path)
        resolved_config_path = config_path.resolve()
        resolved_root = root.resolve() if root else resolved_config_path.parent.parent
    else:
        # Discover config from workspace
        resolved_root = resolve_workspace(root)
        resolved_config_path = resolved_root / "config" / "config.toml"
        if not resolved_config_path.exists():
            raise ConfigNotFoundError(resolved_config_path)

    # Step 3: Load and validate config
    config = load_config(resolved_config_path)

    # Step 4: Resolve all paths (use internal helper preserving exact config_file)
    workspace = _resolve_paths_with_config_file(config, resolved_root, resolved_config_path)

    # Step 5: Verify input directory and discover videos
    if not workspace.input_dir.exists():
        raise DirectoryNotFoundError(workspace.input_dir)

    discover_inputs(workspace.input_dir)

    return PreflightResult(
        config=config,
        workspace=workspace,
        warnings=warnings,
    )
