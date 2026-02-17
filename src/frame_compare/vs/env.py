"""VapourSynth environment setup and dependency detection."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from frame_compare.errors import PluginNotFoundError, VapourSynthError, VapourSynthNotFoundError

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore


def is_vapoursynth_available() -> bool:
    """Check if VapourSynth is usable (import + core creation)."""
    try:
        vs_module = importlib.import_module("vapoursynth")
        _ = vs_module.core  # Validate core creation
        return True
    except (ImportError, ModuleNotFoundError):
        return False
    except Exception:
        return False


def ensure_vs_environment() -> vs.Core:
    """Initialize VapourSynth core with plugins.

    Returns:
        Configured vs.Core instance

    Raises:
        VapourSynthNotFoundError: If vapoursynth import fails (FC-2001)
        VapourSynthError: If VS core initialization fails (FC-2002)
    """
    try:
        vs_module = importlib.import_module("vapoursynth")
    except (ImportError, ModuleNotFoundError) as e:
        raise VapourSynthNotFoundError() from e

    try:
        return vs_module.core
    except Exception as e:
        raise VapourSynthError(f"Failed to initialize VapourSynth core: {e}") from e


def detect_plugins(core: vs.Core) -> dict[str, bool]:
    """Detect available VapourSynth plugins.

    Returns dict of plugin_name -> is_available.
    """
    return {
        # L-SMASH Works (lsmas) - source loading
        "lsmas": (hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"))
        or (hasattr(core, "lw") and hasattr(core.lw, "LWLibavSource")),
        # libplacebo - tonemapping
        "libplacebo": hasattr(core, "placebo") and hasattr(core.placebo, "Tonemap"),
    }


def require_plugin(core: vs.Core, plugin: str) -> None:
    """Ensure plugin is available, raising PluginNotFoundError if not."""
    available = detect_plugins(core)
    if not available.get(plugin, False):
        raise PluginNotFoundError(plugin)
