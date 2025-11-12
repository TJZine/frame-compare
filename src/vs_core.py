"""Compatibility shim for the legacy ``src.vs_core`` import path."""

from __future__ import annotations

import sys as _sys
from types import ModuleType as _ModuleType

from src.frame_compare.vs import *  # noqa: F401,F403
from src.frame_compare.vs import __all__  # noqa: F401
from src.frame_compare.vs import color as _vs_color
from src.frame_compare.vs import env as _vs_env
from src.frame_compare.vs import tonemap as _vs_tonemap

_FORWARDED_ATTRS = {
    "_compute_luma_bounds": (_vs_color, "_compute_luma_bounds"),
    "_detect_rgb_color_range": (_vs_color, "_detect_rgb_color_range"),
    "normalise_color_metadata": (_vs_color, "normalise_color_metadata"),
    "_TONEMAP_UNSUPPORTED_KWARGS": (_vs_tonemap, "_TONEMAP_UNSUPPORTED_KWARGS"),
    "_pick_verify_frame": (_vs_tonemap, "_pick_verify_frame"),
    "_resolve_tonemap_settings": (_vs_tonemap, "_resolve_tonemap_settings"),
    "_compute_verification": (_vs_tonemap, "_compute_verification"),
    "_apply_post_gamma_levels": (_vs_tonemap, "_apply_post_gamma_levels"),
    "_tonemap_with_retries": (_vs_tonemap, "_tonemap_with_retries"),
}


class _VSCoreModule(_ModuleType):
    def __getattribute__(self, name: str):
        if name in _FORWARDED_ATTRS:
            module, attr = _FORWARDED_ATTRS[name]
            return getattr(module, attr)
        if name == "_vs_module":
            return _vs_env._vs_module
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value) -> None:
        if name in _FORWARDED_ATTRS:
            module, attr = _FORWARDED_ATTRS[name]
            setattr(module, attr, value)
            return
        if name == "_vs_module":
            _vs_env._vs_module = value
        else:
            super().__setattr__(name, value)


_module = _sys.modules[__name__]
if not isinstance(_module, _VSCoreModule):
    _module.__class__ = _VSCoreModule
