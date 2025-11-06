"""VapourSynth integration helpers used by the frame comparison tool."""

from __future__ import annotations

import importlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    cast,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .datatypes import ColorConfig

_VS_MODULE_NAME = "vapoursynth"
_ENV_VAR = "VAPOURSYNTH_PYTHONPATH"
_EXTRA_SEARCH_PATHS: list[str] = []
_vs_module: Any | None = None
_SOURCE_PREFERENCE = "lsmas"
_VALID_SOURCE_PLUGINS = {"lsmas", "ffms2"}
_SOURCE_PLUGIN_FUNCS = {"lsmas": "LWLibavSource", "ffms2": "Source"}
_CACHE_SUFFIX = {"lsmas": ".lwi", "ffms2": ".ffindex"}


class ClipInitError(RuntimeError):
    """Raised when a clip cannot be created via VapourSynth."""


class ClipProcessError(RuntimeError):
    """Raised when screenshot preparation fails."""


class VSPluginError(ClipInitError):
    """Base class for VapourSynth plugin discovery failures."""

    def __init__(self, plugin: str, message: str) -> None:
        super().__init__(message)
        self.plugin = plugin


class VSPluginMissingError(VSPluginError):
    """Raised when a required VapourSynth plugin is absent."""


class VSPluginWrongArchError(VSPluginError):
    """Raised when a plugin binary targets the wrong CPU architecture."""


class VSPluginDepMissingError(VSPluginError):
    """Raised when a plugin has unresolved shared library dependencies."""

    def __init__(self, plugin: str, dependency: str | None, message: str) -> None:
        super().__init__(plugin, message)
        self.dependency = dependency


class VSPluginBadBinaryError(VSPluginError):
    """Raised when a plugin binary is malformed or lacks an entry point."""


class VSSourceUnavailableError(ClipInitError):
    """Raised when no usable source plugin is available."""

    def __init__(self, message: str, *, errors: Mapping[str, VSPluginError] | None = None) -> None:
        super().__init__(message)
        self.errors: Mapping[str, VSPluginError] = dict(errors or {})


_HDR_PRIMARIES_NAMES = {"bt2020", "bt.2020", "2020"}
_HDR_PRIMARIES_CODES = {9}
_HDR_TRANSFER_NAMES = {"st2084", "pq", "smpte2084", "hlg", "arib-b67"}
_HDR_TRANSFER_CODES = {16, 18}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TonemapInfo:
    """Metadata describing how a clip was tonemapped."""

    applied: bool
    tone_curve: Optional[str]
    dpd: int
    target_nits: float
    dst_min_nits: float
    src_csp_hint: Optional[int]
    reason: Optional[str] = None
    output_color_range: Optional[int] = None
    range_detection: Optional[str] = None
    knee_offset: Optional[float] = None
    dpd_preset: Optional[str] = None
    dpd_black_cutoff: Optional[float] = None
    post_gamma: Optional[float] = None
    post_gamma_enabled: bool = False
    smoothing_period: Optional[float] = None
    scene_threshold_low: Optional[float] = None
    scene_threshold_high: Optional[float] = None
    percentile: Optional[float] = None
    contrast_recovery: Optional[float] = None
    metadata: Optional[int] = None
    use_dovi: Optional[bool] = None
    visualize_lut: bool = False
    show_clipping: bool = False


@dataclass(frozen=True)
class VerificationResult:
    """Result of comparing a tonemapped clip against a naive SDR convert."""

    frame: int
    average: float
    maximum: float
    auto_selected: bool


@dataclass(frozen=True)
class ColorDebugArtifacts:
    """Clips and metadata captured for colour debugging."""

    normalized_clip: Any | None
    normalized_props: Mapping[str, Any] | None
    original_props: Mapping[str, Any] | None
    color_tuple: tuple[Optional[int], Optional[int], Optional[int], Optional[int]] | None


@dataclass(frozen=True)
class TonemapSettings:
    """Resolved tonemap configuration used for the current clip."""

    preset: str
    tone_curve: str
    target_nits: float
    dynamic_peak_detection: bool
    dst_min_nits: float
    knee_offset: float
    dpd_preset: str
    dpd_black_cutoff: float
    smoothing_period: float
    scene_threshold_low: float
    scene_threshold_high: float
    percentile: float
    contrast_recovery: float
    metadata: Optional[int]
    use_dovi: Optional[bool]
    visualize_lut: bool
    show_clipping: bool


@dataclass(frozen=True)
class ClipProcessResult:
    """Container for processed clip and metadata."""

    clip: Any
    tonemap: TonemapInfo
    overlay_text: Optional[str]
    verification: Optional[VerificationResult]
    source_props: Mapping[str, Any]
    debug: Optional[ColorDebugArtifacts] = None


_MATRIX_NAME_TO_CODE = {
    "rgb": 0,
    "0": 0,
    "bt709": 1,
    "bt.709": 1,
    "709": 1,
    "bt470bg": 5,
    "470bg": 5,
    "smpte170m": 6,
    "170m": 6,
    "bt601": 6,
    "601": 6,
    "bt2020": 9,
    "bt.2020": 9,
    "2020": 9,
    "2020ncl": 9,
}

_PRIMARIES_NAME_TO_CODE = {
    "bt709": 1,
    "bt.709": 1,
    "709": 1,
    "bt470bg": 5,
    "470bg": 5,
    "smpte170m": 6,
    "170m": 6,
    "bt601": 6,
    "601": 6,
    "bt2020": 9,
    "bt.2020": 9,
    "2020": 9,
}

_TRANSFER_NAME_TO_CODE = {
    "bt709": 1,
    "709": 1,
    "bt1886": 1,
    "gamma2.2": 1,
    "st2084": 16,
    "smpte2084": 16,
    "pq": 16,
    "hlg": 18,
    "arib-b67": 18,
    "smpte170m": 6,
    "170m": 6,
    "bt601": 6,
    "601": 6,
}

_RANGE_NAME_TO_CODE = {
    "limited": 1,
    "tv": 1,
    "full": 0,
    "pc": 0,
    "jpeg": 0,
}

_MATRIX_CODE_LABELS = {
    0: "rgb",
    1: "bt709",
    5: "bt470bg",
    6: "smpte170m",
    9: "bt2020",
}

_PRIMARIES_CODE_LABELS = {
    1: "bt709",
    5: "bt470bg",
    6: "smpte170m",
    9: "bt2020",
}

_TRANSFER_CODE_LABELS = {
    1: "bt1886",
    6: "smpte170m",
    16: "st2084",
    18: "hlg",
}

_RANGE_CODE_LABELS = {
    0: "full",
    1: "limited",
}


def _describe_code(value: Optional[int], mapping: Mapping[int, str], default: str = "auto") -> str:
    """
    Convert a numeric code to its human-readable label using a provided mapping.

    Parameters:
        value (Optional[int]): The code to describe; if `None`, `default` is returned.
        mapping (Mapping[int, str]): Mapping from integer codes to their human-readable labels.
        default (str): Value to return when `value` is `None`. Defaults to "auto".

    Returns:
        str: The label from `mapping` for `int(value)` if present; otherwise `default` when `value` is `None`, or `str(value)` if no mapping entry exists.
    """
    if value is None:
        return default
    try:
        return mapping[int(value)]
    except Exception:
        return str(value)


def _normalise_search_path(path: str) -> str:
    """
    Normalize a filesystem search path by expanding a user home and resolving to an absolute path when possible.

    Parameters:
        path (str): The input filesystem path, may contain a leading `~` for the user home.

    Returns:
        normalized_path (str): The expanded and resolved absolute path when resolution succeeds; otherwise the expanded path.
    """
    expanded = Path(path).expanduser()
    try:
        return str(expanded.resolve())
    except (OSError, RuntimeError):
        return str(expanded)


def _add_search_paths(paths: Iterable[str]) -> None:
    for raw in paths:
        if not raw:
            continue
        resolved = _normalise_search_path(raw)
        if resolved in _EXTRA_SEARCH_PATHS:
            continue
        _EXTRA_SEARCH_PATHS.append(resolved)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)


def _set_source_preference(preference: str) -> None:
    """Record the preferred VapourSynth source plugin."""

    global _SOURCE_PREFERENCE
    normalized = preference.strip().lower()
    if normalized not in _VALID_SOURCE_PLUGINS:
        raise ValueError(
            f"Unsupported VapourSynth source preference '{preference}'."
            " Valid options are: " + ", ".join(sorted(_VALID_SOURCE_PLUGINS))
        )
    _SOURCE_PREFERENCE = normalized


def _load_env_paths_from_env() -> None:
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        return
    entries = [entry.strip() for entry in raw.split(os.pathsep)]
    _add_search_paths(entry for entry in entries if entry)


def configure(
    *, search_paths: Sequence[str] | None = None, source_preference: str | None = None
) -> None:
    if search_paths:
        _add_search_paths(search_paths)
    if source_preference is not None:
        _set_source_preference(source_preference)


def _build_missing_vs_message() -> str:
    details: List[str] = []
    if _EXTRA_SEARCH_PATHS:
        details.append("Tried extra search paths: " + ", ".join(_EXTRA_SEARCH_PATHS))
    details.append(
        "Install VapourSynth for this interpreter or expose it via "
        "runtime.vapoursynth_python_paths in config.toml."
    )
    return " ".join(["VapourSynth is not available in this environment."] + details)


def _get_vapoursynth_module() -> Any:
    global _vs_module
    if _vs_module is not None:
        return _vs_module
    try:
        module = importlib.import_module(_VS_MODULE_NAME)
    except Exception as exc:  # pragma: no cover - import failure depends on env
        raise ClipInitError(_build_missing_vs_message()) from exc
    _vs_module = module
    return module


_load_env_paths_from_env()


def _resolve_core(core: Optional[Any]) -> Any:
    if core is not None:
        return core
    vs_module = _get_vapoursynth_module()
    module_core = getattr(vs_module, "core", None)
    if callable(module_core):
        try:
            resolved = module_core()
            if resolved is not None:
                return resolved
        except TypeError:
            resolved = module_core
            if resolved is not None:
                return resolved
    if module_core is not None and not callable(module_core):
        return module_core
    get_core = getattr(vs_module, "get_core", None)
    if callable(get_core):
        resolved = get_core()
        if resolved is not None:
            return resolved
    fallback_core = getattr(vs_module, "core", None)
    if fallback_core is None:
        raise ClipInitError("VapourSynth core is not available on this interpreter")
    return fallback_core


def _build_source_order() -> list[str]:
    """Return the ordered list of source plugins to try."""

    if _SOURCE_PREFERENCE == "ffms2":
        return ["ffms2", "lsmas"]
    return ["lsmas", "ffms2"]


def _build_plugin_missing_message(plugin: str) -> str:
    base = f"VapourSynth plugin '{plugin}' is not available on the current core."
    if plugin == "lsmas":
        return (
            base
            + " Install L-SMASH-Works (LWLibavSource) built for this architecture and place"
            " it in ~/Library/VapourSynth/plugins or /opt/homebrew/lib/vapoursynth."
        )
    if plugin == "ffms2":
        return (
            base
            + " Install FFMS2 and ensure the plugin dylib resides in a VapourSynth plugin"
            " directory (e.g. via 'brew install vapoursynth-ffms2')."
        )
    return base


def _resolve_source_callable(core: Any, plugin: str) -> Callable[..., Any]:
    namespace = getattr(core, plugin, None)
    if namespace is None:
        raise VSPluginMissingError(plugin, _build_plugin_missing_message(plugin))
    func_name = _SOURCE_PLUGIN_FUNCS.get(plugin)
    if not func_name:
        raise VSPluginBadBinaryError(plugin, f"No loader defined for plugin '{plugin}'")
    source = getattr(namespace, func_name, None)
    if not callable(source):
        raise VSPluginBadBinaryError(
            plugin,
            f"{plugin}.{func_name} is not callable. The plugin may have failed to load or"
            " is not a VapourSynth binary compatible with this release.",
        )
    return source


def _cache_path_for(cache_root: Path, base_name: str, plugin: str) -> Path:
    suffix = _CACHE_SUFFIX.get(plugin, ".lwi")
    return cache_root / f"{base_name}{suffix}"


_DEPENDENCY_PATTERN = re.compile(r"Library not loaded: (?P<path>\S+)")
_ENTRY_POINT_PATTERN = re.compile(r"(vapoursynthplugininit|entry point)", re.IGNORECASE)
_WRONG_ARCH_PATTERN = re.compile(r"wrong architecture", re.IGNORECASE)


def _extract_major_version(library_name: str) -> str | None:
    match = re.search(r"\.(\d+)(?:\.dylib)?$", library_name)
    if match:
        return match.group(1)
    return None


def _build_dependency_hint(plugin: str, dependency: str | None, details: str) -> str:
    parts = [
        f"{plugin} plugin could not be initialised because a dependency was missing.",
        details,
    ]
    if dependency:
        dep_name = Path(dependency).name
        parts.append(f"Missing library: {dep_name} ({dependency}).")
        lowered = dep_name.lower()
        major = _extract_major_version(dep_name)
        if "libav" in lowered:
            if major:
                parts.append(
                    f"Install an FFmpeg build that provides {dep_name} (major {major})"
                    " or adjust the plugin's install_name to point at /opt/homebrew/lib."
                )
            else:
                parts.append(
                    "Install a matching FFmpeg build (e.g. via Homebrew) and ensure the"
                    " dylibs are discoverable."
                )
        if "liblsmash" in lowered:
            parts.append(
                "Install liblsmash (brew install l-smash) or ensure DYLD_LIBRARY_PATH"
                " includes the directory that provides it."
            )
    else:
        parts.append(
            "Check that the plugin binary and its dependencies are located in a"
            " VapourSynth plugin directory."
        )
    return " ".join(parts)


def _build_wrong_arch_message(plugin: str, details: str) -> str:
    return (
        f"{plugin} plugin failed to load because the binary targets a different CPU"
        f" architecture. {details} Install an arm64-compatible build or run under"
        " Rosetta with matching x86_64 dependencies."
    )


def _classify_plugin_exception(plugin: str, exc: Exception) -> VSPluginError | None:
    message = str(exc)
    lower = message.lower()
    if _WRONG_ARCH_PATTERN.search(lower):
        return VSPluginWrongArchError(plugin, _build_wrong_arch_message(plugin, message))
    match = _DEPENDENCY_PATTERN.search(message)
    if match:
        dependency = match.group("path")
        return VSPluginDepMissingError(
            plugin,
            dependency,
            _build_dependency_hint(plugin, dependency, message),
        )
    if "image not found" in lower and "dlopen" in lower:
        return VSPluginDepMissingError(
            plugin,
            None,
            _build_dependency_hint(plugin, None, message),
        )
    if _ENTRY_POINT_PATTERN.search(lower) or "no entry point" in lower:
        return VSPluginBadBinaryError(
            plugin,
            f"{plugin} plugin appears to be an incompatible binary. {message} Ensure"
            " it exports VapourSynthPluginInit2 and matches this VapourSynth release.",
        )
    return None


def _open_clip_with_sources(core: Any, path: str, cache_root: Path) -> Any:
    order = _build_source_order()
    errors: dict[str, VSPluginError] = {}
    base_name = Path(path).name
    for plugin in order:
        try:
            source = _resolve_source_callable(core, plugin)
        except VSPluginError as plugin_error:
            logger.warning(
                "VapourSynth plugin '%s' unavailable: %s", plugin, plugin_error
            )
            errors[plugin] = plugin_error
            continue

        cache_path = _cache_path_for(cache_root, base_name, plugin)
        try:
            return source(path, cachefile=str(cache_path))
        except Exception as exc:
            classified = _classify_plugin_exception(plugin, exc)
            if isinstance(classified, VSPluginError):
                logger.warning(
                    "VapourSynth plugin '%s' unavailable: %s", plugin, classified
                )
                errors[plugin] = classified
                continue
            raise ClipInitError(f"Failed to open clip '{path}' via {plugin}: {exc}") from exc

    if errors:
        detail = "; ".join(f"{name}: {err}" for name, err in errors.items())
        raise VSSourceUnavailableError(
            (
                f"No usable VapourSynth source plugin was able to open '{path}'. Tried"
                f" {', '.join(order)}. Details: {detail}"
            ),
            errors=errors,
        )
    raise VSSourceUnavailableError(
        f"No VapourSynth source plugins were available to open '{path}'.",
        errors=errors,
    )


def _ensure_std_namespace(clip: Any, error: RuntimeError) -> Any:
    std = getattr(clip, "std", None)
    if std is None:
        raise error
    return std


def _call_set_frame_prop(set_prop: Any, clip: Any, **kwargs) -> Any:
    try:
        return set_prop(clip, **kwargs)
    except TypeError as exc_first:
        try:
            return set_prop(**kwargs)
        except TypeError:
            raise exc_first


def _apply_set_frame_prop(clip: Any, **kwargs) -> Any:
    std_ns = _ensure_std_namespace(
        clip,
        ClipProcessError("clip.std namespace missing for SetFrameProp"),
    )
    set_prop = getattr(std_ns, "SetFrameProp", None)
    if not callable(set_prop):  # pragma: no cover - defensive
        raise ClipProcessError("clip.std.SetFrameProp is unavailable")
    return _call_set_frame_prop(set_prop, clip, **kwargs)


def _slice_clip(clip: Any, *, start: Optional[int] = None, end: Optional[int] = None) -> Any:
    try:
        if start is not None and end is not None:
            return clip[start:end]
        if start is not None:
            return clip[start:]
        if end is not None:
            return clip[:end]
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError("Failed to apply trim to clip") from exc
    return clip


def _extend_with_blank(clip: Any, core: Any, length: int) -> Any:
    std_ns = getattr(core, "std", None)
    if std_ns is None:
        raise ClipInitError("VapourSynth core missing std namespace for BlankClip")
    blank_clip = getattr(std_ns, "BlankClip", None)
    if not callable(blank_clip):
        raise ClipInitError("std.BlankClip is unavailable on the VapourSynth core")
    try:
        extension = blank_clip(clip, length=length)
        return extension + clip
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError("Failed to prepend blank frames to clip") from exc


def _apply_fps_map(clip: Any, fps_map: Tuple[int, int]) -> Any:
    std = _ensure_std_namespace(clip, ClipInitError("Clip is missing std namespace for AssumeFPS"))
    num, den = fps_map
    if den <= 0:
        raise ClipInitError("fps_map denominator must be positive")
    try:
        return std.AssumeFPS(num=num, den=den)
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError("Failed to apply FPS mapping to clip") from exc


def init_clip(
    path: str,
    *,
    trim_start: int = 0,
    trim_end: Optional[int] = None,
    fps_map: Tuple[int, int] | None = None,
    cache_dir: Optional[str | Path] = None,
    core: Optional[Any] = None,
) -> Any:
    """Initialise a VapourSynth clip for subsequent processing."""

    resolved_core = _resolve_core(core)

    path_obj = Path(path)
    cache_root = Path(cache_dir) if cache_dir is not None else path_obj.parent
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError(f"Failed to prepare cache directory '{cache_root}': {exc}") from exc

    try:
        clip = _open_clip_with_sources(resolved_core, str(path_obj), cache_root)
    except ClipInitError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError(f"Failed to open clip '{path}': {exc}") from exc

    if trim_start < 0:
        clip = _extend_with_blank(clip, resolved_core, abs(int(trim_start)))
    elif trim_start > 0:
        clip = _slice_clip(clip, start=int(trim_start))

    if trim_end is not None and trim_end != 0:
        clip = _slice_clip(clip, end=int(trim_end))
    if fps_map is not None:
        clip = _apply_fps_map(clip, fps_map)
    return clip


def set_ram_limit(limit_mb: int, *, core: Optional[Any] = None) -> None:
    """Apply a global VapourSynth cache limit based on *limit_mb*."""

    if limit_mb <= 0:
        raise ClipInitError("ram_limit_mb must be positive")

    resolved_core = _resolve_core(core)
    try:
        setattr(resolved_core, "max_cache_size", int(limit_mb))
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError("Failed to apply VapourSynth RAM limit") from exc


def _normalise_property_value(value: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _value_matches(value: Any, names: set[str], codes: set[int]) -> bool:
    if isinstance(value, int):
        return value in codes
    value = _normalise_property_value(value)
    if isinstance(value, str):
        return value in names
    return False


def _extract_frame_props(clip: Any) -> Mapping[str, Any]:
    getter = getattr(clip, "get_frame_props", None)
    if callable(getter):
        props = getter()
        if isinstance(props, Mapping):
            return props
    frame_props = getattr(clip, "frame_props", None)
    if isinstance(frame_props, Mapping):
        return frame_props
    return {}

def _snapshot_frame_props(clip: Any) -> Mapping[str, Any]:
    try:
        frame = clip.get_frame(0)
    except Exception:
        return dict(_extract_frame_props(clip))
    props = getattr(frame, "props", None)
    if props is None:
        return dict(_extract_frame_props(clip))
    return dict(props)


def _props_signal_hdr(props: Mapping[str, Any]) -> bool:
    primaries = props.get("_Primaries") or props.get("Primaries")
    transfer = props.get("_Transfer") or props.get("Transfer")
    if not _value_matches(primaries, _HDR_PRIMARIES_NAMES, _HDR_PRIMARIES_CODES):
        return False
    return _value_matches(transfer, _HDR_TRANSFER_NAMES, _HDR_TRANSFER_CODES)


def _coerce_prop(value: Any, mapping: Mapping[str, int] | None = None) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, str)):
        normalized = _normalise_property_value(value)
        if isinstance(normalized, str):
            if mapping and normalized in mapping:
                return mapping[normalized]
            try:
                return int(normalized)
            except ValueError:
                return None
    return None


def _first_present(props: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in props:
            return props[key]
    return None


def _normalise_resolved_code(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    if code == 2:
        return None
    return code


def _resolve_color_metadata(
    props: Mapping[str, Any],
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    matrix = _coerce_prop(
        _first_present(props, "_Matrix", "Matrix"),
        _MATRIX_NAME_TO_CODE,
    )
    primaries = _coerce_prop(
        _first_present(props, "_Primaries", "Primaries"),
        _PRIMARIES_NAME_TO_CODE,
    )
    transfer = _coerce_prop(
        _first_present(props, "_Transfer", "Transfer"),
        _TRANSFER_NAME_TO_CODE,
    )
    color_range = _coerce_prop(
        _first_present(props, "_ColorRange", "ColorRange"),
        _RANGE_NAME_TO_CODE,
    )
    return (
        _normalise_resolved_code(matrix),
        _normalise_resolved_code(transfer),
        _normalise_resolved_code(primaries),
        _normalise_resolved_code(color_range),
    )


def _infer_frame_height(clip: Any, props: Mapping[str, Any]) -> Optional[int]:
    height = getattr(clip, "height", None)
    try:
        if height is not None:
            return int(height)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        pass
    for key in ("_Height", "Height"):
        candidate = props.get(key)
        try:
            if candidate is not None:
                return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _resolve_configured_color_defaults(
    color_cfg: "ColorConfig | None",
    *,
    is_sd: bool,
    is_hd: bool,
) -> Dict[str, Optional[int]]:
    resolved: Dict[str, Optional[int]] = {
        "matrix": None,
        "primaries": None,
        "transfer": None,
        "range": None,
    }
    if color_cfg is None:
        return resolved

    def _value(name: str) -> Any:
        return getattr(color_cfg, name, None)

    def _coerce(value: Any, mapping: Mapping[str, int]) -> Optional[int]:
        if value in (None, ""):
            return None
        return _coerce_prop(value, mapping)

    if is_sd:
        resolved["matrix"] = _coerce(_value("default_matrix_sd"), _MATRIX_NAME_TO_CODE)
        resolved["primaries"] = _coerce(_value("default_primaries_sd"), _PRIMARIES_NAME_TO_CODE)
    elif is_hd:
        resolved["matrix"] = _coerce(_value("default_matrix_hd"), _MATRIX_NAME_TO_CODE)
        resolved["primaries"] = _coerce(_value("default_primaries_hd"), _PRIMARIES_NAME_TO_CODE)
    else:
        resolved["matrix"] = _coerce(
            _value("default_matrix_hd") or _value("default_matrix_sd"),
            _MATRIX_NAME_TO_CODE,
        )
        resolved["primaries"] = _coerce(
            _value("default_primaries_hd") or _value("default_primaries_sd"),
            _PRIMARIES_NAME_TO_CODE,
        )

    resolved["transfer"] = _coerce(_value("default_transfer_sdr"), _TRANSFER_NAME_TO_CODE)
    resolved["range"] = _coerce(_value("default_range_sdr"), _RANGE_NAME_TO_CODE)
    return resolved


def _resolve_color_overrides(
    color_cfg: "ColorConfig | None",
    file_name: str | None,
) -> Dict[str, Optional[int]]:
    if color_cfg is None:
        return {}
    overrides: Dict[str, Dict[str, Any]] = getattr(color_cfg, "color_overrides", {})
    if not overrides:
        return {}

    lookup_keys: List[str] = []
    if file_name:
        lookup_keys.append(file_name)
        lookup_keys.append(Path(file_name).name)
    lookup_keys.append("*")

    selected: Dict[str, Any] = {}
    for key in lookup_keys:
        if key in overrides:
            selected = overrides[key]
            break
    if not selected:
        return {}

    resolved: Dict[str, Optional[int]] = {}
    for attr, mapping in (
        ("matrix", _MATRIX_NAME_TO_CODE),
        ("primaries", _PRIMARIES_NAME_TO_CODE),
        ("transfer", _TRANSFER_NAME_TO_CODE),
        ("range", _RANGE_NAME_TO_CODE),
    ):
        value = selected.get(attr)
        if value in (None, ""):
            continue
        coerced = _coerce_prop(value, mapping)
        if coerced is None:
            logger.warning(
                "Ignoring invalid color_overrides value for %s: %r (file=%s)",
                attr,
                value,
                file_name or "",
            )
            continue
        resolved[attr] = coerced
    return resolved


def _apply_frame_props_dict(clip: Any, props: Mapping[str, int]) -> Any:
    if not props:
        return clip
    std_ns = getattr(clip, "std", None)
    if std_ns is None:
        return clip
    set_props = getattr(std_ns, "SetFrameProps", None)
    if not callable(set_props):  # pragma: no cover - depends on VapourSynth build
        return clip
    try:
        return _call_set_frame_prop(set_props, clip, **props)
    except Exception:  # pragma: no cover - best effort
        return clip


def _guess_default_colourspace(
    clip: Any,
    props: Mapping[str, Any],
    matrix: Optional[int],
    transfer: Optional[int],
    primaries: Optional[int],
    color_range: Optional[int],
    *,
    color_cfg: "ColorConfig | None" = None,
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    if _props_signal_hdr(props):
        return matrix, transfer, primaries, color_range

    vs_module = _get_vapoursynth_module()
    fmt = getattr(clip, "format", None)
    color_family = getattr(fmt, "color_family", None) if fmt is not None else None
    yuv_family = getattr(vs_module, "YUV", object())
    if color_family != yuv_family:
        return matrix, transfer, primaries, color_range

    height = _infer_frame_height(clip, props)
    is_sd = bool(height is not None and height <= 576)
    is_hd = bool(height is not None and height >= 720)
    configured = _resolve_configured_color_defaults(
        color_cfg,
        is_sd=is_sd,
        is_hd=is_hd,
    )

    if matrix is None:
        matrix = configured.get("matrix")
        if matrix is None:
            matrix = int(
                getattr(
                    vs_module,
                    "MATRIX_SMPTE170M" if is_sd else "MATRIX_BT709",
                    6 if is_sd else 1,
                )
            )
    if primaries is None:
        primaries = configured.get("primaries")
        if primaries is None:
            primaries = int(
                getattr(
                    vs_module,
                    "PRIMARIES_SMPTE170M" if is_sd else "PRIMARIES_BT709",
                    6 if is_sd else 1,
                )
            )
    if transfer is None:
        transfer = configured.get("transfer")
        if transfer is None:
            transfer = int(
                getattr(
                    vs_module,
                    "TRANSFER_SMPTE170M" if is_sd else "TRANSFER_BT709",
                    6 if is_sd else 1,
                )
            )
    if color_range is None:
        color_range = configured.get("range")
        if color_range is None:
            color_range = int(getattr(vs_module, "RANGE_LIMITED", 1))

    return matrix, transfer, primaries, color_range


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalise_to_8bit(
    sample_type: Any,
    bits_per_sample: Optional[int],
    value: Optional[float],
) -> Optional[float]:
    if value is None:
        return None
    try:
        sample_type_int = int(sample_type)
    except Exception:
        sample_type_int = None
    if sample_type_int == 1:  # FLOAT
        return float(value) * 255.0
    if bits_per_sample is None or bits_per_sample <= 0:
        return None
    scale = float((1 << bits_per_sample) - 1)
    if scale <= 0.0:
        return None
    return float(value) * 255.0 / scale


def _classify_rgb_range_from_stats(
    sample_type: Any,
    bits_per_sample: Optional[int],
    y_min: Optional[float],
    y_max: Optional[float],
) -> Optional[str]:
    min_8 = _normalise_to_8bit(sample_type, bits_per_sample, y_min)
    max_8 = _normalise_to_8bit(sample_type, bits_per_sample, y_max)
    if min_8 is None or max_8 is None:
        return None

    limited_low = 16.0
    limited_high = 235.0
    limited_tolerance = 12.0
    limited_by_max = max_8 <= limited_high + limited_tolerance
    limited_by_band = (max_8 - min_8) <= 6.0 and min_8 <= limited_low + limited_tolerance
    if limited_by_max or limited_by_band:
        return "limited"

    full_margin_high = 6.0
    full_margin_low = 6.0
    full_high = max_8 >= limited_high + full_margin_high
    full_low = min_8 <= limited_low - full_margin_low
    if full_high and full_low:
        return "full"
    return None


def _detect_rgb_color_range(
    core: Any,
    clip: Any,
    *,
    log: logging.Logger,
    label: str,
    max_samples: int = 6,
) -> tuple[Optional[int], Optional[str]]:
    vs_module = _get_vapoursynth_module()
    std_ns = getattr(core, "std", None)
    plane_stats = getattr(std_ns, "PlaneStats", None) if std_ns is not None else None
    if not callable(plane_stats):
        return (None, None)

    fmt = getattr(clip, "format", None)
    if fmt is None:
        return (None, None)
    if getattr(fmt, "color_family", None) != getattr(vs_module, "RGB", object()):
        return (None, None)

    sample_type = getattr(fmt, "sample_type", None)
    bits_per_sample = getattr(fmt, "bits_per_sample", None)

    try:
        stats_clip = cast(Any, plane_stats(clip))
    except Exception as exc:
        log.debug("[TM RANGE] %s failed to create PlaneStats node: %s", label, exc)
        return (None, None)

    total_frames = getattr(stats_clip, "num_frames", None)
    candidate_indices: set[int] = {0}
    if isinstance(total_frames, int) and total_frames > 0:
        candidate_indices.update(
            {
                max(0, total_frames - 1),
                total_frames // 2,
                total_frames // 4,
                (3 * total_frames) // 4,
            }
        )
    indices = sorted(idx for idx in candidate_indices if isinstance(idx, int) and idx >= 0)
    indices = indices[:max_samples] if max_samples > 0 else indices

    limited_hits = 0
    full_hits = 0

    for idx in indices:
        try:
            frame = stats_clip.get_frame(idx)
        except Exception as exc:
            log.debug("[TM RANGE] %s failed to sample frame %s: %s", label, idx, exc)
            continue
        props = getattr(frame, "props", {})
        classification = _classify_rgb_range_from_stats(
            sample_type,
            bits_per_sample,
            _coerce_float(props.get("PlaneStatsMin")),
            _coerce_float(props.get("PlaneStatsMax")),
        )
        if classification == "limited":
            limited_hits += 1
        elif classification == "full":
            full_hits += 1

    limited_code = int(getattr(vs_module, "RANGE_LIMITED", 1))
    full_code = int(getattr(vs_module, "RANGE_FULL", 0))

    if limited_hits and not full_hits:
        log.info("[TM RANGE] %s detected limited RGB (samples=%d)", label, limited_hits)
        return (limited_code, "plane_stats")
    if full_hits and not limited_hits:
        log.info("[TM RANGE] %s detected full-range RGB (samples=%d)", label, full_hits)
        return (full_code, "plane_stats")
    if limited_hits and full_hits:
        log.warning(
            "[TM RANGE] %s samples span both limited and full ranges (limited=%d full=%d)",
            label,
            limited_hits,
            full_hits,
        )
    else:
        log.debug(
            "[TM RANGE] %s range detection inconclusive (limited=%d full=%d)",
            label,
            limited_hits,
            full_hits,
        )
    return (None, None)


def _compute_luma_bounds(clip: Any) -> tuple[Optional[float], Optional[float]]:
    core = getattr(clip, "core", None)
    std_ns = getattr(core, "std", None)
    plane_stats = getattr(std_ns, "PlaneStats", None) if std_ns is not None else None
    if not callable(plane_stats):
        return (None, None)
    try:
        stats_clip = cast(Any, plane_stats(clip))
    except Exception:
        return (None, None)

    total_frames = getattr(clip, "num_frames", 0) or 0
    if total_frames <= 0:
        indices = [0]
    else:
        indices = list(range(min(total_frames, 3)))

    mins: List[float] = []
    maxs: List[float] = []

    for idx in indices:
        try:
            frame = stats_clip.get_frame(idx)
        except Exception:
            break
        props = getattr(frame, "props", {})
        y_min = _coerce_float(props.get("PlaneStatsMin"))
        y_max = _coerce_float(props.get("PlaneStatsMax"))
        if y_min is not None:
            mins.append(y_min)
        if y_max is not None:
            maxs.append(y_max)

    if not mins or not maxs:
        return (None, None)
    return (min(mins), max(maxs))


def _adjust_color_range_from_signal(
    clip: Any,
    *,
    color_range: Optional[int],
    warning_sink: Optional[List[str]],
    file_name: str | None,
    range_inferred: bool,
    range_from_override: bool,
) -> Optional[int]:
    vs_module = _get_vapoursynth_module()
    limited_code = int(getattr(vs_module, "RANGE_LIMITED", 1))
    full_code = int(getattr(vs_module, "RANGE_FULL", 0))

    # If already limited and appears consistent, keep as-is but warn when signal contradicts metadata.
    y_min, y_max = _compute_luma_bounds(clip)
    if y_min is None or y_max is None:
        if range_inferred or (not range_from_override and color_range in (None, full_code)):
            message = (
                f"[COLOR] {file_name or 'clip'} lacks colour-range metadata and "
                "signal sampling is unavailable; defaulting to limited range."
            )
            logger.warning(message)
            if warning_sink is not None:
                warning_sink.append(message)
            return limited_code
        return color_range

    label = file_name or "clip"

    if range_inferred or color_range in (None, full_code):
        if 12.0 <= y_min <= 20.0 and y_max <= 245.0:
            message = (
                f"[COLOR] {label} lacks reliable colour-range metadata; "
                f"treating as limited (sample min={y_min:.1f}, max={y_max:.1f})."
            )
            logger.warning(message)
            if warning_sink is not None:
                warning_sink.append(message)
            return limited_code
    if color_range == limited_code and (y_min < 4.0 or y_max > 251.0):
        message = (
            f"[COLOR] {label} is tagged limited but sampled values span full range "
            f"(min={y_min:.1f}, max={y_max:.1f}); verify source metadata."
        )
        logger.warning(message)
        if warning_sink is not None:
            warning_sink.append(message)
    return color_range


def normalise_color_metadata(
    clip: Any,
    source_props: Mapping[str, Any] | None,
    *,
    color_cfg: "ColorConfig | None" = None,
    file_name: str | None = None,
    warning_sink: Optional[List[str]] = None,
) -> tuple[
    Any,
    Mapping[str, Any],
    tuple[Optional[int], Optional[int], Optional[int], Optional[int]],
]:
    """Ensure colour metadata is usable, applying heuristics and overrides when needed."""

    props = dict(source_props or {})
    matrix, transfer, primaries, color_range = _resolve_color_metadata(props)

    overrides = _resolve_color_overrides(color_cfg, file_name)
    if "matrix" in overrides:
        matrix = overrides["matrix"]
    if "transfer" in overrides:
        transfer = overrides["transfer"]
    if "primaries" in overrides:
        primaries = overrides["primaries"]
    if "range" in overrides:
        color_range = overrides["range"]
    range_from_override = "range" in overrides
    range_inferred = color_range is None and "range" not in overrides

    matrix, transfer, primaries, color_range = _guess_default_colourspace(
        clip,
        props,
        matrix,
        transfer,
        primaries,
        color_range,
        color_cfg=color_cfg,
    )

    color_range = _adjust_color_range_from_signal(
        clip,
        color_range=color_range,
        warning_sink=warning_sink,
        file_name=file_name,
        range_inferred=range_inferred,
        range_from_override=range_from_override,
    )

    update_props: Dict[str, int] = {}
    if matrix is not None:
        update_props["_Matrix"] = int(matrix)
        props["_Matrix"] = int(matrix)
    if transfer is not None:
        update_props["_Transfer"] = int(transfer)
        props["_Transfer"] = int(transfer)
    if primaries is not None:
        update_props["_Primaries"] = int(primaries)
        props["_Primaries"] = int(primaries)
    if color_range is not None:
        update_props["_ColorRange"] = int(color_range)
        props["_ColorRange"] = int(color_range)

    clip_with_props = _apply_frame_props_dict(clip, update_props)
    return clip_with_props, props, (matrix, transfer, primaries, color_range)


def _normalize_rgb_props(clip: Any, transfer: Optional[int], primaries: Optional[int]) -> Any:
    work = _apply_set_frame_prop(clip, prop="_Matrix", intval=0)
    work = _apply_set_frame_prop(work, prop="_ColorRange", intval=0)
    if transfer is not None:
        work = _apply_set_frame_prop(work, prop="_Transfer", intval=int(transfer))
    if primaries is not None:
        work = _apply_set_frame_prop(work, prop="_Primaries", intval=int(primaries))
    return work


def _deduce_src_csp_hint(transfer: Optional[int], primaries: Optional[int]) -> Optional[int]:
    if transfer == 16 and primaries == 9:
        return 1
    if transfer == 18 and primaries == 9:
        return 2
    return None


_TONEMAP_UNSUPPORTED_KWARGS: set[str] = set()


def _parse_unexpected_kwarg(exc: BaseException) -> tuple[str, ...]:
    """
    Extract unexpected keyword argument names from TypeError/vapoursynth errors.

    Returns:
        tuple[str, ...]: Names of any kwargs rejected by the downstream Tonemap call.
    """

    message = str(exc)
    match = re.search(r"unexpected keyword argument '([^']+)'", message)
    if match:
        return (match.group(1),)

    match = re.search(
        r"does not take argument\(s\) named ([^:]+)",
        message,
        re.IGNORECASE,
    )
    if match:
        raw = match.group(1)
        sanitized = raw.replace(" and ", ",")
        names = [
            part.strip().strip("'\"")
            for part in sanitized.split(",")
        ]
        filtered = tuple(name for name in names if name)
        if filtered:
            return filtered

    return ()


def _call_tonemap_function(
    func: Callable[..., Any],
    clip: Any,
    call_kwargs: Dict[str, Any],
    *,
    file_name: str,
) -> Any:
    usable_kwargs = {
        key: value for key, value in call_kwargs.items() if key not in _TONEMAP_UNSUPPORTED_KWARGS
    }
    max_attempts = len(usable_kwargs) + 1
    attempts = 0
    while True:
        attempts += 1
        try:
            return func(clip, **usable_kwargs)
        except Exception as exc:  # pragma: no cover - vapoursynth raises custom errors
            missing_names = _parse_unexpected_kwarg(exc)
            handled = False
            for missing in missing_names:
                if missing in usable_kwargs:
                    if missing not in _TONEMAP_UNSUPPORTED_KWARGS:
                        _TONEMAP_UNSUPPORTED_KWARGS.add(missing)
                        logger.warning(
                            "[Tonemap compat] %s missing support for '%s'; retrying without it",
                            file_name,
                            missing,
                        )
                    usable_kwargs.pop(missing, None)
                    handled = True
            if handled and attempts < max_attempts:
                continue
            raise


def _apply_post_gamma_levels(
    core: Any,
    clip: Any,
    *,
    gamma: float,
    file_name: str,
    log: logging.Logger,
) -> tuple[Any, bool]:
    if abs(gamma - 1.0) < 1e-4:
        return clip, False

    def _resolve_level_bounds() -> tuple[float | int, float | int, float | int, float | int]:
        fmt = getattr(clip, "format", None)
        if fmt is None:
            return 16, 235, 16, 235
        sample_type = getattr(fmt, "sample_type", None)
        bits = getattr(fmt, "bits_per_sample", None)
        sample_type_val: Optional[int] = None
        if sample_type is not None:
            try:
                sample_type_val = int(sample_type)
            except Exception:
                name = str(getattr(sample_type, "name", "")).upper()
                if name == "INTEGER":
                    sample_type_val = 0
                elif name == "FLOAT":
                    sample_type_val = 1
        min_ratio = 16.0 / 255.0
        max_ratio = 235.0 / 255.0
        if sample_type_val == 1:
            return min_ratio, max_ratio, min_ratio, max_ratio
        if sample_type_val == 0 and isinstance(bits, int) and bits > 0:
            full_scale = float((1 << bits) - 1)
            min_value = round(min_ratio * full_scale)
            max_value = round(max_ratio * full_scale)
            return int(min_value), int(max_value), int(min_value), int(max_value)
        return 16, 235, 16, 235

    min_in, max_in, min_out, max_out = _resolve_level_bounds()
    std_ns = getattr(core, "std", None)
    levels = getattr(std_ns, "Levels", None) if std_ns is not None else None
    if not callable(levels):
        log.warning("[TM GAMMA] %s requested post-gamma but std.Levels is unavailable", file_name)
        return clip, False
    try:
        adjusted = levels(
            clip,
            min_in=min_in,
            max_in=max_in,
            min_out=min_out,
            max_out=max_out,
            gamma=float(gamma),
        )
        log.info("[TM GAMMA] %s applied gamma=%.3f", file_name, gamma)
        return adjusted, True
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("[TM GAMMA] %s failed to apply gamma: %s", file_name, exc)
        return clip, False


def _tonemap_with_retries(
    core: Any,
    rgb_clip: Any,
    *,
    tone_curve: str,
    target_nits: float,
    dst_min: float,
    dpd: int,
    knee_offset: float,
    dpd_preset: str,
    dpd_black_cutoff: float,
    smoothing_period: float,
    scene_threshold_low: float,
    scene_threshold_high: float,
    percentile: float,
    contrast_recovery: float,
    metadata: Optional[int],
    use_dovi: Optional[bool],
    visualize_lut: bool,
    show_clipping: bool,
    src_hint: Optional[int],
    file_name: str,
) -> Any:
    libplacebo = getattr(core, "libplacebo", None)
    tonemap = getattr(libplacebo, "Tonemap", None) if libplacebo is not None else None
    if not callable(tonemap):
        libplacebo = getattr(core, "placebo", None)
        tonemap = getattr(libplacebo, "Tonemap", None) if libplacebo is not None else None
    if not callable(tonemap):
        raise ClipProcessError("libplacebo.Tonemap is unavailable")

    kwargs = dict(
        dst_csp=0,
        dst_prim=1,
        dst_max=float(target_nits),
        dst_min=float(dst_min),
        dynamic_peak_detection=int(dpd),
        smoothing_period=float(smoothing_period),
        scene_threshold_low=float(scene_threshold_low),
        scene_threshold_high=float(scene_threshold_high),
        percentile=float(percentile),
        gamut_mapping=1,
        tone_mapping_function_s=tone_curve,
        tone_mapping_param=float(knee_offset),
        peak_detection_preset=str(dpd_preset),
        black_cutoff=float(dpd_black_cutoff),
        contrast_recovery=float(contrast_recovery),
        visualize_lut=bool(visualize_lut),
        show_clipping=bool(show_clipping),
        log_level=2,
    )
    if metadata is not None:
        kwargs["metadata"] = int(metadata)
    if use_dovi is not None:
        kwargs["use_dovi"] = bool(use_dovi)

    def _attempt(**extra_kwargs: Any) -> Any:
        combined = dict(kwargs)
        combined.update(extra_kwargs)
        return _call_tonemap_function(tonemap, rgb_clip, combined, file_name=file_name)

    if src_hint is not None:
        try:
            return _attempt(src_csp=src_hint)
        except Exception as exc:
            logger.warning("[Tonemap attempt A failed] %s src_csp=%s: %s", file_name, src_hint, exc)
    try:
        return _attempt()
    except Exception as exc:
        logger.warning("[Tonemap attempt B failed] %s infer-from-props: %s", file_name, exc)
    try:
        return _attempt(src_csp=1)
    except Exception as exc:
        raise ClipProcessError(
            f"libplacebo.Tonemap final fallback failed for '{file_name}': {exc}"
        ) from exc


_TONEMAP_PRESETS: Dict[str, Dict[str, float | str | bool]] = {
    "reference": {
        "tone_curve": "bt.2390",
        "target_nits": 100.0,
        "dynamic_peak_detection": True,
        "knee_offset": 0.50,
        "dst_min_nits": 0.18,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.01,
        "smoothing_period": 45.0,
        "scene_threshold_low": 0.8,
        "scene_threshold_high": 2.4,
        "percentile": 99.995,
        "contrast_recovery": 0.30,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
    "bt2390_spec": {
        "tone_curve": "bt.2390",
        "target_nits": 100.0,
        "dynamic_peak_detection": True,
        "knee_offset": 0.50,
        "dst_min_nits": 0.18,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.0,
        "smoothing_period": 25.0,
        "scene_threshold_low": 0.9,
        "scene_threshold_high": 3.0,
        "percentile": 100.0,
        "contrast_recovery": 0.05,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
    "filmic": {
        "tone_curve": "bt.2446a",
        "target_nits": 100.0,
        "dynamic_peak_detection": True,
        "dst_min_nits": 0.16,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.008,
        "knee_offset": 0.58,
        "smoothing_period": 55.0,
        "scene_threshold_low": 0.7,
        "scene_threshold_high": 2.0,
        "percentile": 99.9,
        "contrast_recovery": 0.20,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
    "spline": {
        "tone_curve": "spline",
        "target_nits": 105.0,
        "dynamic_peak_detection": True,
        "dst_min_nits": 0.17,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.009,
        "knee_offset": 0.52,
        "smoothing_period": 35.0,
        "scene_threshold_low": 0.8,
        "scene_threshold_high": 2.2,
        "percentile": 99.98,
        "contrast_recovery": 0.25,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
    "contrast": {
        "tone_curve": "bt.2390",
        "target_nits": 110.0,
        "dynamic_peak_detection": True,
        "dst_min_nits": 0.15,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.008,
        "knee_offset": 0.42,
        "smoothing_period": 30.0,
        "scene_threshold_low": 0.8,
        "scene_threshold_high": 2.2,
        "percentile": 99.99,
        "contrast_recovery": 0.45,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
    "bright_lift": {
        "tone_curve": "bt.2390",
        "target_nits": 130.0,
        "dynamic_peak_detection": True,
        "dst_min_nits": 0.22,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.012,
        "knee_offset": 0.46,
        "smoothing_period": 35.0,
        "scene_threshold_low": 0.8,
        "scene_threshold_high": 2.0,
        "percentile": 99.99,
        "contrast_recovery": 0.50,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
    "highlight_guard": {
        "tone_curve": "bt.2390",
        "target_nits": 90.0,
        "dynamic_peak_detection": True,
        "dst_min_nits": 0.16,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.008,
        "knee_offset": 0.55,
        "smoothing_period": 50.0,
        "scene_threshold_low": 0.9,
        "scene_threshold_high": 3.0,
        "percentile": 99.9,
        "contrast_recovery": 0.15,
        "metadata": "auto",
        "use_dovi": True,
        "visualize_lut": False,
        "show_clipping": False,
    },
}


_METADATA_NAME_TO_CODE = {
    "auto": 0,
    "none": 1,
    "hdr10": 2,
    "hdr10+": 3,
    "hdr10plus": 3,
    "luminance": 4,
    "ciey": 4,
    "cie_y": 4,
}


def _resolve_tonemap_settings(cfg: Any) -> TonemapSettings:
    preset = str(getattr(cfg, "preset", "") or "").strip().lower()
    tone_curve = str(getattr(cfg, "tone_curve", "bt.2390") or "bt.2390")
    provided = getattr(cfg, "_provided_keys", None) or set()
    if preset and preset != "custom":
        preset_vals = _TONEMAP_PRESETS.get(preset) or {}
    else:
        preset_vals = {}

    def _resolve_value(field: str, default: Any) -> Any:
        if preset_vals and field in preset_vals and field not in provided:
            return preset_vals[field]
        return getattr(cfg, field, preset_vals.get(field, default))

    tone_curve = str(_resolve_value("tone_curve", tone_curve))
    target_nits = float(_resolve_value("target_nits", 100.0))
    dpd_flag = bool(_resolve_value("dynamic_peak_detection", True))
    dst_min = float(_resolve_value("dst_min_nits", 0.18))
    knee_offset = float(_resolve_value("knee_offset", 0.5))
    dpd_preset_value = str(_resolve_value("dpd_preset", "high_quality") or "").strip().lower()
    dpd_black_cutoff = float(_resolve_value("dpd_black_cutoff", 0.01))
    smoothing_period = float(_resolve_value("smoothing_period", 20.0))
    scene_threshold_low = float(_resolve_value("scene_threshold_low", 1.0))
    scene_threshold_high = float(_resolve_value("scene_threshold_high", 3.0))
    percentile = float(_resolve_value("percentile", 100.0))
    contrast_recovery = float(_resolve_value("contrast_recovery", 0.0))
    metadata_value = _resolve_value("metadata", "auto")
    use_dovi_value = _resolve_value("use_dovi", None)
    visualize_lut = bool(_resolve_value("visualize_lut", False))
    show_clipping = bool(_resolve_value("show_clipping", False))

    if not dpd_flag:
        dpd_preset_value = "off"
        dpd_black_cutoff = 0.0

    if dpd_preset_value not in {"off", "fast", "balanced", "high_quality"}:
        dpd_preset_value = "off" if not dpd_flag else "high_quality"

    metadata_code: Optional[int]
    if metadata_value is None:
        metadata_code = None
    elif isinstance(metadata_value, (int, float)):
        metadata_code = int(metadata_value)
    else:
        metadata_key = str(metadata_value).strip().lower().replace(" ", "")
        if metadata_key in _METADATA_NAME_TO_CODE:
            metadata_code = _METADATA_NAME_TO_CODE[metadata_key]
        else:
            try:
                metadata_code = int(metadata_key)
            except ValueError:
                metadata_code = 0
            else:
                metadata_code = max(0, min(4, metadata_code))

    if metadata_code is not None and metadata_code < 0:
        metadata_code = 0

    if isinstance(use_dovi_value, str):
        lowered = use_dovi_value.strip().lower()
        if lowered in {"auto", ""}:
            use_dovi_value = None
        elif lowered in {"true", "1", "yes", "on"}:
            use_dovi_value = True
        elif lowered in {"false", "0", "no", "off"}:
            use_dovi_value = False
        else:
            use_dovi_value = None
    elif use_dovi_value is not None:
        use_dovi_value = bool(use_dovi_value)

    return TonemapSettings(
        preset=preset or "custom",
        tone_curve=tone_curve,
        target_nits=float(target_nits),
        dynamic_peak_detection=bool(dpd_flag),
        dst_min_nits=float(dst_min),
        knee_offset=float(knee_offset),
        dpd_preset=dpd_preset_value or ("off" if not dpd_flag else "high_quality"),
        dpd_black_cutoff=float(dpd_black_cutoff),
        smoothing_period=float(smoothing_period),
        scene_threshold_low=float(scene_threshold_low),
        scene_threshold_high=float(scene_threshold_high),
        percentile=float(percentile),
        contrast_recovery=float(contrast_recovery),
        metadata=metadata_code,
        use_dovi=use_dovi_value if isinstance(use_dovi_value, (bool, type(None))) else None,
        visualize_lut=bool(visualize_lut),
        show_clipping=bool(show_clipping),
    )


def resolve_effective_tonemap(cfg: Any) -> Dict[str, Any]:
    """Resolve the effective tonemap preset, curve, and luminance for ``cfg``."""

    settings = _resolve_tonemap_settings(cfg)
    return {
        "preset": settings.preset,
        "tone_curve": settings.tone_curve,
        "target_nits": float(settings.target_nits),
        "dynamic_peak_detection": bool(settings.dynamic_peak_detection),
        "dst_min_nits": float(settings.dst_min_nits),
        "knee_offset": float(settings.knee_offset),
        "dpd_preset": settings.dpd_preset,
        "dpd_black_cutoff": float(settings.dpd_black_cutoff),
        "smoothing_period": float(settings.smoothing_period),
        "scene_threshold_low": float(settings.scene_threshold_low),
        "scene_threshold_high": float(settings.scene_threshold_high),
        "percentile": float(settings.percentile),
        "contrast_recovery": float(settings.contrast_recovery),
        "metadata": settings.metadata,
        "use_dovi": settings.use_dovi,
        "visualize_lut": bool(settings.visualize_lut),
        "show_clipping": bool(settings.show_clipping),
    }


def _format_overlay_text(
    template: str,
    *,
    tone_curve: str,
    dpd: int,
    target_nits: float,
    preset: str,
    dst_min_nits: float,
    knee_offset: float,
    dpd_preset: str,
    dpd_black_cutoff: float,
    post_gamma: float,
    post_gamma_enabled: bool,
    smoothing_period: float,
    scene_threshold_low: float,
    scene_threshold_high: float,
    percentile: float,
    contrast_recovery: float,
    metadata: Optional[int],
    use_dovi: Optional[bool],
    visualize_lut: bool,
    show_clipping: bool,
    reason: Optional[str] = None,
) -> str:
    """
    Format an overlay text template with tonemapping parameters.

    Parameters:
        template (str): A format string that may reference the following keys: `tone_curve`, `curve` (alias),
        `dynamic_peak_detection`, `dpd` (numeric), `dynamic_peak_detection_bool`, `dpd_bool` (boolean),
        `target_nits` (int when whole number, otherwise float), `target_nits_float` (always float),
        `dst_min_nits`, `knee_offset`, `dpd_preset`, `dpd_black_cutoff`, `post_gamma`,
        `post_gamma_enabled`, `preset`, and `reason`.
        tone_curve (str): Name of the tone curve to show.
        dpd (int): Dynamic peak detection flag (0 or 1); boolean aliases are provided in the template values.
        target_nits (float): Target display luminance in nits.
        preset (str): Tonemap preset name.
        reason (Optional[str]): Optional explanatory text included as `reason` in the template.

    Returns:
        Formatted overlay string using the provided template and values; returns `template` unchanged if formatting fails.
    """
    values = {
        "tone_curve": tone_curve,
        "curve": tone_curve,
        "dynamic_peak_detection": dpd,
        "dpd": dpd,
        "dynamic_peak_detection_bool": bool(dpd),
        "dpd_bool": bool(dpd),
        "target_nits": (
            int(target_nits)
            if abs(target_nits - round(target_nits)) < 1e-6
            else target_nits
        ),
        "target_nits_float": target_nits,
        "preset": preset,
        "reason": reason or "",
        "dst_min_nits": dst_min_nits,
        "knee_offset": knee_offset,
        "dpd_preset": dpd_preset,
        "dpd_black_cutoff": dpd_black_cutoff,
        "post_gamma": post_gamma,
        "post_gamma_enabled": post_gamma_enabled,
        "smoothing_period": smoothing_period,
        "scene_threshold_low": scene_threshold_low,
        "scene_threshold_high": scene_threshold_high,
        "percentile": percentile,
        "contrast_recovery": contrast_recovery,
        "metadata": metadata,
        "use_dovi": use_dovi,
        "visualize_lut": visualize_lut,
        "show_clipping": show_clipping,
    }
    try:
        return template.format(**values)
    except Exception:
        return template


def _pick_verify_frame(
    clip: Any,
    cfg: Any,
    *,
    fps: float,
    file_name: str,
    warning_sink: Optional[List[str]] = None,
) -> tuple[int, bool]:
    """
    Select a frame index to use for verification, optionally using an automatic brightness-based sampling.

    Parameters:
        clip (Any): VapourSynth clip to inspect; must expose `num_frames` and support `std.PlaneStats()`.
        cfg (Any): Configuration object with optional attributes:
            - verify_frame (int): explicit frame index to use.
            - verify_auto (bool): enable automatic sampling when not set.
            - verify_start_seconds (float): sampling start time in seconds.
            - verify_step_seconds (float): sampling step in seconds.
            - verify_max_seconds (float): maximum sampling time in seconds.
            - verify_luma_threshold (float): PlaneStatsAverage threshold for selection.
        fps (float): Frames-per-second used to convert seconds to frame indices.
        file_name (str): File name used in log and warning messages.
        warning_sink (Optional[List[str]]): Optional list to append human-readable warning strings.

    Returns:
        tuple[int, bool]: Selected frame index and a flag that is `true` if the frame was chosen by automatic sampling, `false` otherwise.
    """
    num_frames = getattr(clip, "num_frames", 0) or 0
    if num_frames <= 0:
        message = f"[VERIFY] {file_name} has no frames; using frame 0"
        logger.warning(message)
        if warning_sink is not None:
            warning_sink.append(message)
        return 0, False

    manual = getattr(cfg, "verify_frame", None)
    if isinstance(manual, int):
        idx = max(0, min(num_frames - 1, manual))
        logger.info("[VERIFY] %s using configured frame %d", file_name, idx)
        return idx, False

    if not bool(getattr(cfg, "verify_auto", True)):
        idx = max(0, min(num_frames - 1, num_frames // 2))
        logger.info("[VERIFY] %s auto disabled; using middle frame %d", file_name, idx)
        return idx, False

    start_seconds = float(getattr(cfg, "verify_start_seconds", 10.0))
    step_seconds = float(getattr(cfg, "verify_step_seconds", 10.0))
    max_seconds = float(getattr(cfg, "verify_max_seconds", 90.0))
    threshold = float(getattr(cfg, "verify_luma_threshold", 0.10))

    step_frames = (
        max(1, int(round(step_seconds * fps)))
        if fps > 0
        else max(1, int(step_seconds) or 1)
    )
    start_frame = int(round(start_seconds * fps)) if fps > 0 else int(start_seconds)
    start_frame = max(0, min(num_frames - 1, start_frame))
    max_frame = int(round(max_seconds * fps)) if fps > 0 else int(max_seconds)
    max_frame = max(
        start_frame,
        min(num_frames - 1, max_frame if max_frame > 0 else num_frames - 1),
    )

    stats_clip = None
    try:
        stats_clip = clip.std.PlaneStats()
    except Exception as exc:
        message = f"[VERIFY] {file_name} unable to create PlaneStats: {exc}"
        logger.warning(message)
        if warning_sink is not None:
            warning_sink.append(message)
        middle = max(0, min(num_frames - 1, num_frames // 2))
        return middle, False

    best_idx: Optional[int] = None
    best_avg = -1.0
    for idx in range(start_frame or 1, max_frame + 1, step_frames):
        try:
            frame = stats_clip.get_frame(idx)
        except Exception:
            continue
        avg = float(frame.props.get("PlaneStatsAverage", 0.0))
        if avg >= threshold:
            logger.info(
                "[VERIFY] %s auto-picked frame %d (avg=%.4f) start=%d step=%d",
                file_name,
                idx,
                avg,
                start_frame,
                step_frames,
            )
            return idx, True
        if avg > best_avg:
            best_idx, best_avg = idx, avg

    if best_idx is not None:
        logger.info(
            "[VERIFY] %s brightest sampled frame %d (avg=%.4f) threshold %.3f",
            file_name,
            best_idx,
            best_avg,
            threshold,
        )
        return best_idx, True

    middle = max(0, min(num_frames - 1, num_frames // 2))
    logger.info("[VERIFY] %s fallback to middle frame %d", file_name, middle)
    return middle, False


def _compute_verification(
    core: Any,
    tonemapped: Any,
    naive: Any,
    frame_idx: int,
    *,
    auto_selected: bool,
) -> VerificationResult:
    expr = core.std.Expr([tonemapped, naive], "x y - abs")
    stats = core.std.PlaneStats(expr)
    props = stats.get_frame(frame_idx).props
    average = float(props.get("PlaneStatsAverage", 0.0))
    maximum = float(props.get("PlaneStatsMax", 0.0))
    fmt = getattr(expr, "format", None)
    bits = getattr(fmt, "bits_per_sample", None) if fmt is not None else None
    sample_type = getattr(fmt, "sample_type", None) if fmt is not None else None

    is_integer_format = False
    if sample_type is not None:
        name = getattr(sample_type, "name", None)
        if isinstance(name, str):
            is_integer_format = name.upper() == "INTEGER"
        else:
            try:
                is_integer_format = int(sample_type) == 0
            except Exception:
                is_integer_format = False

    if is_integer_format and isinstance(bits, int) and bits > 0:
        peak = float((1 << bits) - 1)
        if peak > 0.0:
            average /= peak
            maximum /= peak
    return VerificationResult(
        frame=frame_idx,
        average=average,
        maximum=maximum,
        auto_selected=auto_selected,
    )


def process_clip_for_screenshot(
    clip: Any,
    file_name: str,
    cfg: Any,
    *,
    enable_overlay: bool = True,
    enable_verification: bool = True,
    logger_override: Optional[logging.Logger] = None,
    warning_sink: Optional[List[str]] = None,
    debug_color: bool = False,
) -> ClipProcessResult:
    """
    Prepare a VapourSynth clip for screenshot export by applying HDR->SDR tonemapping, optional overlay text, and optional verification against a naive SDR conversion.

    Parameters:
        clip: VapourSynth clip to process.
        file_name (str): Source filename used in log messages.
        cfg: Configuration object supplying tonemap and verification settings (e.g., enable_tonemap, overlay_text_template, overlay_enabled, verify_enabled, strict, tonemap preset/parameters).
        enable_overlay (bool): Runtime override to enable or disable overlay generation.
        enable_verification (bool): Runtime override to enable or disable verification.
        logger_override (Optional[logging.Logger]): Logger to use instead of the module logger.
        warning_sink (Optional[List[str]]): Optional list to which the function will append human-readable warning messages produced during frame selection/verification.

    Returns:
        ClipProcessResult: Container with the processed clip, tonemap metadata (TonemapInfo), optional overlay text, optional verification results (VerificationResult), and a snapshot of source frame properties.

    Raises:
        ClipProcessError: If VapourSynth core/resize namespaces or required resize methods are missing, if clip has no associated core, or if verification fails in strict mode; also used for other processing failures.
    """

    log = logger_override or logger
    source_props = _snapshot_frame_props(clip)
    original_props = dict(source_props)
    clip, source_props, color_tuple = normalise_color_metadata(
        clip,
        source_props,
        color_cfg=cfg,
        file_name=file_name,
        warning_sink=warning_sink,
    )
    debug_artifacts: Optional[ColorDebugArtifacts] = None
    if debug_color:
        debug_artifacts = ColorDebugArtifacts(
            normalized_clip=clip,
            normalized_props=dict(source_props),
            original_props=original_props,
            color_tuple=color_tuple,
        )
    vs_module = _get_vapoursynth_module()
    core = getattr(clip, "core", None)
    if core is None:
        core = getattr(vs_module, "core", None)
    if core is None:
        raise ClipProcessError("Clip has no associated VapourSynth core")

    tonemap_settings = _resolve_tonemap_settings(cfg)
    preset = tonemap_settings.preset
    tone_curve = tonemap_settings.tone_curve
    target_nits = tonemap_settings.target_nits
    dpd = int(tonemap_settings.dynamic_peak_detection)
    dst_min = tonemap_settings.dst_min_nits
    post_gamma_cfg_enabled = bool(getattr(cfg, "post_gamma_enable", False))
    post_gamma_value = float(getattr(cfg, "post_gamma", 1.0))
    overlay_enabled = enable_overlay and bool(getattr(cfg, "overlay_enabled", True)) and not debug_color
    verify_enabled = enable_verification and bool(getattr(cfg, "verify_enabled", True))
    strict = bool(getattr(cfg, "strict", False))

    matrix_in, transfer_in, primaries_in, color_range_in = color_tuple
    tonemap_enabled = bool(getattr(cfg, "enable_tonemap", True))
    is_hdr_source = _props_signal_hdr(source_props)
    is_hdr = tonemap_enabled and is_hdr_source

    range_limited = getattr(vs_module, "RANGE_LIMITED", 1)
    range_full = getattr(vs_module, "RANGE_FULL", 0)

    tonemap_reason = None
    if not is_hdr:
        if not tonemap_enabled and is_hdr_source:
            tonemap_reason = "Tonemap disabled"
        elif not is_hdr_source:
            tonemap_reason = "SDR source"
        else:
            tonemap_reason = "Tonemap bypass"

    source_range_value: Optional[int]
    try:
        source_range_value = int(color_range_in) if color_range_in is not None else None
    except Exception:
        source_range_value = None
    if source_range_value not in (range_full, range_limited):
        source_range_value = None

    tonemap_info = TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=dpd,
        target_nits=target_nits,
        dst_min_nits=dst_min,
        src_csp_hint=None,
        reason=tonemap_reason,
        output_color_range=source_range_value,
        range_detection="source_props" if source_range_value is not None else None,
        knee_offset=tonemap_settings.knee_offset,
        dpd_preset=tonemap_settings.dpd_preset,
        dpd_black_cutoff=tonemap_settings.dpd_black_cutoff if dpd else 0.0,
        post_gamma=post_gamma_value if post_gamma_cfg_enabled else 1.0,
        post_gamma_enabled=False,
        smoothing_period=tonemap_settings.smoothing_period,
        scene_threshold_low=tonemap_settings.scene_threshold_low,
        scene_threshold_high=tonemap_settings.scene_threshold_high,
        percentile=tonemap_settings.percentile,
        contrast_recovery=tonemap_settings.contrast_recovery,
        metadata=tonemap_settings.metadata,
        use_dovi=tonemap_settings.use_dovi,
        visualize_lut=tonemap_settings.visualize_lut,
        show_clipping=tonemap_settings.show_clipping,
    )
    overlay_text = None
    verification: Optional[VerificationResult] = None

    if not is_hdr:
        log.info(
            "[TM BYPASS] %s reason=%s Matrix=%s Transfer=%s Primaries=%s Range=%s",
            file_name,
            tonemap_reason,
            matrix_in,
            transfer_in,
            primaries_in,
            color_range_in,
        )
        return ClipProcessResult(
            clip=clip,
            tonemap=tonemap_info,
            overlay_text=overlay_text,
            verification=None,
            source_props=source_props,
            debug=debug_artifacts,
        )

    resize_ns = getattr(core, "resize", None)
    if resize_ns is None:
        raise ClipProcessError("VapourSynth core missing resize namespace")
    spline36 = getattr(resize_ns, "Spline36", None)
    if not callable(spline36):
        raise ClipProcessError("VapourSynth resize.Spline36 is unavailable")

    log.info(
        "[TM INPUT] %s Matrix=%s Transfer=%s Primaries=%s Range=%s",
        file_name,
        matrix_in,
        transfer_in,
        primaries_in,
        color_range_in,
    )

    rgb16 = spline36(
        clip,
        format=getattr(vs_module, "RGB48"),
        matrix_in=matrix_in if matrix_in is not None else 1,
        transfer_in=transfer_in if transfer_in is not None else None,
        primaries_in=primaries_in if primaries_in is not None else None,
        range_in=color_range_in if color_range_in is not None else range_limited,
        dither_type="error_diffusion",
    )
    rgb16 = _normalize_rgb_props(rgb16, transfer_in, primaries_in)

    src_hint = _deduce_src_csp_hint(transfer_in, primaries_in)
    tonemapped = _tonemap_with_retries(
        core,
        rgb16,
        tone_curve=tone_curve,
        target_nits=target_nits,
        dst_min=dst_min,
        dpd=dpd,
        knee_offset=tonemap_settings.knee_offset,
        dpd_preset=tonemap_settings.dpd_preset,
        dpd_black_cutoff=tonemap_settings.dpd_black_cutoff,
        smoothing_period=tonemap_settings.smoothing_period,
        scene_threshold_low=tonemap_settings.scene_threshold_low,
        scene_threshold_high=tonemap_settings.scene_threshold_high,
        percentile=tonemap_settings.percentile,
        contrast_recovery=tonemap_settings.contrast_recovery,
        metadata=tonemap_settings.metadata,
        use_dovi=tonemap_settings.use_dovi,
        visualize_lut=tonemap_settings.visualize_lut,
        show_clipping=tonemap_settings.show_clipping,
        src_hint=src_hint,
        file_name=file_name,
    )

    tonemapped = _apply_set_frame_prop(
        tonemapped,
        prop="_Tonemapped",
        data=f"placebo:{tone_curve},dpd={dpd},dst_max={target_nits}",
    )
    tonemapped = _normalize_rgb_props(tonemapped, transfer=1, primaries=1)
    applied_post_gamma = False
    if post_gamma_cfg_enabled:
        tonemapped, applied_post_gamma = _apply_post_gamma_levels(
            core,
            tonemapped,
            gamma=post_gamma_value,
            file_name=file_name,
            log=log,
        )

    detected_range, detection_source = _detect_rgb_color_range(
        core,
        tonemapped,
        log=log,
        label=file_name,
    )

    effective_range: Optional[int] = detected_range
    fallback_source = detection_source
    if (
        effective_range is None
        and color_range_in is not None
        and color_range_in in (range_full, range_limited)
    ):
        try:
            effective_range = int(color_range_in)
        except Exception:
            effective_range = None
        else:
            fallback_source = fallback_source or "source_props"

    source_range_int: Optional[int] = None
    if color_range_in is not None and color_range_in in (range_full, range_limited):
        try:
            source_range_int = int(color_range_in)
        except Exception:
            source_range_int = None

    if effective_range is not None:
        range_value = int(effective_range)
        changed_from_source = (
            source_range_int is not None and source_range_int != range_value
        )
        if (
            changed_from_source
            and source_range_int == range_limited
            and range_value == range_full
        ):
            log.info(
                "[TM RANGE] %s plane-stats suggested full range; retaining limited metadata",
                file_name,
            )
            fallback_source = (fallback_source or "plane_stats") + "_conflict"
            assert source_range_int is not None
            effective_range = source_range_int
            range_value = int(source_range_int)
            changed_from_source = False
        tonemapped = _apply_set_frame_prop(
            tonemapped,
            prop="_ColorRange",
            intval=range_value,
        )
        if changed_from_source:
            log.info(
                "[TM RANGE] %s remapping colour range %s\u2192%s",
                file_name,
                color_range_in,
                effective_range,
            )
            if source_range_int is not None:
                tonemapped = _apply_set_frame_prop(
                    tonemapped,
                    prop="_SourceColorRange",
                    intval=source_range_int,
                )

    tonemap_info = TonemapInfo(
        applied=True,
        tone_curve=tone_curve,
        dpd=dpd,
        target_nits=target_nits,
        dst_min_nits=dst_min,
        src_csp_hint=src_hint,
        reason=None,
        output_color_range=effective_range,
        range_detection=fallback_source,
        knee_offset=tonemap_settings.knee_offset,
        dpd_preset=tonemap_settings.dpd_preset,
        dpd_black_cutoff=tonemap_settings.dpd_black_cutoff if dpd else 0.0,
        post_gamma=post_gamma_value if applied_post_gamma else 1.0,
        post_gamma_enabled=applied_post_gamma,
        smoothing_period=tonemap_settings.smoothing_period,
        scene_threshold_low=tonemap_settings.scene_threshold_low,
        scene_threshold_high=tonemap_settings.scene_threshold_high,
        percentile=tonemap_settings.percentile,
        contrast_recovery=tonemap_settings.contrast_recovery,
        metadata=tonemap_settings.metadata,
        use_dovi=tonemap_settings.use_dovi,
        visualize_lut=tonemap_settings.visualize_lut,
        show_clipping=tonemap_settings.show_clipping,
    )

    overlay_template = str(
        getattr(
            cfg,
            "overlay_text_template",
            "Tonemapping Algorithm: {tone_curve} dpd = {dynamic_peak_detection} dst = {target_nits} nits",
        )
    )
    if overlay_enabled:
        overlay_text = _format_overlay_text(
            overlay_template,
            tone_curve=tone_curve,
            dpd=dpd,
            target_nits=target_nits,
            preset=preset,
            dst_min_nits=dst_min,
            knee_offset=tonemap_settings.knee_offset,
            dpd_preset=tonemap_settings.dpd_preset,
            dpd_black_cutoff=tonemap_settings.dpd_black_cutoff if dpd else 0.0,
            post_gamma=post_gamma_value,
            post_gamma_enabled=applied_post_gamma,
            smoothing_period=tonemap_settings.smoothing_period,
            scene_threshold_low=tonemap_settings.scene_threshold_low,
            scene_threshold_high=tonemap_settings.scene_threshold_high,
            percentile=tonemap_settings.percentile,
            contrast_recovery=tonemap_settings.contrast_recovery,
            metadata=tonemap_settings.metadata,
            use_dovi=tonemap_settings.use_dovi,
            visualize_lut=tonemap_settings.visualize_lut,
            show_clipping=tonemap_settings.show_clipping,
            reason="HDR",
        )
        log.info("[OVERLAY] %s using text '%s'", file_name, overlay_text)

    log.info(
        "[TM APPLIED] %s curve=%s dpd=%d dst_max=%.2f hint=%s",
        file_name,
        tone_curve,
        dpd,
        target_nits,
        src_hint,
    )

    if verify_enabled:
        fps_num = getattr(tonemapped, "fps_num", None)
        fps_den = getattr(tonemapped, "fps_den", None)
        fps = (
            (fps_num / fps_den)
            if isinstance(fps_num, int)
            and isinstance(fps_den, int)
            and fps_den
            else 0.0
        )
        frame_idx, auto = _pick_verify_frame(
            tonemapped,
            cfg,
            fps=fps,
            file_name=file_name,
            warning_sink=warning_sink,
        )
        try:
            naive = spline36(
                clip,
                format=getattr(vs_module, "RGB24"),
                matrix_in=matrix_in if matrix_in is not None else 1,
                transfer_in=transfer_in if transfer_in is not None else None,
                primaries_in=primaries_in if primaries_in is not None else None,
                range_in=color_range_in if color_range_in is not None else range_limited,
                transfer=1,
                primaries=1,
                range=range_full,
                dither_type="error_diffusion",
            )
            point = getattr(resize_ns, "Point", None)
            if not callable(point):
                raise ClipProcessError("VapourSynth resize.Point is unavailable")
            tm_rgb24 = point(
                tonemapped,
                format=getattr(vs_module, "RGB24"),
                range=range_full,
                dither_type="error_diffusion",
            )
            verification = _compute_verification(
                core,
                tm_rgb24,
                naive,
                frame_idx,
                auto_selected=auto,
            )
            log.info(
                "[VERIFY] %s frame=%d avg=%.4f max=%.4f vs naive SDR",
                file_name,
                verification.frame,
                verification.average,
                verification.maximum,
            )
        except Exception as exc:
            message = f"Verification failed for '{file_name}': {exc}"
            log.error("[VERIFY] %s", message)
            if strict:
                raise ClipProcessError(message) from exc

    return ClipProcessResult(
        clip=tonemapped,
        tonemap=tonemap_info,
        overlay_text=overlay_text,
        verification=verification,
        source_props=source_props,
        debug=debug_artifacts,
    )
