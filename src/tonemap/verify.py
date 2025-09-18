"""Verification metrics for tonemapped output."""

from __future__ import annotations

import logging
import math
from typing import Any, Iterable

from .config import TMConfig

logger = logging.getLogger(__name__)

_LUMA_WEIGHTS = (0.2126, 0.7152, 0.0722)


def _require_numpy() -> Any:
    try:
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("NumPy is required for verification metrics") from exc
    return np


def _frame_to_array(frame: Any) -> Any:
    np = _require_numpy()
    fmt = getattr(frame, "format", None)
    if fmt is None:
        raise RuntimeError("Frame is missing format information")
    num_planes = getattr(fmt, "num_planes", 0)
    if num_planes <= 0:
        raise RuntimeError("Frame format is not planar")
    arrays = []
    for plane in range(num_planes):
        data = frame.get_read_array(plane)
        arrays.append(np.asarray(data, dtype=np.float32))
    stacked = np.stack(arrays, axis=-1)
    bits = getattr(fmt, "bits_per_sample", 8)
    scale = float((1 << bits) - 1)
    if scale <= 0:
        scale = 255.0
    return stacked / scale


def _estimate_luma(rgb_array: Any) -> float:
    np = _require_numpy()
    weights = np.array(_LUMA_WEIGHTS, dtype=rgb_array.dtype)
    luma = rgb_array @ weights
    return float(np.mean(luma))


def _metric_absdiff(ref: Any, test: Any) -> dict[str, float]:
    np = _require_numpy()
    diff = np.abs(ref - test)
    return {"avg": float(np.mean(diff)), "max": float(np.max(diff))}


def _metric_psnr(ref: Any, test: Any) -> dict[str, float]:
    np = _require_numpy()
    mse = float(np.mean((ref - test) ** 2))
    if mse <= 0:
        return {"psnr": float("inf")}
    return {"psnr": 10.0 * math.log10(1.0 / mse)}


def _metric_ssim(ref: Any, test: Any) -> dict[str, float]:
    np = _require_numpy()
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    mu_x = float(np.mean(ref))
    mu_y = float(np.mean(test))
    sigma_x = float(np.var(ref))
    sigma_y = float(np.var(test))
    sigma_xy = float(np.mean((ref - mu_x) * (test - mu_y)))
    numerator = (2 * mu_x * mu_y + c1) * (2 * sigma_xy + c2)
    denominator = (mu_x ** 2 + mu_y ** 2 + c1) * (sigma_x + sigma_y + c2)
    if denominator == 0:
        return {"ssim": 1.0}
    return {"ssim": numerator / denominator}


def _metric_deltae(ref: Any, test: Any) -> dict[str, float]:
    try:
        import colour  # type: ignore
        from colour import RGB_COLOURSPACES, XYZ_to_Lab  # type: ignore
        from colour.models.rgb import RGB_to_XYZ  # type: ignore
        from colour.algebra import euclidean_distance  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("colour-science is required for deltaE verification") from exc
    np = _require_numpy()
    space = RGB_COLOURSPACES.get("ITU-R BT.709")
    if space is None:
        raise RuntimeError("colour-science missing BT.709 space definition")
    ref_xyz = RGB_to_XYZ(ref, space.whitepoint, space.whitepoint, space.matrix_RGB_to_XYZ)
    test_xyz = RGB_to_XYZ(test, space.whitepoint, space.whitepoint, space.matrix_RGB_to_XYZ)
    ref_lab = XYZ_to_Lab(ref_xyz, space.whitepoint)
    test_lab = XYZ_to_Lab(test_xyz, space.whitepoint)
    delta = euclidean_distance(ref_lab.reshape(-1, 3), test_lab.reshape(-1, 3))
    return {"deltae": float(np.mean(delta))}


_METRIC_MAP = {
    "abs": _metric_absdiff,
    "psnr": _metric_psnr,
    "ssim": _metric_ssim,
    "deltae": _metric_deltae,
}


def _auto_pick_frame(clip: Any, cfg: TMConfig, baseline_clip: Any) -> int:
    np = _require_numpy()
    start = max(0, int(cfg.verify_start_frame))
    step = max(1, int(cfg.verify_search_step))
    limit = max(start, start + int(cfg.verify_search_max))
    threshold = float(cfg.verify_luma_thresh)
    for frame_idx in range(start, limit, step):
        try:
            frame = baseline_clip.get_frame(frame_idx)
        except Exception:
            break
        try:
            luma = _estimate_luma(_frame_to_array(frame))
        except Exception:
            continue
        if luma >= threshold:
            return frame_idx
    return start


def run_verification(clip: Any, tonemapped: Any, fallback: Any, cfg: TMConfig) -> dict[str, float] | None:
    if not cfg.verify:
        return None
    try:
        _require_numpy()
    except RuntimeError as exc:
        logger.warning("tonemap verification skipped: %s", exc)
        return None

    target_frame = cfg.verify_frame
    if target_frame is None and cfg.verify_auto_search:
        target_frame = _auto_pick_frame(clip, cfg, fallback)
    if target_frame is None:
        target_frame = cfg.verify_start_frame

    try:
        ref_frame = fallback.get_frame(int(target_frame))
        tm_frame = tonemapped.get_frame(int(target_frame))
    except Exception as exc:
        logger.warning("tonemap verification failed to fetch frame %s: %s", target_frame, exc)
        return None

    try:
        ref_arr = _frame_to_array(ref_frame)
        tm_arr = _frame_to_array(tm_frame)
    except Exception as exc:
        logger.warning("tonemap verification failed to convert frame %s: %s", target_frame, exc)
        return None

    metric_key = cfg.verify_metric
    metric_fn = _METRIC_MAP.get(metric_key)
    if metric_fn is None:
        logger.warning("tonemap verification metric '%s' unsupported", metric_key)
        return None

    try:
        results = metric_fn(ref_arr, tm_arr)
    except RuntimeError as exc:
        logger.warning("tonemap verification metric '%s' unavailable: %s", metric_key, exc)
        return None

    logger.info("tonemap verify metric=%s frame=%s results=%s", metric_key, target_frame, results)
    return results
