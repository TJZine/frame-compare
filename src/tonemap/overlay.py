"""Overlay helpers for tonemap diagnostics."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .config import TMConfig

logger = logging.getLogger(__name__)


def build_overlay_lines(cfg: TMConfig) -> list[str]:
    dpd = "on" if cfg.dpd else "off"
    dovi = "on" if cfg.use_dovi else "off"
    line_1 = f"TM {cfg.func} dpd={dpd} dst={cfg.dst_min:.3f}-{cfg.dst_max:.1f}nits"
    line_2 = f"gamut={cfg.gamut_mapping} smooth={cfg.smoothing_period} scene={cfg.scene_threshold_low:.2f}/{cfg.scene_threshold_high:.2f} DoVi={dovi} tag={cfg.fingerprint()}"
    return [line_1, line_2]


def apply_overlay(clip: Any, cfg: TMConfig) -> Any:
    if not cfg.overlay:
        return clip
    core = getattr(clip, "core", None)
    if core is None:
        logger.debug("overlay skipped: clip has no core")
        return clip
    text_ns = getattr(core, "text", None) or getattr(core, "sub", None)
    draw = getattr(text_ns, "Text", None) if text_ns is not None else None
    if not callable(draw):
        logger.debug("overlay skipped: VapourSynth text.Text unavailable")
        return clip

    limited_clip = clip
    restore_range: Optional[int] = None
    resize_ns = getattr(core, "resize", None)
    point = getattr(resize_ns, "Point", None) if resize_ns is not None else None

    def _normalise_range(value: Any) -> Optional[int]:
        if isinstance(value, int):
            return value if value in (0, 1) else None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"0", "full", "range_full"}:
                return 0
            if lowered in {"1", "limited", "range_limited"}:
                return 1
        return None

    limited_value = 1
    full_value = 0
    try:  # pragma: no cover - optional dependency may be absent in tests
        import vapoursynth as vs  # type: ignore
    except Exception:  # pragma: no cover - handled by fallbacks
        vs = None
    if vs is not None:
        limited_value = getattr(vs, "RANGE_LIMITED", limited_value)
        full_value = getattr(vs, "RANGE_FULL", full_value)

    if callable(point):
        try:
            limited_clip = point(clip, range=limited_value, dither_type="none")
            target_range = _normalise_range(cfg.dst_range)
            if target_range in (None, 0):
                restore_range = full_value
        except Exception:  # pragma: no cover - defensive
            logger.debug("overlay limited-range shim failed", exc_info=True)
            limited_clip = clip
            restore_range = None
    else:
        logger.debug("overlay skipped: resize.Point unavailable for range shim")

    try:
        stamped = draw(limited_clip, "\n".join(build_overlay_lines(cfg)), alignment=9, scale=1)
    except Exception as exc:  # pragma: no cover - depends on runtime text plugin
        logger.debug("overlay failed: %s", exc)
        return clip

    if callable(point) and restore_range is not None:
        try:
            stamped = point(stamped, range=restore_range, dither_type="none")
        except Exception:  # pragma: no cover - defensive
            logger.debug("overlay range restore failed", exc_info=True)
    return stamped
