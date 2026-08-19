"""Screenshot-render phase mapping from canonical orchestration state."""

from __future__ import annotations

import re

from frame_compare.orchestration.context import ClipProbeSnapshot, ClipState, RunContext
from frame_compare.orchestration.execution_types import RenderArtifacts, RenderPhaseOutput
from frame_compare.orchestration.phase_selection import (
    map_aligned_to_source_frame,
    selection_detail_for_frame,
    selection_label_for_frame,
)
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.render.geometry import active_picture_provenance_from_rect_source
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    HDRStaticFacts,
    SourceSignalFacts,
)
from frame_compare.vs.props import range_label_from_props

_MASTERING_LUMINANCE = re.compile(r"L\((\d+(?:\.\d+)?|\.\d+),(\d+(?:\.\d+)?|\.\d+)\)")


def run_render_phase(
    ctx: RunContext,
    *,
    frames: list[int],
    runner: FFmpegRunner,
) -> RenderPhaseOutput:
    from frame_compare.render.batch.orchestrator import render_screenshots_from_batch_detailed
    from frame_compare.render.types import BatchRenderOptions, ScreenshotBatchRequest

    clips = [ctx.reference, *ctx.comparisons]
    output_dir = ctx.workspace.screenshots_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_frames = [
        map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=frame) for frame in frames
    ]
    selection_labels = [
        detail.label
        if (
            detail := selection_detail_for_frame(
                source_frame,
                ctx.selection_details_by_source_frame,
            )
        )
        is not None
        else selection_label_for_frame(source_frame, ctx.selection_breakdown)
        for source_frame in reference_frames
    ]

    requests: list[ScreenshotBatchRequest] = []
    expected_frames: dict[str, list[int]] = {}
    for clip in clips:
        source_frames = [
            map_aligned_to_source_frame(clip=clip, aligned_frame=frame) for frame in frames
        ]
        expected_frames[clip.label] = source_frames
        active_picture = _active_picture_facts(clip)
        requests.append(
            ScreenshotBatchRequest(
                clip_path=clip.path,
                label=clip.label,
                filename_label=clip.path.stem,
                source_frames=source_frames,
                comparison_frames=frames,
                selection_labels=selection_labels,
                size_bytes=clip.probe.fingerprint.size_bytes,
                source_resolution=(clip.probe.width, clip.probe.height),
                source_total_frames=clip.probe.num_frames,
                signal=_source_signal_facts(clip.probe),
                active_picture=active_picture,
            )
        )

    warnings: list[str] = []
    rendered = render_screenshots_from_batch_detailed(
        batch_requests=requests,
        output_dir=output_dir,
        config=ctx.config,
        options=BatchRenderOptions(
            overlay_mode=ctx.config.screenshots.overlay_mode,
            ffmpeg_runner=runner,
            reporter=ctx.reporter,
        ),
    )
    for label, expected in expected_frames.items():
        actual = [fact.source_frame for fact in rendered.frame_facts_by_label[label]]
        if actual != expected:
            raise ValueError(f"rendered frame facts do not match source mapping for {label!r}")
        missing_count = sum(
            fact.picture_type is None for fact in rendered.frame_facts_by_label[label]
        )
        if missing_count:
            warnings.append(
                f"render: picture type unavailable for {missing_count} selected frame(s) in "
                f"{label}; screenshots were rendered without picture-type metadata"
            )

    return RenderPhaseOutput(
        render=RenderArtifacts(
            screenshots_by_label=rendered.screenshots_by_label,
            frame_facts_by_label=rendered.frame_facts_by_label,
            clip_facts_by_label=rendered.clip_facts_by_label,
            screenshot_dir=output_dir,
            warnings=warnings,
        )
    )


def _source_signal_facts(probe: ClipProbeSnapshot) -> SourceSignalFacts:
    props = {key.lstrip("_").lower(): value for key, value in probe.preserved_frame_props.items()}
    color_props: dict[str, int] = {}
    for source_key, target_key in (("range", "_Range"), ("colorrange", "_ColorRange")):
        value = props.get(source_key)
        if isinstance(value, int) and not isinstance(value, bool):
            color_props[target_key] = value
    range_label = range_label_from_props(color_props)
    color_range = (
        "limited"
        if range_label is not None and range_label.lower() == "limited"
        else "full"
        if range_label is not None and range_label.lower() == "full"
        else None
    )
    hdr = probe.hdr_metadata
    primaries = _observed_int(props.get("primaries"))
    if primaries is None and hdr is not None:
        primaries = _observed_int(hdr.color_primaries)
    transfer = _observed_int(props.get("transfer"))
    if transfer is None and hdr is not None:
        transfer = _observed_int(hdr.transfer)
    matrix = _observed_int(props.get("matrix"))
    if matrix is None and hdr is not None:
        matrix = _observed_int(hdr.matrix)
    static = None
    if hdr is not None:
        mastering_min, mastering_max = _mastering_luminance(hdr.mastering_display)
        if any(
            value is not None for value in (mastering_min, mastering_max, hdr.max_cll, hdr.max_fall)
        ):
            static = HDRStaticFacts(
                mastering_min_nits=mastering_min,
                mastering_max_nits=mastering_max,
                max_cll=hdr.max_cll,
                max_fall=hdr.max_fall,
            )
    return SourceSignalFacts(
        is_hdr=probe.is_hdr,
        primaries=primaries,
        transfer=transfer,
        matrix=matrix,
        color_range=color_range,
        dolby_vision_rpu="dolbyvisionrpu" in props,
        hdr_static=static,
    )


def _observed_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value != 2 else None


def _mastering_luminance(value: str | None) -> tuple[float | None, float | None]:
    if value is None or (match := _MASTERING_LUMINANCE.search(value)) is None:
        return None, None
    maximum_token, minimum_token = match.groups()
    try:
        if "." in maximum_token or "." in minimum_token:
            maximum = float(maximum_token)
            minimum = float(minimum_token)
        else:
            maximum = int(maximum_token) / 10000
            minimum = int(minimum_token) / 10000
    except ValueError:
        return None, None
    return minimum, maximum


def _active_picture_facts(clip: ClipState) -> ActivePictureFacts:
    active = clip.active_rect
    if active is None:
        return ActivePictureFacts(
            0,
            0,
            clip.probe.width,
            clip.probe.height,
            "full_frame",
            True,
        )
    provenance = active_picture_provenance_from_rect_source(active.source)
    return ActivePictureFacts(
        active.x,
        active.y,
        active.width,
        active.height,
        provenance,
        active.x == 0
        and active.y == 0
        and active.width == clip.probe.width
        and active.height == clip.probe.height,
    )
