"""Map selected comparison frames to the reference-source evidence used for labels."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from frame_compare.analysis.types import SelectionDetail
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.phase_selection import (
    map_aligned_to_source_frame,
    selection_detail_for_frame,
    selection_label_for_frame,
)


@dataclass(frozen=True, slots=True)
class SelectionRow:
    frame: int
    reference_source_frame: int
    label: str | None
    detail: SelectionDetail | None


def selection_rows(ctx: RunContext, *, frames: Sequence[int]) -> list[SelectionRow]:
    rows: list[SelectionRow] = []
    for frame in frames:
        source_frame = map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=frame)
        detail = selection_detail_for_frame(source_frame, ctx.selection.details_by_source_frame)
        label = (
            detail.label
            if detail is not None
            else selection_label_for_frame(source_frame, ctx.selection.breakdown)
        )
        rows.append(SelectionRow(frame, source_frame, label, detail))
    return rows
