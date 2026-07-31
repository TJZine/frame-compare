"""Tests for tonemapping module."""

from unittest.mock import MagicMock

import vapoursynth as vs  # noqa: E402, I001

import frame_compare.vs.tonemap as tonemap_module  # noqa: E402, I001


def test_convert_non_rgb_with_matrix_hint_preserves_existing_matrix_prop() -> None:
    """Existing frame props should drive numeric source conversion kwargs."""
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": 9},
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=9,
        range_in=vs.RANGE_LIMITED,
    )


def test_convert_non_rgb_with_matrix_hint_preserves_parseable_matrix_prop() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": b"9"},
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=9,
        range_in=vs.RANGE_LIMITED,
    )


def test_convert_non_rgb_with_matrix_hint_forwards_valid_transfer_primaries_and_range() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={
            "_Matrix": 9,
            "_Transfer": 16,
            "_Primaries": 9,
            "_Range": vs.RANGE_LIMITED,
        },
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=9,
        range_in=vs.RANGE_LIMITED,
        transfer_in=16,
        primaries_in=9,
    )


def test_convert_non_rgb_with_matrix_hint_normalizes_deprecated_color_range() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": 9, "_ColorRange": 1},
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=9,
        range_in=vs.RANGE_LIMITED,
    )


def test_convert_non_rgb_with_matrix_hint_normalizes_deprecated_full_color_range() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": 9, "_ColorRange": 0},
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=9,
        range_in=vs.RANGE_FULL,
    )


def test_convert_non_rgb_with_matrix_hint_treats_unspecified_matrix_as_sdr_missing() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": 2},
        detected_is_hdr=False,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT709,
        range_in=vs.RANGE_LIMITED,
    )


def test_convert_non_rgb_with_matrix_hint_treats_unspecified_matrix_as_hdr_missing() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": 2},
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT2020_NCL,
        range_in=vs.RANGE_LIMITED,
    )


def test_convert_non_rgb_with_matrix_hint_treats_unparseable_matrix_as_sdr_missing() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": "oops"},
        detected_is_hdr=False,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT709,
        range_in=vs.RANGE_LIMITED,
    )


def test_convert_non_rgb_with_matrix_hint_treats_unparseable_bytes_matrix_as_hdr_missing() -> None:
    mock_clip = MagicMock()
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = tonemap_module._convert_non_rgb_with_matrix_hint(
        mock_clip,
        target_format=vs.RGBS,
        props={"_Matrix": b"oops"},
        detected_is_hdr=True,
    )

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT2020_NCL,
        range_in=vs.RANGE_LIMITED,
    )


def test_to_rgbs_no_op_when_already_rgbs_real():
    """Verify _to_rgbs is no-op if format is already RGBS (real function)."""
    from frame_compare.vs.tonemap import _to_rgbs

    mock_clip = MagicMock()
    mock_clip.format.id = vs.RGBS

    result = _to_rgbs(mock_clip)

    assert result is mock_clip
    mock_clip.resize.Bicubic.assert_not_called()


def test_to_rgbs_converts_non_rgbs():
    """Verify _to_rgbs converts to RGBS when needed."""
    from frame_compare.vs.tonemap import _to_rgbs

    mock_clip = MagicMock()
    # Something different from mock_vs.RGBS (which is 0)
    mock_clip.format.id = 1

    # Setup resize return
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = _to_rgbs(mock_clip)

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(
        format=vs.RGBS,
        matrix_in=vs.MATRIX_BT709,
        range_in=vs.RANGE_LIMITED,
    )
