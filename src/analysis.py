from __future__ import annotations

"""Frame analysis and selection utilities."""

import math
import random
from typing import List, Sequence, Tuple

from .datatypes import AnalysisConfig
from . import vs_core


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


def _collect_metrics_vapoursynth(clip, cfg: AnalysisConfig, indices: Sequence[int]) -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
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

    return brightness, motion


def _generate_metrics_fallback(indices: Sequence[int], cfg: AnalysisConfig) -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
    brightness: List[tuple[int, float]] = []
    motion: List[tuple[int, float]] = []
    for idx in indices:
        brightness.append((idx, (math.sin(idx * 0.137) + 1.0) / 2.0))
        phase = 0.21 if cfg.motion_use_absdiff else 0.17
        motion.append((idx, (math.cos(idx * phase) + 1.0) / 2.0))
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


def select_frames(clip, cfg: AnalysisConfig, files: List[str], file_under_analysis: str) -> List[int]:
    """Select frame indices for comparison using quantiles and motion heuristics."""

    num_frames = int(getattr(clip, "num_frames", 0))
    if num_frames <= 0:
        return []

    fps = _frame_rate(clip)
    rng = random.Random(cfg.random_seed)
    min_sep_frames = 0 if cfg.screen_separation_sec <= 0 else int(round(cfg.screen_separation_sec * fps))

    analysis_clip = clip
    if cfg.analyze_in_sdr:
        analysis_clip = vs_core.process_clip_for_screenshot(clip, file_under_analysis, cfg)

    step = max(1, int(cfg.step))
    indices = list(range(0, num_frames, step))

    try:
        brightness, motion = _collect_metrics_vapoursynth(analysis_clip, cfg, indices)
    except Exception:
        brightness, motion = _generate_metrics_fallback(indices, cfg)

    brightness_values = [val for _, val in brightness]

    selected: List[int] = []
    selected_set = set()

    def try_add(frame: int, enforce_gap: bool = True) -> bool:
        frame_idx = _clamp_frame(frame, num_frames)
        if frame_idx in selected_set:
            return False
        if enforce_gap and min_sep_frames > 0:
            for existing in selected:
                if abs(existing - frame_idx) < min_sep_frames:
                    return False
        selected.append(frame_idx)
        selected_set.add(frame_idx)
        return True

    for frame in cfg.user_frames:
        try_add(frame, enforce_gap=False)

    def pick_from_candidates(candidates: List[tuple[int, float]], count: int, reverse: bool = False) -> None:
        if count <= 0 or not candidates:
            return
        ordered = sorted(candidates, key=lambda item: item[1], reverse=reverse)
        unique_indices = []
        seen_local = set()
        for idx, _ in ordered:
            if idx in seen_local:
                continue
            seen_local.add(idx)
            unique_indices.append(idx)
        filtered_indices = dedupe(unique_indices, cfg.screen_separation_sec, fps)
        added = 0
        for frame_idx in filtered_indices:
            if try_add(frame_idx, enforce_gap=True):
                added += 1
            if added >= count:
                break

    dark_candidates: List[tuple[int, float]] = []
    if cfg.frame_count_dark > 0:
        if cfg.use_quantiles:
            threshold = _quantile(brightness_values, cfg.dark_quantile)
            dark_candidates = [(idx, val) for idx, val in brightness if val <= threshold]
        else:
            dark_candidates = [(idx, val) for idx, val in brightness if 0.062746 <= val <= 0.38]
    pick_from_candidates(dark_candidates, cfg.frame_count_dark, reverse=False)

    bright_candidates: List[tuple[int, float]] = []
    if cfg.frame_count_bright > 0:
        if cfg.use_quantiles:
            threshold = _quantile(brightness_values, cfg.bright_quantile)
            bright_candidates = [(idx, val) for idx, val in brightness if val >= threshold]
        else:
            bright_candidates = [(idx, val) for idx, val in brightness if 0.45 <= val <= 0.8]
    pick_from_candidates(bright_candidates, cfg.frame_count_bright, reverse=True)

    motion_candidates: List[tuple[int, float]] = []
    if cfg.frame_count_motion > 0:
        smoothed_motion = _smooth_motion(motion, max(0, int(cfg.motion_diff_radius)))
        filtered = smoothed_motion
        if cfg.motion_scenecut_quantile > 0:
            threshold = _quantile([val for _, val in smoothed_motion], cfg.motion_scenecut_quantile)
            filtered = [(idx, val) for idx, val in smoothed_motion if val <= threshold]
        motion_candidates = filtered
    pick_from_candidates(motion_candidates, cfg.frame_count_motion, reverse=True)

    random_count = max(0, int(cfg.random_frames))
    attempts = 0
    while random_count > 0 and attempts < random_count * 10 and num_frames > 0:
        candidate = rng.randrange(num_frames)
        if try_add(candidate, enforce_gap=True):
            random_count -= 1
        attempts += 1

    ordered = sorted(selected)
    if min_sep_frames > 0:
        ordered = dedupe(ordered, cfg.screen_separation_sec, fps)
    return ordered
