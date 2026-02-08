"""HDR tonemapping module."""

from __future__ import annotations

import structlog
import vapoursynth as vs

from frame_compare.errors import TonemapError
from frame_compare.vs.env import detect_plugins
from frame_compare.vs.source import _detect_hdr  # pyright: ignore[reportPrivateUsage]
from frame_compare.vs.types import HDRMetadata, TonemapSettings

log = structlog.get_logger()

# Private constants
_TONE_CURVE_MAP = {"bt2390": 2, "spline": 1, "reinhard": 4}

_TONEMAP_PRESETS: dict[str, TonemapSettings] = {
    "reference": TonemapSettings(
        preset="reference", tone_curve="bt2390", target_nits=203, gamma_lift=False
    ),
    "filmic": TonemapSettings(
        preset="filmic", tone_curve="spline", target_nits=203, gamma_lift=False
    ),
    "contrast": TonemapSettings(
        preset="contrast", tone_curve="reinhard", target_nits=203, gamma_lift=False
    ),
    "bt2390_spec": TonemapSettings(
        preset="bt2390_spec", tone_curve="bt2390", target_nits=100, gamma_lift=False
    ),
    "spline": TonemapSettings(
        preset="spline", tone_curve="spline", target_nits=203, gamma_lift=False
    ),
    "bright_lift": TonemapSettings(
        preset="bright_lift", tone_curve="bt2390", target_nits=250, gamma_lift=True
    ),
    "highlight_guard": TonemapSettings(
        preset="highlight_guard",
        tone_curve="spline",
        target_nits=180,
        gamma_lift=False,
    ),
}


def _deduce_src_csp_hint(transfer: int | None, primaries: int | None) -> int | None:
    """Return vs-placebo `src_csp` hint based on HDR signaling.

    This mirrors the legacy behavior documented in `docs/archive/legacy_tonemap_info.md`.
    """
    if transfer == 16 and primaries == 9:
        return 1  # PQ + BT.2020 → HDR10
    if transfer == 18 and primaries == 9:
        return 2  # HLG + BT.2020 → HLG
    return None


def _normalize_rgb_props(
    clip: vs.VideoNode, *, transfer: int | None, primaries: int | None
) -> vs.VideoNode:
    """Normalize RGB clip props before libplacebo tonemapping.

    Sets:
        _Matrix=0 (RGB), _ColorRange=0 (full)
    Preserves (when provided):
        _Transfer, _Primaries
    """
    kwargs: dict[str, int] = {"_Matrix": 0, "_ColorRange": 0}
    if transfer is not None:
        kwargs["_Transfer"] = int(transfer)
    if primaries is not None:
        kwargs["_Primaries"] = int(primaries)
    return clip.std.SetFrameProps(**kwargs)


def _to_rgbs(clip: vs.VideoNode) -> vs.VideoNode:
    """Convert clip to RGBS if needed."""
    try:
        if clip.format.id != vs.RGBS:  # type: ignore
            if clip.format.color_family == vs.RGB:  # type: ignore
                return clip.resize.Bicubic(format=vs.RGBS)  # type: ignore
            else:
                props = dict(clip.get_frame(0).props)
                matrix_prop = props.get("_Matrix")
                matrix_in_s: str | None = None
                if matrix_prop is None:
                    is_hdr, _ = _detect_hdr(props)
                    matrix_in_s = "2020ncl" if is_hdr else "709"

                if matrix_in_s is None:
                    return clip.resize.Bicubic(format=vs.RGBS)  # type: ignore
                return clip.resize.Bicubic(format=vs.RGBS, matrix_in_s=matrix_in_s)  # type: ignore
        return clip
    except Exception as e:
        raise TonemapError(
            reason=f"Failed to convert to RGBS: {e}",
            hint="Check input clip format compatibility",
        ) from e


def _apply_post_processing(clip: vs.VideoNode, settings: TonemapSettings) -> vs.VideoNode:
    """Apply unified post-processing (contrast recovery and gamma lift)."""
    try:
        if settings.contrast_recovery > 0.0:
            factor = 1 + settings.contrast_recovery
            expr = f"x 0.5 - {factor} * 0.5 + 0 max 1 min"
            clip = clip.std.Expr(expr=[expr, expr, expr])

        if settings.gamma_lift:
            clip = clip.std.Levels(gamma=0.9)

        return clip
    except Exception as e:
        raise TonemapError(
            reason=f"Post-processing failed: {e}",
            hint="Check post-processing parameters",
        ) from e


def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode | None:
    """Apply tonemapping using libplacebo."""
    if settings.tone_curve not in _TONE_CURVE_MAP:
        raise TonemapError(
            reason=f"Unsupported tone curve '{settings.tone_curve}'",
            hint="Supported: bt2390, spline, reinhard",
        )

    props: dict[str, object] | None = None
    detected_is_hdr: bool | None = None
    detected_hdr_metadata: HDRMetadata | None = None

    def _ensure_hdr_detection() -> None:
        nonlocal props, detected_is_hdr, detected_hdr_metadata
        if detected_is_hdr is not None:
            return
        if props is None:
            props = dict(clip.get_frame(0).props)
        detected_is_hdr, detected_hdr_metadata = _detect_hdr(props)

    if hdr_metadata is None:
        _ensure_hdr_detection()
        hdr_metadata = detected_hdr_metadata
    transfer_raw: object | None = (
        getattr(hdr_metadata, "transfer", None) if hdr_metadata is not None else None
    )
    primaries_raw: object | None = (
        getattr(hdr_metadata, "color_primaries", None) if hdr_metadata is not None else None
    )
    transfer: int | None = transfer_raw if isinstance(transfer_raw, int) else None
    primaries: int | None = primaries_raw if isinstance(primaries_raw, int) else None

    # Exact conversion call for libplacebo path
    try:
        if clip.format.bits_per_sample != 16 or clip.format.color_family != vs.RGB:  # type: ignore
            if clip.format.color_family == vs.RGB:  # type: ignore
                clip = clip.resize.Bicubic(format=vs.RGB48)  # type: ignore
            else:
                if props is None:
                    props = dict(clip.get_frame(0).props)
                matrix_prop = props.get("_Matrix")
                matrix_in_s: str | None = None
                if matrix_prop is None:
                    _ensure_hdr_detection()
                    matrix_in_s = "2020ncl" if detected_is_hdr else "709"

                if matrix_in_s is None:
                    clip = clip.resize.Bicubic(format=vs.RGB48)  # type: ignore
                else:
                    clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s=matrix_in_s)  # type: ignore
    except Exception as e:
        raise TonemapError(reason=f"Failed to convert to RGB48: {e}") from e

    try:
        clip = _normalize_rgb_props(clip, transfer=transfer, primaries=primaries)
    except Exception as e:
        raise TonemapError(reason=f"Failed to normalize RGB props for tonemap: {e}") from e

    src_max = settings.source_peak
    if src_max is None:
        src_max = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

    try:
        src_csp = _deduce_src_csp_hint(transfer, primaries)
        tm_kwargs: dict[str, object] = {
            "src_max": src_max,
            "dst_max": settings.target_nits,
            "tone_mapping_function": _TONE_CURVE_MAP[settings.tone_curve],
            # SDR output targeting BT.709 (legacy default).
            "dst_csp": 0,
            "dst_prim": 1,
        }
        if src_csp is not None:
            tm_kwargs["src_csp"] = src_csp

        log.debug(
            "libplacebo_tonemap_call",
            transfer=transfer,
            primaries=primaries,
            src_csp=src_csp,
            src_max=src_max,
            dst_max=settings.target_nits,
            tone_curve=settings.tone_curve,
        )

        # We need to type ignore because VS plugin properties are dynamic.
        try:
            clip = core.placebo.Tonemap(clip, **tm_kwargs)  # type: ignore[misc]
        except TypeError as e:
            # Compatibility retry: some vs-placebo builds may not support all kwargs.
            msg = str(e)
            if "unexpected keyword" not in msg:
                raise

            minimal_kwargs: dict[str, object] = {
                "src_max": tm_kwargs["src_max"],
                "dst_max": tm_kwargs["dst_max"],
                "tone_mapping_function": tm_kwargs["tone_mapping_function"],
            }
            # Keep the retry minimal for broad compatibility across placebo builds.
            # In practice `src_csp` is the most likely optional kwarg to be unsupported.

            log.debug(
                "libplacebo_tonemap_retry_dropped_kwargs",
                error=msg,
                dropped=sorted(set(tm_kwargs.keys()) - set(minimal_kwargs.keys())),
            )
            clip = core.placebo.Tonemap(clip, **minimal_kwargs)  # type: ignore[misc]
    except Exception as e:
        # Runtime failure (Vulkan/context/bit-depth) — signal fallback
        log.warning(
            "libplacebo_tonemap_runtime_failure_falling_back",
            error=f"{type(e).__name__}: {e}",
        )
        return None

    # Convert libplacebo output back to RGBS for post-processing (runs on SUCCESS only)
    clip = clip.resize.Point(format=vs.RGBS)  # type: ignore

    return _apply_post_processing(clip, settings)


def _fallback_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Fallback tonemapping using a scaled Reinhard-style curve via std.Expr."""
    clip = _to_rgbs(clip)

    if hdr_metadata is None:
        props = dict(clip.get_frame(0).props)
        _, hdr_metadata = _detect_hdr(props)

    peak = settings.source_peak
    if peak is None:
        peak = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

    target_nits = settings.target_nits

    try:
        # Heuristic fallback when libplacebo is unavailable or fails at runtime.
        #
        # Notes:
        # - VS float RGB clips are typically normalized, and we want to avoid producing
        #   near-zero output (black screenshots). We therefore operate on a relative
        #   scale and normalize roughly around the configured target nits.
        #
        # Define:
        #   x_rel = x * (peak / target_nits)
        #   y = 2 * x_rel / (1 + x_rel)
        # which maps x_rel=1 → y≈1 (after the 2x), and compresses highlights.
        scale = float(peak) / float(target_nits)
        scale_s = f"{scale:.10g}"
        expr = f"x {scale_s} * dup 1 + / 2 * 0 max 1 min"
        clip = clip.std.Expr(expr=[expr, expr, expr])
    except Exception as e:
        raise TonemapError(
            reason=f"Fallback tonemap failed: {e}",
            hint="Check fallback parameters",
        ) from e

    return _apply_post_processing(clip, settings)


def get_preset_settings(preset: str) -> TonemapSettings:
    """Get settings for named preset."""
    if preset not in _TONEMAP_PRESETS:
        raise TonemapError(
            reason=f"Unknown preset '{preset}'",
            hint=f"Available: {', '.join(_TONEMAP_PRESETS.keys())}",
        )
    return _TONEMAP_PRESETS[preset]


def apply_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Apply HDR to SDR tonemapping."""
    if not settings.enabled:
        return clip

    core = vs.core

    plugins = detect_plugins(core)

    if plugins.get("libplacebo", False):
        result = _apply_libplacebo(clip, settings, core, hdr_metadata)
        if result is not None:
            return result
        # libplacebo failed at runtime, fall through to fallback
    return _fallback_tonemap(clip, settings, hdr_metadata)
