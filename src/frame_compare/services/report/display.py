"""Report-owned frame display metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass

from frame_compare.services.report.payload import FrameDetail


@dataclass(frozen=True)
class SourceFrameSelectionDetail:
    """Plain selection detail data needed for report display shaping."""

    label: str | None = None
    timecode: str | None = None
    notes: str | None = None


def category_from_selection_label(label: str | None) -> str | None:
    if label is None:
        return None
    match label:
        case "Dark":
            return "quantile_dark"
        case "Bright":
            return "quantile_bright"
        case "Motion":
            return "motion"
        case "Random":
            return "random"
        case _:
            return None


def frame_detail_for_source_frame(
    *,
    source_frame: int,
    selection_detail: SourceFrameSelectionDetail | None,
    selection_label: str | None,
) -> FrameDetail:
    """Build report display metadata for a selected source-domain frame."""
    label = (
        selection_detail.label
        if selection_detail is not None and selection_detail.label is not None
        else selection_label
    )
    detail_text = f"Source frame {source_frame}"
    if selection_detail is not None and selection_detail.timecode is not None:
        detail_text = f"{detail_text} ({selection_detail.timecode})"

    category = None
    if selection_detail is not None:
        category = selection_detail.notes or category_from_selection_label(selection_detail.label)
    if category is None:
        category = category_from_selection_label(selection_label)

    return FrameDetail(
        label=label,
        detail=detail_text,
        category=category,
    )
