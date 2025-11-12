"""Clip initialisation and selection helpers used by the runner."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, List, Optional, Sequence, Tuple

from rich.markup import escape

from src.datatypes import AnalysisConfig, RuntimeConfig
from src.frame_compare import vs as vs_core
from src.frame_compare.analysis import SelectionWindowSpec, compute_selection_window
from src.frame_compare.cli_runtime import CLIAppError

logger = logging.getLogger(__name__)

__all__: Final = [
    "extract_clip_fps",
    "init_clips",
    "resolve_selection_windows",
    "log_selection_windows",
]

if TYPE_CHECKING:
    from src.frame_compare.cli_runtime import CliOutputManagerProtocol, ClipPlan
else:  # pragma: no cover - runtime-only fallback
    CliOutputManagerProtocol = Any  # type: ignore[assignment]
    ClipPlan = Any  # type: ignore[assignment]


def _extract_clip_fps(clip: object) -> Tuple[int, int]:
    """Return (fps_num, fps_den) from *clip*, defaulting to 24000/1001 when missing."""
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return (num, den)
    return (24000, 1001)


extract_clip_fps = _extract_clip_fps


def init_clips(
    plans: Sequence[ClipPlan],
    runtime_cfg: RuntimeConfig,
    cache_dir: Path | None,
    *,
    reporter: CliOutputManagerProtocol | None = None,
) -> None:
    """Initialise VapourSynth clips for each plan and capture source metadata."""
    vs_core.set_ram_limit(runtime_cfg.ram_limit_mb)

    def _indexing_note(filename: str) -> None:
        label = escape(filename)
        if reporter is not None:
            reporter.console.print(f"[dim][CACHE] Indexing {label}…[/]")
        else:
            logger.info("[CACHE] Indexing %s…", filename)

    cache_dir_str = str(cache_dir) if cache_dir is not None else None

    reference_index = next((idx for idx, plan in enumerate(plans) if plan.use_as_reference), None)
    reference_fps: Optional[Tuple[int, int]] = None

    if reference_index is not None:
        plan = plans[reference_index]
        clip = vs_core.init_clip(
            str(plan.path),
            trim_start=plan.trim_start,
            trim_end=plan.trim_end,
            cache_dir=cache_dir_str,
            indexing_notifier=_indexing_note,
        )
        plan.clip = clip
        plan.effective_fps = _extract_clip_fps(clip)
        plan.source_fps = plan.effective_fps
        plan.source_num_frames = int(getattr(clip, "num_frames", 0) or 0)
        plan.source_width = int(getattr(clip, "width", 0) or 0)
        plan.source_height = int(getattr(clip, "height", 0) or 0)
        reference_fps = plan.effective_fps

    for idx, plan in enumerate(plans):
        if idx == reference_index and plan.clip is not None:
            continue
        fps_override = plan.fps_override
        if fps_override is None and reference_fps is not None and idx != reference_index:
            fps_override = reference_fps

        clip = vs_core.init_clip(
            str(plan.path),
            trim_start=plan.trim_start,
            trim_end=plan.trim_end,
            fps_map=fps_override,
            cache_dir=cache_dir_str,
            indexing_notifier=_indexing_note,
        )
        plan.clip = clip
        plan.applied_fps = fps_override
        plan.effective_fps = _extract_clip_fps(clip)
        plan.source_fps = plan.effective_fps
        plan.source_num_frames = int(getattr(clip, "num_frames", 0) or 0)
        plan.source_width = int(getattr(clip, "width", 0) or 0)
        plan.source_height = int(getattr(clip, "height", 0) or 0)


def resolve_selection_windows(
    plans: Sequence[ClipPlan],
    analysis_cfg: AnalysisConfig,
) -> tuple[List[SelectionWindowSpec], tuple[int, int], bool]:
    specs: List[SelectionWindowSpec] = []
    min_total_frames: Optional[int] = None
    for plan in plans:
        clip = plan.clip
        if clip is None:
            raise CLIAppError("Clip initialisation failed")
        total_frames = int(getattr(clip, "num_frames", 0))
        if min_total_frames is None or total_frames < min_total_frames:
            min_total_frames = total_frames
        fps_num, fps_den = plan.effective_fps or _extract_clip_fps(clip)
        fps_val = fps_num / fps_den if fps_den else 0.0
        try:
            spec = compute_selection_window(
                total_frames,
                fps_val,
                analysis_cfg.ignore_lead_seconds,
                analysis_cfg.ignore_trail_seconds,
                analysis_cfg.min_window_seconds,
            )
        except TypeError as exc:
            detail = (
                f"Invalid analysis window values for {plan.path.name}: "
                f"lead={analysis_cfg.ignore_lead_seconds!r} "
                f"trail={analysis_cfg.ignore_trail_seconds!r} "
                f"min={analysis_cfg.min_window_seconds!r}"
            )
            raise CLIAppError(
                detail,
                rich_message=f"[red]{escape(detail)}[/red]",
            ) from exc
        specs.append(spec)

    if not specs:
        return [], (0, 0), False

    start = max(spec.start_frame for spec in specs)
    end = min(spec.end_frame for spec in specs)
    collapsed = False
    if end <= start:
        collapsed = True
        fallback_end = min_total_frames or 0
        start = 0
        end = fallback_end

    if end <= start:
        raise CLIAppError("No frames remain after applying ignore window")

    return specs, (start, end), collapsed


def log_selection_windows(
    plans: Sequence[ClipPlan],
    specs: Sequence[SelectionWindowSpec],
    intersection: tuple[int, int],
    *,
    collapsed: bool,
    analyze_fps: float,
    reporter: CliOutputManagerProtocol | None = None,
) -> None:
    """Log per-clip selection windows plus the common intersection summary."""

    def _emit(markup: str, plain: str, *, warning: bool = False) -> None:
        if reporter is not None:
            reporter.console.print(markup)
        else:
            log_fn = logger.warning if warning else logger.info
            log_fn(plain)

    for plan, spec in zip(plans, specs):
        raw_label = plan.metadata.get("label") or plan.path.name
        label_plain = (raw_label or plan.path.name).strip()
        label_markup = escape(label_plain)
        selection_markup = (
            f"[cyan]{label_markup}[/]: Selecting frames within [start={spec.start_seconds:.2f}s, "
            f"end={spec.end_seconds:.2f}s] (frames [{spec.start_frame}, {spec.end_frame})) — "
            f"lead={spec.applied_lead_seconds:.2f}s, trail={spec.applied_trail_seconds:.2f}s"
        )
        selection_plain = (
            f"{label_plain}: Selecting frames within start={spec.start_seconds:.2f}s, "
            f"end={spec.end_seconds:.2f}s (frames [{spec.start_frame}, {spec.end_frame})) — "
            f"lead={spec.applied_lead_seconds:.2f}s, trail={spec.applied_trail_seconds:.2f}s"
        )
        _emit(selection_markup, selection_plain)
        for warning in spec.warnings:
            warning_markup = f"[yellow]{label_markup}[/]: {warning}"
            warning_plain = f"{label_plain}: {warning}"
            _emit(warning_markup, warning_plain, warning=True)

    start_frame, end_frame = intersection
    if analyze_fps > 0 and end_frame > start_frame:
        start_seconds = start_frame / analyze_fps
        end_seconds = end_frame / analyze_fps
    else:
        start_seconds = float(start_frame)
        end_seconds = float(end_frame)

    common_markup = (
        f"[cyan]Common selection window[/]: frames [{start_frame}, {end_frame}) — "
        f"seconds [{start_seconds:.2f}s, {end_seconds:.2f}s)"
    )
    common_plain = (
        f"Common selection window: frames [{start_frame}, {end_frame}) — "
        f"seconds [{start_seconds:.2f}s, {end_seconds:.2f}s)"
    )
    _emit(common_markup, common_plain)

    if collapsed:
        collapsed_markup = (
            "[yellow]Ignore lead/trail settings did not overlap across all sources; using fallback range.[/yellow]"
        )
        collapsed_plain = (
            "Ignore lead/trail settings did not overlap across all sources; using fallback range."
        )
        _emit(collapsed_markup, collapsed_plain, warning=True)
