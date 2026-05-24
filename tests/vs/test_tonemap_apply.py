"""Tests for tonemapping module."""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest
import vapoursynth as vs  # noqa: E402, I001

import frame_compare.vs.tonemap as tonemap_module  # noqa: E402, I001
from frame_compare.config.schema import ToneCurve  # noqa: E402, I001
from frame_compare.vs.errors import TonemapError  # noqa: E402, I001
from frame_compare.vs.tonemap import apply_tonemap  # noqa: E402, I001
from frame_compare.vs.types import HDRMetadata, TonemapSettings  # noqa: E402, I001


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


@patch("frame_compare.vs.tonemap_fallback.detect_hdr")
@patch("frame_compare.vs.tonemap.detect_plugins")
def test_apply_tonemap_detects_metadata_when_missing_fallback(mock_detect, mock_detect_hdr):
    """Verify metadata extraction is attempted in fallback path if missing."""
    mock_detect.return_value = {"libplacebo": False}

    mock_clip = MagicMock()
    # Mock fallback needs std.Expr
    mock_clip.std.Expr = MagicMock()
    mock_clip.format.id = vs.RGBS

    # Mock detect_hdr return
    mock_metadata = MagicMock()
    mock_metadata.max_cll = 5678
    mock_detect_hdr.return_value = (True, mock_metadata)

    settings = TonemapSettings(enabled=True, tone_curve=ToneCurve.REINHARD)

    apply_tonemap(mock_clip, settings, hdr_metadata=None)

    # Verify _detect_hdr called
    mock_detect_hdr.assert_called_once()

    # Verify max_cll was used in expression (via computed scale factor)
    mock_clip.std.Expr.assert_called_once()
    call_args = mock_clip.std.Expr.call_args
    # The expression uses scale = max_cll / target_nits, not raw max_cll
    # With max_cll=5678 and default target_nits=203: scale ≈ 27.97
    expected_scale = 5678 / 203
    expr_string = call_args.kwargs["expr"][0]
    # Extract the numeric scale from the expression (first number after "x ")
    import re

    match = re.search(r"x\s+([\d.]+)", expr_string)
    assert match, f"Could not find scale in expression: {expr_string}"
    actual_scale = float(match.group(1))
    assert abs(actual_scale - expected_scale) < 0.01, (
        f"Scale mismatch: expected ~{expected_scale:.2f}, got {actual_scale}"
    )


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_falls_back_on_libplacebo_runtime_failure(
    mock_fallback, mock_libplacebo, mock_runtime_usable, mock_detect
):
    """Verify runtime failure in libplacebo triggers fallback."""
    mock_detect.return_value = {"libplacebo": True}
    mock_libplacebo.return_value = None  # Signals runtime failure
    mock_fallback.return_value = MagicMock()

    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True)

    result = apply_tonemap(mock_clip, settings)

    mock_runtime_usable.assert_called_once_with()
    mock_libplacebo.assert_called_once()
    mock_fallback.assert_called_once()
    assert result is mock_fallback.return_value


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_uses_libplacebo_when_available(
    mock_fallback, mock_libplacebo, mock_runtime_usable, mock_detect
):
    """Verify libplacebo path is chosen when plugin is available."""
    mock_detect.return_value = {"libplacebo": True}
    mock_clip = MagicMock()
    # Ensure vs.core is used
    with patch("vapoursynth.core", MagicMock()) as mock_core:
        settings = TonemapSettings(enabled=True)

        apply_tonemap(mock_clip, settings)

        mock_runtime_usable.assert_called_once_with()
        mock_libplacebo.assert_called_once_with(mock_clip, settings, mock_core, None)
        mock_fallback.assert_not_called()


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
def test_apply_tonemap_unsupported_tone_curve_raises_error(mock_runtime_usable, mock_detect):
    """Verify unsupported tone curve raises error in libplacebo path."""
    mock_detect.return_value = {"libplacebo": True}
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True, tone_curve="invalid")  # type: ignore[arg-type]

    with pytest.raises(TonemapError) as exc:
        apply_tonemap(mock_clip, settings)

    mock_runtime_usable.assert_called_once_with()
    assert exc.value.context.code == "FC-4003"
    assert "bt2390, spline, reinhard" in exc.value.context.hint


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_uses_fallback_when_libplacebo_missing(
    mock_fallback, mock_libplacebo, mock_detect
):
    """Verify fallback path is chosen when plugin is missing."""
    mock_detect.return_value = {"libplacebo": False}
    mock_clip = MagicMock()

    settings = TonemapSettings(enabled=True)

    apply_tonemap(mock_clip, settings)

    mock_fallback.assert_called_once_with(mock_clip, settings, None)
    mock_libplacebo.assert_not_called()


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=False)
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_uses_fallback_when_libplacebo_unusable(
    mock_fallback, mock_libplacebo, mock_runtime_usable, mock_detect
):
    """Plugin presence alone must not force the crashing libplacebo path."""
    mock_detect.return_value = {"libplacebo": True}
    mock_fallback.return_value = MagicMock()

    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True)

    result = apply_tonemap(mock_clip, settings)

    mock_runtime_usable.assert_called_once_with()
    mock_libplacebo.assert_not_called()
    mock_fallback.assert_called_once_with(mock_clip, settings, None)
    assert result is mock_fallback.return_value


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
def test_apply_tonemap_rejects_non_positive_target_nits_before_processing(
    mock_runtime_usable, mock_detect
):
    """Invalid target_nits should fail early with explicit validation error."""
    mock_detect.return_value = {"libplacebo": True}
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True, tone_curve=ToneCurve.BT2390, target_nits=0)

    with pytest.raises(TonemapError, match="target_nits must be > 0"):
        apply_tonemap(mock_clip, settings)

    mock_runtime_usable.assert_not_called()


@patch("frame_compare.vs.tonemap_conversion.detect_hdr")
@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
def test_apply_tonemap_detects_metadata_when_missing_libplacebo(
    mock_runtime_usable, mock_detect, mock_detect_hdr
):
    """Verify metadata extraction is attempted in libplacebo path if missing."""
    mock_detect.return_value = {"libplacebo": True}

    mock_clip = MagicMock()
    mock_clip.format.id = vs.RGBS

    # Mock detect_hdr return
    mock_metadata = MagicMock()
    mock_metadata.max_cll = 1234
    mock_detect_hdr.return_value = (True, mock_metadata)

    settings = TonemapSettings(enabled=True, tone_curve=ToneCurve.BT2390)

    with patch("vapoursynth.core", MagicMock()) as mock_core:
        apply_tonemap(mock_clip, settings, hdr_metadata=None)

        mock_runtime_usable.assert_called_once_with()
        # Verify _detect_hdr called
        mock_detect_hdr.assert_called_once()

        # Verify max_cll was used in placebo call (src_max)
        mock_core.placebo.Tonemap.assert_called_once()
        _, kwargs = mock_core.placebo.Tonemap.call_args
        assert kwargs["src_max"] == 1234


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
def test_apply_tonemap_retries_minimal_kwargs_on_any_typeerror(mock_runtime_usable, mock_detect):
    """Compatibility retry should not depend on exact TypeError message text."""
    mock_detect.return_value = {"libplacebo": True}
    mock_clip = MagicMock()
    mock_clip.format.bits_per_sample = 16
    mock_clip.format.color_family = vs.RGB
    mock_clip.std.SetFrameProps = MagicMock(return_value=mock_clip)
    mock_clip.resize.Point = MagicMock(return_value=mock_clip)

    settings = TonemapSettings(enabled=True, tone_curve=ToneCurve.BT2390, target_nits=203)
    with patch("vapoursynth.core", MagicMock()) as mock_core:
        mock_core.placebo.Tonemap.side_effect = [
            TypeError("libplacebo signature mismatch"),
            mock_clip,
        ]

        result = apply_tonemap(mock_clip, settings)

        mock_runtime_usable.assert_called_once_with()
        assert result is mock_clip
        assert mock_core.placebo.Tonemap.call_count == 2
        first_call = mock_core.placebo.Tonemap.call_args_list[0]
        second_call = mock_core.placebo.Tonemap.call_args_list[1]
        assert "dst_csp" in first_call.kwargs
        assert "dst_csp" not in second_call.kwargs
        assert "dst_prim" not in second_call.kwargs


@patch("frame_compare.vs.tonemap.detect_plugins")
def test_apply_tonemap_rejects_non_positive_target_nits_for_fallback_path(mock_detect):
    """Validation should run before selecting libplacebo/fallback path."""
    mock_detect.return_value = {"libplacebo": False}
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True, tone_curve=ToneCurve.REINHARD, target_nits=-5)

    with pytest.raises(TonemapError, match="target_nits must be > 0"):
        apply_tonemap(mock_clip, settings)


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True)
def test_apply_tonemap_passes_src_csp_hint_for_hdr10(mock_runtime_usable, mock_detect):
    """Verify HDR10 metadata yields src_csp hint and SDR output defaults."""
    mock_detect.return_value = {"libplacebo": True}

    mock_clip = MagicMock()
    mock_clip.format.bits_per_sample = 16
    mock_clip.format.color_family = vs.RGB
    mock_clip.std.SetFrameProps = MagicMock(return_value=mock_clip)
    mock_clip.resize.Point = MagicMock(return_value=mock_clip)

    hdr_metadata = HDRMetadata(
        mastering_display=None,
        max_cll=1000,
        max_fall=400,
        color_primaries=9,
        transfer=16,
        matrix=9,
    )

    settings = TonemapSettings(enabled=True, tone_curve=ToneCurve.BT2390, target_nits=203)

    with patch("vapoursynth.core", MagicMock()) as mock_core:
        apply_tonemap(mock_clip, settings, hdr_metadata=hdr_metadata)

        mock_runtime_usable.assert_called_once_with()
        _, kwargs = mock_core.placebo.Tonemap.call_args
        assert kwargs["src_csp"] == 1
        assert kwargs["dst_csp"] == 0
        assert kwargs["dst_prim"] == 1
