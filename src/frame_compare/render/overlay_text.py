from __future__ import annotations

from collections.abc import Sequence

from frame_compare.render.types import OverlayMode


def compose_frame_info_lines(
    *,
    mode: OverlayMode,
    label: str | None,
    display_frame_number: int,
    num_frames: int | None,
    picture_type: str | None,
    selection_label: str | None,
) -> list[str]:
    """
    Compose the "frame-info" block lines for the overlay.

    Invariants:
    - MINIMAL: label only (single line).
    - STANDARD/DIAGNOSTIC: frame line, picture type, label, optional selection.
    - NONE: no lines.
    """
    if mode == OverlayMode.NONE:
        return []

    clip_label = label or "Clip"

    if mode == OverlayMode.MINIMAL:
        return [clip_label]

    if num_frames is None:
        frame_line = f"Frame {display_frame_number}"
    else:
        frame_line = f"Frame {display_frame_number} of {num_frames}"

    pict = picture_type or "N/A"
    lines = [
        frame_line,
        f"Picture type: {pict}",
        clip_label,
    ]
    if selection_label:
        lines.append(f"Selection: {selection_label}")
    return lines


def compose_overlay_text_lines(
    *,
    mode: OverlayMode,
    base_text: str | None,
    width: int,
    height: int,
    selection_type: str | None,
    diagnostic_lines: Sequence[str],
) -> list[str]:
    """
    Compose the "overlay-text" block lines for the overlay.

    Invariants:
    - STANDARD: optional base text, resolution, selection type.
    - DIAGNOSTIC: like STANDARD, but inserts diagnostic lines before selection type.
    - MINIMAL/NONE: no lines.
    """
    if mode in (OverlayMode.NONE, OverlayMode.MINIMAL):
        return []

    lines: list[str] = []
    if base_text:
        lines.append(base_text)

    if width > 0 and height > 0:
        lines.append(f"{width} × {height}  (native)")

    if mode == OverlayMode.DIAGNOSTIC:
        lines.extend(diagnostic_lines)

    selection = selection_type or "(unknown)"
    lines.append(f"Frame Selection Type: {selection}")
    return lines
