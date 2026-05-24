"""Tests for tonemapping module."""

import importlib.util
from unittest.mock import MagicMock

import pytest
import vapoursynth as vs  # noqa: E402, I001

import frame_compare.vs.tonemap as tonemap_module  # noqa: E402, I001


def _vs_spec_available() -> bool:
    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False


def _reset_libplacebo_runtime_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tonemap_module,
        "_LIBPLACEBO_RUNTIME_STATE",
        tonemap_module._LibplaceboRuntimeState(),
    )


def test_convert_non_rgb_with_matrix_hint_preserves_existing_matrix_prop() -> None:
    """Existing frame props should prevent us from inventing a matrix fallback hint."""
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
    mock_clip.resize.Bicubic.assert_called_once_with(format=vs.RGBS)


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
    mock_clip.resize.Bicubic.assert_called_once_with(format=vs.RGBS, matrix_in_s="709")
