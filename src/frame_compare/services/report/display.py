"""Report-owned frame display metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass

from frame_compare.services.report.category_display import label_repeats_category
from frame_compare.services.report.payload import FrameDetail


@dataclass(frozen=True)
class SourceFrameSelectionDetail:
    """Plain selection detail data needed for report display shaping."""

    label: str | None = None
    timecode: str | None = None
    notes: str | None = None


def _default_frame_label(source_frame: int) -> str:
    return f"Frame {source_frame}"


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
    category = None
    if selection_detail is not None:
        category = selection_detail.notes or category_from_selection_label(selection_detail.label)
    if category is None:
        category = category_from_selection_label(selection_label)

    label = _default_frame_label(source_frame)
    if (
        selection_detail is not None
        and selection_detail.label is not None
        and not label_repeats_category(selection_detail.label, category)
    ):
        label = selection_detail.label

    detail_text = f"Source frame {source_frame}"

    return FrameDetail(
        label=label,
        detail=detail_text,
        category=category,
    )
