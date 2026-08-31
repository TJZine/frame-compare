"""Managed Windows VSView bootstrap."""

from __future__ import annotations

import runpy

from frame_compare.vs.env import ensure_vs_environment
from frame_compare.vs.runtime_contract import runtime_kind


def preload_vapoursynth_runtime() -> None:
    """Load bundled native libraries before Qt without creating a VS policy."""
    ensure_vs_environment()


def main() -> None:
    if runtime_kind().casefold() == "windows-portable":
        preload_vapoursynth_runtime()
    runpy.run_module("vsview", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
