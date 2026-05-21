from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING

from frame_compare.errors import PluginNotFoundError, VapourSynthError, VapourSynthNotFoundError

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore

_REGISTERED_WINDOWS_DLL_DIRS: set[str] = set()
_WINDOWS_DLL_HANDLES: list[object] = []


def register_windows_dll_dirs() -> None:
    """Register candidate DLL directories for bundled Windows runtime imports.

    Python 3.8+ on Windows can require explicit DLL directory registration for
    extension-module dependencies. This keeps VapourSynth imports working in the
    portable bundle layout where runtime DLLs live under ``vs/core``.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    candidates: list[str] = []
    env_home = os.environ.get("VAPOURSYNTH_HOME")
    if env_home:
        candidates.append(env_home)

    python_dir = os.path.dirname(sys.executable)
    bundle_root = os.path.dirname(python_dir)
    vs_core = os.path.join(bundle_root, "vs", "core")
    if os.path.isdir(vs_core):
        candidates.append(vs_core)
        for root, dirs, _ in os.walk(vs_core):
            for dirname in dirs:
                candidates.append(os.path.join(root, dirname))

    app_site_packages = os.path.join(bundle_root, "app", "site-packages")
    nested_site_packages = os.path.join(app_site_packages, "Lib", "site-packages")
    for site_dir in (app_site_packages, nested_site_packages):
        if os.path.isdir(site_dir):
            candidates.append(site_dir)

    for candidate in candidates:
        if not candidate or not os.path.isdir(candidate):
            continue
        normalized = os.path.normcase(os.path.normpath(candidate))
        if normalized in _REGISTERED_WINDOWS_DLL_DIRS:
            continue
        try:
            handle = os.add_dll_directory(candidate)
        except (OSError, FileNotFoundError) as e:
            import logging

            logging.getLogger("frame_compare.vs.env").debug(
                "Skipping DLL directory candidate %s due to error: %s",
                candidate,
                e,
            )
            continue
        _WINDOWS_DLL_HANDLES.append(handle)
        _REGISTERED_WINDOWS_DLL_DIRS.add(normalized)


def is_vapoursynth_available() -> bool:
    """Check if VapourSynth is usable (import + core creation)."""
    try:
        register_windows_dll_dirs()
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
        register_windows_dll_dirs()
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
