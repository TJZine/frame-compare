"""libplacebo tonemap implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from frame_compare.config.schema import ToneCurve
from frame_compare.vs.errors import TonemapError
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.tonemap_conversion import (
    HdrTonemapInputs,
    apply_post_processing,
    convert_non_rgb_with_matrix_hint,
    deduce_src_csp_hint,
    normalize_rgb_props,
    resolve_hdr_tonemap_inputs,
    validate_target_nits,
)
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

log = structlog.get_logger()

TONE_CURVE_MAP: dict[ToneCurve, int] = {
    ToneCurve.BT2390: 2,
    ToneCurve.SPLINE: 1,
    ToneCurve.REINHARD: 4,
}

TONE_CURVE_STRING_MAP: dict[ToneCurve, str] = {
    ToneCurve.BT2390: "bt.2390",
    ToneCurve.SPLINE: "spline",
    ToneCurve.REINHARD: "reinhard",
}
_TONE_CURVE_STRING_TO_NUMERIC = {
    value: TONE_CURVE_MAP[key] for key, value in TONE_CURVE_STRING_MAP.items()
}

_BASELINE_COMPAT_KEYS = {
    "src_max",
    "dst_max",
    "tone_mapping_function",
    "tone_mapping_function_s",
    "dst_csp",
    "dst_prim",
    "src_csp",
}


def convert_for_libplacebo(clip: vs.VideoNode, inputs: HdrTonemapInputs) -> vs.VideoNode:
    import vapoursynth as vs

    try:
        if clip.format.bits_per_sample == 16 and clip.format.color_family == vs.RGB:
            return clip
        if clip.format.color_family == vs.RGB:
            return clip.resize.Bicubic(format=vs.RGB48)

        props = inputs.props if inputs.props is not None else dict(clip.get_frame(0).props)
        detected_is_hdr = inputs.detected_is_hdr
        if detected_is_hdr is None:
            detected_is_hdr, _ = detect_hdr(props)
        rgb48_format = vs.RGB48
        return convert_non_rgb_with_matrix_hint(
            clip,
            target_format=rgb48_format,
            props=props,
            detected_is_hdr=detected_is_hdr,
        )
    except Exception as e:
        raise TonemapError(reason=f"Failed to convert to RGB48: {e}") from e


def build_libplacebo_tonemap_kwargs(
    *,
    settings: TonemapSettings,
    target_nits: int,
    inputs: HdrTonemapInputs,
) -> dict[str, object]:
    src_max = settings.source_peak
    if src_max is None:
        metadata = inputs.hdr_metadata
        src_max = metadata.max_cll if metadata and metadata.max_cll else 1000

    src_csp = deduce_src_csp_hint(inputs.transfer, inputs.primaries)
    tm_kwargs: dict[str, object] = {
        "src_max": src_max,
        "dst_max": target_nits,
        "tone_mapping_function_s": TONE_CURVE_STRING_MAP[settings.tone_curve],
        "tone_mapping_param": settings.knee_offset,
        # SDR output targeting BT.709 (legacy default).
        "dst_csp": 0,
        "dst_prim": 1,
        "dst_min": settings.dst_min_nits,
        "dynamic_peak_detection": int(settings.dynamic_peak_detection),
        "smoothing_period": settings.smoothing_period,
        "scene_threshold_low": settings.scene_threshold_low,
        "scene_threshold_high": settings.scene_threshold_high,
        "percentile": settings.percentile,
        "gamut_mapping": settings.gamut_mapping,
        "contrast_recovery": settings.contrast_recovery,
        "log_level": 2,
    }
    if settings.metadata is not None:
        tm_kwargs["metadata"] = settings.metadata
    if settings.use_dovi is not None:
        tm_kwargs["use_dovi"] = int(settings.use_dovi)
    if src_csp is not None:
        tm_kwargs["src_csp"] = src_csp

    log.debug(
        "libplacebo_tonemap_call",
        transfer=inputs.transfer,
        primaries=inputs.primaries,
        src_csp=src_csp,
        src_max=src_max,
        dst_max=target_nits,
        tone_curve=settings.tone_curve,
    )
    return tm_kwargs


def _parse_rejected_tonemap_kwargs(message: str) -> set[str]:
    unexpected = "unexpected keyword argument "
    if unexpected in message:
        raw = message.split(unexpected, 1)[1].split(" ", 1)[0]
        return {raw.strip().strip("'\"")} if raw.strip() else set()

    marker = "named "
    if marker not in message:
        return set()

    raw = message.split(marker, 1)[1]
    raw = raw.split(":", 1)[0]
    raw = raw.replace(" and ", ",")
    return {part.strip().strip("'\"") for part in raw.split(",") if part.strip()}


def _add_numeric_tone_curve_fallback(kwargs: dict[str, object]) -> None:
    if "tone_mapping_function" in kwargs or "tone_mapping_function_s" not in kwargs:
        return
    tone_curve = kwargs.get("tone_mapping_function_s")
    if not isinstance(tone_curve, str):
        return
    numeric = _TONE_CURVE_STRING_TO_NUMERIC.get(tone_curve)
    if numeric is not None:
        kwargs["tone_mapping_function"] = numeric


def call_libplacebo_with_compat_retry(
    core: vs.Core,
    clip: vs.VideoNode,
    tm_kwargs: dict[str, object],
) -> vs.VideoNode:
    try:
        return core.placebo.Tonemap(clip, **tm_kwargs)  # type: ignore[misc]
    except TypeError as e:
        rejected = _parse_rejected_tonemap_kwargs(str(e))
        if rejected:
            minimal_kwargs = {key: value for key, value in tm_kwargs.items() if key not in rejected}
            if "tone_mapping_function_s" in rejected:
                _add_numeric_tone_curve_fallback(tm_kwargs)
                if "tone_mapping_function" in tm_kwargs:
                    minimal_kwargs["tone_mapping_function"] = tm_kwargs["tone_mapping_function"]
        else:
            minimal_kwargs = {
                key: value for key, value in tm_kwargs.items() if key in _BASELINE_COMPAT_KEYS
            }
        log.debug(
            "libplacebo_tonemap_retry_dropped_kwargs",
            error=str(e),
            dropped=sorted(set(tm_kwargs.keys()) - set(minimal_kwargs.keys())),
        )
        return core.placebo.Tonemap(clip, **minimal_kwargs)  # type: ignore[misc]


def apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode | None:
    """Apply tonemapping using libplacebo."""
    import vapoursynth as vs

    target_nits = validate_target_nits(settings)

    if settings.tone_curve not in TONE_CURVE_MAP:
        raise TonemapError(
            reason=f"Unsupported tone curve '{settings.tone_curve}'",
            hint="Supported: bt2390, spline, reinhard",
        )

    inputs = resolve_hdr_tonemap_inputs(clip, hdr_metadata)
    clip = convert_for_libplacebo(clip, inputs)

    try:
        clip = normalize_rgb_props(clip, transfer=inputs.transfer, primaries=inputs.primaries)
    except Exception as e:
        raise TonemapError(reason=f"Failed to normalize RGB props for tonemap: {e}") from e

    try:
        tm_kwargs = build_libplacebo_tonemap_kwargs(
            settings=settings,
            target_nits=target_nits,
            inputs=inputs,
        )
        clip = call_libplacebo_with_compat_retry(core, clip, tm_kwargs)
    except Exception as e:
        if isinstance(e, TonemapError | AttributeError | KeyError | AssertionError):
            raise
        log.warning(
            "libplacebo_tonemap_runtime_failure_falling_back",
            error=f"{type(e).__name__}: {e}",
        )
        return None

    clip = clip.resize.Point(format=vs.RGBS)

    clip = apply_post_processing(clip, settings)
    return clip.std.SetFrameProps(_Tonemapped=1, _FrameCompareExpandRange=1)
