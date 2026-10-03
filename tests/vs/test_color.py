"""Unit tests for color operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from frame_compare.vs.color import (
    apply_color_props,
    expand_limited_rgb_to_full,
    infer_color_props,
    to_rgb24,
)
from frame_compare.vs.types import ColorProps


def test_apply_color_props_calls_setframeprops():
    """Verify std.SetFrameProps is called with correct values."""
    clip = MagicMock()
    props = ColorProps(primaries=1, transfer=1, matrix=1, color_range=1)

    apply_color_props(clip, props)
    clip.std.SetFrameProps.assert_called_once_with(
        _Matrix=1, _Transfer=1, _Primaries=1, _ColorRange=1
    )


def test_expand_limited_rgb_to_full_integer_rgb():
    """Verify resize.Point called with correct expansion params for integer RGB."""
    clip = MagicMock()
    clip.format.color_family = 0  # RGB
    clip.format.sample_type = 0  # Integer
    clip.format.bits_per_sample = 8

    expand_limited_rgb_to_full(clip)
    clip.resize.Point.assert_called_once_with(
        range_in=1,
        range=0,
        min_in=16.0,
        max_in=235.0,
        min_out=0.0,
        max_out=255.0,
        planes=[0, 1, 2],
    )


def test_expand_limited_rgb_to_full_no_op_for_float():
    """Float RGB should be no-op."""
    clip = MagicMock()
    clip.format.color_family = 0  # RGB
    clip.format.sample_type = 1  # Float

    result = expand_limited_rgb_to_full(clip)
    assert result == clip
    clip.resize.Point.assert_not_called()


def test_to_rgb24_passes_resize_kwargs_and_sets_output_props():
    """Verify resize.Point called and output props applied (with expansion)."""
    clip = MagicMock()
    clip.height = 1080
    # Input is limited
    props = ColorProps(primaries=2, transfer=2, matrix=2, color_range=1)

    # Mock format for expansion check
    clip.format.color_family = 0  # RGB
    clip.format.sample_type = 0  # Integer
    clip.format.bits_per_sample = 8

    # We need to mock the sequence of clips
    # clip -> resize.Point -> expand_limited -> std.SetFrameProps
    resized_clip = MagicMock()
    expanded_clip = MagicMock()
    final_clip = MagicMock()

    clip.resize.Point.return_value = resized_clip

    mock_vs = MagicMock()
    mock_vs.RGB24 = 123

    with (
        patch.dict("sys.modules", {"vapoursynth": mock_vs}),
        patch(
            "frame_compare.vs.color.expand_limited_rgb_to_full", return_value=expanded_clip
        ) as mock_expand,
    ):
        expanded_clip.std.SetFrameProps.return_value = final_clip

        result = to_rgb24(clip, props=props, output_range=0, expand_to_full=True)

        assert result == final_clip
        clip.resize.Point.assert_called_once_with(
            format=123,
            matrix_in=1,
            transfer_in=1,
            primaries_in=1,
            range_in=1,
            range=0,
            dither_type="error_diffusion",
        )
        mock_expand.assert_called_once_with(resized_clip)
        expanded_clip.std.SetFrameProps.assert_called_once_with(
            _Matrix=0,
            _Transfer=1,
            _Primaries=1,
            _ColorRange=0,
        )


def test_to_rgb24_does_not_expand_when_output_range_limited():
    """Expansion should not occur if output_range is limited."""
    clip = MagicMock()
    clip.height = 1080
    props = ColorProps(primaries=1, transfer=1, matrix=1, color_range=1)

    mock_vs = MagicMock()
    mock_vs.RGB24 = 123

    with (
        patch.dict("sys.modules", {"vapoursynth": mock_vs}),
        patch("frame_compare.vs.color.expand_limited_rgb_to_full") as mock_expand,
    ):
        to_rgb24(clip, props=props, output_range=1, expand_to_full=True)
        mock_expand.assert_not_called()


@pytest.mark.parametrize(
    "height, props, expected, hdr",
    [
        pytest.param(
            480,
            ColorProps(2, 2, 2, 1),
            {"primaries": 6, "transfer": 6, "matrix": 6, "color_range": 1},
            False,
            id="sd_defaults",
        ),
        pytest.param(
            1080,
            ColorProps(2, 2, 2, 1),
            {"primaries": 1, "transfer": 1, "matrix": 1, "color_range": 1},
            False,
            id="hd_defaults",
        ),
        pytest.param(
            2160, ColorProps(2, 16, 2, 1), {"matrix": 9, "primaries": 9}, True, id="hdr_matrix"
        ),
        pytest.param(
            1080,
            ColorProps(6, 6, 6, 0),
            {"primaries": 6, "transfer": 6, "matrix": 6, "color_range": 0},
            False,
            id="specified",
        ),
    ],
)
def test_infer_color_props_cases(
    height: int, props: ColorProps, expected: dict[str, int], hdr: bool
) -> None:
    clip = MagicMock()
    clip.height = height
    if hdr:
        mock_vs = MagicMock()
        mock_vs.MATRIX_BT2020_NCL = 9
        with patch.dict("sys.modules", {"vapoursynth": mock_vs}):
            inferred = infer_color_props(clip, props)
    else:
        inferred = infer_color_props(clip, props)
    for field, value in expected.items():
        assert getattr(inferred, field) == value
