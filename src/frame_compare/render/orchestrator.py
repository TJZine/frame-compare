from __future__ import annotations

import json
import subprocess
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
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

    from frame_compare.config.schema import ConfigSchema
    from frame_compare.vs.types import SourceInfo, TonemapSettings

log = structlog.get_logger()


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting rendering progress."""

    def start_phase(self, name: str, total: int) -> None:
        """Start a new progress phase."""
        ...

    def set_description(self, desc: str) -> None:
        """Set current task description."""
        ...

    def advance(self, amount: int = 1) -> None:
        """Advance progress by amount units."""
        ...

    def complete_phase(self) -> None:
        """Finish current progress phase."""
        ...


# ─── Tonemap Helper Functions (SSOT: render-module.md §1.4) ────────────────────


def should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool:
    """Determine if tonemap MUST be applied.

    Args:
        source_info: Loaded source metadata from VSLoader
        config: Resolved configuration

    Returns:
        True if tonemap MUST be applied
    """
    return source_info.is_hdr and config.color.enable_tonemap


def resolve_tonemap_settings(
    config: ConfigSchema, cli_overrides: dict[str, object] | None = None
) -> TonemapSettings:
    """Resolve tonemap settings from config and CLI overrides.

    Args:
        config: Resolved configuration
        cli_overrides: Optional CLI flag overrides (tm_preset, tm_target, tm_curve)

    Returns:
        Complete TonemapSettings ready for apply_tonemap()
    """
    from frame_compare.vs.tonemap import get_preset_settings

    # Start with preset
    preset_name = (cli_overrides or {}).get("tm_preset") or config.color.preset.value
    if preset_name is None:
        preset_name = "reference"
    settings = get_preset_settings(str(preset_name))

    # Apply config overrides (config values always have defaults; direct access)
    settings = replace(settings, target_nits=config.color.target_nits)
    settings = replace(settings, tone_curve=config.color.tone_curve.value)
    settings = replace(settings, gamma_lift=config.color.gamma_lift)
    settings = replace(settings, contrast_recovery=config.color.contrast_recovery)

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        if cli_overrides.get("tm_target") is not None:
            settings = replace(settings, target_nits=int(cli_overrides["tm_target"]))  # type: ignore[arg-type]
        if cli_overrides.get("tm_curve") is not None:
            settings = replace(settings, tone_curve=str(cli_overrides["tm_curve"]))

    return settings


def probe_is_hdr_ffprobe(path: Path) -> bool:
    """Determine HDR using ffprobe stream metadata (no VS required).

    SSOT: render-module.md §1.4.1 — HDR detection when VS is unavailable.

    HDR detection rule (deterministic):
    - Treat as HDR if and only if BOTH:
      - color_transfer in {"smpte2084", "arib-std-b67"} (PQ or HLG)
      - color_primaries == "bt2020"

    Returns:
        True if source appears to be HDR, False otherwise.
        Conservative: returns True on missing/unknown metadata.

    Raises:
        FFmpegNotFoundError: If ffprobe is not found
        SourceLoadError: If ffprobe fails or output is invalid
    """
    from frame_compare.errors import FFmpegNotFoundError, SourceLoadError

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=color_transfer,color_primaries",
        "-of",
        "json",
        str(path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegNotFoundError() from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceLoadError(path, "ffprobe timed out") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise SourceLoadError(path, f"ffprobe failed: {stderr[:200]}")

    try:
        output = result.stdout.decode("utf-8")
        data = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceLoadError(path, f"ffprobe output invalid: {exc}") from exc

    # Parse streams — conservative policy: missing/empty → HDR
    streams: list[dict[str, object]] | None = data.get("streams")
    if not isinstance(streams, list) or len(streams) == 0:
        return True  # Conservative: treat as HDR

    stream: dict[str, object] = streams[0]
    color_transfer: object = stream.get("color_transfer", "")
    color_primaries: object = stream.get("color_primaries", "")

    # Normalize
    if not isinstance(color_transfer, str) or not color_transfer.strip():
        return True  # Conservative: treat as HDR
    if not isinstance(color_primaries, str) or not color_primaries.strip():
        return True  # Conservative: treat as HDR

    color_transfer_norm = color_transfer.lower().strip()
    color_primaries_norm = color_primaries.lower().strip()

    # HDR detection: PQ/HLG + BT.2020
    is_hdr_transfer = color_transfer_norm in {"smpte2084", "arib-std-b67"}
    is_bt2020_primaries = color_primaries_norm == "bt2020"

    return is_hdr_transfer and is_bt2020_primaries


def _render_description(request: RenderRequest) -> str:
    """Build a consistent progress description for a render request."""
    label = request.overlay.label if request.overlay is not None else None
    return f"{label} — Frame {request.frame_number}" if label else f"Frame {request.frame_number}"


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
                    reporter.set_description(_render_description(req))
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
                                reporter.set_description(_render_description(requests[idx]))
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
    config: ConfigSchema,
    label_map: dict[Path, str] | None = None,
    renderer: Renderer = "auto",
    overlay_mode: OverlayMode = OverlayMode.STANDARD,
    reporter: ProgressReporter | None = None,
    *,
    output_frames: list[int] | None = None,
    selection_labels: list[str | None] | None = None,
) -> dict[str, list[Path]]:
    """Render multiple frames from multiple clips.

    Args:
        clips: List of video paths
        frames: List of frame indices to render
        output_frames: Optional list of frame indices used for output filenames and overlay display.
        output_dir: Base output directory
        config: Resolved configuration (required for tonemap gating)
        label_map: Optional mapping of Path -> label string
        renderer: "vapoursynth", "ffmpeg", or "auto"
        overlay_mode: Overlay verbosity
        reporter: Optional progress reporter

    Returns:
        Dict mapping label -> list of rendered screenshot paths

    Raises:
        TonemapRequiresVapourSynthError: If HDR + enable_tonemap=True on FFmpeg-only path
        PluginNotFoundError: If required VS plugin is missing (renderer=vapoursynth)
        SourceLoadError: If source loading fails (renderer=vapoursynth)
        FFmpegNotFoundError: If ffprobe is missing for HDR probe
        RenderError: For other rendering failures
    """
    from frame_compare.errors import (
        PluginNotFoundError,
        RenderError,
        SourceLoadError,
        TonemapRequiresVapourSynthError,
        VapourSynthNotFoundError,
    )

    label_map = label_map or {}
    all_requests: list[RenderRequest] = []

    if output_frames is not None and len(output_frames) != len(frames):
        raise ValueError("output_frames must have the same length as frames")
    if selection_labels is not None and len(selection_labels) != len(frames):
        raise ValueError("selection_labels must have the same length as frames")

    # Store labels in order to preserve clip ordering in result dict
    ordered_labels: list[str] = []

    for clip_path in clips:
        label = label_map.get(clip_path, clip_path.stem)
        ordered_labels.append(label)

        # Load clip
        loaded_clip: vs.VideoNode | Path = clip_path
        resolution = (0, 0)
        hdr_info: str | None = None
        source_info = None
        vs_load_failure: Exception | None = None

        if renderer in ("vapoursynth", "auto"):
            try:
                from frame_compare.vs.loader import DefaultVSLoader

                loader = DefaultVSLoader()
                source_info = loader.load(clip_path)
                loaded_clip = source_info.clip
                resolution = (source_info.width, source_info.height)

                # === TONEMAP INTEGRATION POINT (§1.4.3) ===
                if should_tonemap(source_info, config):
                    from frame_compare.vs.tonemap import apply_tonemap

                    settings = resolve_tonemap_settings(config)
                    loaded_clip = apply_tonemap(loaded_clip, settings, source_info.hdr_metadata)
                    # Mark that tonemap was applied for overlay (§1.4.6)
                    hdr_info = f"HDR (tonemapped: {settings.preset}, {settings.target_nits} nits)"
                elif source_info.is_hdr:
                    # HDR source, tonemap disabled (§1.4.6)
                    hdr_info = "HDR (native, no tonemap)"
                else:
                    # SDR source
                    hdr_info = None  # or "SDR" in DIAGNOSTIC mode

            except (VapourSynthNotFoundError, PluginNotFoundError, SourceLoadError) as exc:
                if renderer == "vapoursynth":
                    raise
                # Store failure for fallback logic
                vs_load_failure = exc
            except Exception as e:
                if renderer == "vapoursynth":
                    raise RenderError(reason=f"{type(e).__name__}: {e}") from e
                vs_load_failure = e

        # === DETERMINISTIC FALLBACK LOGIC (§1.4.1, §1.4.4) ===
        if vs_load_failure is not None and renderer == "auto":
            # VS load failed, check if we can fall back to FFmpeg
            if config.color.enable_tonemap:
                # Must probe HDR status before deciding
                try:
                    is_hdr = probe_is_hdr_ffprobe(clip_path)
                except Exception:
                    # Probe failed — propagate (no fallback)
                    log.debug(
                        "probe_failed_no_fallback",
                        path=str(clip_path),
                        exc_info=True,
                    )
                    raise  # Propagate probe exception

                if is_hdr:
                    # HDR + tonemap required in auto mode + VS unavailable → re-raise original VS failure.
                    log.debug(
                        "hdr_tonemap_required_no_fallback",
                        path=str(clip_path),
                    )
                    raise vs_load_failure  # Re-raise VS failure
                else:
                    # SDR — fallback allowed
                    log.warning(
                        "vs_load_failed_falling_back",
                        path=str(clip_path),
                        renderer=renderer,
                        exc_info=True,
                    )
            else:
                # enable_tonemap=False — fallback allowed
                log.warning(
                    "vs_load_failed_falling_back",
                    path=str(clip_path),
                    renderer=renderer,
                    exc_info=True,
                )

        # === RENDERER=FFMPEG WITH TONEMAP GATING (§1.4.4) ===
        if renderer == "ffmpeg" and config.color.enable_tonemap:
            try:
                is_hdr = probe_is_hdr_ffprobe(clip_path)
            except Exception:
                # Probe failed — propagate (no FFmpeg path)
                log.debug(
                    "probe_failed_no_ffmpeg",
                    path=str(clip_path),
                    exc_info=True,
                )
                raise  # Propagate probe exception

            if is_hdr:
                # HDR + tonemap required → FFmpeg-only path is invalid.
                raise TonemapRequiresVapourSynthError()

        for idx, frame in enumerate(frames):
            output_frame = output_frames[idx] if output_frames is not None else frame
            output_path = generate_screenshot_path(output_dir, label, output_frame)
            selection_label = selection_labels[idx] if selection_labels is not None else None

            overlay = OverlayConfig(
                mode=overlay_mode,
                label=label,
                frame_number=frame,
                display_frame_number=output_frame,
                num_frames=source_info.num_frames if source_info is not None else None,
                selection_label=selection_label,
                resolution=resolution,
                hdr_info=hdr_info,
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
