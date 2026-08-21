"""Analysis-source resolution and benchmarking policy."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from frame_compare.orchestration.context import ClipState
from frame_compare.orchestration.errors import FastestAnalysisSourceError
from frame_compare.orchestration.source_selection import resolve_source_selector

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader


@runtime_checkable
class _FrameReadable(Protocol):
    @property
    def num_frames(self) -> int: ...

    def get_frame(self, n: int) -> object: ...


@dataclass(frozen=True)
class AnalysisSourceSelection:
    """Resolved source used for metric analysis."""

    clip: ClipState
    reason: str
    warning: str | None = None


def resolve_analysis_source(
    *,
    selector: str,
    input_dir: Path,
    clips: list[ClipState],
    vs_loader: VSLoader | None,
) -> AnalysisSourceSelection:
    """Resolve the configured analysis source for metric-producing runs."""
    if not clips:
        raise FastestAnalysisSourceError()

    if selector == "reference":
        return AnalysisSourceSelection(clip=clips[0], reason="reference")
    if selector == "fastest":
        selected = _select_fastest_clip(clips=clips, vs_loader=vs_loader)
        return AnalysisSourceSelection(
            clip=selected,
            reason="fastest",
            warning=f"Analysis source: {_clip_role(clips, selected)} | selected by fastest-source policy",
        )

    paths = [clip.path for clip in clips]
    selected_path = resolve_source_selector(
        selector=selector,
        input_dir=input_dir,
        paths=paths,
        role="sources.analysis_source",
    )
    for clip in clips:
        if clip.path == selected_path:
            return AnalysisSourceSelection(
                clip=clip,
                reason="configured",
                warning=f"Analysis source: {_clip_role(clips, clip)} | selected by configured policy",
            )
    raise FastestAnalysisSourceError()


def _clip_role(clips: list[ClipState], selected: ClipState) -> str:
    index = clips.index(selected)
    return "Reference" if index == 0 else f"Comparison {index}"


def _select_fastest_clip(*, clips: list[ClipState], vs_loader: VSLoader | None) -> ClipState:
    if vs_loader is None:
        raise FastestAnalysisSourceError()

    timings: list[tuple[float, int, ClipState]] = []
    for index, clip in enumerate(clips):
        elapsed = _benchmark_clip(clip=clip, vs_loader=vs_loader)
        if elapsed is None:
            continue
        timings.append((elapsed, index, clip))

    if not timings:
        raise FastestAnalysisSourceError()
    return min(timings, key=lambda item: (item[0], item[1]))[2]


def _benchmark_clip(*, clip: ClipState, vs_loader: VSLoader) -> float | None:
    try:
        source = vs_loader.load(clip.path)
        node: _FrameReadable | None = None
        benchmark_node: _FrameReadable | None = None
        try:
            node = source.clip
            benchmark_node = _plane_stats_node(node)
            frames = list(_benchmark_frames(max(0, int(node.num_frames))))
            if not frames:
                return None

            started = perf_counter()
            for frame in frames:
                benchmark_node.get_frame(frame)
            return (perf_counter() - started) / len(frames)
        finally:
            benchmark_node = None
            node = None
            del source
    except Exception:
        return None


def _plane_stats_node(node: _FrameReadable) -> _FrameReadable:
    std = getattr(node, "std", None)
    plane_stats = getattr(std, "PlaneStats", None)
    if callable(plane_stats):
        result = plane_stats()
        if isinstance(result, _FrameReadable):
            return result
    return node


def _benchmark_frames(frame_count: int) -> Iterable[int]:
    if frame_count <= 0:
        return ()

    windows = (frame_count // 3, (frame_count * 2) // 3)
    frames: list[int] = []
    for start in windows:
        bounded_start = min(max(0, start), frame_count - 1)
        remaining = frame_count - bounded_start
        for offset in range(min(15, remaining)):
            frames.append(bounded_start + offset)
    return frames
