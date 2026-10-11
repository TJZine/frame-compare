"""Managed VSView runtime bootstrap."""

from __future__ import annotations

import importlib
import os
import runpy
from typing import Any

from frame_compare.vs.env import ensure_vs_environment
from frame_compare.vs.runtime_contract import runtime_kind


def preload_vapoursynth_runtime() -> None:
    """Load bundled native libraries before Qt without creating a VS policy."""
    ensure_vs_environment()


def _skip_cjk_warmup(_font: object) -> None:
    pass


def disable_offscreen_cjk_warmup() -> None:
    """Skip VSView's Windows font-cache warmup when Qt cannot display a UI."""
    application: Any = importlib.import_module("vsview.app.main").Application
    application._warmup_cjk_fallback = staticmethod(_skip_cjk_warmup)


def main() -> None:
    preload_vapoursynth_runtime()
    if (
        runtime_kind().casefold() == "windows-portable"
        and os.environ.get("QT_QPA_PLATFORM", "").casefold() == "offscreen"
    ):
        disable_offscreen_cjk_warmup()
    runpy.run_module("vsview", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
