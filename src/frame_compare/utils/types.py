"""Shared utility types for Frame Compare 2.0.

This module contains cross-cutting type definitions used by multiple layers.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Resolved absolute paths for a workspace.

    These paths are computed once during preflight and passed through
    the execution context. All paths are guaranteed to be absolute
    and (for output paths) writable.

    Attributes:
        root: Workspace root directory (contains sentinel like .frame-compare)
        input_dir: Video input directory (may be same as root or subdir)
        screenshots_dir: Screenshot output directory
        generated_dir: Cache and generated files directory
        config_dir: Config and presets directory
        config_file: Path to config.toml (or None if using defaults)
    """

    root: Path
    input_dir: Path
    screenshots_dir: Path
    generated_dir: Path
    config_dir: Path
    config_file: Path | None

    @property
    def cache_dir(self) -> Path:
        """Directory for analysis cache files."""
        return self.generated_dir / "cache"

    @property
    def probe_cache_dir(self) -> Path:
        """Directory for video probe cache."""
        return self.generated_dir / "probe"
