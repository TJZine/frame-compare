"""Shared utility types for Frame Compare 2.0.

This module contains cross-cutting type definitions used by multiple layers.
"""

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Resolved absolute paths for a workspace.

    These paths are computed once during preflight and passed through
    the execution context. All paths are guaranteed to be absolute
    and (for output paths) writable.

    Run folder mode (when run_dir is set):
    - screenshots_dir and generated_dir are resolved relative to run_dir
    - This enables centralized, per-comparison outputs inside input_dir

    Legacy mode (when run_dir is None):
    - screenshots_dir and generated_dir are resolved at workspace root level

    Attributes:
        root: Workspace root directory (contains sentinel like .frame-compare)
        input_dir: Video input directory (may be same as root or subdir)
        run_dir: Run folder for centralized outputs (None = legacy mode)
        screenshots_dir: Screenshot output directory
        generated_dir: Cache and generated files directory
        config_dir: Config and presets directory
        config_file: Path to config.toml (or None if using defaults)
    """

    root: Path
    input_dir: Path
    run_dir: Path | None
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

    def with_run_dir(self, run_dir: Path) -> "WorkspacePaths":
        """Return a new WorkspacePaths with run_dir set and paths updated.

        This updates screenshots_dir and generated_dir to be inside run_dir.

        Args:
            run_dir: The run folder path (e.g., input_dir / "Movie (2024)")

        Returns:
            New WorkspacePaths instance with run folder mode enabled
        """
        return replace(
            self,
            run_dir=run_dir,
            screenshots_dir=run_dir / "screenshots",
            generated_dir=run_dir / "generated",
        )
