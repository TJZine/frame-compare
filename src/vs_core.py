"""VapourSynth integration helpers used by the frame comparison tool."""

from __future__ import annotations

import importlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Mapping, Optional, Sequence, Tuple

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


@dataclass(frozen=True)
class VerificationResult:
    """Result of comparing a tonemapped clip against a naive SDR convert."""

    frame: int
    average: float
    maximum: float
    auto_selected: bool


@dataclass(frozen=True)
class ClipProcessResult:
    """Container for processed clip and metadata."""

    clip: Any
    tonemap: TonemapInfo
    overlay_text: Optional[str]
    verification: Optional[VerificationResult]
    source_props: Mapping[str, Any]


_MATRIX_NAME_TO_CODE = {
    "rgb": 0,
    "0": 0,
    "bt709": 1,
    "bt.709": 1,
    "709": 1,
    "bt2020": 9,
    "bt.2020": 9,
    "2020": 9,
    "2020ncl": 9,
}

_PRIMARIES_NAME_TO_CODE = {
    "bt709": 1,
    "bt.709": 1,
    "709": 1,
    "bt2020": 9,
    "bt.2020": 9,
    "2020": 9,
}

_TRANSFER_NAME_TO_CODE = {
    "bt1886": 1,
    "gamma2.2": 1,
    "st2084": 16,
    "smpte2084": 16,
    "pq": 16,
    "hlg": 18,
    "arib-b67": 18,
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
    9: "bt2020",
}

_PRIMARIES_CODE_LABELS = {
    1: "bt709",
    9: "bt2020",
}

_TRANSFER_CODE_LABELS = {
    1: "bt1886",
    16: "st2084",
    18: "hlg",
}

_RANGE_CODE_LABELS = {
    0: "full",
    1: "limited",
}


def _describe_code(value: Optional[int], mapping: Mapping[int, str], default: str = "auto") -> str:
    if value is None:
        return default
    try:
        return mapping[int(value)]
    except Exception:
        return str(value)


def _normalise_search_path(path: str) -> str:
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
    details = []
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


def _resolve_color_metadata(
    props: Mapping[str, Any],
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    matrix = _coerce_prop(
        props.get("_Matrix") or props.get("Matrix"),
        _MATRIX_NAME_TO_CODE,
    )
    primaries = _coerce_prop(
        props.get("_Primaries") or props.get("Primaries"),
        _PRIMARIES_NAME_TO_CODE,
    )
    transfer = _coerce_prop(
        props.get("_Transfer") or props.get("Transfer"),
        _TRANSFER_NAME_TO_CODE,
    )
    color_range = _coerce_prop(
        props.get("_ColorRange") or props.get("ColorRange"),
        _RANGE_NAME_TO_CODE,
    )
    return matrix, transfer, primaries, color_range


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


def _tonemap_with_retries(
    core: Any,
    rgb_clip: Any,
    *,
    tone_curve: str,
    target_nits: float,
    dst_min: float,
    dpd: int,
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
        smoothing_period=2.0,
        scene_threshold_low=0.15,
        scene_threshold_high=0.30,
        gamut_mapping=1,
        tone_mapping_function_s=tone_curve,
        use_dovi=True,
        log_level=2,
    )

    if src_hint is not None:
        try:
            return tonemap(rgb_clip, src_csp=src_hint, **kwargs)
        except Exception as exc:
            logger.warning("[Tonemap attempt A failed] %s src_csp=%s: %s", file_name, src_hint, exc)
    try:
        return tonemap(rgb_clip, **kwargs)
    except Exception as exc:
        logger.warning("[Tonemap attempt B failed] %s infer-from-props: %s", file_name, exc)
    try:
        return tonemap(rgb_clip, src_csp=1, **kwargs)
    except Exception as exc:
        raise ClipProcessError(
            f"libplacebo.Tonemap final fallback failed for '{file_name}': {exc}"
        ) from exc


_TONEMAP_PRESETS = {
    "reference": {"tone_curve": "bt.2390", "target_nits": 100.0, "dynamic_peak_detection": True},
    "contrast": {"tone_curve": "mobius", "target_nits": 120.0, "dynamic_peak_detection": False},
    "filmic": {"tone_curve": "hable", "target_nits": 100.0, "dynamic_peak_detection": True},
}


def _resolve_tonemap_settings(cfg: Any) -> tuple[str, str, float, int, float]:
    preset = str(getattr(cfg, "preset", "") or "").strip().lower()
    tone_curve = str(getattr(cfg, "tone_curve", "bt.2390") or "bt.2390")
    target_nits = float(getattr(cfg, "target_nits", 100.0))
    dpd_flag = bool(getattr(cfg, "dynamic_peak_detection", True))
    dst_min = float(getattr(cfg, "dst_min_nits", 0.1))

    provided = getattr(cfg, "_provided_keys", None)

    def _was_provided(field: str) -> bool:
        if provided is None:
            return True
        return field in provided

    if preset and preset != "custom":
        preset_vals = _TONEMAP_PRESETS.get(preset)
        if preset_vals:
            if not _was_provided("tone_curve"):
                tone_curve = str(preset_vals["tone_curve"])
            if not _was_provided("target_nits"):
                target_nits = float(preset_vals["target_nits"])
            if not _was_provided("dynamic_peak_detection"):
                dpd_flag = bool(preset_vals["dynamic_peak_detection"])

    return preset or "custom", tone_curve, target_nits, int(dpd_flag), dst_min


def _format_overlay_text(
    template: str,
    *,
    tone_curve: str,
    dpd: int,
    target_nits: float,
    preset: str,
    reason: Optional[str] = None,
) -> str:
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
) -> ClipProcessResult:
    """Prepare *clip* for screenshot export (tonemap, overlay metadata, verify)."""

    log = logger_override or logger
    source_props = _snapshot_frame_props(clip)
    vs_module = _get_vapoursynth_module()
    core = getattr(clip, "core", None)
    if core is None:
        core = getattr(vs_module, "core", None)
    if core is None:
        raise ClipProcessError("Clip has no associated VapourSynth core")

    preset, tone_curve, target_nits, dpd, dst_min = _resolve_tonemap_settings(cfg)
    overlay_enabled = enable_overlay and bool(getattr(cfg, "overlay_enabled", True))
    verify_enabled = enable_verification and bool(getattr(cfg, "verify_enabled", True))
    strict = bool(getattr(cfg, "strict", False))

    matrix_in, transfer_in, primaries_in, color_range_in = _resolve_color_metadata(source_props)
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

    tonemap_info = TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=dpd,
        target_nits=target_nits,
        dst_min_nits=dst_min,
        src_csp_hint=None,
        reason=tonemap_reason,
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
        src_hint=src_hint,
        file_name=file_name,
    )

    tonemapped = _apply_set_frame_prop(
        tonemapped,
        prop="_Tonemapped",
        data=f"placebo:{tone_curve},dpd={dpd},dst_max={target_nits}",
    )
    tonemapped = _apply_set_frame_prop(tonemapped, prop="_ColorRange", intval=0)
    tonemapped = _normalize_rgb_props(tonemapped, transfer=1, primaries=1)

    tonemap_info = TonemapInfo(
        applied=True,
        tone_curve=tone_curve,
        dpd=dpd,
        target_nits=target_nits,
        dst_min_nits=dst_min,
        src_csp_hint=src_hint,
        reason=None,
    )

    overlay_template = str(
        getattr(
            cfg,
            "overlay_text_template",
            "Tonemapping Algorithm: {tone_curve} dpd = {dynamic_peak_detection} dst = {target_nits} nits",
        )
    )
    overlay_mode = str(getattr(cfg, "overlay_mode", "minimal")).strip().lower()
    if overlay_enabled:
        base_overlay = _format_overlay_text(
            overlay_template,
            tone_curve=tone_curve,
            dpd=dpd,
            target_nits=target_nits,
            preset=preset,
            reason="HDR",
        )
        if overlay_mode == "diagnostic":
            source_summary = (
                f"Source: matrix={_describe_code(matrix_in, _MATRIX_CODE_LABELS)} "
                f"transfer={_describe_code(transfer_in, _TRANSFER_CODE_LABELS)} "
                f"primaries={_describe_code(primaries_in, _PRIMARIES_CODE_LABELS)} "
                f"range={_describe_code(color_range_in, _RANGE_CODE_LABELS)}"
            )
            tonemap_summary = (
                f"Tonemap: preset={preset} curve={tone_curve} dpd={'on' if dpd else 'off'} "
                f"target={target_nits}nits dst_min={dst_min}"
            )
            diagnostic_lines = [line for line in (base_overlay, source_summary, tonemap_summary) if line]
            overlay_text = "\n".join(diagnostic_lines)
        else:
            overlay_text = base_overlay
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
    )
