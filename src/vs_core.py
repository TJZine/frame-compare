from __future__ import annotations

"""VapourSynth integration helpers used by the frame comparison tool."""

import importlib
import os
import sys
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple
from .tonemap.config import TMConfig
from .tonemap.core import apply_tonemap
from .tonemap.verify import run_verification
from .tonemap.exceptions import TonemapError

_VS_MODULE_NAME = "vapoursynth"
_ENV_VAR = "VAPOURSYNTH_PYTHONPATH"
_EXTRA_SEARCH_PATHS: list[str] = []
_vs_module: Any | None = None


logger = logging.getLogger(__name__)


class ClipInitError(RuntimeError):
    """Raised when a clip cannot be created via VapourSynth."""


class ClipProcessError(RuntimeError):
    """Raised when screenshot preparation fails."""




def _normalise_search_path(path: str) -> str:
    expanded = Path(path).expanduser()
    try:
        return str(expanded.resolve())
    except (OSError, RuntimeError):
        return str(expanded)


def _add_search_paths(paths: Iterable[str]) -> None:
    added = False
    for raw in paths:
        if not raw:
            continue
        resolved = _normalise_search_path(raw)
        if resolved in _EXTRA_SEARCH_PATHS:
            continue
        _EXTRA_SEARCH_PATHS.append(resolved)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        added = True


def _load_env_paths_from_env() -> None:
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        return
    entries = [entry.strip() for entry in raw.split(os.pathsep)]
    _add_search_paths(entry for entry in entries if entry)


def configure(*, search_paths: Sequence[str] | None = None) -> None:
    if search_paths:
        _add_search_paths(search_paths)


def _build_missing_vs_message() -> str:
    details = []
    if _EXTRA_SEARCH_PATHS:
        details.append("Tried extra search paths: " + ", ".join(_EXTRA_SEARCH_PATHS))
    details.append(
        "Install VapourSynth for this interpreter or expose it via runtime.vapoursynth_python_paths in config.toml."
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
    return vs_module.core


def _resolve_source(core: Any) -> Any:
    lsmas = getattr(core, "lsmas", None)
    if lsmas is None:
        raise ClipInitError("VapourSynth core is missing the lsmas plugin")
    source = getattr(lsmas, "LWLibavSource", None)
    if not callable(source):
        raise ClipInitError("lsmas.LWLibavSource is not callable")
    return source


def _ensure_std_namespace(clip: Any, error: RuntimeError) -> Any:
    std = getattr(clip, "std", None)
    if std is None:
        raise error
    return std


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
    source = _resolve_source(resolved_core)

    path_obj = Path(path)
    cache_root = Path(cache_dir) if cache_dir is not None else path_obj.parent
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise ClipInitError(f"Failed to prepare cache directory '{cache_root}': {exc}") from exc

    cache_file = cache_root / f"{path_obj.name}.lwi"

    try:
        clip = source(str(path_obj), cachefile=str(cache_file))
    except Exception as exc:  # pragma: no cover - exercised via mocks
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


def _coerce_tonemap_config(cfg: Any) -> TMConfig:
    if isinstance(cfg, TMConfig):
        return cfg.resolved()
    if cfg is None:
        return TMConfig().resolved()
    if isinstance(cfg, Mapping):
        return TMConfig.from_mapping(cfg).resolved()

    base = TMConfig()
    overrides: dict[str, Any] = {}
    attr_map = {
        'func': 'func',
        'tone_mapping': 'func',
        'preset': 'preset',
        'dpd': 'dpd',
        'dst_max': 'dst_max',
        'target_nits': 'dst_max',
        'dst_min': 'dst_min',
        'gamut_mapping': 'gamut_mapping',
        'smoothing_period': 'smoothing_period',
        'scene_threshold_low': 'scene_threshold_low',
        'scene_threshold_high': 'scene_threshold_high',
        'overlay': 'overlay',
        'verify': 'verify',
        'verify_metric': 'verify_metric',
        'verify_frame': 'verify_frame',
        'verify_auto_search': 'verify_auto_search',
        'verify_search_max': 'verify_search_max',
        'verify_search_step': 'verify_search_step',
        'verify_start_frame': 'verify_start_frame',
        'verify_luma_thresh': 'verify_luma_thresh',
        'use_dovi': 'use_dovi',
        'always_try_placebo': 'always_try_placebo',
        'dest_primaries': 'dst_primaries',
        'dst_primaries': 'dst_primaries',
        'dest_transfer': 'dst_transfer',
        'dst_transfer': 'dst_transfer',
        'dest_matrix': 'dst_matrix',
        'dst_matrix': 'dst_matrix',
        'dest_range': 'dst_range',
        'dst_range': 'dst_range',
    }
    for attr, canonical in attr_map.items():
        if hasattr(cfg, attr):
            overrides[canonical] = getattr(cfg, attr)
    if not overrides:
        return base.resolved()
    return base.merged(**overrides).resolved()


def process_clip_for_screenshot(clip: Any, file_name: str, cfg: Any) -> Any:
    """Apply tonemapping with the modern subsystem when required."""

    try:
        tm_cfg = _coerce_tonemap_config(cfg)
    except Exception as exc:
        raise ClipProcessError(f"Invalid tonemap configuration for {file_name}: {exc}") from exc

    try:
        result = apply_tonemap(clip, tm_cfg)
    except TonemapError as exc:
        raise ClipProcessError(f"Tonemap application failed for {file_name}: {exc}") from exc

    if tm_cfg.verify:
        try:
            run_verification(clip, result.clip, result.fallback_clip, tm_cfg)
        except Exception as exc:
            logger.debug("tonemap verification failed for %s: %s", file_name, exc)
    return result.clip
