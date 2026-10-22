"""libplacebo tonemap implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from frame_compare.config.schema import ToneCurve
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.vs import tonemap_runtime
from frame_compare.vs.errors import TonemapError
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.tonemap_conversion import (
    HdrTonemapInputs,
    apply_post_processing,
    convert_non_rgb_with_matrix_hint,
    deduce_src_csp_hint,
    libplacebo_output_to_srgb,
    normalize_rgb_props,
    resolve_hdr_tonemap_inputs,
    resolve_source_peak,
    validate_target_nits,
)
from frame_compare.vs.types import (
    AppliedTonemap,
    HDRMetadata,
    LibplaceboTonemap,
    TonemapFallbackCause,
    TonemapResult,
    TonemapSettings,
)

if TYPE_CHECKING:
    import vapoursynth as vs

log = structlog.get_logger()

TONE_CURVE_STRING_MAP: dict[ToneCurve, str] = {
    ToneCurve.BT2390: "bt2390",
    ToneCurve.SPLINE: "spline",
    ToneCurve.REINHARD: "reinhard",
}


def convert_for_libplacebo(clip: vs.VideoNode, inputs: HdrTonemapInputs) -> vs.VideoNode:
    import vapoursynth as vs

    try:
        if clip.format.bits_per_sample == 16 and clip.format.color_family == vs.RGB:
            return clip
        if clip.format.color_family == vs.RGB:
            raise_if_cancelling()
            return clip.resize.Bicubic(format=vs.RGB48)

        props = inputs.props
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
    src_max = resolve_source_peak(settings, inputs.hdr_metadata).nits

    src_csp = deduce_src_csp_hint(inputs.transfer, inputs.primaries)
    tm_kwargs: dict[str, object] = {
        "src_max": src_max,
        "dst_max": target_nits,
        "tone_mapping_function_s": TONE_CURVE_STRING_MAP[settings.tone_curve],
        "tone_mapping_param": settings.knee_offset,
        # SDR output targeting BT.709.
        "dst_csp": 0,
        "dst_prim": 3,
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


def apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
    *,
    still_image: bool = False,
) -> TonemapResult | TonemapFallbackCause:
    """Apply tonemapping using libplacebo."""
    import vapoursynth as vs

    target_nits = validate_target_nits(settings)

    if settings.tone_curve not in TONE_CURVE_STRING_MAP:
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
        raise_if_cancelling()
        clip = (
            _still_frame_tonemap(clip, core, tm_kwargs)
            if still_image
            else core.placebo.Tonemap(clip, **tm_kwargs)
        )
    except TypeError as e:
        raise TonemapError(reason=f"Invalid libplacebo Tonemap arguments: {e}") from e
    except Exception as e:
        if isinstance(e, TonemapError | AttributeError | KeyError | AssertionError):
            raise
        log.warning(
            "libplacebo_tonemap_runtime_failure_falling_back",
            error=f"{type(e).__name__}: {e}",
        )
        return TonemapFallbackCause.RUNTIME_CALL_FAILED

    raise_if_cancelling()
    clip = clip.resize.Point(format=vs.RGBS)

    clip = apply_post_processing(clip, settings)
    clip = libplacebo_output_to_srgb(clip, black_nits=settings.dst_min_nits, white_nits=target_nits)
    raise_if_cancelling()
    return TonemapResult(
        clip,
        AppliedTonemap(
            settings,
            LibplaceboTonemap(
                settings.tone_curve,
                settings,
                resolve_source_peak(settings, inputs.hdr_metadata),
                frame_policy="independent_frames" if still_image else "sequence",
            ),
        ),
    )


def _still_frame_tonemap(
    clip: vs.VideoNode, core: vs.Core, kwargs: dict[str, object]
) -> vs.VideoNode:
    """Use verified experimental reuse only for its admitted native input class."""
    if tonemap_runtime.experimental_native_stills_enabled():
        import vapoursynth as vs

        fmt = cast("vs.VideoFormat | None", clip.format)
        admitted = (
            fmt is not None
            and clip.width > 0
            and clip.height > 0
            and fmt.id == vs.RGB48
            and fmt.color_family == vs.RGB
            and fmt.sample_type == vs.INTEGER
            and fmt.bits_per_sample == 16
            and fmt.num_planes == 3
            and fmt.subsampling_w == 0
            and fmt.subsampling_h == 0
            and kwargs.get("src_csp") == 1
            and kwargs.get("dst_csp") == 0
            and "dovi_el" not in kwargs
        )
        identity = tonemap_runtime.experimental_native_still_plugin(core) if admitted else None
        if identity is not None:
            log.debug(
                "native_still_backend_selected",
                backend="experimental_independent",
                plugin_path=identity.path,
                plugin_sha256=identity.sha256,
            )
            return core.placebo.Tonemap(clip, **kwargs, independent=1)
        log.debug(
            "native_still_backend_selected",
            backend="fresh_per_frame",
            reason="capability_unverified" if admitted else "unsupported_input",
        )
    return _independent_frame_tonemap(clip, core, kwargs)


def _independent_frame_tonemap(
    clip: vs.VideoNode, core: vs.Core, kwargs: dict[str, object]
) -> vs.VideoNode:
    """Give each original frame its own native peak-detector/renderer state.

    Zero smoothing alone still retains epsilon-sized history in the native
    detector. Each mapper here sees only one source frame, even for helper reads,
    out-of-order requests and cache eviction. Loop AFTER Tonemap so the mapper
    always receives local frame zero. FrameEval owns transient node lifetimes;
    there is no Python cache retaining a renderer per screenshot.
    """
    # Admit the backend eagerly, preserving constructor failure/fallback behavior.
    first = core.placebo.Tonemap(clip[0], **kwargs).std.Loop(times=clip.num_frames)

    def evaluate(n: int) -> vs.VideoNode:
        if n == 0:
            return first
        # Later errors propagate; silently mixing fallback pixels would falsify
        # the single AppliedTonemap attached to this prepared source.
        return core.placebo.Tonemap(clip[n], **kwargs).std.Loop(times=clip.num_frames)

    return core.std.FrameEval(first, eval=evaluate, clip_src=[clip])
