"""Managed Windows VSPreview bootstrap."""

from __future__ import annotations

import importlib
import runpy

from frame_compare.vs.env import ensure_vs_environment
from frame_compare.vs.runtime_contract import runtime_kind


def preload_vapoursynth_runtime() -> None:
    """Load bundled native libraries before Qt without creating a VS policy."""
    ensure_vs_environment()


def prepare_vspreview_compatibility() -> None:
    """Restore the VSJetPack 1.x APIs still used by VSPreview 0.20."""
    vstools = importlib.import_module("vstools")
    vspreview = importlib.import_module("vspreview")

    if not hasattr(vstools, "vs_object") and hasattr(vstools, "VSObject"):
        vstools.__dict__["vs_object"] = vstools.VSObject
    if not hasattr(vstools, "set_output") and hasattr(vspreview, "set_output"):
        vstools.__dict__["set_output"] = vspreview.set_output

    dither_type = vstools.DitherType
    if not hasattr(dither_type, "is_fmtc"):
        fmtc_dither_types = frozenset(
            (
                dither_type.SIERRA_2_4A,
                dither_type.STUCKI,
                dither_type.ATKINSON,
                dither_type.OSTROMOUKHOV,
                dither_type.QUASIRANDOM,
            )
        )
        type.__setattr__(
            dither_type,
            "is_fmtc",
            property(lambda self: self in fmtc_dither_types),
        )


def main() -> None:
    if runtime_kind().casefold() == "windows-portable":
        preload_vapoursynth_runtime()
    prepare_vspreview_compatibility()
    runpy.run_module("vspreview", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
