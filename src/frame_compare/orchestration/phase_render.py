"""Screenshot-render phase execution and overlay diagnostic mapping."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from frame_compare.config.schema import OverlayMode
from frame_compare.orchestration.context import ClipProbeSnapshot, RunContext
from frame_compare.orchestration.execution_types import RenderArtifacts, RenderPhaseOutput
from frame_compare.orchestration.phase_selection import (
    map_aligned_to_source_frame,
    selection_detail_for_frame,
    selection_label_for_frame,
    to_overlay_selection_detail,
)
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.vs.props import range_label_from_props

if TYPE_CHECKING:
    from frame_compare.render.types import (
        OverlayDiagnosticMetadata,
        OverlayDolbyVisionMetadata,
        OverlayFrameMeasurement,
        OverlaySelectionDetail,
    )


def _normalize_preserved_prop_key(key: str) -> str:
    return key.lstrip("_").lower()


def _coerce_float(value: str | int | float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _coerce_int(value: str | int | float) -> int | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(round(number))


def _color_range_from_preserved_props(
    preserved_props: dict[str, str | int | float],
) -> str | None:
    normalized_props: dict[str, int] = {}
    for key, value in preserved_props.items():
        normalized = _normalize_preserved_prop_key(key)
        if normalized not in {"range", "colorrange"}:
            continue
        coerced = _coerce_int(value)
        if coerced is not None:
            if normalized == "range":
                normalized_props["_Range"] = coerced
            else:
                normalized_props["_ColorRange"] = coerced
    return range_label_from_props(normalized_props)


def _dolby_vision_metadata_from_preserved_props(
    preserved_props: dict[str, str | int | float],
) -> OverlayDolbyVisionMetadata | None:
    from frame_compare.render.types import OverlayDolbyVisionMetadata

    rpu_present = False
    block_index: int | None = None
    block_total: int | None = None
    target_nits: float | None = None
    l2_target_nits: float | None = None
    l1_average: float | None = None
    l1_maximum: float | None = None
    l5_left: int | None = None
    l5_right: int | None = None
    l5_top: int | None = None
    l5_bottom: int | None = None
    l6_max_cll: float | None = None
    l6_max_fall: float | None = None

    for key, value in preserved_props.items():
        normalized = _normalize_preserved_prop_key(key)
        if normalized == "dolbyvisionrpu":
            rpu_present = True
            continue
        if not any(
            token in normalized for token in ("dolby", "dovi", "rpu", "l1", "l2", "l5", "l6")
        ):
            continue
        if "l2" in normalized and "target" in normalized:
            if l2_target_nits is None:
                l2_target_nits = _coerce_float(value)
            continue
        if "l1" in normalized and any(token in normalized for token in ("avg", "average", "mean")):
            if l1_average is None:
                l1_average = _coerce_float(value)
            continue
        if "l1" in normalized and "max" in normalized:
            if l1_maximum is None:
                l1_maximum = _coerce_float(value)
            continue
        if "l5" in normalized:
            coerced = _coerce_int(value)
            if coerced is None or coerced < 0:
                continue
            if "left" in normalized and l5_left is None:
                l5_left = coerced
            elif "right" in normalized and l5_right is None:
                l5_right = coerced
            elif "top" in normalized and l5_top is None:
                l5_top = coerced
            elif "bottom" in normalized and l5_bottom is None:
                l5_bottom = coerced
            continue
        if "l6" in normalized:
            if "cll" in normalized and l6_max_cll is None:
                l6_max_cll = _coerce_float(value)
            elif "fall" in normalized and l6_max_fall is None:
                l6_max_fall = _coerce_float(value)
            continue
        if "block" in normalized and "index" in normalized and block_index is None:
            block_index = _coerce_int(value)
            continue
        if (
            "block" in normalized
            and ("total" in normalized or "count" in normalized)
            and block_total is None
        ):
            block_total = _coerce_int(value)
            continue
        if (
            "target" in normalized
            and any(token in normalized for token in ("nit", "pq", "brightness"))
            and target_nits is None
        ):
            target_nits = _coerce_float(value)

    has_metadata = rpu_present or any(
        value is not None
        for value in (
            block_index,
            block_total,
            target_nits,
            l2_target_nits,
            l1_average,
            l1_maximum,
            l5_left,
            l5_right,
            l5_top,
            l5_bottom,
            l6_max_cll,
            l6_max_fall,
        )
    )
    if not has_metadata:
        return None
    return OverlayDolbyVisionMetadata(
        rpu_present=rpu_present,
        block_index=block_index,
        block_total=block_total,
        target_nits=target_nits,
        l2_target_nits=l2_target_nits,
        l1_average=l1_average,
        l1_maximum=l1_maximum,
        l5_left=l5_left,
        l5_right=l5_right,
        l5_top=l5_top,
        l5_bottom=l5_bottom,
        l6_max_cll=l6_max_cll,
        l6_max_fall=l6_max_fall,
    )


def _score_measurement_for_selection(
    *,
    selection_detail: OverlaySelectionDetail | None,
    overlay_mode: OverlayMode,
    per_frame_nits_enabled: bool,
    target_nits: int,
) -> OverlayFrameMeasurement | None:
    from frame_compare.render.types import OverlayFrameMeasurement

    if (
        not per_frame_nits_enabled
        or overlay_mode != OverlayMode.DIAGNOSTIC
        or selection_detail is None
        or selection_detail.score is None
    ):
        return None
    score = float(selection_detail.score)
    if score != score:
        return None
    clamped_score = max(0.0, min(score, 1.0))
    measurement_nits = clamped_score * float(target_nits)
    category = selection_detail.label.strip() or None
    return OverlayFrameMeasurement(
        avg_nits=measurement_nits,
        max_nits=measurement_nits,
        category=category,
    )


def _overlay_diagnostic_metadata_for_frame(
    *,
    probe: ClipProbeSnapshot,
    selection_detail: OverlaySelectionDetail | None,
    overlay_mode: OverlayMode,
    per_frame_nits_enabled: bool,
    target_nits: int,
) -> OverlayDiagnosticMetadata | None:
    from frame_compare.render.types import OverlayDiagnosticMetadata

    hdr_metadata = probe.hdr_metadata
    measurement = _score_measurement_for_selection(
        selection_detail=selection_detail,
        overlay_mode=overlay_mode,
        per_frame_nits_enabled=per_frame_nits_enabled,
        target_nits=target_nits,
    )
    color_range = _color_range_from_preserved_props(probe.preserved_frame_props)
    dolby_vision = _dolby_vision_metadata_from_preserved_props(probe.preserved_frame_props)
    mastering_display = hdr_metadata.mastering_display if hdr_metadata is not None else None
    max_cll = hdr_metadata.max_cll if hdr_metadata is not None else None
    max_fall = hdr_metadata.max_fall if hdr_metadata is not None else None
    if (
        mastering_display is None
        and max_cll is None
        and max_fall is None
        and color_range is None
        and dolby_vision is None
        and measurement is None
    ):
        return None
    return OverlayDiagnosticMetadata(
        mastering_display=mastering_display,
        max_cll=max_cll,
        max_fall=max_fall,
        color_range=color_range,
        dolby_vision=dolby_vision,
        measurement=measurement,
    )


def run_render_phase(
    ctx: RunContext,
    *,
    frames: list[int],
    runner: FFmpegRunner,
) -> RenderPhaseOutput:
    from frame_compare.render.batch.orchestrator import render_screenshots_from_batch
    from frame_compare.render.geometry import GeometryRect
    from frame_compare.render.types import (
        BatchRenderOptions,
        ScreenshotBatchRequest,
    )

    clips_state = [ctx.reference, *ctx.comparisons]
    output_dir = ctx.workspace.screenshots_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    overlay_mode = ctx.config.screenshots.overlay_mode
    reference_source_frames = [
        map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=aligned_frame)
        for aligned_frame in frames
    ]
    selection_details: list[OverlaySelectionDetail | None] = [
        to_overlay_selection_detail(detail)
        if (
            detail := selection_detail_for_frame(
                source_frame,
                ctx.selection_details_by_source_frame,
            )
        )
        is not None
        else None
        for source_frame in reference_source_frames
    ]
    selection_labels = [
        detail.label
        if detail is not None
        else selection_label_for_frame(source_frame, ctx.selection_breakdown)
        for source_frame, detail in zip(reference_source_frames, selection_details, strict=True)
    ]

    batch_requests: list[ScreenshotBatchRequest] = []
    for clip in clips_state:
        source_frames = [
            map_aligned_to_source_frame(clip=clip, aligned_frame=aligned_frame)
            for aligned_frame in frames
        ]
        diagnostic_metadata = [
            _overlay_diagnostic_metadata_for_frame(
                probe=clip.probe,
                selection_detail=detail,
                overlay_mode=overlay_mode,
                per_frame_nits_enabled=ctx.config.diagnostics.per_frame_nits,
                target_nits=ctx.config.color.target_nits,
            )
            for detail in selection_details
        ]
        batch_requests.append(
            ScreenshotBatchRequest(
                clip_path=clip.path,
                label=clip.label,
                filename_label=clip.path.stem,
                source_frames=source_frames,
                display_frames=frames,
                selection_labels=selection_labels,
                selection_details=selection_details,
                diagnostic_metadata=diagnostic_metadata,
                active_rect=GeometryRect(
                    clip.active_rect.x if clip.active_rect is not None else 0,
                    clip.active_rect.y if clip.active_rect is not None else 0,
                    clip.active_rect.width if clip.active_rect is not None else clip.probe.width,
                    clip.active_rect.height if clip.active_rect is not None else clip.probe.height,
                ),
                active_rect_source=(
                    clip.active_rect.source if clip.active_rect is not None else "full-frame"
                ),
                active_rect_detection_mode=(
                    clip.active_rect.detection_mode
                    if clip.active_rect is not None
                    else ctx.config.screenshots.active_rect_detection.value
                ),
                probe_width=clip.probe.width,
                probe_height=clip.probe.height,
                probe_num_frames=clip.probe.num_frames,
                probe_is_hdr=clip.probe.is_hdr,
            )
        )

    render_warnings: list[str] = []
    rendered = render_screenshots_from_batch(
        batch_requests=batch_requests,
        output_dir=output_dir,
        config=ctx.config,
        options=BatchRenderOptions(
            overlay_mode=overlay_mode,
            ffmpeg_runner=runner,
            reporter=ctx.reporter,
            warnings=render_warnings,
        ),
    )

    return RenderPhaseOutput(
        render=RenderArtifacts(
            screenshots_by_label=rendered,
            screenshot_dir=output_dir,
            warnings=render_warnings,
        )
    )
