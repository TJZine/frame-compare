"""M4: the PQ/BT.2020 source receives the configured tonemap and RGB export."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tests.e2e.harness import CommandResult, Workspace, render_summary

_PQ_M1 = 2610 / 16384
_PQ_M2 = 2523 / 32
_PQ_C1 = 3424 / 4096
_PQ_C2 = 2413 / 128
_PQ_C3 = 2392 / 128

# BT.2020 and BT.709 D65 matrices from the standards' reference primaries.
_BT2020_TO_XYZ = (
    (0.636958, 0.144617, 0.168881),
    (0.262700, 0.677998, 0.059302),
    (0.000000, 0.028073, 1.060985),
)
_XYZ_TO_BT709 = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)


def _matrix_vector_product(
    matrix: tuple[tuple[float, float, float], ...], vector: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        sum(matrix[0][index] * vector[index] for index in range(3)),
        sum(matrix[1][index] * vector[index] for index in range(3)),
        sum(matrix[2][index] * vector[index] for index in range(3)),
    )


def _pq_encode(nits: float) -> int:
    normalized = max(nits / 10_000, 0.0)
    encoded = ((_PQ_C1 + _PQ_C2 * normalized**_PQ_M1) / (1 + _PQ_C3 * normalized**_PQ_M1)) ** _PQ_M2
    return round(encoded * 65_535)


def _pq_decode(code: int) -> float:
    encoded = code / 65_535
    normalized = max(encoded ** (1 / _PQ_M2) - _PQ_C1, 0.0) / (
        _PQ_C2 - _PQ_C3 * encoded ** (1 / _PQ_M2)
    )
    return 10_000 * normalized ** (1 / _PQ_M1)


def _bt709_oetf(linear: float) -> float:
    linear = max(0.0, min(1.0, linear))
    if linear <= 0.0031308:
        return 12.92 * linear
    return 1.055 * linear ** (1 / 2.4) - 0.055


def _expected_bt709_patch() -> tuple[float, float, float]:
    source_codes = (_pq_encode(20.0), _pq_encode(50.0), _pq_encode(30.0))
    source_linear = (
        _pq_decode(source_codes[0]) / 100,
        _pq_decode(source_codes[1]) / 100,
        _pq_decode(source_codes[2]) / 100,
    )
    xyz = _matrix_vector_product(_BT2020_TO_XYZ, source_linear)
    bt709_linear = _matrix_vector_product(_XYZ_TO_BT709, xyz)
    return (
        _bt709_oetf(bt709_linear[0]),
        _bt709_oetf(bt709_linear[1]),
        _bt709_oetf(bt709_linear[2]),
    )


def _render_native_color_patch(*, destination_primaries: int | None) -> tuple[float, float, float]:
    import vapoursynth as vs

    from frame_compare.vs.tonemap_libplacebo import (
        HdrTonemapInputs,
        apply_libplacebo,
        build_libplacebo_tonemap_kwargs,
    )
    from frame_compare.vs.types import HDRMetadata, TonemapResult, TonemapSettings

    core = vs.core
    assert hasattr(core, "placebo") and hasattr(core.placebo, "Tonemap"), (
        "libplacebo is required for the native BT.709 color-patch check"
    )

    settings = TonemapSettings(
        source_peak=100,
        target_nits=100,
        dynamic_peak_detection=False,
        gamut_mapping=0,
        metadata=0,
        use_dovi=False,
        contrast_recovery=0,
    )
    source_nits = (20.0, 50.0, 30.0)
    source_codes = [_pq_encode(nits) for nits in source_nits]
    clip = core.std.BlankClip(
        width=32,
        height=32,
        format=vs.RGB48,
        length=1,
        color=source_codes,
    ).std.SetFrameProps(_Matrix=0, _Range=1, _Transfer=16, _Primaries=9)
    metadata = HDRMetadata(None, None, None, 9, 16, 0)

    if destination_primaries is None:
        rendered = apply_libplacebo(clip, settings, core, metadata)
        assert isinstance(rendered, TonemapResult), "libplacebo tonemap did not render the patch"
        output = rendered.clip
    else:
        inputs = HdrTonemapInputs(
            hdr_metadata=metadata,
            transfer=16,
            primaries=9,
            props={"_Matrix": 0, "_Range": 1, "_Transfer": 16, "_Primaries": 9},
            detected_is_hdr=True,
        )
        kwargs = build_libplacebo_tonemap_kwargs(
            settings=settings,
            target_nits=100,
            inputs=inputs,
        )
        kwargs["dst_prim"] = destination_primaries
        output = core.placebo.Tonemap(clip, **kwargs).resize.Point(format=vs.RGBS)

    frame = output.get_frame(0)
    planes = cast(Any, frame)
    return (float(planes[0][0, 0]), float(planes[1][0, 0]), float(planes[2][0, 0]))


@pytest.mark.e2e
@pytest.mark.vs_required
def test_native_bt709_destination_primaries_color_patch(media_gate: None) -> None:
    """A saturated BT.2020 patch must render with BT.709 destination primaries."""
    expected = _expected_bt709_patch()
    actual = _render_native_color_patch(destination_primaries=None)
    smpte_c = _render_native_color_patch(destination_primaries=1)
    tolerance = 0.08

    assert actual == pytest.approx(expected, abs=tolerance)
    assert (
        max(abs(value - target) for value, target in zip(smpte_c, expected, strict=True))
        > tolerance
    )


@pytest.mark.e2e
@pytest.mark.vs_required
def test_media_hdr_tonemap(
    media_gate: None,
    media_files: dict[str, Path],
    run_cli: Callable[..., CommandResult],
    workspace: Callable[..., Workspace],
    record: Callable[..., None],
) -> None:
    root = workspace(
        {
            "analysis": {"random_frame_count": 0, "user_frames": [1, 2]},
            "audio_alignment": {"enable": False},
            "sources": {"reference": "reference.mkv"},
            "screenshots": {"overlay_mode": "none", "active_rect_detection": "provided"},
            "color": {"target_nits": 200},
        }
    )
    shutil.copy2(media_files["hdr"], root.input_dir / "reference.mkv")
    shutil.copy2(media_files["sdr"], root.input_dir / "comparison.mkv")
    arguments = ["run", "--json", "--skip-metadata", "--no-upload", "--root", str(root.root)]
    result = run_cli(root.root, arguments, timeout=60)
    summary, run_dir, report = render_summary(result)
    settings = report["rendering"]["tonemap"]["requested"]
    assert report["rendering"]["tonemap"]["shared"]["implementation"] == "libplacebo"
    summary["tonemap"] = (
        None
        if settings is None
        else {"preset": settings["preset"], "target_nits": settings["target_nits"]}
    )
    # Tonemap Preset And Target Resolution and Report And Overlay Metadata Contract.
    expected = {
        "success": True,
        "frame_count": 2,
        "clips_processed": 2,
        "cache_hit": False,
        "errors": [],
        "status": "completed",
        "clip_count": 2,
        "selected_frame_count": 2,
        "metrics_cache_status": "skipped",
        "frames": [
            [1, "user", [["reference", 1], ["comparison", 1]]],
            [2, "user", [["reference", 2], ["comparison", 2]]],
        ],
        "screenshots": [
            ["screenshots/1 - comparison.png", "RGB", [128, 72]],
            ["screenshots/1 - reference.png", "RGB", [64, 48]],
            ["screenshots/2 - comparison.png", "RGB", [128, 72]],
            ["screenshots/2 - reference.png", "RGB", [64, 48]],
        ],
        "tonemap": {"preset": "reference", "target_nits": 200},
    }
    record("M4-tonemap", root, [(arguments, result)], summary, expected, run_dir)
