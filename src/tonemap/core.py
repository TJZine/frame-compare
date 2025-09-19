"""Tonemapping pipeline built around libplacebo."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Optional

from .config import TMConfig
from .detect import is_hdr
from .exceptions import TonemapError
from .overlay import apply_overlay, build_overlay_lines

logger = logging.getLogger(__name__)

_SDR_PROPS = {
    "_Matrix": 1,
    "_Primaries": 1,
    "_Transfer": 1,
    "_ColorRange": 0,
}

_RANGE_NAME_TO_VALUE = {
    "full": 0,
    "range_full": 0,
    "limited": 1,
    "range_limited": 1,
}

_RANGE_VALUE_TO_NAME = {
    0: "full",
    1: "limited",
}

_MATRIX_CODE_TO_NAME = {
    0: "rgb",
    1: "bt709",
    6: "smpte240m",
    8: "bt2020ncl",
    9: "bt2020cl",
}

_PRIMARIES_CODE_TO_NAME = {
    1: "bt709",
    4: "bt470bg",
    5: "smpte170m",
    6: "smpte240m",
    9: "bt2020",
}

_TRANSFER_CODE_TO_NAME = {
    1: "bt709",
    4: "gamma22",
    5: "gamma28",
    6: "smpte170m",
    7: "smpte240m",
    8: "linear",
    9: "log100",
    10: "log316",
    11: "iec61966-2-4",
    13: "iec61966-2-1",
    14: "bt1361",
    15: "bt2020-10",
    16: "st2084",
    17: "bt2020-12",
    18: "arib-std-b67",
}


@dataclass(slots=True)
class TonemapResult:
    """Outcome of an `apply_tonemap` invocation."""

    clip: Any
    fallback_clip: Any
    used_libplacebo: bool
    hdr_detected: bool


def _normalise(value: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _extract_frame_props(clip: Any) -> Mapping[str, Any]:
    getter = getattr(clip, "get_frame_props", None)
    if callable(getter):
        try:
            props = getter()
            if isinstance(props, Mapping):
                return props
        except Exception:  # pragma: no cover - plugin specific behaviour
            pass
    frame_props = getattr(clip, "frame_props", None)
    if isinstance(frame_props, Mapping):
        return frame_props
    return {}


def _normalise_color_range(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value if value in (0, 1) else None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered.isdigit():
            try:
                numeric = int(lowered)
            except ValueError:
                numeric = None
            else:
                if numeric in (0, 1):
                    return numeric
        return _RANGE_NAME_TO_VALUE.get(lowered)
    return None


def _normalise_range_name(value: Any) -> Optional[str]:
    numeric = _normalise_color_range(value)
    if numeric is not None:
        return _RANGE_VALUE_TO_NAME.get(numeric)
    normalised = _normalise(value)
    if isinstance(normalised, str) and normalised:
        return normalised
    return None


def _coerce_csp_value(value: Any, mapping: Mapping[int, str]) -> Optional[str]:
    if value is None:
        return None
    normalised = _normalise(value)
    if isinstance(normalised, int):
        return mapping.get(normalised)
    if isinstance(normalised, str) and normalised:
        return normalised
    return None


def _set_sdr_props(clip: Any, *, color_range: Any = None) -> Any:
    std = getattr(clip, "std", None)
    setter = getattr(std, "SetFrameProps", None) if std is not None else None
    if not callable(setter):
        logger.debug("tonemap.set_props skip: std.SetFrameProps unavailable")
        return clip
    try:
        props = dict(_SDR_PROPS)
        resolved_range = _normalise_color_range(color_range)
        if resolved_range is not None:
            props["_ColorRange"] = resolved_range
        return setter(**props)
    except Exception:  # pragma: no cover - defensive
        logger.debug("tonemap.set_props failure; leaving props untouched", exc_info=True)
        return clip


def _resolve_resize(core: Any, attribute: str) -> Optional[Any]:
    resize = getattr(core, "resize", None)
    if resize is None:
        return None
    return getattr(resize, attribute, None)


def _convert_to_rgb(clip: Any, props: Mapping[str, Any]) -> Any:
    core = getattr(clip, "core", None)
    if core is None:
        raise TonemapError("VapourSynth core is unavailable on clip")
    to_rgb = _resolve_resize(core, "Bicubic") or _resolve_resize(core, "Spline36")
    if not callable(to_rgb):
        logger.debug("tonemap.rgb conversion skipped; resize core missing")
        return clip
    try:
        import vapoursynth as vs  # noqa: WPS433 - optional runtime dep
    except Exception:  # pragma: no cover - VS absent in tests
        vs = None
    kwargs: Dict[str, Any] = {}
    matrix_in = _coerce_csp_value(props.get("_Matrix") or props.get("Matrix"), _MATRIX_CODE_TO_NAME)
    primaries_in = _coerce_csp_value(props.get("_Primaries") or props.get("Primaries"), _PRIMARIES_CODE_TO_NAME)
    transfer_in = _coerce_csp_value(props.get("_Transfer") or props.get("Transfer"), _TRANSFER_CODE_TO_NAME)
    range_in = _normalise_range_name(props.get("_ColorRange") or props.get("ColorRange"))
    if matrix_in:
        kwargs["matrix_in_s"] = matrix_in
    if primaries_in:
        kwargs["primaries_in_s"] = primaries_in
    if transfer_in:
        kwargs["transfer_in_s"] = transfer_in
    if range_in:
        kwargs["range_in_s"] = range_in
    if vs is not None:
        kwargs["format"] = getattr(vs, "RGB48", None)
    try:
        rgb_clip = to_rgb(clip, **kwargs)
        logger.debug("tonemap.rgb conversion completed with kwargs=%s", kwargs)
        return rgb_clip
    except Exception as exc:  # pragma: no cover - depends on runtime
        logger.warning("RGB conversion failed (%s); using source clip", exc)
        return clip


def _dither_to_rgb24(clip: Any, cfg: TMConfig, *, target_range: str) -> Any:
    core = getattr(clip, "core", None)
    if core is None:
        return clip
    to_8bit = _resolve_resize(core, "Point") or _resolve_resize(core, "Bicubic")
    if not callable(to_8bit):
        return clip
    try:
        import vapoursynth as vs  # noqa: WPS433
    except Exception:  # pragma: no cover
        vs = None
    kwargs: Dict[str, Any] = {
        "primaries_s": cfg.dst_primaries,
        "transfer_s": cfg.dst_transfer,
        "matrix_s": cfg.dst_matrix,
        "range_s": target_range,
        "range_in_s": "full",
    }
    if vs is not None:
        kwargs["format"] = getattr(vs, "RGB24", None)
    try:
        return to_8bit(clip, **kwargs)
    except Exception:  # pragma: no cover
        logger.debug("RGB24 dither failed; returning high bit-depth clip", exc_info=True)
        return clip


def _stamp_tonemap_metadata(clip: Any, cfg: TMConfig, *, backend: str) -> Any:
    std = getattr(clip, "std", None)
    set_props = getattr(std, "SetFrameProps", None) if std is not None else None
    if not callable(set_props):
        logger.debug("tonemap.metadata skip: SetFrameProps unavailable")
        return clip

    summary = (
        f"{backend}:{cfg.func},dpd={int(bool(cfg.dpd))},dst_max={cfg.dst_max:.2f},"
        f"dst_min={cfg.dst_min:.4f},gamut={cfg.gamut_mapping},smooth={cfg.smoothing_period},"
        f"scene={cfg.scene_threshold_low:.2f}/{cfg.scene_threshold_high:.2f},dovi={int(bool(cfg.use_dovi))}"
    )
    overlay_lines = build_overlay_lines(cfg)
    props: Dict[str, Any] = {"_Tonemapped": summary}
    if overlay_lines:
        props["_TonemapOverlay"] = "\n".join(overlay_lines)

    try:
        return set_props(**props)
    except Exception:  # pragma: no cover - defensive
        logger.debug("tonemap.metadata stamp failed", exc_info=True)
        return clip


def _call_libplacebo(clip: Any, cfg: TMConfig, props: Mapping[str, Any]) -> Any:
    core = getattr(clip, "core", None)
    if core is None:
        raise TonemapError("VapourSynth core is unavailable on clip")
    libplacebo = getattr(core, "libplacebo", None)
    tonemap = getattr(libplacebo, "Tonemap", None) if libplacebo is not None else None
    if not callable(tonemap):
        raise TonemapError("libplacebo.Tonemap is unavailable")

    base_kwargs = cfg.to_libplacebo_kwargs()
    base_kwargs["use_dovi"] = bool(cfg.use_dovi)

    matrix = _normalise(props.get("_Matrix") or props.get("Matrix"))
    primaries = _normalise(props.get("_Primaries") or props.get("Primaries"))
    transfer = _normalise(props.get("_Transfer") or props.get("Transfer"))

    hint_candidates = [
        {},
        {"src_matrix": matrix, "src_prim": primaries, "src_tf": transfer},
        {"src_tf": "st2084"},
    ]

    last_error: Exception | None = None
    for hint in hint_candidates:
        kwargs = {key: value for key, value in hint.items() if value}
        kwargs.update(base_kwargs)
        try:
            logger.debug("tonemap.libplacebo attempt kwargs=%s", kwargs)
            return tonemap(clip, **kwargs)
        except Exception as exc:  # pragma: no cover - runtime driven
            last_error = exc
            logger.debug("tonemap.libplacebo attempt failed: %s", exc)
    if last_error is not None:
        raise TonemapError(f"libplacebo tonemapping failed: {last_error}") from last_error
    raise TonemapError("libplacebo tonemap failed with no successful attempts")


def _linear_sdr_fallback(clip: Any, props: Mapping[str, Any], cfg: TMConfig, *, target_range: str) -> Any:
    core = getattr(clip, "core", None)
    if core is None:
        raise TonemapError("VapourSynth core unavailable for fallback path")
    convert = _resolve_resize(core, "Bicubic") or _resolve_resize(core, "Spline36")
    if not callable(convert):
        raise TonemapError("resize namespace missing for fallback tonemap")
    try:
        import vapoursynth as vs  # noqa: WPS433
    except Exception:
        vs = None
    kwargs: Dict[str, Any] = {}
    matrix_in = _coerce_csp_value(props.get("_Matrix") or props.get("Matrix"), _MATRIX_CODE_TO_NAME)
    primaries_in = _coerce_csp_value(props.get("_Primaries") or props.get("Primaries"), _PRIMARIES_CODE_TO_NAME)
    transfer_in = _coerce_csp_value(props.get("_Transfer") or props.get("Transfer"), _TRANSFER_CODE_TO_NAME)
    range_in = _normalise_range_name(props.get("_ColorRange") or props.get("ColorRange"))
    if matrix_in:
        kwargs["matrix_in_s"] = matrix_in
    if primaries_in:
        kwargs["primaries_in_s"] = primaries_in
    if transfer_in:
        kwargs["transfer_in_s"] = transfer_in
    if range_in:
        kwargs["range_in_s"] = range_in
    kwargs.update(
        {
            "matrix_s": cfg.dst_matrix,
            "primaries_s": cfg.dst_primaries,
            "transfer_s": cfg.dst_transfer,
            "range_s": target_range,
        }
    )
    if vs is not None:
        kwargs["format"] = getattr(vs, "RGB24", None)
    logger.debug("tonemap.fallback kwargs=%s", kwargs)
    return convert(clip, **kwargs)


def apply_tonemap(clip: Any, cfg: TMConfig, *, force: bool = False) -> TonemapResult:
    """Apply tonemapping to *clip* using configuration *cfg*."""

    props = _extract_frame_props(clip)
    resolved_cfg = cfg.resolved()
    source_range_value = props.get("_ColorRange")
    if source_range_value is None:
        source_range_value = props.get("ColorRange")
    source_range = _normalise_color_range(source_range_value)
    target_range_name = _normalise_range_name(resolved_cfg.dst_range) or "full"
    target_range_value = _RANGE_NAME_TO_VALUE.get(target_range_name, 0)

    try:
        hdr_detected = is_hdr(props)
    except Exception as exc:
        logger.debug("HDR detection failed (%s); assuming SDR", exc)
        hdr_detected = False

    if not hdr_detected and not (force or resolved_cfg.always_try_placebo):
        logger.debug(
            "tonemap skipped (hdr=%s force=%s always_try=%s)",
            hdr_detected,
            force,
            resolved_cfg.always_try_placebo,
        )
        clean_clip = _set_sdr_props(clip, color_range=source_range)
        if resolved_cfg.overlay:
            clean_clip = apply_overlay(clean_clip, resolved_cfg)
        return TonemapResult(clean_clip, clean_clip, False, hdr_detected)

    rgb_clip = _convert_to_rgb(clip, props)

    try:
        fallback_clip = _linear_sdr_fallback(rgb_clip, props, resolved_cfg, target_range=target_range_name)
        fallback_clip = _set_sdr_props(fallback_clip, color_range=target_range_value)
    except TonemapError as exc:
        logger.debug("Fallback path unavailable: %s", exc)
        fallback_clip = _set_sdr_props(rgb_clip, color_range=target_range_value)

    used_libplacebo = True
    try:
        tonemapped = _call_libplacebo(rgb_clip, resolved_cfg, props)
        logger.info(
            "tonemap.libplacebo applied func=%s dpd=%s dst_max=%.2f dst_min=%.4f gamut=%s smooth=%d scene_low=%.3f scene_high=%.3f dovi=%s fingerprint=%s",
            resolved_cfg.func,
            resolved_cfg.dpd,
            resolved_cfg.dst_max,
            resolved_cfg.dst_min,
            resolved_cfg.gamut_mapping,
            resolved_cfg.smoothing_period,
            resolved_cfg.scene_threshold_low,
            resolved_cfg.scene_threshold_high,
            resolved_cfg.use_dovi,
            resolved_cfg.fingerprint(),
        )
    except TonemapError as exc:
        if resolved_cfg.always_try_placebo or force:
            logger.warning("libplacebo failed (%s); reverting to fallback", exc)
        else:
            logger.debug("libplacebo not available (%s); using fallback", exc)
        tonemapped = fallback_clip
        used_libplacebo = False

    output = _dither_to_rgb24(tonemapped, resolved_cfg, target_range=target_range_name)
    backend = "placebo" if used_libplacebo else "fallback"
    output = _stamp_tonemap_metadata(output, resolved_cfg, backend=backend)
    if resolved_cfg.overlay:
        output = apply_overlay(output, resolved_cfg)
    output = _set_sdr_props(output, color_range=target_range_value)
    return TonemapResult(output, fallback_clip, used_libplacebo, hdr_detected)
