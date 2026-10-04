from __future__ import annotations

import pytest

from frame_compare.config.schema_enums import OverlayMode
from frame_compare.render.overlay_text import compose_overlay_text_lines, format_file_size
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
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


def _lines(
    config: OverlayConfig,
    *,
    picture_type: PictureType | None = "B",
) -> list[str]:
    facts = RenderedFrameFacts(
        source_frame=config.source_frame,
        picture_type=picture_type,
    )
    return compose_overlay_text_lines(config, facts)


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


@pytest.mark.parametrize(
    "config, picture_type, start, stop, expected",
    [
        pytest.param(
            _config(OverlayMode.MINIMAL),
            "B",
            None,
            None,
            ["CtrlHD", "Frame 1842 • B-frame • 17.42 GiB"],
            id="required_minimal_example-0",
        ),
        pytest.param(
            _config(OverlayMode.STANDARD),
            "B",
            None,
            None,
            [
                "CtrlHD",
                "Frame 1842/143892 • B-frame",
                "Selection: Bright",
                "Source: 3840×2160 • 17.42 GiB",
            ],
            id="required_standard_examples-0",
        ),
        pytest.param(
            _config(OverlayMode.STANDARD, source_frame=1855),
            "B",
            1,
            None,
            [
                "Comparison 1842 → source 1855/143892 • B-frame",
                "Selection: Bright",
                "Source: 3840×2160 • 17.42 GiB",
            ],
            id="required_standard_examples-1",
        ),
        pytest.param(
            _config(
                OverlayMode.DIAGNOSTIC,
                label="WEB-DL",
                source_resolution=(1920, 1080),
                signal=SourceSignalFacts(
                    is_hdr=False, primaries=1, transfer=1, matrix=1, color_range="limited"
                ),
                selection_label="Random",
                file_size_bytes=int(6.84 * 1024**3),
            ),
            "P",
            None,
            None,
            [
                "WEB-DL",
                "Frame 1842/143892 • P-frame",
                "Selection: Random",
                "Source: 1920×1080 • 6.84 GiB",
                "Signal: SDR • BT.709 / BT.709 / BT.709 • Limited",
            ],
            id="required_diagnostic_sdr_example-0",
        ),
        pytest.param(
            _hdr_config(),
            "B",
            None,
            None,
            [
                "CtrlHD",
                "Comparison 1842 → source 1855/143892 • B-frame",
                "Selection: Bright",
                "Source: 3840×2160 • 17.42 GiB",
                "Signal: HDR • BT.2020 / PQ / BT.2020nc • Limited",
                "Tonemap: BT.2390 → 100 nits",
                "HDR static: MDL 0.005–1000 nits • MaxCLL/FALL 982/244",
            ],
            id="required_diagnostic_hdr_example-0",
        ),
        pytest.param(
            _hdr_config(dovi=True),
            "B",
            None,
            None,
            [
                "UHD Blu-ray",
                "Comparison 1842 → source 1855/143892 • B-frame",
                "Selection: Bright",
                "Source: 3840×2160 • 54.72 GiB",
                "Geometry: active 3840×1608 @ (0,276) • DV L5 → 3840×2160 canvas",
                "Signal: HDR • BT.2020 / PQ / BT.2020nc • Limited • DV RPU",
                "Tonemap: BT.2390 → 100 nits",
                "HDR static: MDL 0.005–1000 nits • MaxCLL/FALL 982/244",
            ],
            id="required_diagnostic_dv_source_facts-0",
        ),
        pytest.param(_config(OverlayMode.NONE), "B", None, None, [], id="none_mode_has_no_lines-0"),
        pytest.param(
            _config(
                OverlayMode.DIAGNOSTIC,
                signal=SourceSignalFacts(is_hdr=True, primaries=2, transfer=99, matrix=None),
                source_resolution=(0, 0),
                file_size_bytes=0,
                selection_label=None,
                presentation_state=PresentationState.HDR_TONEMAP_OFF,
            ),
            None,
            None,
            None,
            ["CtrlHD", "Frame 1842/143892", "Signal: HDR • tonemap off"],
            id="unknown_optional_values_are_omitted_without_dangling_separators-0",
        ),
        pytest.param(
            _config(OverlayMode.STANDARD, include_frame_number=False),
            "B",
            None,
            2,
            ["CtrlHD", "B-frame"],
            id="frame_numbers_can_be_disabled_while_picture_type_remains-0",
        ),
        pytest.param(
            _config(OverlayMode.STANDARD, include_frame_number=False),
            None,
            0,
            2,
            ["CtrlHD", "Selection: Bright"],
            id="frame_numbers_can_be_disabled_while_picture_type_remains-1",
        ),
    ],
)
def test_overlay_text_examples(
    config: OverlayConfig,
    picture_type: PictureType | None,
    start: int | None,
    stop: int | None,
    expected: list[str],
) -> None:
    assert _lines(config, picture_type=picture_type)[start:stop] == expected
