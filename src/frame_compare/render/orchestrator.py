from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import structlog

from frame_compare.render.encoders import render_frame
from frame_compare.render.naming import generate_screenshot_path
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    Renderer,
    RenderRequest,
)

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

log = structlog.get_logger(__name__)


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting rendering progress."""

    def start_phase(self, name: str, total: int) -> None:
        """Start a new progress phase."""
        ...

    def set_description(self, description: str) -> None:
        """Set current task description."""
        ...

    def advance(self, n: int = 1) -> None:
        """Advance progress by n units."""
        ...

    def complete_phase(self) -> None:
        """Finish current progress phase."""
        ...


def render_batch(
    requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None
) -> list[Path]:
    """
    Execute a batch of render requests.

    Args:
        requests: List of requests to process
        parallelism: Number of concurrent threads
        reporter: Optional progress reporter

    Returns:
        List of paths to rendered files in input order

    Raises:
        Exception: The first exception encountered during rendering (fail-fast)
    """
    if not requests:
        return []

    results: list[Path | None] = [None] * len(requests)

    if reporter:
        reporter.start_phase("Rendering", len(requests))

    try:
        if parallelism <= 1:
            for i, req in enumerate(requests):
                if reporter:
                    reporter.set_description(f"Frame {req.frame_number}")
                results[i] = render_frame(req)
                if reporter:
                    reporter.advance(1)
        else:
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                futures: dict[Future[Path], int] = {}
                next_idx = 0
                first_exc: Exception | None = None

                # Initial fill
                while next_idx < min(parallelism, len(requests)):
                    futures[executor.submit(render_frame, requests[next_idx])] = next_idx
                    next_idx += 1

                while futures:
                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                    for f in done:
                        idx = futures.pop(f)
                        try:
                            results[idx] = f.result()
                            if reporter:
                                reporter.set_description(f"Frame {requests[idx].frame_number}")
                                reporter.advance(1)

                            # Submit next if no exception yet
                            if first_exc is None and next_idx < len(requests):
                                futures[executor.submit(render_frame, requests[next_idx])] = (
                                    next_idx
                                )
                                next_idx += 1
                        except Exception as e:
                            if first_exc is None:
                                first_exc = e
                                # Cancel remaining pending tasks
                                for pending_f in futures:
                                    pending_f.cancel()

                    if first_exc:
                        # We continue to wait for already running tasks to finish
                        # but we won't submit more.
                        pass

                if first_exc:
                    raise first_exc

    finally:
        if reporter:
            reporter.complete_phase()

    return cast(list[Path], results)


def render_screenshots(
    clips: list[Path],
    frames: list[int],
    output_dir: Path,
    label_map: dict[Path, str] | None = None,
    renderer: Renderer = "auto",
    overlay_mode: OverlayMode = OverlayMode.STANDARD,
    reporter: ProgressReporter | None = None,
) -> dict[str, list[Path]]:
    """
    Render multiple frames from multiple clips.

    Args:
        clips: List of video paths
        frames: List of frame indices to render
        output_dir: Base output directory
        label_map: Optional mapping of Path -> label string
        renderer: "vapoursynth", "ffmpeg", or "auto"
        overlay_mode: Overlay verbosity
        reporter: Optional progress reporter

    Returns:
        Dict mapping label -> list of rendered screenshot paths
    """
    from frame_compare.errors import (
        PluginNotFoundError,
        RenderError,
        SourceLoadError,
        VapourSynthNotFoundError,
    )

    label_map = label_map or {}
    all_requests: list[RenderRequest] = []

    # Store labels in order to preserve clip ordering in result dict
    ordered_labels: list[str] = []

    for clip_path in clips:
        label = label_map.get(clip_path, clip_path.stem)
        ordered_labels.append(label)

        # Load clip
        loaded_clip: vs.VideoNode | Path = clip_path
        resolution = (0, 0)

        if renderer in ("vapoursynth", "auto"):
            try:
                from frame_compare.vs.loader import DefaultVSLoader

                loader = DefaultVSLoader()
                source_info = loader.load(clip_path)
                loaded_clip = source_info.clip
                resolution = (source_info.width, source_info.height)
            except (VapourSynthNotFoundError, PluginNotFoundError, SourceLoadError):
                if renderer == "vapoursynth":
                    raise
                log.warning(
                    "vs_load_failed_falling_back",
                    path=str(clip_path),
                    renderer=renderer,
                    exc_info=True,
                )
            except Exception as e:
                if renderer == "vapoursynth":
                    raise RenderError() from e
                log.warning(
                    "vs_load_failed_falling_back_unknown",
                    path=str(clip_path),
                    renderer=renderer,
                    exc_info=True,
                )

        for frame in frames:
            output_path = generate_screenshot_path(output_dir, label, frame)

            overlay = OverlayConfig(
                mode=overlay_mode,
                label=label,
                frame_number=frame,
                resolution=resolution,
                hdr_info=None,
                font_path=None,
            )

            req = RenderRequest(
                clip=loaded_clip,
                frame_number=frame,
                output_path=output_path,
                overlay=overlay,
                encoder_settings=EncoderSettings(),
            )
            all_requests.append(req)

    # Execute batch
    # Plan says: "Delegate execution to render_batch". Default parallelism=1.
    rendered_paths = render_batch(all_requests, parallelism=1, reporter=reporter)

    # Reconstruct results dict
    results: dict[str, list[Path]] = {}
    path_idx = 0
    for label in ordered_labels:
        results[label] = []
        for _ in frames:
            results[label].append(rendered_paths[path_idx])
            path_idx += 1

    return results
