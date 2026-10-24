from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
import vapoursynth as vs

from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import ToneCurve, TonemapPreset
from frame_compare.config.schema_enums import TonemapSpeed
from frame_compare.render.prepare import resolve_tonemap_settings
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
)
from frame_compare.vs.tonemap_presets import get_preset_settings
from frame_compare.vs.types import (
    HDRMetadata,
    LibplaceboTonemap,
    TonemapFallbackCause,
    TonemapResult,
    TonemapSettings,
)

if TYPE_CHECKING:
    from vapoursynth import Core, VideoNode


class _RecordingStd:
    def __init__(self, owner: "_Clip") -> None:
        self._owner = owner
        self.expr_calls: list[list[str]] = []
        self.set_frame_props_calls: list[dict[str, object]] = []

    def Expr(self, *, expr: list[str], format: int | None = None) -> "_Clip":
        self.expr_calls.append(expr)
        return self._owner

    def RemoveFrameProps(self, *, props: list[str]) -> "_Clip":
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


def test_fallback_tonemap_detects_metadata_and_uses_reinhard_expression() -> None:
    clip = _Clip(
        props={
            "_Transfer": 16,
            "_Primaries": 9,
            "ContentLightLevelMax": 609,
        }
    )
    settings = TonemapSettings(tone_curve=ToneCurve.REINHARD, target_nits=203)

    result = fallback_tonemap(
        cast("VideoNode", clip), settings, cause=TonemapFallbackCause.PLUGIN_UNAVAILABLE
    )

    assert isinstance(result, TonemapResult)
    assert result.clip is clip
    assert len(clip.std.expr_calls) == 1
    assert clip.std.expr_calls[0] == ["x 3 * dup 1 + / 2 * 0 max 1 min"] * 3


def test_fallback_tonemap_prefers_explicit_source_peak_over_metadata() -> None:
    clip = _Clip(
        props={
            "_Transfer": 16,
            "_Primaries": 9,
            "ContentLightLevelMax": 4000,
        }
    )
    settings = TonemapSettings(source_peak=812, target_nits=203)

    fallback_tonemap(
        cast("VideoNode", clip), settings, cause=TonemapFallbackCause.PLUGIN_UNAVAILABLE
    )

    assert clip.std.expr_calls[0] == ["x 4 * dup 1 + / 2 * 0 max 1 min"] * 3


def test_fallback_tonemap_uses_probed_hdr_signal_for_untagged_yuv_conversion() -> None:
    clip = _Clip(
        props={},
        format_id=cast(int, vars(vs)["YUV420P10"]),
        color_family=vs.YUV,
        bits_per_sample=10,
    )
    metadata = HDRMetadata(None, 1000, 400, 9, 16, 9)

    fallback_tonemap(
        cast("VideoNode", clip),
        TonemapSettings(),
        metadata,
        cause=TonemapFallbackCause.PLUGIN_UNAVAILABLE,
    )

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


@pytest.mark.parametrize(
    ("preset", "tone_curve", "expected_curve", "expected_knee"),
    [
        pytest.param(TonemapPreset.REFERENCE, None, "bt2390", 0.5, id="reference"),
        pytest.param(
            TonemapPreset.HIGHLIGHT_PRESERVE,
            None,
            "bt2390",
            1.0,
            id="highlight_preserve",
        ),
        pytest.param(
            TonemapPreset.HIGHLIGHT_PRESERVE,
            ToneCurve.SPLINE,
            "spline",
            0.5,
            id="highlight_preserve_spline_override",
        ),
    ],
)
def test_build_libplacebo_kwargs_uses_hdr10_hints_and_metadata_peak(
    preset: TonemapPreset,
    tone_curve: ToneCurve | None,
    expected_curve: str,
    expected_knee: float,
) -> None:
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

    config = get_default_config()
    color = config.color.model_copy(update={"preset": preset})
    if tone_curve is not None:
        color = color.model_copy(update={"tone_curve": tone_curve})
    settings = resolve_tonemap_settings(config.model_copy(update={"color": color}))

    kwargs = build_libplacebo_tonemap_kwargs(settings=settings, target_nits=203, inputs=inputs)

    assert kwargs == {
        "src_max": 1000,
        "dst_max": 203,
        "tone_mapping_function_s": expected_curve,
        "tone_mapping_param": expected_knee,
        "dst_csp": 0,
        "dst_prim": 3,
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
    clip = _Clip(
        props={},
        format_id=cast(int, vars(vs)["YUV420P10"]),
        color_family=vs.YUV,
        bits_per_sample=10,
    )
    placebo = _Placebo([clip])
    core = SimpleNamespace(placebo=placebo)
    metadata = HDRMetadata(None, 1000, 400, 9, 16, 9)

    result = apply_libplacebo(
        cast("VideoNode", clip),
        TonemapSettings(),
        cast("Core", core),
        metadata,
    )

    assert isinstance(result, TonemapResult)
    assert result.clip is clip
    assert clip.resize.bicubic_calls[0] == {
        "format": vs.RGB48,
        "matrix_in": 9,
        "range_in": vs.RANGE_LIMITED,
        "transfer_in": 16,
        "primaries_in": 9,
    }
    assert placebo.calls[0]["src_csp"] == 1


def test_apply_libplacebo_fast_still_uses_one_shared_stateless_node() -> None:
    clip = _Clip(
        props={
            "_Transfer": 16,
            "_Primaries": 9,
        }
    )
    placebo = _Placebo([clip])
    core = SimpleNamespace(placebo=placebo)

    result = apply_libplacebo(
        cast("VideoNode", clip),
        TonemapSettings(tonemap_speed=TonemapSpeed.FAST, dynamic_peak_detection=False),
        cast("Core", core),
        HDRMetadata(None, 1000, 400, 9, 16, 9),
        still_image=True,
    )

    assert isinstance(result, TonemapResult)
    assert len(placebo.calls) == 1
    assert placebo.calls[0]["dynamic_peak_detection"] == 0
    assert result.applied is not None
    assert isinstance(result.applied.transform, LibplaceboTonemap)
    assert result.applied.transform.frame_policy == "shared_stateless"


@pytest.mark.parametrize(
    ("tone_curve", "expected_name"),
    [
        (ToneCurve.BT2390, "bt2390"),
        (ToneCurve.SPLINE, "spline"),
        (ToneCurve.REINHARD, "reinhard"),
    ],
)
def test_build_libplacebo_kwargs_emits_canonical_tone_curve_name(
    tone_curve: ToneCurve,
    expected_name: str,
) -> None:
    inputs = HdrTonemapInputs(
        hdr_metadata=None,
        transfer=16,
        primaries=9,
        props={},
        detected_is_hdr=True,
    )
    kwargs = build_libplacebo_tonemap_kwargs(
        settings=TonemapSettings(tone_curve=tone_curve),
        target_nits=100,
        inputs=inputs,
    )

    assert kwargs["tone_mapping_function_s"] == expected_name


def test_apply_post_processing_does_not_apply_contrast_recovery_expr() -> None:
    clip = _Clip()

    result = apply_post_processing(
        cast("VideoNode", clip),
        TonemapSettings(contrast_recovery=0.3, gamma_lift=False),
    )

    assert result is clip
    assert clip.std.expr_calls == []


def test_apply_libplacebo_runtime_failure_reports_cause_after_rgb_prop_normalization() -> None:
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

    assert result is TonemapFallbackCause.RUNTIME_CALL_FAILED
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
            "dst_prim": 3,
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
    assert len(placebo.calls) == 1
    assert clip.resize.point_calls == []


def test_convert_non_rgb_matrix_presence_uses_frame_prop_boundary() -> None:
    clip = _Clip(format_id=999, color_family=999, props={"_Matrix": b"9"})

    result = convert_non_rgb_with_matrix_hint(cast("VideoNode", clip), target_format=vs.RGBS)

    assert result is clip
    assert clip.resize.bicubic_calls == [
        {"format": vs.RGBS, "matrix_in": 9, "range_in": vs.RANGE_LIMITED}
    ]


@pytest.mark.parametrize(
    "preset, expected",
    [
        pytest.param(
            TonemapPreset.BRIGHT_LIFT,
            {
                "preset": TonemapPreset.BRIGHT_LIFT,
                "tone_curve": ToneCurve.BT2390,
                "target_nits": 250,
                "gamma_lift": True,
            },
            id="bright_lift",
        ),
        pytest.param(
            TonemapPreset.REFERENCE,
            {
                "target_nits": 100,
                "dynamic_peak_detection": True,
                "dst_min_nits": 0.18,
                "knee_offset": 0.50,
                "smoothing_period": 45.0,
                "scene_threshold_low": 0.8,
                "scene_threshold_high": 2.4,
                "percentile": 99.995,
                "metadata": 0,
                "use_dovi": True,
                "contrast_recovery": 0.30,
            },
            id="reference",
        ),
    ],
)
def test_extended_preset_settings(preset: TonemapPreset, expected: dict[str, object]) -> None:
    settings = get_preset_settings(preset)
    for field, value in expected.items():
        if field in ("preset", "tone_curve", "gamma_lift", "dynamic_peak_detection", "use_dovi"):
            assert getattr(settings, field) is value
        else:
            assert getattr(settings, field) == value
