"""Tests for tonemapping module."""

from unittest.mock import MagicMock

import pytest
import vapoursynth as vs  # noqa: E402, I001

import frame_compare.vs.tonemap_conversion as tonemap_module  # noqa: E402, I001


def test_to_rgbs_no_op_when_already_rgbs_real():
    """Verify to_rgbs is no-op if format is already RGBS (real function)."""
    from frame_compare.vs.tonemap_conversion import to_rgbs

    mock_clip = MagicMock()
    mock_clip.format.id = vs.RGBS

    result = to_rgbs(mock_clip)

    assert result is mock_clip
    mock_clip.resize.Bicubic.assert_not_called()


def test_to_rgbs_converts_non_rgbs():
    """Verify to_rgbs converts to RGBS when needed."""
    from frame_compare.vs.tonemap_conversion import to_rgbs

    mock_clip = MagicMock()
    # Something different from mock_vs.RGBS (which is 0)
    mock_clip.format.id = 1

    # Setup resize return
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = to_rgbs(mock_clip)

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT709,
        range_in=vs.RANGE_LIMITED,
    )


@pytest.mark.parametrize(
    "props, is_hdr, expected_kwargs",
    [
        pytest.param(
            {"_Matrix": 9},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED},
            id="existing_matrix",
        ),
        pytest.param(
            {"_Matrix": b"9"},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED},
            id="parseable_matrix",
        ),
        pytest.param(
            {"_Matrix": 9, "_Transfer": 16, "_Primaries": 9, "_Range": vs.RANGE_LIMITED},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED, "transfer_in": 16, "primaries_in": 9},
            id="complete_signal",
        ),
        pytest.param(
            {"_Matrix": 9, "_ColorRange": 1},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_LIMITED},
            id="deprecated_limited",
        ),
        pytest.param(
            {"_Matrix": 9, "_ColorRange": 0},
            True,
            {"matrix_in": 9, "range_in": vs.RANGE_FULL},
            id="deprecated_full",
        ),
        pytest.param(
            {"_Matrix": 2},
            False,
            {"matrix_in": vs.MATRIX_BT709, "range_in": vs.RANGE_LIMITED},
            id="unspecified_sdr",
        ),
        pytest.param(
            {"_Matrix": 2},
            True,
            {"matrix_in": vs.MATRIX_BT2020_NCL, "range_in": vs.RANGE_LIMITED},
            id="unspecified_hdr",
        ),
        pytest.param(
            {"_Matrix": "oops"},
            False,
            {"matrix_in": vs.MATRIX_BT709, "range_in": vs.RANGE_LIMITED},
            id="unparseable_sdr",
        ),
        pytest.param(
            {"_Matrix": b"oops"},
            True,
            {"matrix_in": vs.MATRIX_BT2020_NCL, "range_in": vs.RANGE_LIMITED},
            id="unparseable_bytes_hdr",
        ),
    ],
)
def test_convert_non_rgb_signal_cases(
    props: dict[str, object], is_hdr: bool, expected_kwargs: dict[str, int]
) -> None:
    clip = MagicMock()
    resized = MagicMock()
    clip.resize.Bicubic.return_value = resized
    result = tonemap_module.convert_non_rgb_with_matrix_hint(
        clip, target_format=vs.RGBS, props=props, detected_is_hdr=is_hdr
    )
    assert result is resized
    clip.resize.Bicubic.assert_called_once_with(format=vs.RGBS, **expected_kwargs)
