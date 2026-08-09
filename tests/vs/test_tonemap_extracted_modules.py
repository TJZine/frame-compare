"""Direct behavior tests for extracted tonemap owner modules."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
import vapoursynth as vs  # noqa: E402, I001

from frame_compare.config.schema import ToneCurve, TonemapPreset
from frame_compare.vs.errors import TonemapError
from frame_compare.vs.tonemap_conversion import (
    apply_post_processing,
    convert_non_rgb_with_matrix_hint,
    resolve_hdr_tonemap_inputs,
)
from frame_compare.vs.tonemap_fallback import fallback_tonemap
from frame_compare.vs.tonemap_libplacebo import (
    HdrTonemapInputs,
    apply_libplacebo,
    build_libplacebo_tonemap_kwargs,
    call_libplacebo_with_compat_retry,
)
from frame_compare.vs.tonemap_presets import TONEMAP_PRESETS, get_preset_settings
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    from vapoursynth import Core, VideoNode


class _RecordingStd:
    def __init__(self, owner: "_Clip") -> None:
        self._owner = owner
        self.expr_calls: list[list[str]] = []
        self.set_frame_props_calls: list[dict[str, object]] = []

    def Expr(self, *, expr: list[str]) -> "_Clip":
        self.expr_calls.append(expr)
        return self._owner

    def SetFrameProps(self, **kwargs: object) -> "_Clip":
        self.set_frame_props_calls.append(kwargs)
        return self._owner

    def Levels(self, *, gamma: float) -> "_Clip":
        self._owner.levels_gamma = gamma
        return self._owner


class _RecordingResize:
    def __init__(self, owner: "_Clip") -> None:
        self._owner = owner
        self.bicubic_calls: list[dict[str, object]] = []
        self.point_calls: list[dict[str, object]] = []

    def Bicubic(self, **kwargs: object) -> "_Clip":
        self.bicubic_calls.append(kwargs)
        return self._owner

    def Point(self, **kwargs: object) -> "_Clip":
        self.point_calls.append(kwargs)
        return self._owner


class _Clip:
    def __init__(
        self,
        *,
        props: dict[str, object] | None = None,
        format_id: int = vs.RGBS,
        color_family: int = vs.RGB,
        bits_per_sample: int = 16,
    ) -> None:
        self.format = SimpleNamespace(
            id=format_id,
            color_family=color_family,
            bits_per_sample=bits_per_sample,
        )
        self.std = _RecordingStd(self)
        self.resize = _RecordingResize(self)
        self._props = props or {}
        self.levels_gamma: float | None = None

    def get_frame(self, index: int) -> SimpleNamespace:
        assert index == 0
        return SimpleNamespace(props=self._props)


class _Placebo:
    def __init__(self, results: list[object]) -> None:
        self._results = results
        self.calls: list[dict[str, object]] = []

    def Tonemap(self, clip: _Clip, **kwargs: object) -> _Clip:
        self.calls.append(kwargs)
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return cast(_Clip, result)


def test_tonemap_presets_cover_enum_and_return_expected_values() -> None:
    """Preset lookup should expose one concrete settings object per preset enum."""
    assert set(TONEMAP_PRESETS) == set(TonemapPreset)

    settings = get_preset_settings(TonemapPreset.BRIGHT_LIFT)

    assert settings.preset is TonemapPreset.BRIGHT_LIFT
    assert settings.tone_curve is ToneCurve.BT2390
    assert settings.target_nits == 250
    assert settings.gamma_lift is True


def test_reference_preset_uses_legacy_hdr_target() -> None:
    """Reference preset keeps the legacy screenshot baseline target."""
    settings = get_preset_settings(TonemapPreset.REFERENCE)

    assert settings.target_nits == 100
    assert settings.dynamic_peak_detection is True
    assert settings.dst_min_nits == 0.18
    assert settings.knee_offset == 0.50
    assert settings.smoothing_period == 45.0
    assert settings.scene_threshold_low == 0.8
    assert settings.scene_threshold_high == 2.4
    assert settings.percentile == 99.995
    assert settings.metadata == 0
    assert settings.use_dovi is True
    assert settings.contrast_recovery == 0.30


def test_tonemap_presets_unknown_preset_reports_available_values() -> None:
    """Unknown preset errors should include the supported value list."""
    with pytest.raises(TonemapError) as exc:
        get_preset_settings(cast(TonemapPreset, "invalid"))

    assert "Unknown preset" in exc.value.context.message
    assert exc.value.context.hint is not None
    assert "reference, filmic" in exc.value.context.hint


def test_fallback_tonemap_detects_metadata_and_uses_reinhard_expression() -> None:
    """Fallback should derive source peak from HDR metadata when not provided."""
    clip = _Clip(
        props={
            "_Transfer": 16,
            "_Primaries": 9,
            "ContentLightLevelMax": 609,
        }
    )
    settings = TonemapSettings(tone_curve=ToneCurve.REINHARD, target_nits=203)

    result = fallback_tonemap(cast("VideoNode", clip), settings)

    assert result is clip
    assert len(clip.std.expr_calls) == 1
    assert clip.std.expr_calls[0] == ["x 3 * dup 1 + / 2 * 0 max 1 min"] * 3


def test_fallback_tonemap_prefers_explicit_source_peak_over_metadata() -> None:
    """Explicit source_peak should own the fallback scale when configured."""
    clip = _Clip(
        props={
            "_Transfer": 16,
            "_Primaries": 9,
            "ContentLightLevelMax": 4000,
        }
    )
    settings = TonemapSettings(source_peak=812, target_nits=203)

    fallback_tonemap(cast("VideoNode", clip), settings)

    assert clip.std.expr_calls[0] == ["x 4 * dup 1 + / 2 * 0 max 1 min"] * 3


def test_fallback_tonemap_uses_probed_hdr_signal_for_untagged_yuv_conversion() -> None:
    clip = _Clip(props={}, format_id=vs.YUV420P10, color_family=vs.YUV, bits_per_sample=10)
    metadata = HDRMetadata(None, 1000, 400, 9, 16, 9)

    fallback_tonemap(cast("VideoNode", clip), TonemapSettings(), metadata)

    assert clip.resize.bicubic_calls[0] == {
        "format": vs.RGBS,
        "matrix_in": 9,
        "range_in": vs.RANGE_LIMITED,
        "transfer_in": 16,
        "primaries_in": 9,
    }


def test_resolve_hdr_inputs_preserves_explicit_sdr_signal_and_range() -> None:
    clip = _Clip(props={"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": vs.RANGE_FULL})
    metadata = HDRMetadata(None, 1000, 400, 9, 16, 9)

    inputs = resolve_hdr_tonemap_inputs(cast("VideoNode", clip), metadata)

    assert inputs.transfer == 1
    assert inputs.primaries == 1
    assert inputs.detected_is_hdr is False
    assert inputs.props == {
        "_Matrix": 1,
        "_Transfer": 1,
        "_Primaries": 1,
        "_Range": vs.RANGE_FULL,
    }


def test_build_libplacebo_kwargs_uses_hdr10_hints_and_metadata_peak() -> None:
    """HDR10 metadata should map to the legacy libplacebo kwargs."""
    metadata = HDRMetadata(
        mastering_display=None,
        max_cll=1000,
        max_fall=400,
        color_primaries=9,
        transfer=16,
        matrix=9,
    )
    inputs = HdrTonemapInputs(
        hdr_metadata=metadata,
        transfer=16,
        primaries=9,
        props={"_Transfer": 16, "_Primaries": 9},
        detected_is_hdr=True,
    )

    kwargs = build_libplacebo_tonemap_kwargs(
        settings=TonemapSettings(tone_curve=ToneCurve.BT2390),
        target_nits=203,
        inputs=inputs,
    )

    assert kwargs == {
        "src_max": 1000,
        "dst_max": 203,
        "tone_mapping_function_s": "bt.2390",
        "tone_mapping_param": 0.5,
        "dst_csp": 0,
        "dst_prim": 1,
        "dst_min": 0.18,
        "dynamic_peak_detection": 1,
        "smoothing_period": 45.0,
        "scene_threshold_low": 0.8,
        "scene_threshold_high": 2.4,
        "percentile": 99.995,
        "gamut_mapping": 1,
        "contrast_recovery": 0.3,
        "metadata": 0,
        "use_dovi": 1,
        "log_level": 2,
        "src_csp": 1,
    }


def test_libplacebo_uses_probed_hdr_signal_for_untagged_yuv_conversion() -> None:
    clip = _Clip(props={}, format_id=vs.YUV420P10, color_family=vs.YUV, bits_per_sample=10)
    placebo = _Placebo([clip])
    core = SimpleNamespace(placebo=placebo)
    metadata = HDRMetadata(None, 1000, 400, 9, 16, 9)

    result = apply_libplacebo(
        cast("VideoNode", clip),
        TonemapSettings(),
        cast("Core", core),
        metadata,
    )

    assert result is clip
    assert clip.resize.bicubic_calls[0] == {
        "format": vs.RGB48,
        "matrix_in": 9,
        "range_in": vs.RANGE_LIMITED,
        "transfer_in": 16,
        "primaries_in": 9,
    }
    assert placebo.calls[0]["src_csp"] == 1


def test_call_libplacebo_with_compat_retry_drops_newer_kwargs_after_typeerror() -> None:
    """Compatibility retry should preserve baseline kwargs on unknown TypeError."""
    clip = _Clip()
    placebo = _Placebo([TypeError("signature mismatch"), clip])
    core = SimpleNamespace(placebo=placebo)

    result = call_libplacebo_with_compat_retry(
        cast("Core", core),
        cast("VideoNode", clip),
        {
            "src_max": 1000,
            "dst_max": 203,
            "tone_mapping_function": 2,
            "dst_csp": 0,
            "dst_prim": 1,
            "src_csp": 1,
        },
    )

    assert result is clip
    assert placebo.calls == [
        {
            "src_max": 1000,
            "dst_max": 203,
            "tone_mapping_function": 2,
            "dst_csp": 0,
            "dst_prim": 1,
            "src_csp": 1,
        },
        {
            "src_max": 1000,
            "dst_max": 203,
            "tone_mapping_function": 2,
            "dst_csp": 0,
            "dst_prim": 1,
            "src_csp": 1,
        },
    ]


def test_call_libplacebo_with_compat_retry_drops_only_rejected_kwargs() -> None:
    """Compatibility retry should preserve supported legacy tonemap settings."""
    clip = _Clip()
    placebo = _Placebo(
        [
            TypeError("Function does not take argument(s) named metadata, use_dovi"),
            clip,
        ]
    )
    core = SimpleNamespace(placebo=placebo)

    call_libplacebo_with_compat_retry(
        cast("Core", core),
        cast("VideoNode", clip),
        {
            "src_max": 1000,
            "dst_max": 100,
            "tone_mapping_function": 2,
            "dst_min": 0.18,
            "dynamic_peak_detection": 1,
            "metadata": 0,
            "use_dovi": 1,
            "contrast_recovery": 0.3,
        },
    )

    assert placebo.calls[1] == {
        "src_max": 1000,
        "dst_max": 100,
        "tone_mapping_function": 2,
        "dst_min": 0.18,
        "dynamic_peak_detection": 1,
        "contrast_recovery": 0.3,
    }


def test_call_libplacebo_with_compat_retry_parses_unexpected_keyword_message() -> None:
    """Single-kwarg TypeError messages should not drop the full legacy baseline."""
    clip = _Clip()
    placebo = _Placebo(
        [
            TypeError("got an unexpected keyword argument 'metadata'"),
            clip,
        ]
    )
    core = SimpleNamespace(placebo=placebo)

    call_libplacebo_with_compat_retry(
        cast("Core", core),
        cast("VideoNode", clip),
        {
            "dst_max": 100,
            "tone_mapping_function_s": "bt.2390",
            "metadata": 0,
            "contrast_recovery": 0.3,
        },
    )

    assert placebo.calls[1] == {
        "dst_max": 100,
        "tone_mapping_function_s": "bt.2390",
        "contrast_recovery": 0.3,
    }


def test_call_libplacebo_retry_adds_numeric_curve_when_string_curve_is_rejected() -> None:
    """Production-built kwargs should preserve non-default curves on older runtimes."""
    clip = _Clip()
    placebo = _Placebo(
        [
            TypeError("got an unexpected keyword argument 'tone_mapping_function_s'"),
            clip,
        ]
    )
    core = SimpleNamespace(placebo=placebo)
    inputs = HdrTonemapInputs(
        hdr_metadata=None,
        transfer=16,
        primaries=9,
        props={},
        detected_is_hdr=True,
    )
    kwargs = build_libplacebo_tonemap_kwargs(
        settings=TonemapSettings(tone_curve=ToneCurve.SPLINE),
        target_nits=100,
        inputs=inputs,
    )

    call_libplacebo_with_compat_retry(cast("Core", core), cast("VideoNode", clip), kwargs)

    assert "tone_mapping_function_s" not in placebo.calls[1]
    assert placebo.calls[1]["tone_mapping_function"] == 1


def test_apply_post_processing_does_not_apply_contrast_recovery_expr() -> None:
    """contrast_recovery is a libplacebo option, not a post-tonemap shadow crusher."""
    clip = _Clip()

    result = apply_post_processing(
        cast("VideoNode", clip),
        TonemapSettings(contrast_recovery=0.3, gamma_lift=False),
    )

    assert result is clip
    assert clip.std.expr_calls == []


def test_apply_libplacebo_runtime_failure_returns_none_after_rgb_prop_normalization() -> None:
    """Unexpected libplacebo runtime errors should signal fallback without masking setup."""
    clip = _Clip()
    placebo = _Placebo([RuntimeError("vulkan device unavailable")])
    core = SimpleNamespace(placebo=placebo)
    metadata = HDRMetadata(
        mastering_display=None,
        max_cll=2000,
        max_fall=None,
        color_primaries=9,
        transfer=18,
        matrix=9,
    )

    result = apply_libplacebo(
        cast("VideoNode", clip),
        TonemapSettings(tone_curve=ToneCurve.SPLINE, target_nits=180),
        cast("Core", core),
        metadata,
    )

    assert result is None
    assert clip.std.set_frame_props_calls == [
        {"_Matrix": 0, "_ColorRange": 0, "_Transfer": 18, "_Primaries": 9}
    ]
    assert placebo.calls == [
        {
            "src_max": 2000,
            "dst_max": 180,
            "tone_mapping_function_s": "spline",
            "tone_mapping_param": 0.5,
            "dst_csp": 0,
            "dst_prim": 1,
            "dst_min": 0.18,
            "dynamic_peak_detection": 1,
            "smoothing_period": 45.0,
            "scene_threshold_low": 0.8,
            "scene_threshold_high": 2.4,
            "percentile": 99.995,
            "gamut_mapping": 1,
            "contrast_recovery": 0.3,
            "metadata": 0,
            "use_dovi": 1,
            "log_level": 2,
            "src_csp": 2,
        }
    ]
    assert clip.resize.point_calls == []


def test_convert_non_rgb_matrix_presence_uses_frame_prop_boundary() -> None:
    """A present matrix prop should be forwarded as numeric conversion metadata."""
    clip = _Clip(format_id=999, color_family=999, props={"_Matrix": b"9"})

    result = convert_non_rgb_with_matrix_hint(cast("VideoNode", clip), target_format=vs.RGBS)

    assert result is clip
    assert clip.resize.bicubic_calls == [
        {"format": vs.RGBS, "matrix_in": 9, "range_in": vs.RANGE_LIMITED}
    ]
