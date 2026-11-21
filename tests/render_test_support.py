"""Explicit clip jobs and render observations for synthetic test inputs."""

from collections.abc import Sequence
from pathlib import Path

from frame_compare.render.types import (
    PreparedClipRender,
    RenderedClip,
    RenderedClipFacts,
    RenderedFrameResult,
    RenderedScreenshot,
    RenderRequest,
    SelectedScreenshot,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)


def clip_facts() -> RenderedClipFacts:
    return RenderedClipFacts(
        0,
        (1920, 1080),
        100,
        SourceSignalFacts(is_hdr=False),
        PresentationState.SDR,
        None,
        RenderedGeometryFacts(
            (1920, 1080),
            ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
            (1920, 1080),
            (1920, 1080),
            (1920, 1080),
            True,
        ),
    )


def selections(
    source_frames: Sequence[int],
    comparison_frames: Sequence[int] | None = None,
    selection_labels: Sequence[str | None] | None = None,
) -> tuple[SelectedScreenshot, ...]:
    return tuple(
        SelectedScreenshot(comparison, source, label)
        for source, comparison, label in zip(
            source_frames,
            source_frames if comparison_frames is None else comparison_frames,
            [None] * len(source_frames) if selection_labels is None else selection_labels,
            strict=True,
        )
    )


def prepared_jobs(*groups: Sequence[RenderRequest]) -> tuple[PreparedClipRender, ...]:
    return tuple(
        PreparedClipRender(
            str(index), clip_facts(), selections([r.frame_number for r in group]), tuple(group)
        )
        for index, group in enumerate(groups)
    )


def frame_results(clips: Sequence[RenderedClip]) -> list[RenderedFrameResult]:
    return [shot.result for clip in clips for shot in clip.screenshots]


def paths_by_label(clips: Sequence[RenderedClip]) -> dict[str, list[Path]]:
    return {clip.label: [shot.result.path for shot in clip.screenshots] for clip in clips}


def facts_by_label(clips: Sequence[RenderedClip]):
    return {clip.label: [shot.result.facts for shot in clip.screenshots] for clip in clips}


def rendered_clips(
    paths: dict[str, list[Path]],
    frame_facts: dict[str, list[RenderedFrameFacts]],
    clip_metadata: dict[str, RenderedClipFacts],
) -> tuple[RenderedClip, ...]:
    return tuple(
        RenderedClip(
            label,
            clip_metadata[label],
            tuple(
                RenderedScreenshot(
                    SelectedScreenshot(index, fact.source_frame, None),
                    RenderedFrameResult(path, fact),
                )
                for index, (path, fact) in enumerate(zip(values, frame_facts[label], strict=True))
            ),
        )
        for label, values in paths.items()
    )
