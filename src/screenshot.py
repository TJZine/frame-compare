"""Screenshot planning and export utilities."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)

from . import vs_core
from .datatypes import ColorConfig, OddGeometryPolicy, RGBDither, ScreenshotConfig

_INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


logger = logging.getLogger(__name__)


_SELECTION_LABELS = {
    "dark": "Dark",
    "bright": "Bright",
    "motion": "Motion",
    "user": "User",
    "random": "Random",
    "auto": "Auto",
    "cached": "Cached",
}

OverlayStateValue = Union[str, List[str]]
OverlayState = MutableMapping[str, OverlayStateValue]


class FrameEvalFunc(Protocol):
    def __call__(
        self,
        clip: Any,
        func: Callable[[int, Any], Any],
        *,
        prop_src: Any | None = None,
    ) -> Any:
        ...


class SubtitleFunc(Protocol):
    def __call__(
        self,
        clip: Any,
        *,
        text: Sequence[str] | None = None,
        style: Any | None = None,
    ) -> Any:
        ...


def _new_overlay_state() -> OverlayState:
    """Create a mutable overlay state container."""
    return cast(OverlayState, {})


def _append_overlay_warning(state: OverlayState, message: str) -> None:
    """
    Append a formatted overlay warning to the state's warning list in a type-safe manner.
    """
    warnings_value = state.get("warnings")
    if not isinstance(warnings_value, list):
        warnings_value = []
        state["warnings"] = warnings_value
    warnings_value.append(message)


def _get_overlay_warnings(state: OverlayState) -> List[str]:
    """
    Retrieve overlay warning messages from state, returning an empty list when absent.
    """
    warnings_value = state.get("warnings")
    if isinstance(warnings_value, list):
        return warnings_value
    return []


def _format_dimensions(width: int, height: int) -> str:
    """
    Format width and height as "W × H" using integer values.

    Returns:
        str: Formatted dimensions string, e.g. "1920 × 1080".
    """
    return f"{int(width)} \u00D7 {int(height)}"


def _format_resolution_summary(plan: GeometryPlan) -> str:
    """
    Produce a human-readable summary comparing the plan's cropped (original) dimensions with its final dimensions.

    Parameters:
        plan (GeometryPlan): Geometry plan containing 'cropped_w', 'cropped_h' and 'final' width/height.

    Returns:
        str: If final dimensions equal the cropped dimensions, returns "`WxH  (native)`". Otherwise returns
             "`OriginalWxH → TargetWxH  (original → target)`", where sizes are formatted as "W×H".
    """
    original_w = int(plan["cropped_w"])
    original_h = int(plan["cropped_h"])
    final_w, final_h = plan["final"]
    original = _format_dimensions(original_w, original_h)
    target = _format_dimensions(final_w, final_h)
    if final_w == original_w and final_h == original_h:
        return f"{original}  (native)"
    return f"{original} \u2192 {target}  (original \u2192 target)"


def _coerce_luminance_values(value: Any) -> List[float]:
    """
    Normalize various luminance representations into a list of floats.

    Parameters:
        value (Any): A luminance value which may be None, a number, a string containing numeric values, bytes (UTF-8), or an iterable of such values.

    Returns:
        List[float]: A list of extracted luminance values as floats. Returns an empty list when no numeric values can be derived.
    """
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "ignore")
        except Exception:
            return []
    if isinstance(value, str):
        matches = re.findall(r"[-+]?\d+(?:\.\d+)?", value)
        return [float(match) for match in matches]
    if isinstance(value, (list, tuple)):
        results: List[float] = []
        for item in value:
            results.extend(_coerce_luminance_values(item))
        return results
    return []


def _extract_mastering_display_luminance(props: Mapping[str, Any]) -> tuple[Optional[float], Optional[float]]:
    """
    Extract the mastering display minimum and maximum luminance from a properties mapping.

    Checks multiple common property keys for separate min/max entries first; if either is missing, looks for combined mastering display luminance entries that contain two values and uses their min and max as needed.

    Parameters:
        props (Mapping[str, Any]): Source properties that may contain mastering display luminance metadata under several possible keys.

    Returns:
        (min_luminance, max_luminance) (tuple[Optional[float], Optional[float]]): Tuple containing the extracted minimum and maximum mastering display luminance in nits, or `None` for any value that could not be determined.
    """
    min_keys = (
        "_MasteringDisplayMinLuminance",
        "MasteringDisplayMinLuminance",
        "MasteringDisplayLuminanceMin",
    )
    max_keys = (
        "_MasteringDisplayMaxLuminance",
        "MasteringDisplayMaxLuminance",
        "MasteringDisplayLuminanceMax",
    )

    min_value: Optional[float] = None
    max_value: Optional[float] = None

    for key in min_keys:
        if key in props:
            values = _coerce_luminance_values(props.get(key))
            if values:
                min_value = values[0]
                break
    for key in max_keys:
        if key in props:
            values = _coerce_luminance_values(props.get(key))
            if values:
                max_value = values[0]
                break

    if min_value is None or max_value is None:
        combined_keys = ("_MasteringDisplayLuminance", "MasteringDisplayLuminance")
        for key in combined_keys:
            values = _coerce_luminance_values(props.get(key))
            if len(values) >= 2:
                if min_value is None:
                    min_value = min(values)
                if max_value is None:
                    max_value = max(values)
                if min_value is not None and max_value is not None:
                    break

    return min_value, max_value


def _format_luminance_value(value: float) -> str:
    """
    Format a luminance value for display with sensible precision for small and large values.

    Parameters:
        value (float): Luminance in nits.

    Returns:
        str: Formatted luminance: values less than 1.0 are shown with up to four decimal places (trailing zeros and a trailing decimal point are removed), with "0" used if the result would be empty; values greater than or equal to 1.0 are shown with one decimal place.
    """
    if value < 1.0:
        text = f"{value:.4f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
    return f"{value:.1f}"


def _format_mastering_display_line(props: Mapping[str, Any]) -> str:
    """
    Format a single-line Mastering Display Luminance (MDL) summary suitable for overlays or logs.

    Parameters:
        props (Mapping[str, Any]): Source metadata that may contain mastering display luminance information.

    Returns:
        str: A one-line MDL string. If both min and max luminance are available, returns
        "MDL: min: <min> cd/m², max: <max> cd/m²"; otherwise returns "MDL: Insufficient data".
    """
    min_value, max_value = _extract_mastering_display_luminance(props)
    if min_value is None or max_value is None:
        return "MDL: Insufficient data"
    return (
        f"MDL: min: {_format_luminance_value(min_value)} cd/m², "
        f"max: {_format_luminance_value(max_value)} cd/m²"
    )


def _normalize_selection_label(label: Optional[str]) -> str:
    """
    Normalize a selection label into a user-facing display name.

    Parameters:
        label (Optional[str]): Raw selection label (may be None or empty) typically from metadata.

    Returns:
        str: The cleaned display name for the selection; returns `"(unknown)"` if the input is missing or empty. Known internal labels are mapped to their canonical display names.
    """
    if not label:
        return "(unknown)"
    cleaned = label.strip()
    if not cleaned:
        return "(unknown)"
    normalized = cleaned.lower()
    mapped = _SELECTION_LABELS.get(normalized)
    if mapped:
        return mapped
    return cleaned


def _format_selection_line(selection_label: Optional[str]) -> str:
    """
    Format the "Frame Selection Type" line for overlays and metadata.

    Parameters:
        selection_label (Optional[str]): A selection label or key to be normalized; may be None.

    Returns:
        str: A single-line string "Frame Selection Type: <label>" where <label> is a normalized, display-ready name derived from `selection_label`.
    """
    return f"Frame Selection Type: {_normalize_selection_label(selection_label)}"


def _compose_overlay_text(
    base_text: Optional[str],
    color_cfg: ColorConfig,
    plan: GeometryPlan,
    selection_label: Optional[str],
    source_props: Mapping[str, Any],
    *,
    tonemap_info: Optional[vs_core.TonemapInfo],
    selection_detail: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """
    Compose overlay text for a frame when overlays are enabled.

    When overlaying is disabled, returns None. In "minimal" mode the returned string always includes the resolution summary and selection-type lines in addition to any base text. In "diagnostic" mode, returns a multi-line string containing, in order: the base text (if any), a resolution summary derived from the geometry plan, a mastering-display luminance line when tonemapping was applied and HDR metadata is available, and a selection-type line.

    Parameters:
        base_text (Optional[str]): Existing overlay text to include as the first line if present.
        color_cfg (ColorConfig): Configuration object providing overlay_enabled and overlay_mode flags.
        plan (GeometryPlan): Geometry plan used to produce the resolution summary line.
        selection_label (Optional[str]): Selection label to format into the selection-type line.
        source_props (Mapping[str, Any]): Source properties used to extract mastering display luminance data.
        tonemap_info (Optional[vs_core.TonemapInfo]): If provided and its `applied` flag is true, include HDR mastering-display information in diagnostic mode.
        selection_detail (Optional[Mapping[str, Any]]): Selection metadata record retained for compatibility; overlay text omits per-frame detail lines regardless of mode.

    Returns:
        Optional[str]: Composed overlay text when overlays are enabled; otherwise `None`.
    """
    if not bool(getattr(color_cfg, "overlay_enabled", True)):
        return None

    mode = str(getattr(color_cfg, "overlay_mode", "minimal")).strip().lower()
    if mode != "diagnostic":
        lines: List[str] = []
        if base_text:
            lines.append(base_text)
        lines.append(_format_resolution_summary(plan))
        lines.append(_format_selection_line(selection_label))
        return "\n".join(lines)

    lines: List[str] = []
    if base_text:
        lines.append(base_text)

    lines.append(_format_resolution_summary(plan))
    include_hdr_details = bool(tonemap_info and tonemap_info.applied)
    if include_hdr_details:
        lines.append(_format_mastering_display_line(source_props))
    lines.append(_format_selection_line(selection_label))
    return "\n".join(lines)




def _resolve_resize_color_kwargs(props: Mapping[str, Any]) -> Dict[str, int]:
    """Build resize arguments describing the source clip's colour space."""

    matrix, transfer, primaries, color_range = vs_core._resolve_color_metadata(props)

    kwargs: Dict[str, int] = {}
    if matrix is not None:
        kwargs["matrix_in"] = int(matrix)
    if transfer is not None:
        kwargs["transfer_in"] = int(transfer)
    if primaries is not None:
        kwargs["primaries_in"] = int(primaries)
    if color_range is not None:
        kwargs["range_in"] = int(color_range)
    return kwargs


def _normalize_rgb_dither(value: RGBDither | str) -> RGBDither:
    """Normalise a value into an ``RGBDither`` enum with logging for invalid input."""

    try:
        return RGBDither(value)
    except (ValueError, TypeError):
        logger.debug(
            "Invalid rgb_dither value %r; defaulting to ERROR_DIFFUSION",
            value,
        )
        return RGBDither.ERROR_DIFFUSION


def _ensure_rgb24(
    core: Any,
    clip: Any,
    frame_idx: int,
    *,
    source_props: Mapping[str, Any] | None = None,
    rgb_dither: RGBDither | str = RGBDither.ERROR_DIFFUSION,
) -> Any:
    """
    Ensure the given VapourSynth frame is in 8-bit RGB24 color format.

    Parameters:
        core (Any): VapourSynth core instance used for conversions.
        clip (Any): VapourSynth clip or frame to validate/convert.
        frame_idx (int): Index of the frame being processed (used in error messages).

    Returns:
        Any: A clip in RGB24 with full range; returns the original clip if it already is 8-bit RGB24.

    Raises:
        ScreenshotWriterError: If VapourSynth is unavailable, the core lacks the resize namespace or Point, or the conversion fails.
    """
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("VapourSynth is required for screenshot export") from exc

    fmt = getattr(clip, "format", None)
    color_family = getattr(fmt, "color_family", None) if fmt is not None else None
    bits = getattr(fmt, "bits_per_sample", None) if fmt is not None else None
    if color_family == getattr(vs, "RGB", object()) and bits == 8:
        return clip

    resize_ns = getattr(core, "resize", None)
    if resize_ns is None:
        raise ScreenshotWriterError("VapourSynth core is missing resize namespace")
    point = getattr(resize_ns, "Point", None)
    if not callable(point):
        raise ScreenshotWriterError("VapourSynth resize.Point is unavailable")

    dither = _normalize_rgb_dither(rgb_dither).value
    props = dict(source_props or {})
    if not props:
        props = dict(vs_core._snapshot_frame_props(clip))
    resize_kwargs = _resolve_resize_color_kwargs(props)

    yuv_constant = getattr(vs, "YUV", object())
    if color_family == yuv_constant:
        defaults: Dict[str, int] = {}
        if "matrix_in" not in resize_kwargs:
            defaults["matrix_in"] = int(getattr(vs, "MATRIX_BT709", 1))
        if "transfer_in" not in resize_kwargs:
            defaults["transfer_in"] = int(getattr(vs, "TRANSFER_BT709", 1))
        if "primaries_in" not in resize_kwargs:
            defaults["primaries_in"] = int(getattr(vs, "PRIMARIES_BT709", 1))
        if "range_in" not in resize_kwargs:
            defaults["range_in"] = int(getattr(vs, "RANGE_LIMITED", 1))
        if defaults:
            resize_kwargs.update(defaults)
            logger.debug(
                "Colour metadata missing for frame %s; applying Rec.709 limited defaults",
                frame_idx,
            )

    try:
        converted = cast(
            Any,
            point(
                clip,
                format=vs.RGB24,
                range=vs.RANGE_FULL,
                dither_type=dither,
                **resize_kwargs,
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise ScreenshotWriterError(f"Failed to convert frame {frame_idx} to RGB24: {exc}") from exc

    try:
        prop_kwargs: Dict[str, int] = {"_Matrix": 0, "_ColorRange": 0}
        primaries = props.get("_Primaries")
        if isinstance(primaries, int):
            prop_kwargs["_Primaries"] = int(primaries)
        transfer = props.get("_Transfer")
        if isinstance(transfer, int):
            prop_kwargs["_Transfer"] = int(transfer)
        converted = cast(Any, converted.std.SetFrameProps(**prop_kwargs))
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Failed to set RGB frame props: %s", exc)
    return converted


def _clamp_frame_index(clip: Any, frame_idx: int) -> tuple[int, bool]:
    """
    Clamp ``frame_idx`` to the clip's valid range and flag when adjustment occurred.

    Parameters:
        clip (Any): Clip providing a ``num_frames`` attribute describing valid indices.
        frame_idx (int): Desired frame index.

    Returns:
        tuple[int, bool]: Tuple of the clamped frame index and ``True`` when the value was adjusted.
    """
    total_frames = getattr(clip, "num_frames", None)
    if not isinstance(total_frames, int) or total_frames <= 0:
        return max(0, int(frame_idx)), False
    max_index = max(0, total_frames - 1)
    clamped = max(0, min(int(frame_idx), max_index))
    return clamped, clamped != frame_idx


FRAME_INFO_STYLE = (
    'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,'
    '"0,0,0,0,100,100,0,0,1,2,0,7,10,10,10,1"'
)
OVERLAY_STYLE = (
    'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,'
    '"0,0,0,0,100,100,0,0,1,2,0,7,10,10,70,1"'
)

_LETTERBOX_RATIO_TOLERANCE = 0.04


def _apply_frame_info_overlay(
    core: Any,
    clip: Any,
    title: str,
    requested_frame: int | None,
    selection_label: str | None,
) -> Any:
    """
    Add a per-frame information overlay to a VapourSynth clip.

    Attempts to draw a small text block containing the frame index and picture type onto the provided clip.
    If the required VapourSynth namespaces or overlay functions are unavailable, or an error occurs while applying
    the overlay, the original clip is returned unchanged.

    Parameters:
        core: VapourSynth core object used to access std and sub namespaces.
        clip: VapourSynth clip to annotate.
        title: Title text shown above the per-frame info; falls back to "Clip" when empty.
        requested_frame: Frame index to display in the overlay instead of the intrinsic evaluation index; pass None to use the evaluation index.
        selection_label: Optional selection label (not used by this function).

    Returns:
        The annotated clip if overlay application succeeded, otherwise the original clip.
    """
    std_ns = getattr(core, "std", None)
    sub_ns = getattr(core, "sub", None)
    if std_ns is None or sub_ns is None:
        logger.debug('VapourSynth core missing std/sub namespaces; skipping frame overlay')
        return clip

    frame_eval_obj = getattr(std_ns, 'FrameEval', None)
    subtitle_obj = getattr(sub_ns, 'Subtitle', None)
    if not callable(frame_eval_obj) or not callable(subtitle_obj):
        logger.debug('Required VapourSynth overlay functions unavailable; skipping frame overlay')
        return clip
    frame_eval = cast(FrameEvalFunc, frame_eval_obj)
    subtitle = cast(SubtitleFunc, subtitle_obj)

    label = title.strip() if isinstance(title, str) else ''
    if not label:
        label = 'Clip'

    padding_title = " " + ("\n" * 3)

    def _draw_info(n: int, f: Any, clip_ref: Any) -> Any:
        """
        Create a subtitle node containing per-frame information (frame index and picture type) for overlay.

        Parameters:
            n (int): Evaluation frame index provided by the frame evaluation callback.
            f: Frame object whose properties (e.g., `_PictType`) will be read.
            clip_ref: Source clip reference used to construct the subtitle node.

        Returns:
            A subtitle clip node containing the formatted frame information text.
        """
        pict = f.props.get('_PictType')
        if isinstance(pict, bytes):
            pict_text = pict.decode('utf-8', 'ignore')
        elif isinstance(pict, str):
            pict_text = pict
        else:
            pict_text = 'N/A'
        display_idx = requested_frame if requested_frame is not None else n
        lines: List[str] = [
            f"Frame {display_idx} of {clip_ref.num_frames}",
            f"Picture type: {pict_text}",
        ]
        info = "\n".join(lines)
        return subtitle(clip_ref, text=[info], style=FRAME_INFO_STYLE)

    try:
        info_clip = frame_eval(clip, partial(_draw_info, clip_ref=clip), prop_src=clip)
        return subtitle(info_clip, text=[padding_title + label], style=FRAME_INFO_STYLE)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug('Applying frame overlay failed: %s', exc)
        return clip


def _apply_overlay_text(
    core: Any,
    clip: Any,
    text: Optional[str],
    *,
    strict: bool,
    state: OverlayState,
    file_label: str,
) -> object:
    """
    Apply diagnostic text as an overlay to a VapourSynth clip and update overlay state.

    Attempts to render `text` on `clip` using available overlay filters from `core`. If `text` is falsy or the overlay status in `state` is "error", the original `clip` is returned unchanged. On successful application the returned clip contains the rendered overlay and `state["overlay_status"]` is set to `"ok"`. On failure the function records an error message into `state["warnings"]` (prefixed with "[OVERLAY]") and sets `state["overlay_status"]` to `"error"`; when `strict` is True a ScreenshotWriterError is raised instead of returning the original clip.

    Parameters:
        core: The VapourSynth core object providing overlay/filter namespaces.
        clip: The VapourSynth clip to receive the overlay.
        text: The overlay text to apply; if None or empty, no action is taken.
        strict (bool): If True, raise ScreenshotWriterError on overlay unavailability or failure.
        state (OverlayState): Mutable state mapping used and updated by this function. Recognized keys:
            - "overlay_status": read and updated to "ok" or "error".
            - "warnings": a list that will be appended with overlay-related warning strings when failures occur.
        file_label (str): Human-readable identifier for logging and warning messages.

    Returns:
        The clip with the overlay applied, or the original `clip` if no overlay was applied.

    Raises:
        ScreenshotWriterError: If an overlay cannot be applied and `strict` is True.
    """
    if not text:
        return clip
    status = state.get("overlay_status")
    if status == "error":
        return clip
    sub_ns = getattr(core, "sub", None)
    subtitle = getattr(sub_ns, "Subtitle", None) if sub_ns is not None else None
    if callable(subtitle):
        try:
            result = subtitle(clip, text=[text], style=OVERLAY_STYLE)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug('Subtitle overlay failed, falling back: %s', exc)
        else:
            if status != "ok":
                logger.info('[OVERLAY] %s applied', file_label)
                state["overlay_status"] = "ok"
            return result

    text_ns = getattr(core, "text", None)
    draw = getattr(text_ns, "Text", None) if text_ns is not None else None
    if not callable(draw):
        message = f"Overlay filter unavailable for {file_label}"
        logger.error('[OVERLAY] %s', message)
        state["overlay_status"] = "error"
        _append_overlay_warning(state, f"[OVERLAY] {message}")
        if strict:
            raise ScreenshotWriterError(message)
        return clip
    try:
        result = draw(clip, text, alignment=9)
    except Exception as exc:  # pragma: no cover - defensive
        message = f"Overlay failed for {file_label}: {exc}"
        logger.error('[OVERLAY] %s', message)
        state["overlay_status"] = "error"
        _append_overlay_warning(state, f"[OVERLAY] {message}")
        if strict:
            raise ScreenshotWriterError(message) from exc
        return clip
    std_ns = getattr(core, "std", None)
    copy_props = getattr(std_ns, "CopyFrameProps", None) if std_ns is not None else None
    if callable(copy_props):
        try:
            result = copy_props(result, clip)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug('CopyFrameProps failed during overlay preservation: %s', exc)
    if status != "ok":
        logger.info('[OVERLAY] %s applied', file_label)
        state["overlay_status"] = "ok"
    return result


class ScreenshotError(RuntimeError):
    """Base class for screenshot related issues."""


class ScreenshotGeometryError(ScreenshotError):
    """Raised when geometry or cropping cannot be satisfied."""


class ScreenshotWriterError(ScreenshotError):
    """Raised when the underlying writer fails."""


class GeometryPlan(TypedDict):
    """
    Resolved crop/pad/scale plan for rendering a screenshot.

    Attributes:
        width (int): Source clip width.
        height (int): Source clip height.
        crop (tuple[int, int, int, int]): Cropping values for left, top, right, bottom.
        cropped_w (int): Width after cropping.
        cropped_h (int): Height after cropping.
        scaled (tuple[int, int]): Dimensions after scaling.
        pad (tuple[int, int, int, int]): Padding applied around the scaled frame.
        final (tuple[int, int]): Final output dimensions.
        requires_full_chroma (bool): Whether geometry requires a 4:4:4 pivot.
        promotion_axes (str): Subsampling-aware axis label describing which geometry axis
            triggered promotion, or ``"none"`` when no promotion is required.
    """
    width: int
    height: int
    crop: tuple[int, int, int, int]
    cropped_w: int
    cropped_h: int
    scaled: tuple[int, int]
    pad: tuple[int, int, int, int]
    final: tuple[int, int]
    requires_full_chroma: bool
    promotion_axes: str


def _normalise_geometry_policy(value: OddGeometryPolicy | str) -> OddGeometryPolicy:
    if isinstance(value, OddGeometryPolicy):
        return value
    try:
        return OddGeometryPolicy(str(value))
    except Exception:
        return OddGeometryPolicy.AUTO


def _get_subsampling(fmt: Any, attr: str) -> int:
    try:
        raw = getattr(fmt, attr)
    except Exception:
        return 0
    try:
        return int(raw)
    except Exception:
        return 0


def _axis_has_odd(values: Sequence[int]) -> bool:
    for value in values:
        try:
            current = int(value)
        except Exception:
            continue
        if current % 2 != 0:
            return True
    return False


def _describe_plan_axes(plan: GeometryPlan | None) -> str:
    """Return a concise axis label for plans that include odd-pixel geometry."""

    if plan is None:
        return "unknown"

    crop_left, crop_top, crop_right, crop_bottom = plan["crop"]
    pad_left, pad_top, pad_right, pad_bottom = plan["pad"]

    axes: list[str] = []
    if _axis_has_odd((crop_top, crop_bottom, pad_top, pad_bottom)):
        axes.append("vertical")
    if _axis_has_odd((crop_left, crop_right, pad_left, pad_right)):
        axes.append("horizontal")

    if not axes:
        return "none"
    return "+".join(axes)


def _safe_pivot_notify(pivot_notifier: Callable[[str], None] | None, note: str) -> None:
    """Invoke *pivot_notifier* without letting exceptions escape."""

    if pivot_notifier is None:
        return
    try:
        pivot_notifier(note)
    except Exception as exc:
        logger.debug("pivot_notifier failed: %s", exc)


def _resolve_source_props(
    clip: Any,
    source_props: Mapping[str, Any] | None,
    *,
    color_cfg: "ColorConfig | None" = None,
    file_name: str | None = None,
) -> tuple[Any, Dict[str, Any]]:
    """Return a clip and colour metadata ensuring defaults/overrides are applied."""

    props = dict(source_props or {})
    if props.get("_ColorRange") is not None:
        return clip, props

    normalised_clip, resolved_props, _ = vs_core.normalise_color_metadata(
        clip,
        props if props else None,
        color_cfg=color_cfg,
        file_name=file_name,
    )
    return normalised_clip, dict(resolved_props)


def _describe_vs_format(fmt: Any) -> str:
    name = getattr(fmt, "name", None)
    if isinstance(name, str) and name:
        return name
    identifier = getattr(fmt, "id", None)
    if isinstance(identifier, int):
        return f"id={identifier}"
    return repr(fmt)


def _resolve_promotion_axes(
    fmt: Any,
    crop: tuple[int, int, int, int],
    pad: tuple[int, int, int, int],
) -> tuple[bool, str]:
    subsampling_w = _get_subsampling(fmt, "subsampling_w")
    subsampling_h = _get_subsampling(fmt, "subsampling_h")

    axes: List[str] = []
    if subsampling_h > 0 and _axis_has_odd((crop[1], crop[3], pad[1], pad[3])):
        axes.append("vertical")
    if subsampling_w > 0 and _axis_has_odd((crop[0], crop[2], pad[0], pad[2])):
        axes.append("horizontal")

    if not axes:
        return (False, "none")
    return (True, "+".join(axes))


def _is_sdr_pipeline(
    tonemap_info: "vs_core.TonemapInfo | None",
    source_props: Mapping[str, Any],
) -> bool:
    if tonemap_info is not None and tonemap_info.applied:
        return False
    try:
        is_hdr = vs_core._props_signal_hdr(source_props)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        logger.debug("HDR detection failed; defaulting to SDR: %s", exc)
        is_hdr = False
    return not bool(is_hdr)


def _promote_to_yuv444p16(
    core: Any,
    clip: Any,
    *,
    frame_idx: int,
    source_props: Mapping[str, Any],
) -> Any:
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("VapourSynth is required for screenshot export") from exc

    resize_ns = getattr(core, "resize", None)
    if resize_ns is None:
        raise ScreenshotWriterError("VapourSynth core is missing resize namespace")
    point = getattr(resize_ns, "Point", None)
    if not callable(point):
        raise ScreenshotWriterError("VapourSynth resize.Point is unavailable")

    resize_kwargs = _resolve_resize_color_kwargs(source_props)

    fmt = getattr(clip, "format", None)
    yuv_constant = getattr(vs, "YUV", object())
    if getattr(fmt, "color_family", None) == yuv_constant:
        defaults: Dict[str, int] = {}
        if "matrix_in" not in resize_kwargs:
            defaults["matrix_in"] = int(getattr(vs, "MATRIX_BT709", 1))
        if "transfer_in" not in resize_kwargs:
            defaults["transfer_in"] = int(getattr(vs, "TRANSFER_BT709", 1))
        if "primaries_in" not in resize_kwargs:
            defaults["primaries_in"] = int(getattr(vs, "PRIMARIES_BT709", 1))
        if "range_in" not in resize_kwargs:
            defaults["range_in"] = int(getattr(vs, "RANGE_LIMITED", 1))
        if defaults:
            resize_kwargs.update(defaults)
            logger.debug(
                "Colour metadata missing for frame %s during 4:4:4 promotion; applying Rec.709 limited defaults",
                frame_idx,
            )

    try:
        promoted = cast(
            Any,
            point(
                clip,
                format=vs.YUV444P16,
                dither_type="none",
                **resize_kwargs,
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise ScreenshotWriterError(f"Failed to promote frame {frame_idx} to YUV444P16: {exc}") from exc

    std_ns = getattr(core, "std", None)
    set_props = getattr(std_ns, "SetFrameProps", None) if std_ns is not None else None
    if callable(set_props):
        prop_kwargs: Dict[str, int] = {}
        matrix_in = resize_kwargs.get("matrix_in")
        transfer_in = resize_kwargs.get("transfer_in")
        primaries_in = resize_kwargs.get("primaries_in")
        range_in = resize_kwargs.get("range_in")
        if matrix_in is not None:
            prop_kwargs["_Matrix"] = int(matrix_in)
        if transfer_in is not None:
            prop_kwargs["_Transfer"] = int(transfer_in)
        if primaries_in is not None:
            prop_kwargs["_Primaries"] = int(primaries_in)
        if range_in is not None:
            prop_kwargs["_ColorRange"] = int(range_in)
        if prop_kwargs:
            try:
                promoted = cast(Any, set_props(promoted, **prop_kwargs))
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug("Failed to set frame props after promotion: %s", exc)

    return promoted


def _rebalance_axis_even(first: int, second: int) -> tuple[int, int]:
    left = max(0, int(first))
    right = max(0, int(second))
    removed = 0

    if left % 2 != 0:
        left -= 1
        removed += 1
    if right % 2 != 0:
        right -= 1
        removed += 1

    while removed >= 2:
        right += 2
        removed -= 2

    return left, right


def _compute_requires_full_chroma(
    fmt: Any,
    crop: tuple[int, int, int, int],
    pad: tuple[int, int, int, int],
    policy: OddGeometryPolicy,
) -> bool:
    resolved_policy = _normalise_geometry_policy(policy)
    if resolved_policy is OddGeometryPolicy.FORCE_FULL_CHROMA:
        return True
    if resolved_policy is OddGeometryPolicy.SUBSAMP_SAFE:
        return False

    subsampling_w = _get_subsampling(fmt, "subsampling_w")
    subsampling_h = _get_subsampling(fmt, "subsampling_h")

    vertical_odd = _axis_has_odd((crop[1], crop[3], pad[1], pad[3]))
    horizontal_odd = _axis_has_odd((crop[0], crop[2], pad[0], pad[2]))

    return (vertical_odd and subsampling_h > 0) or (horizontal_odd and subsampling_w > 0)


def plan_mod_crop(
    width: int,
    height: int,
    mod: int,
    letterbox_pillarbox_aware: bool,
) -> Tuple[int, int, int, int]:
    """Plan left/top/right/bottom croppings so dimensions align to *mod*."""

    if width <= 0 or height <= 0:
        raise ScreenshotGeometryError("Clip dimensions must be positive")
    if mod <= 1:
        return (0, 0, 0, 0)

    def _axis_crop(size: int) -> Tuple[int, int]:
        remainder = size % mod
        if remainder == 0:
            return (0, 0)
        before = remainder // 2
        after = remainder - before
        return (before, after)

    left, right = _axis_crop(width)
    top, bottom = _axis_crop(height)

    if letterbox_pillarbox_aware:
        if width > height and (top + bottom) == 0 and (left + right) > 0:
            total = left + right
            left = total // 2
            right = total - left
        elif height >= width and (left + right) == 0 and (top + bottom) > 0:
            total = top + bottom
            top = total // 2
            bottom = total - top

    cropped_w = width - left - right
    cropped_h = height - top - bottom
    if cropped_w <= 0 or cropped_h <= 0:
        raise ScreenshotGeometryError("Cropping removed all pixels")

    return (left, top, right, bottom)


def _align_letterbox_pillarbox(plans: List[GeometryPlan]) -> None:
    if not plans:
        return

    widths = [int(plan["width"]) for plan in plans]
    heights = [int(plan["height"]) for plan in plans]
    same_w = len({w for w in widths if w > 0}) == 1
    same_h = len({h for h in heights if h > 0}) == 1

    if same_w:
        target_h = min(int(plan["cropped_h"]) for plan in plans)
        for plan in plans:
            current_h = int(plan["cropped_h"])
            diff = current_h - target_h
            if diff <= 0:
                continue
            add_top = diff // 2
            add_bottom = diff - add_top
            left, top, right, bottom = plan["crop"]
            top += add_top
            bottom += add_bottom
            plan["crop"] = (left, top, right, bottom)
            plan["cropped_h"] = plan["height"] - top - bottom
    elif same_h:
        target_w = min(int(plan["cropped_w"]) for plan in plans)
        for plan in plans:
            current_w = int(plan["cropped_w"])
            diff = current_w - target_w
            if diff <= 0:
                continue
            add_left = diff // 2
            add_right = diff - add_left
            left, top, right, bottom = plan["crop"]
            left += add_left
            right += add_right
            plan["crop"] = (left, top, right, bottom)
            plan["cropped_w"] = plan["width"] - left - right


def _plan_letterbox_offsets(
    plans: Sequence[GeometryPlan],
    *,
    mod: int,
    tolerance: float = _LETTERBOX_RATIO_TOLERANCE,
    max_target_height: int | None = None,
) -> List[tuple[int, int]]:
    ratios: List[float] = []
    for plan in plans:
        try:
            width = float(plan["width"])
            height = float(plan["height"])
        except Exception:
            continue
        if width > 0 and height > 0:
            ratios.append(width / height)

    if not ratios:
        return [(0, 0) for _ in plans]

    target_ratio = max(ratios)
    if target_ratio <= 0:
        return [(0, 0) for _ in plans]

    tolerance = max(0.0, tolerance)
    min_ratio_allowed = target_ratio * (1.0 - tolerance)

    offsets: List[tuple[int, int]] = []
    for plan in plans:
        try:
            width = int(plan["width"])
            height = int(plan["height"])
        except Exception:
            offsets.append((0, 0))
            continue
        if width <= 0 or height <= 0:
            offsets.append((0, 0))
            continue

        ratio = width / height
        if ratio >= min_ratio_allowed:
            offsets.append((0, 0))
            continue

        desired_height = width / target_ratio
        target_height = int(round(desired_height))
        if max_target_height is not None:
            target_height = min(target_height, max_target_height)

        if mod > 1:
            target_height -= target_height % mod
        target_height = max(mod if mod > 0 else 1, target_height)
        if target_height >= height:
            offsets.append((0, 0))
            continue

        crop_total = height - target_height
        if crop_total <= 0:
            offsets.append((0, 0))
            continue

        top_extra = crop_total // 2
        bottom_extra = crop_total - top_extra
        offsets.append((top_extra, bottom_extra))

    return offsets


def _split_padding(total: int, center: bool) -> tuple[int, int]:
    amount = max(0, int(total))
    if amount <= 0:
        return (0, 0)
    if center:
        first = amount // 2
        second = amount - first
        return (first, second)
    return (0, amount)


def _align_padding_mod(
    width: int,
    height: int,
    pad_left: int,
    pad_top: int,
    pad_right: int,
    pad_bottom: int,
    mod: int,
    center: bool,
) -> tuple[int, int, int, int]:
    if mod <= 1:
        return (pad_left, pad_top, pad_right, pad_bottom)

    total_pad = pad_left + pad_top + pad_right + pad_bottom
    if total_pad <= 0:
        return (pad_left, pad_top, pad_right, pad_bottom)

    final_w = width + pad_left + pad_right
    final_h = height + pad_top + pad_bottom

    remainder_w = final_w % mod
    if remainder_w:
        extra = mod - remainder_w
        add_left, add_right = _split_padding(extra, center)
        pad_left += add_left
        pad_right += add_right
        final_w += extra

    remainder_h = final_h % mod
    if remainder_h:
        extra = mod - remainder_h
        add_top, add_bottom = _split_padding(extra, center)
        pad_top += add_top
        pad_bottom += add_bottom

    return (pad_left, pad_top, pad_right, pad_bottom)


def _compute_scaled_dimensions(
    width: int,
    height: int,
    crop: Tuple[int, int, int, int],
    target_height: int,
) -> Tuple[int, int]:
    cropped_w = width - crop[0] - crop[2]
    cropped_h = height - crop[1] - crop[3]
    if cropped_w <= 0 or cropped_h <= 0:
        raise ScreenshotGeometryError("Invalid crop results")

    desired_h = max(1, int(round(target_height)))
    scale = desired_h / cropped_h if cropped_h else 1.0
    target_w = int(round(cropped_w * scale)) if scale != 1 else cropped_w
    target_w = max(1, target_w)
    return (target_w, desired_h)


def _plan_geometry(clips: Sequence[Any], cfg: ScreenshotConfig) -> List[GeometryPlan]:
    policy = _normalise_geometry_policy(cfg.odd_geometry_policy)
    clip_formats: List[Any] = []
    plans: List[GeometryPlan] = []
    for clip in clips:
        width = getattr(clip, "width", None)
        height = getattr(clip, "height", None)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ScreenshotGeometryError("Clip missing width/height metadata")

        clip_formats.append(getattr(clip, "format", None))
        crop = plan_mod_crop(width, height, cfg.mod_crop, cfg.letterbox_pillarbox_aware)
        cropped_w = width - crop[0] - crop[2]
        cropped_h = height - crop[1] - crop[3]
        if cropped_w <= 0 or cropped_h <= 0:
            raise ScreenshotGeometryError("Invalid crop results")

        plans.append(
            GeometryPlan(
                width=width,
                height=height,
                crop=crop,
                cropped_w=cropped_w,
                cropped_h=cropped_h,
                scaled=(cropped_w, cropped_h),
                pad=(0, 0, 0, 0),
                final=(cropped_w, cropped_h),
                requires_full_chroma=False,
                promotion_axes="none",
            )
        )

    if cfg.auto_letterbox_crop:
        try:
            max_target_height = min(int(plan["cropped_h"]) for plan in plans)
        except ValueError:
            max_target_height = None
        offsets = _plan_letterbox_offsets(
            plans,
            mod=cfg.mod_crop,
            max_target_height=max_target_height,
        )
        for plan, (extra_top, extra_bottom) in zip(plans, offsets, strict=True):
            if not (extra_top or extra_bottom):
                continue
            left, top, right, bottom = plan["crop"]
            top += int(extra_top)
            bottom += int(extra_bottom)
            new_height = int(plan["height"]) - top - bottom
            if new_height <= 0:
                raise ScreenshotGeometryError("Letterbox detection removed all pixels")
            plan["crop"] = (left, top, right, bottom)
            plan["cropped_h"] = new_height
            logger.info(
                "[LETTERBOX] Cropping %s px top / %s px bottom for width=%s height=%s",
                extra_top,
                extra_bottom,
                plan["width"],
                plan["height"],
            )

    if cfg.letterbox_pillarbox_aware:
        _align_letterbox_pillarbox(plans)

    if policy is OddGeometryPolicy.SUBSAMP_SAFE:
        for plan, fmt in zip(plans, clip_formats, strict=True):
            subsampling_w = _get_subsampling(fmt, "subsampling_w")
            subsampling_h = _get_subsampling(fmt, "subsampling_h")
            left, top, right, bottom = plan["crop"]

            if subsampling_h > 0:
                new_top, new_bottom = _rebalance_axis_even(top, bottom)
            else:
                new_top, new_bottom = top, bottom

            if subsampling_w > 0:
                new_left, new_right = _rebalance_axis_even(left, right)
            else:
                new_left, new_right = left, right

            changed_vertical = (new_top, new_bottom) != (top, bottom)
            changed_horizontal = (new_left, new_right) != (left, right)

            if changed_vertical:
                logger.warning(
                    "[GEOMETRY] Rebalanced vertical crop from %s/%s to %s/%s for mod-2 safety; content may shift by 1px",
                    top,
                    bottom,
                    new_top,
                    new_bottom,
                )
            if changed_horizontal:
                logger.warning(
                    "[GEOMETRY] Rebalanced horizontal crop from %s/%s to %s/%s for mod-2 safety; content may shift by 1px",
                    left,
                    right,
                    new_left,
                    new_right,
                )

            if changed_vertical or changed_horizontal:
                plan["crop"] = (new_left, new_top, new_right, new_bottom)
                new_cropped_w = int(plan["width"]) - new_left - new_right
                new_cropped_h = int(plan["height"]) - new_top - new_bottom
                if new_cropped_w <= 0 or new_cropped_h <= 0:
                    raise ScreenshotGeometryError("Rebalanced crop removed all pixels")
                plan["cropped_w"] = new_cropped_w
                plan["cropped_h"] = new_cropped_h
                plan["scaled"] = (new_cropped_w, new_cropped_h)

    single_res_target = int(cfg.single_res) if cfg.single_res > 0 else None
    if single_res_target is not None:
        desired_height = max(1, single_res_target)
        global_target = None
    else:
        desired_height = None
        global_target = (
            max((plan["cropped_h"] for plan in plans), default=None)
            if cfg.upscale
            else None
        )

    max_source_width = max((int(plan["width"]) for plan in plans), default=0)

    pad_mode = str(getattr(cfg, "pad_to_canvas", "off")).strip().lower()
    pad_enabled = pad_mode in {"on", "auto"}
    pad_force = pad_mode == "on"
    pad_tolerance = max(0, int(getattr(cfg, "letterbox_px_tolerance", 0)))
    center_pad = bool(getattr(cfg, "center_pad", True))

    target_heights: List[int] = []

    for plan in plans:
        cropped_w = int(plan["cropped_w"])
        cropped_h = int(plan["cropped_h"])
        if desired_height is not None:
            target_h = desired_height
            if not cfg.upscale and target_h > cropped_h:
                target_h = cropped_h
        elif global_target is not None:
            target_h = max(cropped_h, int(global_target))
        else:
            target_h = cropped_h

        target_heights.append(target_h)

        pad_left = pad_top = pad_right = pad_bottom = 0
        scaled_w = cropped_w
        scaled_h = cropped_h

        if target_h != cropped_h:
            if target_h > cropped_h and cfg.upscale:
                scaled_w, scaled_h = _compute_scaled_dimensions(
                    int(plan["width"]),
                    int(plan["height"]),
                    plan["crop"],
                    target_h,
                )
            elif target_h < cropped_h:
                scaled_w, scaled_h = _compute_scaled_dimensions(
                    int(plan["width"]),
                    int(plan["height"]),
                    plan["crop"],
                    target_h,
                )
            elif pad_enabled and target_h > cropped_h:
                diff = target_h - cropped_h
                if pad_force or diff <= pad_tolerance:
                    add_top, add_bottom = _split_padding(diff, center_pad)
                    pad_top += add_top
                    pad_bottom += add_bottom

        if cfg.upscale and max_source_width > 0 and scaled_w > max_source_width:
            base_w = int(plan["cropped_w"])
            if base_w > 0:
                scale = max_source_width / float(base_w)
                adjusted_h = int(round(int(plan["cropped_h"]) * scale))
                scaled_w = max_source_width
                scaled_h = max(1, adjusted_h)

        plan["scaled"] = (scaled_w, scaled_h)
        plan["pad"] = (pad_left, pad_top, pad_right, pad_bottom)

    canvas_height = None
    if desired_height is not None:
        canvas_height = desired_height
    elif global_target is not None:
        try:
            canvas_height = max(int(value) for value in target_heights)
        except ValueError:
            canvas_height = None

    canvas_width = None
    if pad_enabled:
        if single_res_target is not None and max_source_width > 0:
            canvas_width = max_source_width
        else:
            try:
                canvas_width = max(int(plan["scaled"][0]) for plan in plans)
            except ValueError:
                canvas_width = None

    for plan in plans:
        scaled_w, scaled_h = plan["scaled"]
        pad_left, pad_top, pad_right, pad_bottom = plan["pad"]

        if canvas_height is not None and pad_enabled:
            target_h = canvas_height
            current_h = scaled_h + pad_top + pad_bottom
            diff_h = target_h - current_h
            if diff_h > 0:
                if pad_force or diff_h <= pad_tolerance:
                    add_top, add_bottom = _split_padding(diff_h, center_pad)
                    pad_top += add_top
                    pad_bottom += add_bottom
                else:
                    logger.debug(
                        "Skipping vertical padding (%s px) for width=%s due to tolerance",
                        diff_h,
                        plan["width"],
                    )

        if canvas_width is not None and pad_enabled:
            current_w = scaled_w + pad_left + pad_right
            diff_w = canvas_width - current_w
            if diff_w > 0:
                if pad_force or diff_w <= pad_tolerance:
                    add_left, add_right = _split_padding(diff_w, center_pad)
                    pad_left += add_left
                    pad_right += add_right
                else:
                    logger.debug(
                        "Skipping horizontal padding (%s px) for width=%s due to tolerance",
                        diff_w,
                        plan["width"],
                    )

        pad_left, pad_top, pad_right, pad_bottom = _align_padding_mod(
            scaled_w,
            scaled_h,
            pad_left,
            pad_top,
            pad_right,
            pad_bottom,
            cfg.mod_crop,
            center_pad,
        )

        plan["pad"] = (pad_left, pad_top, pad_right, pad_bottom)
        plan["final"] = (
            scaled_w + pad_left + pad_right,
            scaled_h + pad_top + pad_bottom,
        )

    for plan, fmt in zip(plans, clip_formats, strict=True):
        if policy is OddGeometryPolicy.SUBSAMP_SAFE:
            subsampling_w = _get_subsampling(fmt, "subsampling_w")
            subsampling_h = _get_subsampling(fmt, "subsampling_h")
            pad_left, pad_top, pad_right, pad_bottom = plan["pad"]
            scaled_w, scaled_h = plan["scaled"]

            new_pad_top, new_pad_bottom = (pad_top, pad_bottom)
            new_pad_left, new_pad_right = (pad_left, pad_right)

            if subsampling_h > 0:
                new_pad_top, new_pad_bottom = _rebalance_axis_even(pad_top, pad_bottom)
                if (new_pad_top, new_pad_bottom) != (pad_top, pad_bottom):
                    logger.warning(
                        "[GEOMETRY] Rebalanced vertical padding from %s/%s to %s/%s for mod-2 safety; content may shift by 1px",
                        pad_top,
                        pad_bottom,
                        new_pad_top,
                        new_pad_bottom,
                    )
            if subsampling_w > 0:
                new_pad_left, new_pad_right = _rebalance_axis_even(pad_left, pad_right)
                if (new_pad_left, new_pad_right) != (pad_left, pad_right):
                    logger.warning(
                        "[GEOMETRY] Rebalanced horizontal padding from %s/%s to %s/%s for mod-2 safety; content may shift by 1px",
                        pad_left,
                        pad_right,
                        new_pad_left,
                        new_pad_right,
                    )

            if (
                (new_pad_top, new_pad_bottom) != (pad_top, pad_bottom)
                or (new_pad_left, new_pad_right) != (pad_left, pad_right)
            ):
                plan["pad"] = (new_pad_left, new_pad_top, new_pad_right, new_pad_bottom)
                plan["final"] = (
                    scaled_w + new_pad_left + new_pad_right,
                    scaled_h + new_pad_top + new_pad_bottom,
                )

                aligned_pad_left, aligned_pad_top, aligned_pad_right, aligned_pad_bottom = _align_padding_mod(
                    scaled_w,
                    scaled_h,
                    new_pad_left,
                    new_pad_top,
                    new_pad_right,
                    new_pad_bottom,
                    cfg.mod_crop,
                    center_pad,
                )

                if (
                    aligned_pad_left,
                    aligned_pad_top,
                    aligned_pad_right,
                    aligned_pad_bottom,
                ) != plan["pad"]:
                    plan["pad"] = (
                        aligned_pad_left,
                        aligned_pad_top,
                        aligned_pad_right,
                        aligned_pad_bottom,
                    )
                    plan["final"] = (
                        scaled_w + aligned_pad_left + aligned_pad_right,
                        scaled_h + aligned_pad_top + aligned_pad_bottom,
                    )

        plan["requires_full_chroma"] = _compute_requires_full_chroma(
            fmt,
            plan["crop"],
            plan["pad"],
            policy,
        )

        if plan["requires_full_chroma"]:
            needs_promotion, promotion_axes = _resolve_promotion_axes(
                fmt,
                plan["crop"],
                plan["pad"],
            )
            plan["promotion_axes"] = promotion_axes if needs_promotion else "none"
        else:
            plan["promotion_axes"] = "none"

    return plans


def _sanitise_label(label: str) -> str:
    cleaned = _INVALID_LABEL_PATTERN.sub("_", label)
    if os.name == "nt":
        cleaned = cleaned.rstrip(" .")
    cleaned = cleaned.strip()
    return cleaned or "comparison"


def _derive_labels(source: str, metadata: Mapping[str, str]) -> tuple[str, str]:
    raw = metadata.get("label") or Path(source).stem
    cleaned = _sanitise_label(raw)
    return raw.strip() or cleaned, cleaned


def _prepare_filename(frame: int, label: str) -> str:
    return f"{frame} - {label}.png"


def _normalise_compression_level(level: int) -> int:
    try:
        value = int(level)
    except Exception:
        return 1
    return max(0, min(2, value))


def _map_fpng_compression(level: int) -> int:
    normalised = _normalise_compression_level(level)
    return {0: 0, 1: 1, 2: 2}.get(normalised, 1)


def _map_png_compression_level(level: int) -> int:
    """Translate the user configured level into a PNG compress level."""

    normalised = _normalise_compression_level(level)
    mapping = {0: 0, 1: 6, 2: 9}
    return mapping.get(normalised, 6)


def _save_frame_with_fpng(
    clip: Any,
    frame_idx: int,
    crop: Tuple[int, int, int, int],
    scaled: Tuple[int, int],
    pad: Tuple[int, int, int, int],
    path: Path,
    cfg: ScreenshotConfig,
    label: str,
    requested_frame: int,
    selection_label: str | None = None,
    *,
    overlay_text: Optional[str] = None,
    overlay_state: Optional[OverlayState] = None,
    strict_overlay: bool = False,
    source_props: Mapping[str, Any] | None = None,
    geometry_plan: GeometryPlan | None = None,
    tonemap_info: "vs_core.TonemapInfo | None" = None,
    pivot_notifier: Callable[[str], None] | None = None,
    color_cfg: "ColorConfig | None" = None,
    file_name: str | None = None,
) -> None:
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("VapourSynth is required for screenshot export") from exc

    if not isinstance(clip, vs.VideoNode):
        raise ScreenshotWriterError("Expected a VapourSynth clip for rendering")

    resolved_policy = _normalise_geometry_policy(cfg.odd_geometry_policy)
    rgb_dither = _normalize_rgb_dither(cfg.rgb_dither)
    clip, source_props_map = _resolve_source_props(
        clip,
        source_props,
        color_cfg=color_cfg,
        file_name=file_name,
    )
    requires_full_chroma = bool(geometry_plan and geometry_plan.get("requires_full_chroma"))
    fmt = getattr(clip, "format", None)
    has_axis, axis_label = _resolve_promotion_axes(fmt, crop, pad)
    yuv_constant = getattr(vs, "YUV", object())
    color_family = getattr(fmt, "color_family", None)
    is_sdr = _is_sdr_pipeline(tonemap_info, source_props_map)
    should_promote = (
        requires_full_chroma
        and has_axis
        and is_sdr
        and color_family == yuv_constant
    )
    format_label = _describe_vs_format(fmt)

    if should_promote:
        logger.info(
            "Odd-geometry on subsampled SDR \u2192 promoting to YUV444P16 (policy=%s, axis=%s, fmt=%s)",
            resolved_policy.value,
            axis_label,
            format_label,
        )
        logger.debug(
            "Promotion details frame=%s src_format=%s dst_format=YUV444P16 dither=%s",
            frame_idx,
            format_label,
            rgb_dither.value,
        )
        if pivot_notifier is not None:
            note = (
                "Full-chroma pivot active (axis={axis}, policy={policy}, backend=fpng, fmt={fmt})"
            ).format(axis=axis_label, policy=resolved_policy.value, fmt=format_label)
            _safe_pivot_notify(pivot_notifier, note)

    core = getattr(clip, "core", None) or getattr(vs, "core", None)
    fpng_ns = getattr(core, "fpng", None) if core is not None else None
    writer = getattr(fpng_ns, "Write", None) if fpng_ns is not None else None
    if not callable(writer):
        raise ScreenshotWriterError("VapourSynth fpng.Write plugin is unavailable")

    work = clip
    if should_promote:
        work = _promote_to_yuv444p16(
            core,
            work,
            frame_idx=frame_idx,
            source_props=source_props_map,
        )
    try:
        left, top, right, bottom = crop
        if any(crop):
            work = work.std.CropRel(left=left, right=right, top=top, bottom=bottom)
        target_w, target_h = scaled
        if work.width != target_w or work.height != target_h:
            resize_ns = getattr(core, "resize", None)
            if resize_ns is None:
                raise ScreenshotWriterError("VapourSynth core is missing resize namespace")
            resampler = getattr(resize_ns, "Spline36", None)
            if not callable(resampler):
                raise ScreenshotWriterError("VapourSynth resize.Spline36 is unavailable")
            work = resampler(work, width=target_w, height=target_h)

        pad_left, pad_top, pad_right, pad_bottom = pad
        if pad_left or pad_top or pad_right or pad_bottom:
            std_ns = getattr(core, "std", None)
            add_borders = getattr(std_ns, "AddBorders", None) if std_ns is not None else None
            if not callable(add_borders):
                raise ScreenshotWriterError("VapourSynth std.AddBorders is unavailable")
            work = add_borders(
                work,
                left=max(0, pad_left),
                right=max(0, pad_right),
                top=max(0, pad_top),
                bottom=max(0, pad_bottom),
            )
    except Exception as exc:
        raise ScreenshotWriterError(f"Failed to prepare frame {frame_idx}: {exc}") from exc

    render_clip = work
    if cfg.add_frame_info:
        render_clip = _apply_frame_info_overlay(
            core,
            render_clip,
            label,
            requested_frame,
            selection_label,
        )

    overlay_state = overlay_state or _new_overlay_state()
    render_clip = _apply_overlay_text(
        core,
        render_clip,
        overlay_text,
        strict=strict_overlay,
        state=overlay_state,
        file_label=label,
    )

    render_clip = _ensure_rgb24(
        core,
        render_clip,
        frame_idx,
        source_props=source_props_map,
        rgb_dither=rgb_dither,
    )
    logger.debug(
        "RGB24 conversion for frame %s used dither=%s (policy=%s)",
        frame_idx,
        rgb_dither.value,
        resolved_policy.value,
    )

    compression = _map_fpng_compression(cfg.compression_level)
    try:
        job: Any = writer(render_clip, str(path), compression=compression, overwrite=True)
        job.get_frame(frame_idx)
    except Exception as exc:
        raise ScreenshotWriterError(f"fpng failed for frame {frame_idx}: {exc}") from exc


def _map_ffmpeg_compression(level: int) -> int:
    """Map config compression level to ffmpeg's PNG compression scale."""

    return _map_png_compression_level(level)


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("=", "\\=")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("'", "\\'")
        .replace("\n", "\\\n")
    )


def _resolve_source_frame_index(frame_idx: int, trim_start: int) -> int | None:
    if trim_start == 0:
        return frame_idx
    if trim_start > 0:
        return frame_idx + trim_start
    blank = abs(int(trim_start))
    if frame_idx < blank:
        return None
    return frame_idx - blank


def _save_frame_with_ffmpeg(
    source: str,
    frame_idx: int,
    crop: Tuple[int, int, int, int],
    scaled: Tuple[int, int],
    pad: Tuple[int, int, int, int],
    path: Path,
    cfg: ScreenshotConfig,
    width: int,
    height: int,
    selection_label: str | None,
    *,
    overlay_text: Optional[str] = None,
    geometry_plan: GeometryPlan | None = None,
    is_sdr: bool = True,
    pivot_notifier: Callable[[str], None] | None = None,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise ScreenshotWriterError("FFmpeg executable not found in PATH")

    cropped_w = max(1, width - crop[0] - crop[2])
    cropped_h = max(1, height - crop[1] - crop[3])

    requires_full_chroma = bool(geometry_plan and geometry_plan.get("requires_full_chroma"))
    promotion_axes_value = (
        geometry_plan.get("promotion_axes", "") if geometry_plan is not None else ""
    )
    axis_label = str(promotion_axes_value).strip() if promotion_axes_value is not None else ""
    if not axis_label:
        axis_label = _describe_plan_axes(geometry_plan)
    filters = [f"select=eq(n\\,{int(frame_idx)})"]
    should_apply_full_chroma = requires_full_chroma and is_sdr
    if should_apply_full_chroma:
        filters.append("format=yuv444p16")
    if any(crop):
        filters.append(
            "crop={w}:{h}:{x}:{y}".format(
                w=max(1, cropped_w),
                h=max(1, cropped_h),
                x=max(0, crop[0]),
                y=max(0, crop[1]),
            )
        )
    if scaled != (cropped_w, cropped_h):
        filters.append(f"scale={max(1, scaled[0])}:{max(1, scaled[1])}:flags=lanczos")
    pad_left, pad_top, pad_right, pad_bottom = pad
    final_w = max(1, scaled[0] + pad_left + pad_right)
    final_h = max(1, scaled[1] + pad_top + pad_bottom)
    if pad_left or pad_top or pad_right or pad_bottom:
        filters.append(
            "pad={w}:{h}:{x}:{y}".format(
                w=final_w,
                h=final_h,
                x=max(0, pad_left),
                y=max(0, pad_top),
            )
        )
    if cfg.add_frame_info:
        text_lines = [f"Frame\\ {int(frame_idx)}"]
        if selection_label:
            text_lines.append(f"Content Type\\: {selection_label}")
        text = "\\\\n".join(text_lines)
        drawtext = (
            "drawtext=text={text}:fontcolor=white:borderw=2:bordercolor=black:"
            "box=0:shadowx=1:shadowy=1:shadowcolor=black:x=10:y=10"
        ).format(text=_escape_drawtext(text))
        filters.append(drawtext)
    if overlay_text:
        overlay_cmd = (
            "drawtext=text={text}:fontcolor=white:borderw=2:bordercolor=black:"
            "box=0:shadowx=1:shadowy=1:shadowcolor=black:x=10:y=80"
        ).format(text=_escape_drawtext(overlay_text))
        filters.append(overlay_cmd)

    if should_apply_full_chroma:
        configured = _normalize_rgb_dither(cfg.rgb_dither)
        ffmpeg_dither = "ordered"
        if configured is RGBDither.NONE:
            ffmpeg_dither = "none"
        elif configured is RGBDither.ORDERED:
            ffmpeg_dither = "ordered"
        else:
            logger.debug(
                "FFmpeg RGB24 conversion forcing deterministic dither=ordered (configured=%s)",
                configured.value,
            )
        filters.append(f"format=rgb24:dither={ffmpeg_dither}")
        if pivot_notifier is not None:
            resolved_policy = _normalise_geometry_policy(cfg.odd_geometry_policy)
            note = (
                "Full-chroma pivot active (axis={axis}, policy={policy}, backend=ffmpeg)"
            ).format(axis=axis_label, policy=resolved_policy.value)
            _safe_pivot_notify(pivot_notifier, note)
    elif requires_full_chroma and not is_sdr:
        logger.debug(
            "Skipping full-chroma pivot for HDR content (axis=%s)",
            axis_label or "none",
        )

    filter_chain = ",".join(filters)
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        source,
        "-vf",
        filter_chain,
        "-frames:v",
        "1",
        "-vsync",
        "0",
        "-compression_level",
        str(_map_ffmpeg_compression(cfg.compression_level)),
        str(path),
    ]

    timeout_value = getattr(cfg, "ffmpeg_timeout_seconds", None)
    timeout_seconds_raw: float | None
    try:
        timeout_seconds_raw = float(timeout_value) if timeout_value is not None else None
    except (TypeError, ValueError):
        timeout_seconds_raw = None

    if timeout_seconds_raw is not None and timeout_seconds_raw <= 0:
        timeout_seconds: float | None = None
    else:
        timeout_seconds = timeout_seconds_raw

    try:
        process = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        duration = timeout_seconds if timeout_seconds is not None else 0.0
        raise ScreenshotWriterError(
            f"FFmpeg timed out after {duration:.1f}s for frame {frame_idx}"
        ) from exc
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", "ignore").strip()
        message = stderr or "unknown error"
        raise ScreenshotWriterError(
            f"FFmpeg failed for frame {frame_idx}: {message}"
        )



def _save_frame_placeholder(path: Path) -> None:
    path.write_bytes(b"placeholder\n")


def generate_screenshots(
    clips: Sequence[Any],
    frames: Sequence[int],
    files: Sequence[str],
    metadata: Sequence[Mapping[str, str]],
    out_dir: Path,
    cfg: ScreenshotConfig,
    color_cfg: ColorConfig,
    *,
    trim_offsets: Sequence[int] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    frame_labels: Mapping[int, str] | None = None,
    selection_details: Mapping[int, Mapping[str, Any]] | None = None,
    alignment_maps: Sequence[Any] | None = None,
    warnings_sink: List[str] | None = None,
    verification_sink: List[Dict[str, Any]] | None = None,
    pivot_notifier: Callable[[str], None] | None = None,
) -> List[str]:
    """
    Render and save screenshots for the given frames from each input clip using the configured writers.

    Render each requested frame for every clip, applying geometry planning, optional overlays, alignment mapping, and the selected writer backend (fpng or ffmpeg). Created files are written into out_dir and their paths are returned in the order they were produced.

    Parameters:
        clips: Sequence of clip objects prepared for rendering.
        frames: Sequence of frame indices to render for each clip.
        files: Sequence of source file paths corresponding to clips; must match length of clips.
        metadata: Sequence of metadata mappings (one per file); must match length of files.
        out_dir: Destination directory for written screenshot files.
        cfg: ScreenshotConfig controlling writer selection, geometry and format options.
        color_cfg: ColorConfig controlling overlays, tonemapping and related color options.
        trim_offsets: Optional per-file trim start offsets; if None, treated as zeros. Must match length of files.
        progress_callback: Optional callable invoked with 1 for each saved file to indicate progress.
        frame_labels: Optional mapping from frame index to a user-visible selection label used in overlays and filenames.
        alignment_maps: Optional sequence of alignment mappers (one per clip) used to map source frame indices.
        warnings_sink: Optional list to which non-fatal warning messages will be appended.
        verification_sink: Optional list to which per-clip verification records will be appended; each record contains keys: file, frame, average, maximum, auto_selected.
        pivot_notifier: Optional callable invoked with a short text note whenever a full-chroma pivot is applied.

    Returns:
        List[str]: Ordered list of file paths for all created screenshot files.
    """

    if len(clips) != len(files):
        raise ScreenshotError("clips and files must have matching lengths")
    if len(metadata) != len(files):
        raise ScreenshotError("metadata and files must have matching lengths")
    if not frames:
        return []

    if trim_offsets is None:
        trim_offsets = [0] * len(files)
    if len(trim_offsets) != len(files):
        raise ScreenshotError("trim_offsets and files must have matching lengths")

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise ScreenshotError(
            "Unable to create screenshot directory "
            f"'{out_dir}': {exc.strerror or exc}"
        ) from exc
    except OSError as exc:
        raise ScreenshotError(
            f"Unable to prepare screenshot directory '{out_dir}': {exc}"
        ) from exc
    created: List[str] = []

    processed_results: List[vs_core.ClipProcessResult] = []
    overlay_states: List[OverlayState] = []

    for clip, file_path in zip(clips, files, strict=True):
        result = vs_core.process_clip_for_screenshot(
            clip,
            file_path,
            color_cfg,
            enable_overlay=True,
            enable_verification=True,
            logger_override=logger,
            warning_sink=warnings_sink,
        )
        processed_results.append(result)
        overlay_states.append(_new_overlay_state())
        if result.verification is not None:
            logger.info(
                "[VERIFY] %s frame=%d avg=%.4f max=%.4f",
                file_path,
                result.verification.frame,
                result.verification.average,
                result.verification.maximum,
            )
            if verification_sink is not None:
                verification_sink.append(
                    {
                        "file": str(file_path),
                        "frame": int(result.verification.frame),
                        "average": float(result.verification.average),
                        "maximum": float(result.verification.maximum),
                        "auto_selected": bool(result.verification.auto_selected),
                    }
                )

    geometry = _plan_geometry([result.clip for result in processed_results], cfg)

    for clip_index, (result, file_path, meta, plan, trim_start) in enumerate(
        zip(processed_results, files, metadata, geometry, trim_offsets, strict=True)
    ):
        mapper = None
        if alignment_maps is not None and clip_index < len(alignment_maps):
            mapper = alignment_maps[clip_index]
        if frame_labels:
            logger.debug('frame_labels keys: %s', list(frame_labels.keys()))
        crop = plan["crop"]
        scaled = plan["scaled"]
        pad = plan["pad"]
        width = int(plan["width"])
        height = int(plan["height"])
        trim_start = int(trim_start)
        raw_label, safe_label = _derive_labels(file_path, meta)

        overlay_state = overlay_states[clip_index]
        base_overlay_text = getattr(result, "overlay_text", None)
        source_props_raw = getattr(result, "source_props", {})
        resolved_clip, resolved_source_props = _resolve_source_props(
            result.clip,
            source_props_raw,
            color_cfg=color_cfg,
            file_name=str(file_path),
        )
        source_props = resolved_source_props
        is_sdr_pipeline = _is_sdr_pipeline(result.tonemap, resolved_source_props)

        for frame in frames:
            frame_idx = int(frame)
            mapped_idx = frame_idx
            if mapper is not None:
                try:
                    mapped_idx, _, clamped = mapper.map_frame(frame_idx)
                except Exception as exc:  # pragma: no cover - mapper issues
                    logger.warning(
                        "Failed to map frame %s for %s via alignment: %s",
                        frame_idx,
                        file_path,
                        exc,
                    )
                    clamped = False
                else:
                    if clamped:
                        logger.debug(
                            "Alignment clamped frame %s→%s for %s",
                            frame_idx,
                            mapped_idx,
                            file_path,
                        )
            detail_info = selection_details.get(frame_idx) if selection_details else None
            selection_label = frame_labels.get(frame_idx) if frame_labels else None
            if selection_label is None and detail_info is not None:
                derived_label = detail_info.get("label") or detail_info.get("type")
                if derived_label:
                    selection_label = str(derived_label)
            if selection_label is not None:
                logger.debug('Selection label for frame %s: %s', frame_idx, selection_label)
            actual_idx, was_clamped = _clamp_frame_index(resolved_clip, mapped_idx)
            if was_clamped:
                logger.debug(
                    "Frame %s exceeds available frames (%s) in %s; using %s",
                    mapped_idx,
                    getattr(resolved_clip, 'num_frames', 'unknown'),
                    file_path,
                    actual_idx,
                )
            overlay_text = _compose_overlay_text(
                base_overlay_text,
                color_cfg,
                plan,
                selection_label,
                source_props,
                tonemap_info=result.tonemap,
                selection_detail=detail_info,
            )
            file_name = _prepare_filename(frame_idx, safe_label)
            target_path = out_dir / file_name

            try:
                resolved_frame = _resolve_source_frame_index(actual_idx, trim_start)
                use_ffmpeg = cfg.use_ffmpeg and resolved_frame is not None
                if cfg.use_ffmpeg and resolved_frame is None:
                    logger.debug(
                        "Frame %s for %s falls within synthetic trim padding; "
                        "using VapourSynth writer",
                        frame_idx,
                        file_path,
                    )
                if use_ffmpeg:
                    assert resolved_frame is not None
                    if overlay_text and overlay_state.get("overlay_status") != "ok":
                        logger.info("[OVERLAY] %s applied (ffmpeg)", file_path)
                        overlay_state["overlay_status"] = "ok"
                    _save_frame_with_ffmpeg(
                        file_path,
                        resolved_frame,
                        crop,
                        scaled,
                        pad,
                        target_path,
                        cfg,
                        width,
                        height,
                        selection_label,
                        overlay_text=overlay_text,
                        geometry_plan=plan,
                        is_sdr=is_sdr_pipeline,
                        pivot_notifier=pivot_notifier,
                    )
                else:
                    _save_frame_with_fpng(
                        resolved_clip,
                        actual_idx,
                        crop,
                        scaled,
                        pad,
                        target_path,
                        cfg,
                        raw_label,
                        frame_idx,
                        selection_label,
                        overlay_text=overlay_text,
                        overlay_state=overlay_state,
                        strict_overlay=bool(getattr(color_cfg, "strict", False)),
                        source_props=resolved_source_props,
                        geometry_plan=plan,
                        tonemap_info=result.tonemap,
                        pivot_notifier=pivot_notifier,
                        color_cfg=color_cfg,
                        file_name=str(file_path),
                    )
            except ScreenshotWriterError:
                raise
            except Exception as exc:
                message = (
                    f"[RENDER] Falling back to placeholder for frame {frame_idx} of {file_path}: {exc}"
                )
                logger.warning(message)
                if warnings_sink is not None:
                    warnings_sink.append(message)
                _save_frame_placeholder(target_path)

            created.append(str(target_path))
            if progress_callback is not None:
                progress_callback(1)

        if warnings_sink is not None:
            warnings_sink.extend(_get_overlay_warnings(overlay_state))

    return created
