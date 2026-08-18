from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from frame_compare.config.schema_enums import OverlayMode
from frame_compare.render.overlay_text import compose_overlay_text_lines, format_file_size
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    ExactFrameDolbyVisionFacts,
    HDRStaticFacts,
    PictureType,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.vs.types import TonemapSettings


def _geometry(*, transformed: bool = False) -> RenderedGeometryFacts:
    return RenderedGeometryFacts(
        source_size=(3840, 2160),
        active_picture=(
            ActivePictureFacts(0, 276, 3840, 1608, "dolby_vision_l5", False)
            if transformed
            else ActivePictureFacts(0, 0, 3840, 2160, "full_frame", True)
        ),
        cropped_size=(3840, 1608) if transformed else (3840, 2160),
        scaled_size=(3840, 1608) if transformed else (3840, 2160),
        final_canvas_size=(3840, 2160),
        is_noop=not transformed,
    )


def _config(
    mode: OverlayMode,
    *,
    label: str = "CtrlHD",
    comparison_frame: int = 1842,
    source_frame: int = 1842,
    source_total_frames: int | None = 143892,
    include_frame_number: bool = True,
    selection_label: str | None = "Bright",
    file_size_bytes: int = int(17.42 * 1024**3),
    source_resolution: tuple[int, int] = (3840, 2160),
    signal: SourceSignalFacts | None = None,
    presentation_state: PresentationState = PresentationState.SDR,
    tonemap_settings: TonemapSettings | None = None,
    geometry: RenderedGeometryFacts | None = None,
) -> OverlayConfig:
    return OverlayConfig(
        mode=mode,
        label=label,
        comparison_frame=comparison_frame,
        source_frame=source_frame,
        source_total_frames=source_total_frames,
        include_frame_number=include_frame_number,
        selection_label=selection_label,
        file_size_bytes=file_size_bytes,
        source_resolution=source_resolution,
        signal=signal or SourceSignalFacts(is_hdr=False),
        presentation_state=presentation_state,
        tonemap_settings=tonemap_settings,
        geometry=geometry or _geometry(),
        font_path=None,
    )


def _lines(config: OverlayConfig, *, picture_type: str | None = "B", dv=None) -> list[str]:
    facts = RenderedFrameFacts(
        source_frame=config.source_frame,
        picture_type=cast("PictureType | None", picture_type),
        dolby_vision=dv,
    )
    return compose_overlay_text_lines(config, facts)


def test_required_minimal_example() -> None:
    assert _lines(_config(OverlayMode.MINIMAL)) == [
        "CtrlHD",
        "Frame 1842 • B-frame • 17.42 GiB",
    ]


def test_required_standard_examples() -> None:
    assert _lines(_config(OverlayMode.STANDARD)) == [
        "CtrlHD",
        "Frame 1842/143892 • B-frame",
        "Selection: Bright",
        "Source: 3840×2160 • 17.42 GiB",
    ]
    assert _lines(_config(OverlayMode.STANDARD, source_frame=1855))[1:] == [
        "Comparison 1842 → source 1855/143892 • B-frame",
        "Selection: Bright",
        "Source: 3840×2160 • 17.42 GiB",
    ]


def test_required_diagnostic_sdr_example() -> None:
    signal = SourceSignalFacts(
        is_hdr=False, primaries=1, transfer=1, matrix=1, color_range="limited"
    )
    config = _config(
        OverlayMode.DIAGNOSTIC,
        label="WEB-DL",
        source_resolution=(1920, 1080),
        signal=signal,
        selection_label="Random",
        file_size_bytes=int(6.84 * 1024**3),
    )
    assert _lines(config, picture_type="P") == [
        "WEB-DL",
        "Frame 1842/143892 • P-frame",
        "Selection: Random",
        "Source: 1920×1080 • 6.84 GiB",
        "Signal: SDR • BT.709 / BT.709 / BT.709 • Limited",
    ]


def _hdr_config(*, dovi: bool = False) -> OverlayConfig:
    signal = SourceSignalFacts(
        is_hdr=True,
        primaries=9,
        transfer=16,
        matrix=9,
        color_range="limited",
        dolby_vision_rpu=dovi,
        hdr_static=HDRStaticFacts(0.005, 1000, 982, 244),
    )
    return _config(
        OverlayMode.DIAGNOSTIC,
        label="UHD Blu-ray" if dovi else "CtrlHD",
        source_frame=1855,
        file_size_bytes=int((54.72 if dovi else 17.42) * 1024**3),
        signal=signal,
        presentation_state=PresentationState.HDR_TONEMAPPED,
        tonemap_settings=TonemapSettings(),
        geometry=_geometry(transformed=dovi),
    )


def test_required_diagnostic_hdr_example() -> None:
    assert _lines(_hdr_config(), picture_type="B") == [
        "CtrlHD",
        "Comparison 1842 → source 1855/143892 • B-frame",
        "Selection: Bright",
        "Source: 3840×2160 • 17.42 GiB",
        "Signal: HDR • BT.2020 / PQ / BT.2020nc • Limited",
        "Tonemap: BT.2390 → 100 nits",
        "HDR static: MDL 0.005–1000 nits • MaxCLL/FALL 982/244",
    ]


def test_required_diagnostic_dv_examples_and_l6_suppression() -> None:
    config = _hdr_config(dovi=True)
    base = [
        "UHD Blu-ray",
        "Comparison 1842 → source 1855/143892 • B-frame",
        "Selection: Bright",
        "Source: 3840×2160 • 54.72 GiB",
        "Geometry: active 3840×1608 @ (0,276) • DV L5 → 3840×2160 canvas",
        "Signal: HDR • BT.2020 / PQ / BT.2020nc • Limited • DV RPU",
        "Tonemap: BT.2390 → 100 nits",
        "HDR static: MDL 0.005–1000 nits • MaxCLL/FALL 982/244",
    ]
    duplicate_l6 = ExactFrameDolbyVisionFacts(1855, 536, 24.1, 800, 982, 244)
    assert _lines(config, dv=duplicate_l6) == base + [
        "DV frame: L1 max/avg 536/24.1 nits • L2 target 800 nits"
    ]
    differing_l6 = replace(duplicate_l6, l6_max_cll=900, l6_max_fall=300)
    assert _lines(config, dv=differing_l6)[-1] == "DV L6: MaxCLL/FALL 900/300 nits"


def test_none_mode_has_no_lines_and_frame_facts_must_match() -> None:
    config = _config(OverlayMode.NONE)
    assert _lines(config) == []


def test_unknown_optional_values_are_omitted_without_dangling_separators() -> None:
    signal = SourceSignalFacts(is_hdr=True, primaries=2, transfer=99, matrix=None)
    config = _config(
        OverlayMode.DIAGNOSTIC,
        signal=signal,
        source_resolution=(0, 0),
        file_size_bytes=0,
        selection_label=None,
        presentation_state=PresentationState.HDR_TONEMAP_OFF,
    )
    assert _lines(config, picture_type="?") == [
        "CtrlHD",
        "Frame 1842/143892",
        "Signal: HDR • tonemap off",
    ]


def test_frame_numbers_can_be_disabled_while_picture_type_remains() -> None:
    config = _config(OverlayMode.STANDARD, include_frame_number=False)
    assert _lines(config)[:2] == ["CtrlHD", "B-frame"]
    unknown = _config(OverlayMode.STANDARD, include_frame_number=False)
    assert _lines(unknown, picture_type=None)[0:2] == ["CtrlHD", "Selection: Bright"]


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (1024**3 - 1, "1024.00 MiB"),
        (1024**3, "1.00 GiB"),
        (1024**4 - 1, "1024.00 GiB"),
        (1024**4, "1.00 TiB"),
    ],
)
def test_file_size_uses_iec_boundaries(size: int, expected: str) -> None:
    assert format_file_size(size) == expected
