"""Overlay helpers for tonemap diagnostics."""

from __future__ import annotations

import logging
from typing import Any

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
    try:
        return draw(clip, "\n".join(build_overlay_lines(cfg)), alignment=9, scale=1)
    except Exception as exc:  # pragma: no cover - depends on runtime text plugin
        logger.debug("overlay failed: %s", exc)
        return clip
