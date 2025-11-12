from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any, List, Optional, cast

from src.datatypes import ColorConfig
from src.frame_compare.layout_utils import format_resolution_summary

__all__ = [
    "FRAME_INFO_STYLE",
    "OVERLAY_STYLE",
    "OverlayState",
    "OverlayStateValue",
    "append_overlay_warning",
    "compose_overlay_text",
    "extract_mastering_display_luminance",
    "format_luminance_value",
    "format_mastering_display_line",
    "format_selection_line",
    "get_overlay_warnings",
    "new_overlay_state",
    "normalize_selection_label",
]

if TYPE_CHECKING:
    from src.frame_compare import vs as vs_core
    from src.screenshot import GeometryPlan

    TonemapInfo = vs_core.TonemapInfo
else:  # pragma: no cover - runtime type fallback
    GeometryPlan = Mapping[str, Any]  # type: ignore[misc, assignment]
    TonemapInfo = Any


OverlayStateValue = str | List[str]
OverlayState = MutableMapping[str, OverlayStateValue]


SELECTION_LABELS: Mapping[str, str] = {
    "dark": "Dark",
    "bright": "Bright",
    "motion": "Motion",
    "user": "User",
    "random": "Random",
    "auto": "Auto",
    "cached": "Cached",
}


FRAME_INFO_STYLE = (
    'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,'
    '"0,0,0,0,100,100,0,0,1,2,0,7,10,10,10,1"'
)
OVERLAY_STYLE = (
    'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,'
    '"0,0,0,0,100,100,0,0,1,2,0,7,10,10,70,1"'
)


def new_overlay_state() -> OverlayState:
    """Create a mutable overlay state container."""

    return cast(OverlayState, {})


def append_overlay_warning(state: OverlayState, message: str) -> None:
    """Store a warning message inside *state* preserving existing entries."""

    warnings_value = state.get("warnings")
    if not isinstance(warnings_value, list):
        warnings_value = []
        state["warnings"] = warnings_value
    warnings_value.append(message)


def get_overlay_warnings(state: OverlayState) -> List[str]:
    """Return previously recorded overlay warnings."""

    warnings_value = state.get("warnings")
    if isinstance(warnings_value, list):
        return warnings_value
    return []


def normalize_selection_label(label: Optional[str]) -> str:
    """Normalize a selection label into a user-facing display name."""

    if not label:
        return "(unknown)"
    cleaned = label.strip()
    if not cleaned:
        return "(unknown)"
    normalized = cleaned.lower()
    mapped = SELECTION_LABELS.get(normalized)
    if mapped:
        return mapped
    return cleaned


def format_selection_line(selection_label: Optional[str]) -> str:
    """Return the formatted selection line for overlay text."""

    return f"Frame Selection Type: {normalize_selection_label(selection_label)}"


def _coerce_luminance_values(value: Any) -> List[float]:
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
        iterable = cast(Sequence[Any], value)
        results: List[float] = []
        for item in iterable:
            results.extend(_coerce_luminance_values(item))
        return results
    return []


def extract_mastering_display_luminance(props: Mapping[str, Any]) -> tuple[Optional[float], Optional[float]]:
    """Extract mastering display min/max luminance pairs from frame props."""

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
                break

    return min_value, max_value


def format_luminance_value(value: float) -> str:
    """Format luminance values with context-aware precision."""

    if value < 1.0:
        text = f"{value:.4f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
    return f"{value:.1f}"


def format_mastering_display_line(props: Mapping[str, Any]) -> str:
    """Return a human readable mastering display summary line."""

    min_value, max_value = extract_mastering_display_luminance(props)
    if min_value is None or max_value is None:
        return "MDL: Insufficient data"
    return (
        f"MDL: min: {format_luminance_value(min_value)} cd/m², "
        f"max: {format_luminance_value(max_value)} cd/m²"
    )


def compose_overlay_text(
    base_text: Optional[str],
    color_cfg: ColorConfig,
    plan: GeometryPlan,
    selection_label: Optional[str],
    source_props: Mapping[str, Any],
    *,
    tonemap_info: Optional[TonemapInfo],
    selection_detail: Optional[Mapping[str, Any]] = None,  # kept for compatibility
) -> Optional[str]:
    """Compose a user-facing overlay text snippet."""

    if not bool(getattr(color_cfg, "overlay_enabled", True)):
        return None

    mode = str(getattr(color_cfg, "overlay_mode", "minimal")).strip().lower()
    if mode != "diagnostic":
        lines: List[str] = []
        if base_text:
            lines.append(base_text)
        lines.append(format_resolution_summary(plan))
        lines.append(format_selection_line(selection_label))
        return "\n".join(lines)

    lines = []
    if base_text:
        lines.append(base_text)

    lines.append(format_resolution_summary(plan))
    include_hdr_details = bool(tonemap_info and getattr(tonemap_info, "applied", False))
    if include_hdr_details:
        lines.append(format_mastering_display_line(source_props))
    lines.append(format_selection_line(selection_label))
    return "\n".join(lines)
