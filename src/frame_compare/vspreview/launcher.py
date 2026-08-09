"""Managed Windows VSPreview bootstrap."""

from __future__ import annotations

import runpy

from frame_compare.vs.env import ensure_vs_environment


def preload_vapoursynth_runtime() -> None:
    """Load the bundled media runtime before PyQt registers private DLLs."""
    core = ensure_vs_environment()
    list(core.plugins())


def main() -> None:
    preload_vapoursynth_runtime()
    runpy.run_module("vspreview", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
