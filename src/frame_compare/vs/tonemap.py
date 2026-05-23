"""HDR tonemapping module."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import structlog

from frame_compare.config.schema import ToneCurve, TonemapPreset
from frame_compare.errors import TonemapError
from frame_compare.vs.env import detect_plugins
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

log = structlog.get_logger()

_REQUIRE_LIBPLACEBO_ENV = "FRAME_COMPARE_REQUIRE_LIBPLACEBO"
_DISABLE_LIBPLACEBO_ENV = "FRAME_COMPARE_DISABLE_LIBPLACEBO"
_LIBPLACEBO_PROBE_ENV = "FRAME_COMPARE_LIBPLACEBO_PROBE"
_LIBPLACEBO_PROBE_TIMEOUT_SECONDS = 5.0

# Private constants
_TONE_CURVE_MAP: dict[ToneCurve, int] = {
    ToneCurve.BT2390: 2,
    ToneCurve.SPLINE: 1,
    ToneCurve.REINHARD: 4,
}

_TONEMAP_PRESETS: dict[TonemapPreset, TonemapSettings] = {
    TonemapPreset.REFERENCE: TonemapSettings(
        preset=TonemapPreset.REFERENCE,
        tone_curve=ToneCurve.BT2390,
        target_nits=203,
        gamma_lift=False,
    ),
    TonemapPreset.FILMIC: TonemapSettings(
        preset=TonemapPreset.FILMIC, tone_curve=ToneCurve.SPLINE, target_nits=203, gamma_lift=False
    ),
    TonemapPreset.CONTRAST: TonemapSettings(
        preset=TonemapPreset.CONTRAST,
        tone_curve=ToneCurve.REINHARD,
        target_nits=203,
        gamma_lift=False,
    ),
    TonemapPreset.BT2390_SPEC: TonemapSettings(
        preset=TonemapPreset.BT2390_SPEC,
        tone_curve=ToneCurve.BT2390,
        target_nits=100,
        gamma_lift=False,
    ),
    TonemapPreset.SPLINE: TonemapSettings(
        preset=TonemapPreset.SPLINE, tone_curve=ToneCurve.SPLINE, target_nits=203, gamma_lift=False
    ),
    TonemapPreset.BRIGHT_LIFT: TonemapSettings(
        preset=TonemapPreset.BRIGHT_LIFT,
        tone_curve=ToneCurve.BT2390,
        target_nits=250,
        gamma_lift=True,
    ),
    TonemapPreset.HIGHLIGHT_GUARD: TonemapSettings(
        preset=TonemapPreset.HIGHLIGHT_GUARD,
        tone_curve=ToneCurve.SPLINE,
        target_nits=180,
        gamma_lift=False,
    ),
}


@dataclass(slots=True)
class _LibplaceboRuntimeState:
    """Process-owned state for the libplacebo runtime probe."""

    probe_result: bool | None = None


_LIBPLACEBO_RUNTIME_STATE = _LibplaceboRuntimeState()


@dataclass(frozen=True, slots=True)
class _HdrTonemapInputs:
    hdr_metadata: HDRMetadata | None
    transfer: int | None
    primaries: int | None
    props: dict[str, object] | None
    detected_is_hdr: bool | None


def _probe_libplacebo_runtime() -> bool:
    """Run the subprocess probe to check if libplacebo is usable."""
    probe_script = textwrap.dedent(
        """
        import vapoursynth as vs

        core = vs.core
        if not hasattr(core, "placebo") or not hasattr(core.placebo, "Tonemap"):
            raise SystemExit(2)

        clip = core.std.BlankClip(
            width=16,
            height=16,
            format=vs.RGB48,
            length=1,
            color=[32768, 32768, 32768],
        )
        clip = clip.std.SetFrameProps(
            _Matrix=0,
            _ColorRange=0,
            _Transfer=16,
            _Primaries=9,
        )
        out = core.placebo.Tonemap(
            clip,
            src_max=1000,
            dst_max=203,
            tone_mapping_function=2,
            dst_csp=0,
            dst_prim=1,
            src_csp=1,
        )
        _ = out.get_frame(0)
        """
    )
    env = os.environ.copy()
    env[_LIBPLACEBO_PROBE_ENV] = "1"

    try:
        result = subprocess.run(
            [sys.executable, "-c", probe_script],
            env=env,
            capture_output=True,
            text=True,
            timeout=_LIBPLACEBO_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning(
            "libplacebo_probe_failed_disabling",
            error=f"{type(exc).__name__}: {exc}",
        )
        return False

    if result.returncode == 0:
        return True

    log.warning(
        "libplacebo_probe_unusable_disabling",
        returncode=result.returncode,
        stdout=result.stdout.strip()[-400:],
        stderr=result.stderr.strip()[-400:],
    )
    return False


def _libplacebo_runtime_override() -> bool | None:
    """Return a per-call runtime override, if one is set."""
    if os.environ.get(_REQUIRE_LIBPLACEBO_ENV) == "1":
        return True
    if os.environ.get(_DISABLE_LIBPLACEBO_ENV) == "1":
        return False
    if os.environ.get(_LIBPLACEBO_PROBE_ENV) == "1":
        return True
    return None


def _cached_libplacebo_runtime_probe() -> bool:
    """Return the cached subprocess probe result for this process lifetime."""
    cached_result = _LIBPLACEBO_RUNTIME_STATE.probe_result
    if cached_result is not None:
        return cached_result

    probe_result = _probe_libplacebo_runtime()
    _LIBPLACEBO_RUNTIME_STATE.probe_result = probe_result
    return probe_result


def _libplacebo_runtime_usable() -> bool:
    """Return whether libplacebo is safe to call in this process.

    Plugin presence is not sufficient on all Docker/Vulkan setups: some
    environments expose `core.placebo.Tonemap` but crash the process when it is
    invoked. We probe that path in a child Python process once, cache the
    result, and keep the main process on the deterministic fallback path when
    the probe fails.

    Env overrides are re-evaluated on every call and do not mutate the cached
    subprocess probe result. The probe result itself is cached for the process
    lifetime so repeated tonemap decisions stay deterministic after the first
    probe.
    """
    override = _libplacebo_runtime_override()
    if override is not None:
        return override

    return _cached_libplacebo_runtime_probe()


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


def _validate_target_nits(settings: TonemapSettings) -> int:
    """Validate and return target nits used by tonemap operations."""
    target_nits = settings.target_nits
    if target_nits <= 0:
        raise TonemapError(
            reason=f"Invalid target_nits: {target_nits}. target_nits must be > 0",
            hint="Set color.target_nits to a positive value",
        )
    return target_nits


def _convert_non_rgb_with_matrix_hint(
    clip: vs.VideoNode,
    *,
    target_format: int,
    props: dict[str, object] | None = None,
    detected_is_hdr: bool | None = None,
) -> vs.VideoNode:
    """Convert non-RGB clips to RGB target format with deterministic matrix fallback."""
    if props is None:
        props = dict(clip.get_frame(0).props)

    # VapourSynth frame properties are dynamic and populated by the VapourSynth runtime.
    # We read '_Matrix' directly from the clip's frame properties.
    matrix_prop = props.get("_Matrix")
    matrix_in_s: str | None = None
    if matrix_prop is None:
        if detected_is_hdr is None:
            detected_is_hdr, _ = detect_hdr(props)
        matrix_in_s = "2020ncl" if detected_is_hdr else "709"

    if matrix_in_s is None:
        return clip.resize.Bicubic(format=target_format)  # type: ignore[attr-defined]
    return clip.resize.Bicubic(format=target_format, matrix_in_s=matrix_in_s)  # type: ignore[attr-defined]


def _to_rgbs(clip: vs.VideoNode) -> vs.VideoNode:
    """Convert clip to RGBS if needed."""
    import vapoursynth as vs

    try:
        if clip.format.id != vs.RGBS:  # type: ignore
            if clip.format.color_family == vs.RGB:  # type: ignore
                return clip.resize.Bicubic(format=vs.RGBS)  # type: ignore
            rgbs_format = cast(int, vs.RGBS)  # type: ignore[attr-defined]
            return _convert_non_rgb_with_matrix_hint(clip, target_format=rgbs_format)
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


def _resolve_hdr_tonemap_inputs(
    clip: vs.VideoNode,
    hdr_metadata: HDRMetadata | None,
) -> _HdrTonemapInputs:
    props: dict[str, object] | None = None
    detected_is_hdr: bool | None = None
    if hdr_metadata is None:
        props = dict(clip.get_frame(0).props)
        detected_is_hdr, hdr_metadata = detect_hdr(props)

    transfer_raw: object | None = (
        getattr(hdr_metadata, "transfer", None) if hdr_metadata is not None else None
    )
    primaries_raw: object | None = (
        getattr(hdr_metadata, "color_primaries", None) if hdr_metadata is not None else None
    )
    return _HdrTonemapInputs(
        hdr_metadata=hdr_metadata,
        transfer=transfer_raw if isinstance(transfer_raw, int) else None,
        primaries=primaries_raw if isinstance(primaries_raw, int) else None,
        props=props,
        detected_is_hdr=detected_is_hdr,
    )


def _convert_for_libplacebo(clip: vs.VideoNode, inputs: _HdrTonemapInputs) -> vs.VideoNode:
    import vapoursynth as vs

    try:
        if clip.format.bits_per_sample == 16 and clip.format.color_family == vs.RGB:  # type: ignore
            return clip
        if clip.format.color_family == vs.RGB:  # type: ignore
            return clip.resize.Bicubic(format=vs.RGB48)  # type: ignore

        props = inputs.props if inputs.props is not None else dict(clip.get_frame(0).props)
        detected_is_hdr = inputs.detected_is_hdr
        if detected_is_hdr is None:
            detected_is_hdr, _ = detect_hdr(props)
        rgb48_format = cast(int, vs.RGB48)  # type: ignore[attr-defined]
        return _convert_non_rgb_with_matrix_hint(
            clip,
            target_format=rgb48_format,
            props=props,
            detected_is_hdr=detected_is_hdr,
        )
    except Exception as e:
        raise TonemapError(reason=f"Failed to convert to RGB48: {e}") from e


def _build_libplacebo_tonemap_kwargs(
    *,
    settings: TonemapSettings,
    target_nits: int,
    inputs: _HdrTonemapInputs,
) -> dict[str, object]:
    src_max = settings.source_peak
    if src_max is None:
        metadata = inputs.hdr_metadata
        src_max = metadata.max_cll if metadata and metadata.max_cll else 1000

    src_csp = _deduce_src_csp_hint(inputs.transfer, inputs.primaries)
    tm_kwargs: dict[str, object] = {
        "src_max": src_max,
        "dst_max": target_nits,
        "tone_mapping_function": _TONE_CURVE_MAP[settings.tone_curve],
        # SDR output targeting BT.709 (legacy default).
        "dst_csp": 0,
        "dst_prim": 1,
    }
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


def _call_libplacebo_with_compat_retry(
    core: vs.Core,
    clip: vs.VideoNode,
    tm_kwargs: dict[str, object],
) -> vs.VideoNode:
    try:
        return core.placebo.Tonemap(clip, **tm_kwargs)  # type: ignore[misc]
    except TypeError as e:
        minimal_kwargs: dict[str, object] = {
            "src_max": tm_kwargs["src_max"],
            "dst_max": tm_kwargs["dst_max"],
            "tone_mapping_function": tm_kwargs["tone_mapping_function"],
        }
        log.debug(
            "libplacebo_tonemap_retry_dropped_kwargs",
            error=str(e),
            dropped=sorted(set(tm_kwargs.keys()) - set(minimal_kwargs.keys())),
        )
        return core.placebo.Tonemap(clip, **minimal_kwargs)  # type: ignore[misc]


def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode | None:
    """Apply tonemapping using libplacebo."""
    import vapoursynth as vs

    target_nits = _validate_target_nits(settings)

    if settings.tone_curve not in _TONE_CURVE_MAP:
        raise TonemapError(
            reason=f"Unsupported tone curve '{settings.tone_curve}'",
            hint="Supported: bt2390, spline, reinhard",
        )

    inputs = _resolve_hdr_tonemap_inputs(clip, hdr_metadata)
    clip = _convert_for_libplacebo(clip, inputs)

    try:
        clip = _normalize_rgb_props(clip, transfer=inputs.transfer, primaries=inputs.primaries)
    except Exception as e:
        raise TonemapError(reason=f"Failed to normalize RGB props for tonemap: {e}") from e

    try:
        tm_kwargs = _build_libplacebo_tonemap_kwargs(
            settings=settings,
            target_nits=target_nits,
            inputs=inputs,
        )
        clip = _call_libplacebo_with_compat_retry(core, clip, tm_kwargs)
    except Exception as e:
        if isinstance(e, TonemapError | AttributeError | KeyError | AssertionError):
            raise
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
    target_nits = _validate_target_nits(settings)
    clip = _to_rgbs(clip)

    if hdr_metadata is None:
        props = dict(clip.get_frame(0).props)
        _, hdr_metadata = detect_hdr(props)

    peak = settings.source_peak
    if peak is None:
        peak = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

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


def get_preset_settings(preset: TonemapPreset) -> TonemapSettings:
    """Get settings for named preset."""
    if preset not in _TONEMAP_PRESETS:
        raise TonemapError(
            reason=f"Unknown preset '{preset}'",
            hint=f"Available: {', '.join(candidate.value for candidate in _TONEMAP_PRESETS)}",
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
    _validate_target_nits(settings)

    import vapoursynth as vs

    core = vs.core

    plugins = detect_plugins(core)

    if plugins.get("libplacebo", False) and _libplacebo_runtime_usable():
        result = _apply_libplacebo(clip, settings, core, hdr_metadata)
        if result is not None:
            return result
        # libplacebo failed at runtime, fall through to fallback
    return _fallback_tonemap(clip, settings, hdr_metadata)
