"""Pure deterministic overlay text composition."""

from __future__ import annotations

from frame_compare.config.schema import OverlayMode
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import RenderedFrameFacts

_PRIMARIES = {1: "BT.709", 9: "BT.2020"}
_TRANSFER = {1: "BT.709", 16: "PQ", 18: "HLG"}
_MATRIX = {1: "BT.709", 9: "BT.2020nc", 10: "BT.2020c"}


def compose_overlay_text_lines(config: OverlayConfig, frame_facts: RenderedFrameFacts) -> list[str]:
    """Compose ordered non-empty overlay lines from supplied facts only."""
    if config.mode == OverlayMode.NONE:
        return []
    if frame_facts.source_frame != config.source_frame:
        raise ValueError("overlay frame facts do not match the configured source frame")

    lines = [config.label]
    if config.mode == OverlayMode.MINIMAL:
        segments: list[str] = []
        if config.include_frame_number:
            segments.append(f"Frame {config.comparison_frame}")
        if frame_facts.picture_type is not None:
            segments.append(f"{frame_facts.picture_type}-frame")
        if config.file_size_bytes > 0:
            segments.append(format_file_size(config.file_size_bytes))
        if segments:
            lines.append(" • ".join(segments))
        return lines

    frame_line = _frame_line(config, frame_facts)
    if frame_line:
        lines.append(frame_line)
    if config.selection_label:
        lines.append(f"Selection: {config.selection_label}")
    source_segments = [
        f"{config.source_resolution[0]}×{config.source_resolution[1]}",
        format_file_size(config.file_size_bytes) if config.file_size_bytes > 0 else "",
    ]
    lines.append(f"Source: {' • '.join(part for part in source_segments if part)}")

    if config.mode == OverlayMode.STANDARD:
        if not config.geometry.is_noop:
            width, height = config.geometry.final_canvas_size
            lines.append(f"Output: {width}×{height} aligned")
        return lines

    lines.extend(_diagnostic_lines(config, frame_facts))
    return lines


def format_file_size(size_bytes: int) -> str:
    """Format raw bytes with the locked IEC boundary policy."""
    if size_bytes >= 1024**4:
        return f"{size_bytes / 1024**4:.2f} TiB"
    if size_bytes >= 1024**3:
        return f"{size_bytes / 1024**3:.2f} GiB"
    return f"{size_bytes / 1024**2:.2f} MiB"


def _frame_line(config: OverlayConfig, facts: RenderedFrameFacts) -> str | None:
    segments: list[str] = []
    if config.include_frame_number:
        total = f"/{config.source_total_frames}" if config.source_total_frames is not None else ""
        if config.comparison_frame == config.source_frame:
            segments.append(f"Frame {config.comparison_frame}{total}")
        else:
            segments.append(
                f"Comparison {config.comparison_frame} → source {config.source_frame}{total}"
            )
    if facts.picture_type is not None:
        segments.append(f"{facts.picture_type}-frame")
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
        }[active.provenance]
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
    if signal.color_range is not None:
        signal_parts.append(signal.color_range.title())
    if signal.dolby_vision_rpu:
        signal_parts.append("DV RPU")
    if config.presentation_state.value == "hdr_tonemap_off":
        signal_parts.append("tonemap off")
    lines.append(f"Signal: {' • '.join(signal_parts)}")

    settings = config.tonemap_settings
    if settings is not None:
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

    dynamic = facts.dolby_vision
    if dynamic is not None:
        groups = []
        if dynamic.l1_maximum_nits is not None and dynamic.l1_average_nits is not None:
            groups.append(
                f"L1 max/avg {_number(dynamic.l1_maximum_nits)}/"
                f"{_number(dynamic.l1_average_nits)} nits"
            )
        elif dynamic.l1_maximum_nits is not None:
            groups.append(f"L1 max {_number(dynamic.l1_maximum_nits)} nits")
        elif dynamic.l1_average_nits is not None:
            groups.append(f"L1 avg {_number(dynamic.l1_average_nits)} nits")
        if dynamic.l2_target_nits is not None:
            groups.append(f"L2 target {_number(dynamic.l2_target_nits)} nits")
        if groups:
            lines.append(f"DV frame: {' • '.join(groups)}")
    return lines


def _number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


__all__ = ["compose_overlay_text_lines", "format_file_size"]
