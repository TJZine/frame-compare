from __future__ import annotations

import importlib
import logging
import os
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING

from frame_compare.vs.errors import PluginNotFoundError, VapourSynthError, VapourSynthNotFoundError

if TYPE_CHECKING:
    import vapoursynth as vs

log = logging.getLogger(__name__)


def _new_registered_dirs() -> set[str]:
    return set()


def _new_dll_handles() -> list[object]:
    return []


@dataclass(slots=True)
class _WindowsDllRegistrationState:
    """Process-owned state for Windows DLL directory registration."""

    registered_dirs: set[str] = field(default_factory=_new_registered_dirs)
    handles: list[object] = field(default_factory=_new_dll_handles)


_WINDOWS_DLL_REGISTRATION = _WindowsDllRegistrationState()


@dataclass(frozen=True, slots=True)
class PluginPathCandidate:
    """A concrete plugin file candidate and the discovery source that produced it."""

    path: str
    source: str


def _iter_windows_dll_candidates() -> list[str]:
    """Return deterministic DLL directories in bundle-search order.

    The portable runtime never recursively probes directories and deliberately
    excludes the standalone FFmpeg distribution and PyQt's Qt binary directory.
    PyQt registers its own DLLs when imported; process-wide registration would let
    its private MSVC runtime preempt native media plugin dependencies.
    """
    candidates: list[str] = []
    env_home = os.environ.get("VAPOURSYNTH_HOME")
    if env_home:
        candidates.append(env_home)

    python_dir = os.path.dirname(sys.executable)
    bundle_root = os.path.dirname(python_dir)
    app_site_packages = os.path.join(bundle_root, "app", "site-packages")
    candidates.extend(
        [
            python_dir,
            os.path.join(bundle_root, "vs", "core"),
            app_site_packages,
            os.path.join(app_site_packages, "vapoursynth"),
            os.path.join(app_site_packages, "vapoursynth.libs"),
            os.path.join(app_site_packages, "vs_placebo"),
            os.path.join(app_site_packages, "vs_placebo.libs"),
        ]
    )
    return candidates


def _register_windows_dll_candidate(candidate: str) -> None:
    """Register a Windows DLL directory once per process."""
    if not candidate or not os.path.isdir(candidate):
        return

    normalized = os.path.normcase(os.path.normpath(candidate))
    if normalized in _WINDOWS_DLL_REGISTRATION.registered_dirs:
        return

    try:
        handle = os.add_dll_directory(candidate)
    except (OSError, FileNotFoundError) as error:
        log.debug(
            "Skipping DLL directory candidate %s due to error: %s",
            candidate,
            error,
        )
        return

    _WINDOWS_DLL_REGISTRATION.handles.append(handle)
    _WINDOWS_DLL_REGISTRATION.registered_dirs.add(normalized)


def register_windows_dll_dirs() -> None:
    """Register candidate DLL directories for bundled Windows runtime imports.

    Python 3.8+ on Windows can require explicit DLL directory registration for
    extension-module dependencies. This keeps VapourSynth imports working in the
    portable bundle layout where runtime DLLs live under ``vs/core``.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    for candidate in _iter_windows_dll_candidates():
        _register_windows_dll_candidate(candidate)


def import_vapoursynth_module() -> ModuleType:
    """Import VapourSynth, falling back to runtime-path registration on failure."""
    try:
        return __import__("vapoursynth")
    except ImportError:
        register_windows_dll_dirs()
        return __import__("vapoursynth")


def _split_plugin_dirs(value: str) -> list[str]:
    return [plugin_dir for plugin_dir in value.split(os.pathsep) if plugin_dir]


def _normalized_path_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _get_canonical_plugin_dir() -> str | None:
    try:
        vs_module = import_vapoursynth_module()
    except ImportError:
        return None

    get_plugin_dir = getattr(vs_module, "get_plugin_dir", None)
    if not callable(get_plugin_dir):
        return None

    try:
        plugin_dir = get_plugin_dir()
    except Exception as exc:
        log.debug("Skipping VapourSynth canonical plugin dir due to error: %s", exc)
        return None

    if isinstance(plugin_dir, str | os.PathLike):
        return os.fspath(plugin_dir)
    return None


def _candidate_lsmas_filenames() -> list[str]:
    if os.name == "nt":
        return ["LSMASHSource.dll", "libvslsmashsource.dll"]
    return ["libvslsmashsource.so", "libvslsmashsource.dylib", "libvslsmashsource.dll"]


def _candidate_lsmas_manifest_entries(filenames: list[str]) -> set[str]:
    manifest_entries = {os.path.splitext(filename)[0] for filename in filenames}
    manifest_entries.update(filenames)
    return manifest_entries


def _manifest_references_lsmas_plugin(manifest_path: str, filenames: list[str]) -> bool:
    if not os.path.isfile(manifest_path):
        return False

    expected_entries = _candidate_lsmas_manifest_entries(filenames)
    try:
        with open(manifest_path, encoding="utf-8") as manifest_file:
            for raw_line in manifest_file:
                line = raw_line.strip()
                if not line or line.startswith("[") or line.startswith("#"):
                    continue
                if line in expected_entries:
                    return True
    except (OSError, UnicodeDecodeError) as exc:
        log.debug("Skipping manifest check for %s due to error: %s", manifest_path, exc)
    return False


def _contains_lsmas_plugin_artifacts(plugin_dir: str, filenames: list[str]) -> bool:
    if any(os.path.isfile(os.path.join(plugin_dir, filename)) for filename in filenames):
        return True
    manifest_path = os.path.join(plugin_dir, "manifest.vs")
    return _manifest_references_lsmas_plugin(manifest_path, filenames)


def _iter_lsmas_search_dirs(plugin_dir: str, source: str, filenames: list[str]) -> list[str]:
    """Expand plugin search dirs for explicit lsmas fallback loading.

    R75+ optimized plugin installs can place each plugin under a nested directory
    with ``manifest.vs``. When an unmanaged or container runtime supplies an
    extra-plugin root, explicit fallback loading considers those first-level child
    dirs in addition to the root itself. Other discovery sources continue using
    their configured directory directly.
    """

    search_dirs = [plugin_dir]
    if source != "VAPOURSYNTH_EXTRA_PLUGIN_PATH":
        return search_dirs

    try:
        with os.scandir(plugin_dir) as entries:
            nested_dirs: list[str] = []
            for entry in entries:
                try:
                    is_dir = entry.is_dir()
                except OSError as exc:
                    log.debug("Skipping extra-plugin entry %s due to error: %s", entry.path, exc)
                    continue
                if not is_dir or not _contains_lsmas_plugin_artifacts(entry.path, filenames):
                    continue
                nested_dirs.append(entry.path)
    except OSError as exc:
        log.debug("Skipping nested extra-plugin scan for %s due to error: %s", plugin_dir, exc)
        return search_dirs

    nested_dirs.sort(key=_normalized_path_key)
    search_dirs.extend(nested_dirs)
    return search_dirs


def _iter_candidate_plugin_dirs() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    canonical_plugin_dir = _get_canonical_plugin_dir()
    if canonical_plugin_dir:
        candidates.append((canonical_plugin_dir, "vapoursynth.get_plugin_dir"))

    extra_plugin_env = os.environ.get("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "")
    for plugin_dir in _split_plugin_dirs(extra_plugin_env):
        candidates.append((plugin_dir, "VAPOURSYNTH_EXTRA_PLUGIN_PATH"))

    legacy_plugin_env = os.environ.get("VAPOURSYNTH_PLUGIN_PATH", "")
    for plugin_dir in _split_plugin_dirs(legacy_plugin_env):
        candidates.append((plugin_dir, "VAPOURSYNTH_PLUGIN_PATH"))

    return candidates


def candidate_lsmas_plugin_path_details() -> list[PluginPathCandidate]:
    """Return candidate L-SMASH plugin paths with their discovery source.

    VapourSynth R74+ exposes the canonical plugin directory through
    ``vapoursynth.get_plugin_dir()`` and uses ``VAPOURSYNTH_EXTRA_PLUGIN_PATH``
    for supplemental plugin locations. When that extra-plugin path points at a
    root containing nested manifest-based plugin dirs, first-level child dirs
    are also expanded for explicit fallback loading. The legacy
    ``VAPOURSYNTH_PLUGIN_PATH`` remains checked last as a migration bridge for
    existing bundles.
    """
    seen: set[str] = set()
    unique_candidates: list[PluginPathCandidate] = []
    filenames = _candidate_lsmas_filenames()
    for plugin_dir, source in _iter_candidate_plugin_dirs():
        for search_dir in _iter_lsmas_search_dirs(plugin_dir, source, filenames):
            for filename in filenames:
                absolute = os.path.abspath(os.path.normpath(os.path.join(search_dir, filename)))
                normalized = _normalized_path_key(absolute)
                if normalized in seen:
                    continue
                seen.add(normalized)
                unique_candidates.append(PluginPathCandidate(path=absolute, source=source))
    return unique_candidates


def candidate_lsmas_plugin_paths() -> list[str]:
    """Return candidate absolute paths for the L-SMASH-Works plugin binary."""
    return [candidate.path for candidate in candidate_lsmas_plugin_path_details()]


def try_load_lsmas_plugin(core: object) -> str | None:
    """Try loading the bundled lsmas plugin and return loaded path, if any."""
    std_ns = getattr(core, "std", None)
    if std_ns is None:
        return None
    load_plugin = getattr(std_ns, "LoadPlugin", None)
    if not callable(load_plugin):
        return None

    for plugin_path in candidate_lsmas_plugin_paths():
        if not os.path.isfile(plugin_path):
            continue
        try:
            load_plugin(path=plugin_path)
        except Exception as exc:
            log.debug("Skipping L-SMASH plugin candidate %s due to error: %s", plugin_path, exc)
            continue
        return plugin_path
    return None


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
        "lsmas": hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"),
        # libplacebo - tonemapping
        "libplacebo": hasattr(core, "placebo") and hasattr(core.placebo, "Tonemap"),
    }


def require_plugin(core: vs.Core, plugin: str) -> None:
    """Ensure plugin is available, raising PluginNotFoundError if not."""
    available = detect_plugins(core)
    if not available.get(plugin, False):
        raise PluginNotFoundError(plugin)
