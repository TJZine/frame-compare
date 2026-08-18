"""Pure deterministic overlay text composition."""

from __future__ import annotations

from frame_compare.config.schema import OverlayMode
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import (
    ExactFrameDolbyVisionFacts,
    HDRStaticFacts,
    PictureType,
    PresentationState,
    RenderedFrameFacts,
    normalize_picture_type,
)

_PRIMARIES = {1: "BT.709", 9: "BT.2020"}
_TRANSFER = {1: "BT.709", 16: "PQ", 18: "HLG"}
_MATRIX = {1: "BT.709", 9: "BT.2020nc", 10: "BT.2020c"}


def compose_overlay_text_lines(config: OverlayConfig, frame_facts: RenderedFrameFacts) -> list[str]:
    """Compose ordered non-empty overlay lines from supplied facts only."""
    if config.mode == OverlayMode.NONE:
        return []
    if frame_facts.source_frame != config.source_frame:
        raise ValueError("overlay frame facts do not match the configured source frame")

    picture_type = normalize_picture_type(frame_facts.picture_type)

    lines: list[str] = []
    if config.label:
        lines.append(config.label)
    if config.mode == OverlayMode.MINIMAL:
        segments: list[str] = []
        if config.include_frame_number:
            segments.append(f"Frame {config.comparison_frame}")
        if picture_type is not None:
            segments.append(f"{picture_type}-frame")
        if config.file_size_bytes > 0:
            segments.append(format_file_size(config.file_size_bytes))
        if segments:
            lines.append(" • ".join(segments))
        return lines

    frame_line = _frame_line(config, picture_type)
    if frame_line:
        lines.append(frame_line)
    if config.selection_label:
        lines.append(f"Selection: {config.selection_label}")
    source_segments: list[str] = []
    width, height = config.source_resolution
    if width > 0 and height > 0:
        source_segments.append(f"{width}×{height}")
    file_size = _format_file_size_if_valid(config.file_size_bytes)
    if file_size is not None:
        source_segments.append(file_size)
    if source_segments:
        lines.append(f"Source: {' • '.join(source_segments)}")

    if config.mode == OverlayMode.STANDARD:
        if not config.geometry.is_noop:
            width, height = config.geometry.final_canvas_size
            lines.append(f"Output: {width}×{height} aligned")
        return lines

    lines.extend(_diagnostic_lines(config, frame_facts))
    return lines


def format_file_size(size_bytes: int) -> str:
    """Format raw bytes with the locked IEC boundary policy."""
    if size_bytes < 0:
        raise ValueError("file size must be non-negative")
    if size_bytes >= 1024**4:
        return f"{size_bytes / 1024**4:.2f} TiB"
    if size_bytes >= 1024**3:
        return f"{size_bytes / 1024**3:.2f} GiB"
    return f"{size_bytes / 1024**2:.2f} MiB"


def _format_file_size_if_valid(size_bytes: int) -> str | None:
    return format_file_size(size_bytes) if size_bytes > 0 else None


def _frame_line(config: OverlayConfig, picture_type: PictureType | None) -> str | None:
    segments: list[str] = []
    if config.include_frame_number:
        total = f"/{config.source_total_frames}" if config.source_total_frames is not None else ""
        if config.comparison_frame == config.source_frame:
            segments.append(f"Frame {config.comparison_frame}{total}")
        else:
            segments.append(
                f"Comparison {config.comparison_frame} → source {config.source_frame}{total}"
            )
    if picture_type is not None:
        segments.append(f"{picture_type}-frame")
    return " • ".join(segments) or None


def _diagnostic_lines(config: OverlayConfig, facts: RenderedFrameFacts) -> list[str]:
    lines: list[str] = []
    geometry = config.geometry
    if not geometry.is_noop:
        active = geometry.active_picture
        provenance = {
            "explicit": "explicit",
            "dolby_vision_l5": "DV L5",
            "dimension_derived": "dimension-derived",
            "aspect_ratio_derived": "aspect-ratio-derived",
            "content_derived": "content-derived",
            "full_frame": "full-frame",
        }.get(active.provenance)
        if provenance is not None:
            canvas = geometry.final_canvas_size
            lines.append(
                f"Geometry: active {active.width}×{active.height} @ ({active.x},{active.y}) "
                f"• {provenance} → {canvas[0]}×{canvas[1]} canvas"
            )

    signal = config.signal
    signal_parts = ["HDR" if signal.is_hdr else "SDR"]
    color = [
        _PRIMARIES.get(signal.primaries) if signal.primaries is not None else None,
        _TRANSFER.get(signal.transfer) if signal.transfer is not None else None,
        _MATRIX.get(signal.matrix) if signal.matrix is not None else None,
    ]
    named_color = " / ".join(value for value in color if value is not None)
    if named_color:
        signal_parts.append(named_color)
    if signal.color_range in ("limited", "full"):
        signal_parts.append(signal.color_range.title())
    if signal.dolby_vision_rpu:
        signal_parts.append("DV RPU")
    if config.presentation_state == PresentationState.HDR_TONEMAP_OFF:
        signal_parts.append("tonemap off")
    lines.append(f"Signal: {' • '.join(signal_parts)}")

    settings = config.tonemap_settings
    if settings is not None and config.presentation_state == PresentationState.HDR_TONEMAPPED:
        curve = {
            "bt2390": "BT.2390",
            "spline": "Spline",
            "reinhard": "Reinhard",
        }.get(settings.tone_curve.value, settings.tone_curve.value)
        lines.append(f"Tonemap: {curve} → {settings.target_nits} nits")

    static = signal.hdr_static
    if static is not None:
        groups: list[str] = []
        if static.mastering_min_nits is not None and static.mastering_max_nits is not None:
            groups.append(
                f"MDL {_number(static.mastering_min_nits)}–"
                f"{_number(static.mastering_max_nits)} nits"
            )
        if static.max_cll is not None and static.max_fall is not None:
            groups.append(f"MaxCLL/FALL {static.max_cll}/{static.max_fall}")
        elif static.max_cll is not None:
            groups.append(f"MaxCLL {static.max_cll} nits")
        elif static.max_fall is not None:
            groups.append(f"MaxFALL {static.max_fall} nits")
        if groups:
            lines.append(f"HDR static: {' • '.join(groups)}")

    lines.extend(_dolby_vision_lines(facts.dolby_vision, static))
    return lines


def _dolby_vision_lines(
    dynamic: ExactFrameDolbyVisionFacts | None,
    static: HDRStaticFacts | None,
) -> list[str]:
    """Format only exact-frame Dolby Vision facts supplied by the caller."""
    if dynamic is None:
        return []

    l1_max = dynamic.l1_maximum_nits
    l1_average = dynamic.l1_average_nits
    l2_target = dynamic.l2_target_nits
    groups: list[str] = []
    if l1_max is not None and l1_average is not None:
        groups.append(f"L1 max/avg {_number(l1_max)}/{_number(l1_average)} nits")
    elif l1_max is not None:
        groups.append(f"L1 max {_number(l1_max)} nits")
    elif l1_average is not None:
        groups.append(f"L1 avg {_number(l1_average)} nits")
    if l2_target is not None:
        groups.append(f"L2 target {_number(l2_target)} nits")

    lines = [f"DV frame: {' • '.join(groups)}"] if groups else []

    static_max = static.max_cll if static is not None else None
    static_fall = static.max_fall if static is not None else None
    l6_max = dynamic.l6_max_cll
    l6_fall = dynamic.l6_max_fall
    # A matching static value adds no information.  Compare each component
    # independently so partial L6 facts remain useful.
    keep_max = l6_max is not None and l6_max != static_max
    keep_fall = l6_fall is not None and l6_fall != static_fall
    l6_groups: list[str] = []
    if keep_max and l6_max is not None and keep_fall and l6_fall is not None:
        l6_groups.append(f"MaxCLL/FALL {_number(l6_max)}/{_number(l6_fall)} nits")
    elif keep_max and l6_max is not None:
        l6_groups.append(f"MaxCLL {_number(l6_max)} nits")
    elif keep_fall and l6_fall is not None:
        l6_groups.append(f"MaxFALL {_number(l6_fall)} nits")
    if l6_groups:
        lines.append(f"DV L6: {' • '.join(l6_groups)}")
    return lines


def _number(value: float | int) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


__all__ = ["compose_overlay_text_lines", "format_file_size"]
