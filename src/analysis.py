from __future__ import annotations

"""Frame analysis and selection utilities."""

import math
import random
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .datatypes import AnalysisConfig
from . import vs_core


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameMetricsCacheInfo:
    """Context needed to load/save cached frame metrics for analysis."""

    path: Path
    files: Sequence[str]
    analyzed_file: str
    release_group: str
    trim_start: int
    trim_end: Optional[int]
    fps_num: int
    fps_den: int


@dataclass
class CachedMetrics:
    brightness: List[tuple[int, float]]
    motion: List[tuple[int, float]]
    selection_frames: Optional[List[int]]
    selection_hash: Optional[str]
    selection_categories: Optional[Dict[int, str]]


@dataclass(frozen=True)
class SelectionWindowSpec:
    """Resolved selection window boundaries for a clip."""

    start_frame: int
    end_frame: int
    start_seconds: float
    end_seconds: float
    applied_lead_seconds: float
    applied_trail_seconds: float
    duration_seconds: float
    warnings: Tuple[str, ...] = ()


def _quantile(sequence: Sequence[float], q: float) -> float:
    """Return the *q* quantile of *sequence* using linear interpolation."""

    if not sequence:
        raise ValueError("quantile requires a non-empty sequence")
    if math.isnan(q):
        raise ValueError("quantile fraction must be a real number")
    if q <= 0:
        return min(sequence)
    if q >= 1:
        return max(sequence)

    sorted_vals = sorted(sequence)
    position = q * (len(sorted_vals) - 1)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return sorted_vals[lower_index]
    fraction = position - lower_index
    return sorted_vals[lower_index] * (1 - fraction) + sorted_vals[upper_index] * fraction


def _config_fingerprint(cfg: AnalysisConfig) -> str:
    """Return a stable hash for config fields that influence metrics generation."""

    relevant = {
        "frame_count_dark": cfg.frame_count_dark,
        "frame_count_bright": cfg.frame_count_bright,
        "frame_count_motion": cfg.frame_count_motion,
        "downscale_height": cfg.downscale_height,
        "step": cfg.step,
        "analyze_in_sdr": cfg.analyze_in_sdr,
        "use_quantiles": cfg.use_quantiles,
        "dark_quantile": cfg.dark_quantile,
        "bright_quantile": cfg.bright_quantile,
        "motion_use_absdiff": cfg.motion_use_absdiff,
        "motion_scenecut_quantile": cfg.motion_scenecut_quantile,
        "screen_separation_sec": cfg.screen_separation_sec,
        "motion_diff_radius": cfg.motion_diff_radius,
        "random_seed": cfg.random_seed,
        "skip_head_seconds": cfg.skip_head_seconds,
        "skip_tail_seconds": cfg.skip_tail_seconds,
        "ignore_lead_seconds": cfg.ignore_lead_seconds,
        "ignore_trail_seconds": cfg.ignore_trail_seconds,
        "min_window_seconds": cfg.min_window_seconds,
    }
    payload = json.dumps(relevant, sort_keys=True).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def compute_selection_window(
    num_frames: int,
    fps: float,
    ignore_lead_seconds: float,
    ignore_trail_seconds: float,
    min_window_seconds: float,
) -> SelectionWindowSpec:
    """Resolve a trimmed time/frame window respecting configured ignores."""

    if num_frames <= 0:
        return SelectionWindowSpec(
            start_frame=0,
            end_frame=0,
            start_seconds=0.0,
            end_seconds=0.0,
            applied_lead_seconds=0.0,
            applied_trail_seconds=0.0,
            duration_seconds=0.0,
            warnings=(),
        )

    fps_val = float(fps) if isinstance(fps, (int, float)) else 0.0
    if not math.isfinite(fps_val) or fps_val <= 0:
        fps_val = 24000 / 1001

    duration = num_frames / fps_val if fps_val > 0 else 0.0
    lead = max(0.0, float(ignore_lead_seconds))
    trail = max(0.0, float(ignore_trail_seconds))
    min_window = max(0.0, float(min_window_seconds))

    start_sec = min(lead, max(0.0, duration))
    end_sec = max(start_sec, max(0.0, duration - trail))
    warnings: List[str] = []

    span = end_sec - start_sec
    if min_window > 0 and duration > 0 and span < min_window:
        if min_window >= duration:
            start_sec = 0.0
            end_sec = duration
        else:
            needed = min_window - span
            available_end = max(0.0, duration - end_sec)
            extend_end = min(needed, available_end)
            end_sec += extend_end
            needed -= extend_end
            if needed > 0:
                available_start = start_sec
                shift_start = min(needed, available_start)
                start_sec -= shift_start
                needed -= shift_start
            # final clamp inside clip bounds
            start_sec = max(0.0, start_sec)
            end_sec = min(duration, end_sec)
            if end_sec - start_sec < min_window:
                # anchor to trailing edge if needed
                if duration >= min_window:
                    start_sec = max(0.0, duration - min_window)
                    end_sec = duration
                else:
                    start_sec = 0.0
                    end_sec = duration
        warnings.append(
            "Selection window shorter than minimum; expanded within clip bounds."
        )

    start_sec = max(0.0, min(start_sec, duration))
    end_sec = max(start_sec, min(end_sec, duration))

    applied_lead = start_sec
    applied_trail = max(0.0, duration - end_sec)

    epsilon = 1e-9
    start_frame = int(math.ceil(start_sec * fps_val - epsilon))
    end_frame = int(math.ceil(end_sec * fps_val - epsilon))

    start_frame = max(0, min(start_frame, num_frames))
    end_frame = max(start_frame, min(end_frame, num_frames))
    if end_frame == start_frame and start_frame < num_frames:
        end_frame = min(num_frames, start_frame + 1)

    return SelectionWindowSpec(
        start_frame=start_frame,
        end_frame=end_frame,
        start_seconds=start_sec,
        end_seconds=end_sec,
        applied_lead_seconds=applied_lead,
        applied_trail_seconds=applied_trail,
        duration_seconds=duration,
        warnings=tuple(warnings),
    )


def _selection_fingerprint(cfg: AnalysisConfig) -> str:
    relevant = {
        "frame_count_dark": cfg.frame_count_dark,
        "frame_count_bright": cfg.frame_count_bright,
        "frame_count_motion": cfg.frame_count_motion,
        "random_frames": cfg.random_frames,
        "random_seed": cfg.random_seed,
        "user_frames": [int(frame) for frame in cfg.user_frames],
        "use_quantiles": cfg.use_quantiles,
        "dark_quantile": cfg.dark_quantile,
        "bright_quantile": cfg.bright_quantile,
        "motion_use_absdiff": cfg.motion_use_absdiff,
        "motion_scenecut_quantile": cfg.motion_scenecut_quantile,
        "screen_separation_sec": cfg.screen_separation_sec,
        "motion_diff_radius": cfg.motion_diff_radius,
        "skip_head_seconds": cfg.skip_head_seconds,
        "skip_tail_seconds": cfg.skip_tail_seconds,
        "ignore_lead_seconds": cfg.ignore_lead_seconds,
        "ignore_trail_seconds": cfg.ignore_trail_seconds,
        "min_window_seconds": cfg.min_window_seconds,
    }
    payload = json.dumps(relevant, sort_keys=True).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _load_cached_metrics(
    info: FrameMetricsCacheInfo, cfg: AnalysisConfig
) -> Optional[CachedMetrics]:
    path = info.path
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if data.get("version") != 1:
        return None
    if data.get("config_hash") != _config_fingerprint(cfg):
        return None
    if data.get("files") != list(info.files):
        return None
    if data.get("analyzed_file") != info.analyzed_file:
        return None

    cached_group = str(data.get("release_group") or "").lower()
    if cached_group != (info.release_group or "").lower():
        return None

    if data.get("trim_start") != info.trim_start:
        return None
    if data.get("trim_end") != info.trim_end:
        return None

    fps = data.get("fps") or []
    if list(fps) != [info.fps_num, info.fps_den]:
        return None

    try:
        brightness = [(int(idx), float(val)) for idx, val in data.get("brightness", [])]
        motion = [(int(idx), float(val)) for idx, val in data.get("motion", [])]
    except (TypeError, ValueError):
        return None

    if not brightness:
        return None

    selection = data.get("selection") or {}
    selection_frames: Optional[List[int]] = None
    selection_hash: Optional[str] = None
    selection_categories: Optional[Dict[int, str]] = None
    if isinstance(selection, dict):
        frames_val = selection.get("frames")
        hash_val = selection.get("hash")
        cat_val = selection.get("categories")
        try:
            if isinstance(frames_val, list):
                selection_frames = [int(x) for x in frames_val]
            if isinstance(hash_val, str):
                selection_hash = hash_val
            if isinstance(cat_val, list):
                parsed: Dict[int, str] = {}
                for item in cat_val:
                    if not isinstance(item, list) or len(item) != 2:
                        continue
                    frame_raw, label_raw = item
                    parsed[int(frame_raw)] = str(label_raw)
                selection_categories = parsed or None
        except (TypeError, ValueError):
            selection_frames = None
            selection_hash = None
            selection_categories = None

    return CachedMetrics(brightness, motion, selection_frames, selection_hash, selection_categories)


def _save_cached_metrics(
    info: FrameMetricsCacheInfo,
    cfg: AnalysisConfig,
    brightness: Sequence[tuple[int, float]],
    motion: Sequence[tuple[int, float]],
    *,
    selection_hash: Optional[str] = None,
    selection_frames: Optional[Sequence[int]] = None,
    selection_categories: Optional[Dict[int, str]] = None,
) -> None:
    path = info.path
    payload = {
        "version": 1,
        "config_hash": _config_fingerprint(cfg),
        "files": list(info.files),
        "analyzed_file": info.analyzed_file,
        "release_group": info.release_group,
        "trim_start": info.trim_start,
        "trim_end": info.trim_end,
        "fps": [info.fps_num, info.fps_den],
        "brightness": [(int(idx), float(val)) for idx, val in brightness],
        "motion": [(int(idx), float(val)) for idx, val in motion],
    }
    if selection_hash is not None and selection_frames is not None:
        payload["selection"] = {
            "hash": selection_hash,
            "frames": [int(frame) for frame in selection_frames],
        }
        if selection_categories:
            payload["selection"]["categories"] = [
                [int(frame), str(selection_categories.get(int(frame), ""))]
                for frame in selection_frames
            ]

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        # Failing to persist cache data should not abort the pipeline.
        return

def dedupe(frames: Sequence[int], min_separation_sec: float, fps: float) -> List[int]:
    """Remove frames closer than *min_separation_sec* seconds apart (in order)."""

    min_gap = 0 if fps <= 0 else int(round(max(0.0, min_separation_sec) * fps))
    result: List[int] = []
    seen = set()
    for frame in frames:
        candidate = int(frame)
        if candidate in seen:
            continue
        if min_gap > 0:
            too_close = any(abs(candidate - kept) < min_gap for kept in result)
            if too_close:
                continue
        result.append(candidate)
        seen.add(candidate)
    return result


def _frame_rate(clip) -> float:
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    try:
        if isinstance(num, int) and isinstance(den, int) and den:
            return num / den
    except Exception:  # pragma: no cover - defensive
        pass
    return 24000 / 1001


def _clamp_frame(frame: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(total - 1, int(frame)))


def _ensure_even(value: int) -> int:
    return value if value % 2 == 0 else value - 1


def _collect_metrics_vapoursynth(
    clip,
    cfg: AnalysisConfig,
    indices: Sequence[int],
    progress: Callable[[int], None] | None = None,
) -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - handled by fallback
        raise RuntimeError("VapourSynth is unavailable") from exc

    if not isinstance(clip, vs.VideoNode):
        raise TypeError("Expected a VapourSynth clip")

    work = clip
    try:
        if cfg.downscale_height > 0 and work.height > cfg.downscale_height:
            target_h = _ensure_even(max(2, int(cfg.downscale_height)))
            aspect = work.width / work.height
            target_w = _ensure_even(max(2, int(round(target_h * aspect))))
            work = vs.core.resize.Spline36(work, width=target_w, height=target_h)

        # Convert to grayscale for consistent metrics
        target_format = vs.GRAY16
        work = vs.core.resize.Spline36(work, format=target_format)
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Failed to prepare analysis clip: {exc}") from exc

    stats_clip = work.std.PlaneStats()

    motion_stats = None
    if cfg.frame_count_motion > 0 and work.num_frames > 1:
        try:
            previous = work[:-1]
            current = work[1:]
            if cfg.motion_use_absdiff:
                diff_clip = vs.core.std.Expr([previous, current], "x y - abs")
            else:
                diff_clip = vs.core.std.MakeDiff(previous, current)
                diff_clip = vs.core.std.Prewitt(diff_clip)
            motion_stats = diff_clip.std.PlaneStats()
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to build motion metrics: {exc}") from exc

    brightness: List[tuple[int, float]] = []
    motion: List[tuple[int, float]] = []

    for idx in indices:
        if idx >= stats_clip.num_frames:
            break
        frame = stats_clip.get_frame(idx)
        luma = float(frame.props.get("PlaneStatsAverage", 0.0))
        brightness.append((idx, luma))
        del frame

        motion_value = 0.0
        if motion_stats is not None and idx > 0:
            diff_index = min(idx - 1, motion_stats.num_frames - 1)
            if diff_index >= 0:
                diff_frame = motion_stats.get_frame(diff_index)
                motion_value = float(diff_frame.props.get("PlaneStatsAverage", 0.0))
                del diff_frame
        motion.append((idx, motion_value))

        if progress is not None:
            progress(1)

    return brightness, motion


def _generate_metrics_fallback(
    indices: Sequence[int],
    cfg: AnalysisConfig,
    progress: Callable[[int], None] | None = None,
) -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
    brightness: List[tuple[int, float]] = []
    motion: List[tuple[int, float]] = []
    for idx in indices:
        brightness.append((idx, (math.sin(idx * 0.137) + 1.0) / 2.0))
        phase = 0.21 if cfg.motion_use_absdiff else 0.17
        motion.append((idx, (math.cos(idx * phase) + 1.0) / 2.0))
        if progress is not None:
            progress(1)
    return brightness, motion


def _smooth_motion(values: List[tuple[int, float]], radius: int) -> List[tuple[int, float]]:
    if radius <= 0 or not values:
        return values
    smoothed: List[tuple[int, float]] = []
    prefix = [0.0]
    for _, val in values:
        prefix.append(prefix[-1] + val)
    for i, (idx, _) in enumerate(values):
        start = max(0, i - radius)
        end = min(len(values) - 1, i + radius)
        total = prefix[end + 1] - prefix[start]
        count = (end - start) + 1
        smoothed.append((idx, total / max(1, count)))
    return smoothed


def select_frames(
    clip,
    cfg: AnalysisConfig,
    files: List[str],
    file_under_analysis: str,
    cache_info: Optional[FrameMetricsCacheInfo] = None,
    progress: Callable[[int], None] | None = None,
    *,
    frame_window: tuple[int, int] | None = None,
    return_metadata: bool = False,
) -> List[int] | Tuple[List[int], Dict[int, str]]:
    """Select frame indices for comparison using quantiles and motion heuristics."""

    num_frames = int(getattr(clip, "num_frames", 0))
    if num_frames <= 0:
        return []

    window_start = 0
    window_end = num_frames
    if frame_window is not None:
        try:
            candidate_start, candidate_end = frame_window
        except Exception:
            candidate_start, candidate_end = (0, num_frames)
        else:
            try:
                candidate_start = int(candidate_start)
            except (TypeError, ValueError):
                candidate_start = 0
            try:
                candidate_end = int(candidate_end)
            except (TypeError, ValueError):
                candidate_end = num_frames
        candidate_start = max(0, candidate_start)
        candidate_end = max(candidate_start, candidate_end)
        window_start = min(candidate_start, num_frames)
        window_end = min(candidate_end, num_frames)
        if window_end <= window_start:
            if num_frames > 0:
                logger.warning(
                    "Frame window collapsed for %s; falling back to full clip", file_under_analysis
                )
                window_start = 0
                window_end = num_frames

    if window_end <= window_start:
        return []

    window_span = window_end - window_start

    fps = _frame_rate(clip)
    rng = random.Random(cfg.random_seed)
    min_sep_frames = 0 if cfg.screen_separation_sec <= 0 else int(round(cfg.screen_separation_sec * fps))
    skip_head_cutoff = window_start
    if cfg.skip_head_seconds > 0 and fps > 0:
        skip_head_cutoff = min(
            window_end,
            window_start + max(0, int(round(cfg.skip_head_seconds * fps))),
        )
    skip_tail_limit = window_end
    if cfg.skip_tail_seconds > 0 and fps > 0:
        skip_tail_limit = max(
            window_start,
            window_end - max(0, int(round(cfg.skip_tail_seconds * fps))),
        )

    analysis_clip = clip
    if cfg.analyze_in_sdr:
        analysis_clip = vs_core.process_clip_for_screenshot(clip, file_under_analysis, cfg)

    step = max(1, int(cfg.step))
    indices = list(range(window_start, window_end, step))

    cached_metrics = _load_cached_metrics(cache_info, cfg) if cache_info is not None else None

    selection_hash = _selection_fingerprint(cfg)
    cached_selection: Optional[List[int]] = None
    cached_categories: Optional[Dict[int, str]] = None

    if cached_metrics is not None:
        brightness = [
            (idx, val)
            for idx, val in cached_metrics.brightness
            if window_start <= idx < window_end
        ]
        motion = [
            (idx, val)
            for idx, val in cached_metrics.motion
            if window_start <= idx < window_end
        ]
        if cached_metrics.selection_hash == selection_hash:
            if cached_metrics.selection_frames is not None:
                cached_selection = [
                    frame
                    for frame in cached_metrics.selection_frames
                    if window_start <= int(frame) < window_end
                ]
            else:
                cached_selection = None
            cached_categories = cached_metrics.selection_categories
        if progress is not None:
            progress(len(brightness))
    else:
        try:
            brightness, motion = _collect_metrics_vapoursynth(analysis_clip, cfg, indices, progress)
        except Exception:
            brightness, motion = _generate_metrics_fallback(indices, cfg, progress)

    if cached_selection is not None:
        frames_sorted = sorted(dict.fromkeys(int(frame) for frame in cached_selection))
        if return_metadata:
            categories = cached_categories or {}
            return frames_sorted, {frame: categories.get(frame, "Cached") for frame in frames_sorted}
        return frames_sorted

    brightness_values = [val for _, val in brightness]

    selected: List[int] = []
    selected_set = set()
    frame_categories: Dict[int, str] = {}

    def try_add(
        frame: int,
        enforce_gap: bool = True,
        gap_frames: Optional[int] = None,
        allow_edges: bool = False,
        category: Optional[str] = None,
    ) -> bool:
        frame_idx = _clamp_frame(frame, num_frames)
        if frame_idx in selected_set:
            return False
        if frame_idx < window_start or frame_idx >= window_end:
            return False
        if not allow_edges:
            if frame_idx < skip_head_cutoff:
                return False
            if frame_idx >= skip_tail_limit:
                return False
        effective_gap = min_sep_frames if gap_frames is None else max(0, int(gap_frames))
        if enforce_gap and effective_gap > 0:
            for existing in selected:
                if abs(existing - frame_idx) < effective_gap:
                    return False
        selected.append(frame_idx)
        selected_set.add(frame_idx)
        if category and frame_idx not in frame_categories:
            frame_categories[frame_idx] = category
        return True

    dropped_user_frames: List[int] = []
    for frame in cfg.user_frames:
        try:
            frame_int = int(frame)
        except (TypeError, ValueError):
            continue
        if window_start <= frame_int < window_end:
            try_add(frame_int, enforce_gap=False, allow_edges=True, category="User")
        else:
            dropped_user_frames.append(frame_int)

    if dropped_user_frames:
        preview = ", ".join(str(val) for val in dropped_user_frames[:5])
        if len(dropped_user_frames) > 5:
            preview += ", …"
        logger.warning(
            "Dropped %d pinned frame(s) outside trimmed window for %s: %s",
            len(dropped_user_frames),
            file_under_analysis,
            preview,
        )

    def pick_from_candidates(
        candidates: List[tuple[int, float]],
        count: int,
        mode: str,
        gap_seconds_override: Optional[float] = None,
    ) -> None:
        if count <= 0 or not candidates:
            return
        unique_indices: List[int] = []
        seen_local: set[int] = set()
        if mode == "motion":
            ordered = sorted(candidates, key=lambda item: item[1], reverse=True)
            for idx, _ in ordered:
                if idx in seen_local:
                    continue
                seen_local.add(idx)
                unique_indices.append(idx)
        elif mode in {"dark", "bright"}:
            for idx, _ in candidates:
                if idx in seen_local:
                    continue
                seen_local.add(idx)
                unique_indices.append(idx)
            rng.shuffle(unique_indices)
        else:
            raise ValueError(f"Unknown candidate mode: {mode}")
        separation = cfg.screen_separation_sec
        if gap_seconds_override is not None:
            separation = gap_seconds_override
        filtered_indices = dedupe(unique_indices, separation, fps)
        gap_frames = (
            None
            if gap_seconds_override is None
            else int(round(max(0.0, gap_seconds_override) * fps))
        )
        added = 0
        category_label = "Motion" if mode == "motion" else mode.capitalize()
        for frame_idx in filtered_indices:
            if try_add(frame_idx, enforce_gap=True, gap_frames=gap_frames, category=category_label):
                added += 1
            if added >= count:
                break

    dark_candidates: List[tuple[int, float]] = []
    if cfg.frame_count_dark > 0 and brightness_values:
        if cfg.use_quantiles:
            threshold = _quantile(brightness_values, cfg.dark_quantile)
            dark_candidates = [(idx, val) for idx, val in brightness if val <= threshold]
        else:
            dark_candidates = [(idx, val) for idx, val in brightness if 0.062746 <= val <= 0.38]
    pick_from_candidates(dark_candidates, cfg.frame_count_dark, mode="dark")

    bright_candidates: List[tuple[int, float]] = []
    if cfg.frame_count_bright > 0 and brightness_values:
        if cfg.use_quantiles:
            threshold = _quantile(brightness_values, cfg.bright_quantile)
            bright_candidates = [(idx, val) for idx, val in brightness if val >= threshold]
        else:
            bright_candidates = [(idx, val) for idx, val in brightness if 0.45 <= val <= 0.8]
    pick_from_candidates(bright_candidates, cfg.frame_count_bright, mode="bright")

    motion_candidates: List[tuple[int, float]] = []
    if cfg.frame_count_motion > 0 and motion:
        smoothed_motion = _smooth_motion(motion, max(0, int(cfg.motion_diff_radius)))
        filtered = smoothed_motion
        if cfg.motion_scenecut_quantile > 0:
            threshold = _quantile([val for _, val in smoothed_motion], cfg.motion_scenecut_quantile)
            filtered = [(idx, val) for idx, val in smoothed_motion if val <= threshold]
        motion_candidates = filtered
    motion_gap = cfg.screen_separation_sec / 4 if cfg.screen_separation_sec > 0 else 0
    pick_from_candidates(
        motion_candidates,
        cfg.frame_count_motion,
        mode="motion",
        gap_seconds_override=motion_gap,
    )

    random_count = max(0, int(cfg.random_frames))
    attempts = 0
    while random_count > 0 and attempts < random_count * 10 and window_span > 0:
        candidate = window_start + rng.randrange(window_span)
        if try_add(candidate, enforce_gap=True, category="Random"):
            random_count -= 1
        attempts += 1

    final_frames = sorted(selected)

    if cache_info is not None:
        try:
            _save_cached_metrics(
                cache_info,
                cfg,
                brightness,
                motion,
                selection_hash=selection_hash,
                selection_frames=final_frames,
                selection_categories=frame_categories,
            )
        except Exception:
            pass

    if return_metadata:
        return final_frames, {frame: frame_categories.get(frame, "Auto") for frame in final_frames}
    return final_frames
