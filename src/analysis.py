"""Frame analysis and selection utilities."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import math
import numbers
import random
import time
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, TypedDict, cast

from . import vs_core
from .datatypes import AnalysisConfig, ColorConfig

logger = logging.getLogger(__name__)

_SELECTION_METADATA_VERSION = "1"
_SELECTION_SOURCE_ID = "select_frames.v1"
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


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
    """
    Stored brightness and motion metrics captured from previous analyses.

    Attributes:
        brightness (List[tuple[int, float]]): Frame index and brightness pairs.
        motion (List[tuple[int, float]]): Frame index and motion score pairs.
        selection_frames (Optional[List[int]]): Frame indices selected during the cached run.
        selection_hash (Optional[str]): Hash of the selection inputs that produced ``selection_frames``.
        selection_categories (Optional[Dict[int, str]]): Optional per-frame category labels.
    """
    brightness: List[tuple[int, float]]
    motion: List[tuple[int, float]]
    selection_frames: Optional[List[int]]
    selection_hash: Optional[str]
    selection_categories: Optional[Dict[int, str]]
    selection_details: Optional[Dict[int, "SelectionDetail"]]


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


@dataclass
class SelectionDetail:
    """Captured metadata describing how and why a frame was selected."""

    frame_index: int
    label: str
    score: Optional[float]
    source: str
    timecode: Optional[str]
    clip_role: Optional[str] = None
    notes: Optional[str] = None


class _SerializedSelectionDetail(TypedDict, total=False):
    frame_index: int | float | str
    type: str
    score: float | int | str | None
    source: str | None
    ts_tc: str | int | float | None
    clip_role: str | None
    notes: str | int | float | None


def _coerce_frame_index(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _coerce_optional_float(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        if not math.isfinite(parsed):
            return None
        return parsed
    return None


def _coerce_optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _coerce_str_dict(value: object) -> Dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result: Dict[str, object] = {}
    for key, entry in value.items():
        if not isinstance(key, str):
            return None
        result[key] = entry
    return result


def _coerce_int_list(value: object) -> List[int] | None:
    if not isinstance(value, list):
        return None
    result: List[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            return None
    return result


def _coerce_selection_categories(value: object) -> Optional[Dict[int, str]]:
    if not isinstance(value, list):
        return None
    parsed: Dict[int, str] = {}
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            continue
        frame_raw, label_raw = item
        try:
            frame_idx = int(frame_raw)
        except (TypeError, ValueError):
            continue
        parsed[frame_idx] = str(label_raw)
    return parsed or None


def _coerce_metric_series(value: object) -> List[tuple[int, float]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("metrics payload must be a list")
    result: List[tuple[int, float]] = []
    for entry in value:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise TypeError("invalid metrics entry")
        idx_obj, val_obj = entry
        result.append((int(idx_obj), float(val_obj)))
    return result


def _now_utc_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime(_TIME_FORMAT)


def _frame_to_timecode(frame_idx: int, fps: float) -> Optional[str]:
    if fps <= 0:
        return None
    seconds = frame_idx / fps
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds - hours * 3600 - minutes * 60
    milliseconds = int(round(remainder * 1000))
    if milliseconds >= 1000:
        milliseconds -= 1000
        remainder = 0.0
        minutes += 1
    seconds_whole = int(remainder)
    milliseconds = int(milliseconds)
    return f"{hours:02d}:{minutes:02d}:{seconds_whole:02d}.{milliseconds:03d}"


def _atomic_write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_handle = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
        ) as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_handle = handle.name
        os.replace(temp_handle, path)
    finally:
        if temp_handle and os.path.exists(temp_handle):
            try:
                os.remove(temp_handle)
            except OSError:
                pass


def _compute_file_sha1(path: Path, *, chunk_size: int = 1024 * 1024) -> Optional[str]:
    try:
        with path.open("rb") as handle:
            digest = hashlib.sha1()
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _serialize_selection_details(details: Mapping[int, SelectionDetail]) -> List[_SerializedSelectionDetail]:
    records: List[_SerializedSelectionDetail] = []
    for frame_idx in sorted(details.keys()):
        detail = details[frame_idx]
        record: _SerializedSelectionDetail = {
            "frame_index": int(detail.frame_index),
            "type": detail.label,
            "score": None if detail.score is None else float(detail.score),
            "source": detail.source,
            "ts_tc": detail.timecode,
            "clip_role": detail.clip_role,
            "notes": detail.notes,
        }
        records.append(record)
    return records


def _deserialize_selection_details(value: object) -> Dict[int, SelectionDetail]:
    if not isinstance(value, list):
        return {}
    results: Dict[int, SelectionDetail] = {}
    for entry in value:
        if not isinstance(entry, dict):
            continue
        record = cast(_SerializedSelectionDetail, entry)
        frame_idx = _coerce_frame_index(record.get("frame_index"))
        if frame_idx is None:
            continue
        label_obj: object = record.get("type")
        label = str(label_obj).strip() if isinstance(label_obj, str) and label_obj.strip() else "Auto"
        score = _coerce_optional_float(record.get("score"))
        source_obj: object = record.get("source")
        source = (
            str(source_obj).strip()
            if isinstance(source_obj, str) and source_obj.strip()
            else _SELECTION_SOURCE_ID
        )
        timecode = _coerce_optional_str(record.get("ts_tc"))
        clip_role = _coerce_optional_str(record.get("clip_role"))
        notes = _coerce_optional_str(record.get("notes"))
        results[frame_idx] = SelectionDetail(
            frame_index=frame_idx,
            label=label,
            score=score,
            source=source,
            timecode=timecode,
            clip_role=clip_role,
            notes=notes,
        )
    return results


def _format_selection_annotation(detail: SelectionDetail) -> str:
    parts = [f"sel={detail.label}"]
    if detail.score is not None:
        parts.append(f"score={detail.score:.4f}")
    if detail.source:
        parts.append(f"src={detail.source}")
    if detail.timecode:
        parts.append(f"tc={detail.timecode}")
    if detail.notes:
        parts.append(f"note={detail.notes}")
    return ";".join(parts)


def selection_details_to_json(details: Mapping[int, SelectionDetail]) -> Dict[str, Dict[str, object]]:
    """Return JSON-friendly mapping for selection details."""

    serialised: Dict[str, Dict[str, object]] = {}
    for frame, detail in details.items():
        serialised[str(frame)] = {
            "frame_index": int(detail.frame_index),
            "type": detail.label,
            "score": detail.score,
            "source": detail.source,
            "timecode": detail.timecode,
            "clip_role": detail.clip_role,
            "notes": detail.notes,
        }
    return serialised


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


def _coerce_seconds(value: object, label: str) -> float:
    """
    Convert ``value`` into a floating-point seconds value with validation.

    Parameters:
        value (object): Raw value to convert; accepts numbers or numeric strings.
        label (str): Configuration label used when raising validation errors.

    Returns:
        float: The coerced seconds value.

    Raises:
        TypeError: If ``value`` cannot be interpreted as a number.
    """
    if isinstance(value, numbers.Real):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            pass
    raise TypeError(f"{label} must be numeric (got {type(value).__name__})")


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
    lead = max(0.0, _coerce_seconds(ignore_lead_seconds, "analysis.ignore_lead_seconds"))
    trail = max(0.0, _coerce_seconds(ignore_trail_seconds, "analysis.ignore_trail_seconds"))
    min_window = max(0.0, _coerce_seconds(min_window_seconds, "analysis.min_window_seconds"))

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
    """
    Return a hash of configuration fields relevant to frame selection.

    Parameters:
        cfg (AnalysisConfig): Analysis configuration whose selection-related fields should be fingerprinted.

    Returns:
        str: Hex digest capturing the selection-relevant configuration values.
    """
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


def selection_hash_for_config(cfg: AnalysisConfig) -> str:
    """Public helper exposing the stable selection fingerprint."""

    return _selection_fingerprint(cfg)


def _load_cached_metrics(
    info: FrameMetricsCacheInfo, cfg: AnalysisConfig
) -> Optional[CachedMetrics]:
    """
    Load previously computed metrics when cache metadata still matches.

    Parameters:
        info (FrameMetricsCacheInfo): Cache metadata describing the expected file and clip characteristics.
        cfg (AnalysisConfig): Current analysis configuration whose fingerprint must match the cached payload.

    Returns:
        Optional[CachedMetrics]: Cached metrics if the persisted payload is valid; otherwise ``None``.
    """
    path = info.path
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None

    try:
        data_raw = json.loads(raw)
    except json.JSONDecodeError:
        return None

    data = _coerce_str_dict(data_raw)
    if data is None:
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

    fps_obj = data.get("fps")
    fps_values: List[int] = []
    if isinstance(fps_obj, (list, tuple)):
        try:
            fps_values = [int(part) for part in fps_obj]
        except (TypeError, ValueError):
            return None
    if fps_values != [info.fps_num, info.fps_den]:
        return None

    try:
        brightness = _coerce_metric_series(data.get("brightness"))
        motion = _coerce_metric_series(data.get("motion"))
    except (TypeError, ValueError):
        return None

    if not brightness:
        return None

    selection = data.get("selection") or {}
    selection_frames: Optional[List[int]] = None
    selection_hash: Optional[str] = None
    selection_categories: Optional[Dict[int, str]] = None
    selection_details: Optional[Dict[int, SelectionDetail]] = None
    selection_map = _coerce_str_dict(selection)
    if selection_map is not None:
        frames_val = _coerce_int_list(selection_map.get("frames"))
        if frames_val is not None:
            selection_frames = frames_val
        hash_val = selection_map.get("hash")
        if isinstance(hash_val, str):
            selection_hash = hash_val
        categories_val = _coerce_selection_categories(selection_map.get("categories"))
        if categories_val is not None:
            selection_categories = categories_val
        details_val = selection_map.get("details")
        if details_val is not None:
            parsed_details = _deserialize_selection_details(details_val)
            if parsed_details:
                selection_details = parsed_details

    if selection_details is None:
        annotations_map = _coerce_str_dict(data.get("selection_annotations"))
        if annotations_map:
            parsed_ann: Dict[int, SelectionDetail] = {}
            for key, value in annotations_map.items():
                try:
                    frame_idx = int(key)
                except (TypeError, ValueError):
                    continue
                label: Optional[str] = None
                score: Optional[float] = None
                source = _SELECTION_SOURCE_ID
                timecode: Optional[str] = None
                notes: Optional[str] = None
                if isinstance(value, str):
                    label = value.split(";")[0].split("=", 1)[-1] if "=" in value else value
                else:
                    value_dict = _coerce_str_dict(value)
                    if value_dict is None:
                        continue
                    label_obj = value_dict.get("type") or value_dict.get("label")
                    if isinstance(label_obj, str):
                        label = label_obj
                    score = _coerce_optional_float(value_dict.get("score"))
                    source_obj = value_dict.get("source")
                    if isinstance(source_obj, str) and source_obj.strip():
                        source = source_obj.strip()
                    timecode = _coerce_optional_str(value_dict.get("ts_tc"))
                    notes = _coerce_optional_str(value_dict.get("notes"))
                if not label:
                    label = "Auto"
                parsed_ann[frame_idx] = SelectionDetail(
                    frame_index=frame_idx,
                    label=label,
                    score=score,
                    source=source,
                    timecode=timecode,
                    notes=notes,
                )
            if parsed_ann:
                selection_details = parsed_ann

    return CachedMetrics(
        brightness,
        motion,
        selection_frames,
        selection_hash,
        selection_categories,
        selection_details,
    )


def _selection_sidecar_path(info: FrameMetricsCacheInfo) -> Path:
    """Return the filesystem location for the lightweight selection sidecar."""

    return info.path.parent / "generated.selection.v1.json"


def _infer_clip_role(index: int, name: str, analyzed_file: str, total: int) -> str:
    lowered = name.lower()
    analyzed_lower = analyzed_file.lower()
    if lowered == analyzed_lower:
        return "analyze"
    if index == 0:
        return "ref"
    if index == 1:
        return "tgt"
    return f"aux{index}"


def _build_clip_inputs(info: FrameMetricsCacheInfo) -> List[Dict[str, object]]:
    root = info.path.parent
    entries: List[Dict[str, object]] = []
    total = len(info.files)
    for idx, file_name in enumerate(info.files):
        candidate = Path(file_name)
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        try:
            stat_result = candidate.stat()
            size = int(stat_result.st_size)
            mtime = _dt.datetime.fromtimestamp(stat_result.st_mtime, tz=_dt.timezone.utc).isoformat()
        except OSError:
            size = None
            mtime = None
        sha1 = _compute_file_sha1(candidate)
        entries.append(
            {
                "role": _infer_clip_role(idx, file_name, info.analyzed_file, total),
                "path": str(candidate),
                "name": file_name,
                "size": size,
                "mtime": mtime,
                "sha1": sha1,
            }
        )
    return entries


def _selection_cache_key(
    *,
    clip_inputs: Sequence[Mapping[str, object]],
    cfg: AnalysisConfig,
    selection_source: str,
) -> str:
    payload = {
        "clips": clip_inputs,
        "config_hash": _config_fingerprint(cfg),
        "selection_source": selection_source,
    }
    canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"



def _selection_payload_from_inputs(
    clip_inputs: Sequence[Mapping[str, object]],
    cfg: AnalysisConfig,
    selection_hash: str,
    selection_frames: Sequence[int],
    selection_details: Mapping[int, SelectionDetail] | None,
    analyzed_file: str,
) -> Dict[str, object]:
    cache_key = _selection_cache_key(
        clip_inputs=clip_inputs,
        cfg=cfg,
        selection_source=_SELECTION_SOURCE_ID,
    )
    detail_records = _serialize_selection_details(selection_details or {})
    return {
        "version": _SELECTION_METADATA_VERSION,
        "created_utc": _now_utc_iso(),
        "cache_key": cache_key,
        "analyzed_file": analyzed_file,
        "selection_hash": selection_hash,
        "selection_source": _SELECTION_SOURCE_ID,
        "inputs": {
            "clips": list(clip_inputs),
            "config_fingerprint": _config_fingerprint(cfg),
        },
        "selections": detail_records,
        "frames": [int(frame) for frame in selection_frames],
    }


def _build_selection_sidecar_payload(
    info: FrameMetricsCacheInfo,
    cfg: AnalysisConfig,
    selection_hash: str,
    selection_frames: Sequence[int],
    selection_details: Mapping[int, SelectionDetail] | None,
) -> Dict[str, object]:
    clip_inputs = _build_clip_inputs(info)
    return _selection_payload_from_inputs(
        clip_inputs,
        cfg,
        selection_hash,
        selection_frames,
        selection_details,
        info.analyzed_file,
    )


def _save_selection_sidecar(
    info: FrameMetricsCacheInfo,
    cfg: AnalysisConfig,
    selection_hash: Optional[str],
    selection_frames: Optional[Sequence[int]],
    selection_details: Mapping[int, SelectionDetail] | None = None,
) -> None:
    """Persist rich selection metadata for fast reloads."""

    if selection_hash is None or selection_frames is None:
        return

    payload = _build_selection_sidecar_payload(
        info,
        cfg,
        selection_hash,
        selection_frames,
        selection_details,
    )

    target = _selection_sidecar_path(info)
    try:
        _atomic_write_json(target, payload)
    except OSError:
        return



def build_clip_inputs_from_paths(
    analyzed_file: str, clip_paths: Sequence[Path]
) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    total = len(clip_paths)
    for idx, clip_path in enumerate(clip_paths):
        resolved = clip_path.resolve()
        try:
            stat_result = resolved.stat()
            size = int(stat_result.st_size)
            mtime = _dt.datetime.fromtimestamp(stat_result.st_mtime, tz=_dt.timezone.utc).isoformat()
        except OSError:
            size = None
            mtime = None
        sha1 = _compute_file_sha1(resolved)
        entries.append(
            {
                "role": _infer_clip_role(idx, resolved.name, analyzed_file, total),
                "path": str(resolved),
                "name": resolved.name,
                "size": size,
                "mtime": mtime,
                "sha1": sha1,
            }
        )
    return entries



def export_selection_metadata(
    target_path: Path,
    *,
    analyzed_file: str,
    clip_paths: Sequence[Path],
    cfg: AnalysisConfig,
    selection_hash: str,
    selection_frames: Sequence[int],
    selection_details: Mapping[int, SelectionDetail],
) -> None:
    clip_inputs = build_clip_inputs_from_paths(analyzed_file, clip_paths)
    payload = _selection_payload_from_inputs(
        clip_inputs,
        cfg,
        selection_hash,
        selection_frames,
        selection_details,
        analyzed_file,
    )
    _atomic_write_json(target_path, payload)


def write_selection_cache_file(
    target_path: Path,
    *,
    analyzed_file: str,
    clip_paths: Sequence[Path],
    cfg: AnalysisConfig,
    selection_hash: str,
    selection_frames: Sequence[int],
    selection_details: Mapping[int, SelectionDetail],
    selection_categories: Mapping[int, str],
) -> None:
    """Write a generated.compframes-style JSON payload with selection annotations only."""

    clip_inputs = build_clip_inputs_from_paths(analyzed_file, clip_paths)
    payload = _selection_payload_from_inputs(
        clip_inputs,
        cfg,
        selection_hash,
        selection_frames,
        selection_details,
        analyzed_file,
    )
    normalized_frames = [int(frame) for frame in selection_frames]

    def _detail_or_default(frame: int) -> SelectionDetail:
        existing = selection_details.get(frame)
        if existing is not None:
            return existing
        return SelectionDetail(
            frame_index=frame,
            label="Auto",
            score=None,
            source=_SELECTION_SOURCE_ID,
            timecode=None,
            clip_role=None,
            notes=None,
        )

    categories = [
        [frame, str(selection_categories.get(frame, _detail_or_default(frame).label))]
        for frame in normalized_frames
    ]
    selection_section_obj = payload.setdefault("selection", {})
    if not isinstance(selection_section_obj, dict):
        selection_section_obj = {}
        payload["selection"] = selection_section_obj
    selection_section = cast(Dict[str, object], selection_section_obj)
    selection_section["frames"] = normalized_frames
    selection_section["categories"] = categories
    selection_section["annotations"] = {
        str(frame): _format_selection_annotation(_detail_or_default(frame))
        for frame in normalized_frames
    }
    payload.setdefault("brightness", [])
    payload.setdefault("motion", [])
    _atomic_write_json(target_path, payload)


def _load_selection_sidecar(
    info: Optional[FrameMetricsCacheInfo], cfg: AnalysisConfig, selection_hash: Optional[str]
) -> Optional[Tuple[List[int], Dict[int, SelectionDetail]]]:
    """Load previously stored selection frames if the sidecar matches current state."""

    if info is None or not selection_hash:
        return None

    path = _selection_sidecar_path(info)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None

    try:
        data_raw = json.loads(raw)
    except json.JSONDecodeError:
        return None

    data = _coerce_str_dict(data_raw)
    if data is None:
        return None

    version = str(data.get("version") or "")
    if version not in {"1", _SELECTION_METADATA_VERSION}:
        return None

    inputs_section = _coerce_str_dict(data.get("inputs")) or {}
    clip_inputs = inputs_section.get("clips")
    recomputed_inputs = _build_clip_inputs(info)
    if clip_inputs is not None:
        clip_names: List[object] = []
        if isinstance(clip_inputs, list):
            for entry in clip_inputs:
                entry_map = _coerce_str_dict(entry)
                if entry_map is None:
                    continue
                clip_names.append(entry_map.get("name"))
        if clip_names != list(info.files):
            return None

    cache_key = data.get("cache_key")
    expected_cache_key = _selection_cache_key(
        clip_inputs=recomputed_inputs,
        cfg=cfg,
        selection_source=str(data.get("selection_source") or _SELECTION_SOURCE_ID),
    )
    if cache_key and cache_key != expected_cache_key:
        return None

    if data.get("analyzed_file") != info.analyzed_file:
        return None

    if data.get("selection_hash") != selection_hash:
        return None

    frames_raw = data.get("frames")
    if not isinstance(frames_raw, list):
        return None

    try:
        normalized_frames = [int(value) for value in frames_raw]
    except (TypeError, ValueError):
        return None

    detail_records = _deserialize_selection_details(data.get("selections"))
    return normalized_frames, detail_records


def _save_cached_metrics(
    info: FrameMetricsCacheInfo,
    cfg: AnalysisConfig,
    brightness: Sequence[tuple[int, float]],
    motion: Sequence[tuple[int, float]],
    *,
    selection_hash: Optional[str] = None,
    selection_frames: Optional[Sequence[int]] = None,
    selection_categories: Optional[Dict[int, str]] = None,
    selection_details: Optional[Mapping[int, SelectionDetail]] = None,
) -> None:
    """
    Persist metrics and optional frame selections for reuse across runs.

    Parameters:
        info (FrameMetricsCacheInfo): Cache metadata describing the target persistence location.
        cfg (AnalysisConfig): Analysis configuration whose fingerprint will be stored alongside the metrics.
        brightness (Sequence[tuple[int, float]]): Per-frame brightness measurements.
        motion (Sequence[tuple[int, float]]): Per-frame motion measurements.
        selection_hash (Optional[str]): Fingerprint describing the selection parameters that produced ``selection_frames``.
        selection_frames (Optional[Sequence[int]]): Optional frame indices chosen for screenshot generation.
        selection_categories (Optional[Dict[int, str]]): Optional per-frame category labels to persist.
    """
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
    annotations: Dict[str, str] = {}
    if selection_hash is not None and selection_frames is not None:
        serialized_details = _serialize_selection_details(selection_details or {})
        selection_details_map = selection_details or {}

        payload["selection"] = {
            "hash": selection_hash,
            "frames": [int(frame) for frame in selection_frames],
        }

        if selection_categories is not None:
            categories_payload: List[list[object]] = []
            for frame in selection_frames:
                frame_idx = int(frame)
                category_value = selection_categories.get(frame_idx, "")
                categories_payload.append([frame_idx, str(category_value)])
            if categories_payload:
                payload["selection"]["categories"] = categories_payload

        if serialized_details:
            payload["selection"]["details"] = serialized_details

            for record in serialized_details:
                frame_idx = _coerce_frame_index(record.get("frame_index"))
                if frame_idx is None or frame_idx < 0:
                    continue

                detail = selection_details_map.get(frame_idx)
                if detail is None:
                    label_obj: object = record.get("type")
                    source_obj: object = record.get("source")
                    detail = SelectionDetail(
                        frame_index=frame_idx,
                        label=str(label_obj).strip() if isinstance(label_obj, str) and label_obj.strip() else "Auto",
                        score=_coerce_optional_float(record.get("score")),
                        source=str(source_obj).strip() if isinstance(source_obj, str) and source_obj.strip() else _SELECTION_SOURCE_ID,
                        timecode=_coerce_optional_str(record.get("ts_tc")),
                        clip_role=_coerce_optional_str(record.get("clip_role")),
                        notes=_coerce_optional_str(record.get("notes")),
                    )
                annotations[str(frame_idx)] = _format_selection_annotation(detail)

        if annotations:
            payload["selection_annotations"] = annotations

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        # Failing to persist cache data should not abort the pipeline.
        return

    _save_selection_sidecar(info, cfg, selection_hash, selection_frames, selection_details or {})

def dedupe(frames: Sequence[int], min_separation_sec: float, fps: float) -> List[int]:
    """
    Remove frames closer than ``min_separation_sec`` seconds apart while preserving order.

    Parameters:
        frames (Sequence[int]): Candidate frame indices.
        min_separation_sec (float): Minimum allowed spacing between kept frames, expressed in seconds.
        fps (float): Clip frame rate used to convert seconds to frame distances.

    Returns:
        List[int]: Filtered frame indices respecting the minimum separation constraint.
    """

    min_gap = 0 if fps <= 0 else int(round(max(0.0, min_separation_sec) * fps))
    result: List[int] = []
    seen: set[int] = set()
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
    """
    Return the best-effort floating-point frame rate for ``clip``.

    Parameters:
        clip: VapourSynth-like clip exposing ``fps_num``/``fps_den`` attributes.

    Returns:
        float: Floating-point frames-per-second value, or ``0.0`` if unavailable.
    """
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    try:
        if isinstance(num, int) and isinstance(den, int) and den:
            return num / den
    except Exception:  # pragma: no cover - defensive
        pass
    return 24000 / 1001


def _clamp_frame(frame: int, total: int) -> int:
    """
    Clamp ``frame`` to the valid index range for a clip with ``total`` frames.

    Parameters:
        frame (int): Candidate frame index.
        total (int): Total number of frames available.

    Returns:
        int: Frame index restricted to ``[0, total - 1]`` (or ``0`` when ``total`` is non-positive).
    """
    if total <= 0:
        return 0
    return max(0, min(total - 1, int(frame)))


def _ensure_even(value: int) -> int:
    """
    Return ``value`` unchanged when even; otherwise subtract one to make it even.

    Parameters:
        value (int): Integer to normalise.

    Returns:
        int: An even integer not greater than ``value``.
    """
    return value if value % 2 == 0 else value - 1


class _ProgressCoalescer:
    """Batch frequent progress callbacks to reduce Python overhead."""

    __slots__ = ("_cb", "_pending", "_last_flush", "_min_batch", "_min_interval")

    def __init__(
        self,
        callback: Callable[[int], None],
        *,
        min_batch: int = 8,
        min_ms: float = 100.0,
    ) -> None:
        self._cb = callback
        self._pending = 0
        self._last_flush = time.perf_counter()
        self._min_batch = max(1, int(min_batch))
        self._min_interval = max(0.0, float(min_ms)) / 1000.0

    def add(self, count: int = 1) -> None:
        self._pending += int(count)
        now = time.perf_counter()
        if self._pending >= self._min_batch or (now - self._last_flush) >= self._min_interval:
            self.flush(now)

    def flush(self, now: Optional[float] = None) -> None:
        if self._pending <= 0:
            return
        try:
            self._cb(self._pending)
        finally:
            self._pending = 0
            self._last_flush = time.perf_counter() if now is None else now


def _is_hdr_source(clip) -> bool:
    """Return True when the clip's transfer characteristics indicate HDR."""

    try:
        props = vs_core._snapshot_frame_props(clip)
        _, transfer, _, _ = vs_core._resolve_color_metadata(props)
    except Exception:
        return False

    if transfer is None:
        return False

    try:
        code = int(transfer)
    except (TypeError, ValueError):
        code = None

    if code in {16, 18}:
        return True

    name = str(transfer).strip().upper()
    return name in {"ST2084", "SMPTE2084", "PQ", "HLG", "ARIB-B67"}


def _collect_metrics_vapoursynth(
    clip,
    cfg: AnalysisConfig,
    indices: Sequence[int],
    progress: Callable[[int], None] | None = None,
) -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
    """
    Measure per-frame brightness and motion metrics using VapourSynth.

    Parameters:
        clip: VapourSynth clip to analyse.
        cfg (AnalysisConfig): Analysis settings controlling scaling, colours, and motion smoothing.
        indices (Sequence[int]): Frame indices to sample.
        progress (Callable[[int], None] | None): Optional callback invoked with the count of processed frames.

    Returns:
        tuple[List[tuple[int, float]], List[tuple[int, float]]]: Brightness and motion metric pairs for each processed frame.

    Raises:
        RuntimeError: If VapourSynth processing fails after retries.
    """
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - handled by fallback
        raise RuntimeError("VapourSynth is unavailable") from exc

    if not isinstance(clip, vs.VideoNode):
        raise TypeError("Expected a VapourSynth clip")

    props = vs_core._snapshot_frame_props(clip)
    matrix_in, transfer_in, primaries_in, color_range_in = vs_core._resolve_color_metadata(props)

    def _resize_kwargs_for_source() -> Dict[str, int]:
        """Return color-metadata kwargs describing the source clip."""
        kwargs: Dict[str, int] = {}
        if matrix_in is not None:
            kwargs["matrix_in"] = int(matrix_in)
        else:
            try:
                if clip.format is not None and clip.format.color_family == vs.RGB:
                    kwargs["matrix_in"] = getattr(vs, "MATRIX_RGB", 0)
            except AttributeError:
                pass
        if transfer_in is not None:
            kwargs["transfer_in"] = int(transfer_in)
        if primaries_in is not None:
            kwargs["primaries_in"] = int(primaries_in)
        if color_range_in is not None:
            kwargs["range_in"] = int(color_range_in)
        return kwargs

    processed_indices = [
        int(idx)
        for idx in indices
        if isinstance(idx, numbers.Integral) and 0 <= int(idx) < clip.num_frames
    ]

    if not processed_indices:
        return [], []

    def _detect_uniform_step(values: Sequence[int]) -> Optional[int]:
        """Return a positive step size when frame indices form an arithmetic series."""
        if len(values) <= 1:
            return 1
        step_value = values[1] - values[0]
        if step_value <= 0:
            return None
        for prev, curr in zip(values, values[1:]):
            if curr - prev != step_value:
                return None
        return step_value

    step_value = _detect_uniform_step(processed_indices)

    sequential = step_value is not None

    resize_kwargs = _resize_kwargs_for_source()

    try:
        if sequential:
            first_idx = processed_indices[0]
            last_idx = processed_indices[-1]
            trimmed = vs.core.std.Trim(clip, first=first_idx, last=last_idx)
            if len(processed_indices) > 1 and step_value and step_value > 1:
                sampled = vs.core.std.SelectEvery(trimmed, cycle=step_value, offsets=[0])
            else:
                sampled = trimmed
        else:
            sampled = clip
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Failed to trim analysis clip: {exc}") from exc

    def _prepare_analysis_clip(node):
        """Resize and convert *node* to a grayscale analysis representation."""
        work = node
        try:
            height_obj = getattr(work, "height", None)
            if (
                cfg.downscale_height > 0
                and isinstance(height_obj, numbers.Real)
                and float(height_obj) > float(cfg.downscale_height)
            ):
                target_h = _ensure_even(max(2, int(cfg.downscale_height)))
                width_obj = getattr(work, "width", None)
                height_value = max(1, int(float(height_obj)))
                aspect = 1.0
                if isinstance(width_obj, numbers.Real) and height_value > 0:
                    aspect = float(width_obj) / float(height_value)
                target_w = _ensure_even(max(2, int(round(target_h * aspect))))
                work = vs.core.resize.Bilinear(
                    work,
                    width=target_w,
                    height=target_h,
                    **resize_kwargs,
                )

            target_format = getattr(vs, "GRAY8", None) or getattr(vs, "GRAY16")
            gray_kwargs: Dict[str, int] = dict(resize_kwargs)
            gray_formats = {
                getattr(vs, "GRAY8", None),
                getattr(vs, "GRAY16", None),
                getattr(vs, "GRAY32", None),
            }
            format_obj = getattr(work, "format", None)
            color_family = getattr(format_obj, "color_family", None)
            rgb_constant = getattr(vs, "RGB", None)
            if format_obj is not None and color_family == rgb_constant:
                matrix_in_val = gray_kwargs.get("matrix_in")
                if matrix_in_val is None:
                    matrix_in_val = getattr(vs, "MATRIX_RGB", 0)
                convert_kwargs: Dict[str, int] = dict(gray_kwargs)
                convert_kwargs.pop("matrix", None)
                convert_kwargs["matrix_in"] = int(matrix_in_val)
                if "matrix" not in convert_kwargs:
                    convert_kwargs["matrix"] = getattr(vs, "MATRIX_BT709", 1)
                yuv = vs.core.resize.Bilinear(
                    work,
                    format=getattr(vs, "YUV444P16"),
                    **convert_kwargs,
                )
                work = vs.core.std.ShufflePlanes(yuv, planes=0, colorfamily=vs.GRAY)
            if target_format not in gray_formats:
                if "matrix" not in gray_kwargs:
                    matrix_in_value = gray_kwargs.get("matrix_in")
                    if matrix_in_value is not None:
                        gray_kwargs["matrix"] = int(matrix_in_value)
                    else:
                        gray_kwargs["matrix"] = getattr(vs, "MATRIX_BT709", 1)
            else:
                gray_kwargs.pop("matrix", None)
            work = vs.core.resize.Bilinear(work, format=target_format, **gray_kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to prepare analysis clip: {exc}") from exc
        return work

    prepared = _prepare_analysis_clip(sampled)

    try:
        stats_clip = prepared.std.PlaneStats()
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Failed to prepare metrics pipeline: {exc}") from exc

    motion_stats = None
    if cfg.frame_count_motion > 0 and prepared.num_frames > 1:
        try:
            previous = prepared[:-1]
            current = prepared[1:]
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

    coalescer = _ProgressCoalescer(progress) if progress is not None else None

    try:
        if sequential:
            for position, idx in enumerate(processed_indices):
                if position >= stats_clip.num_frames:
                    break
                frame = stats_clip.get_frame(position)
                luma = float(frame.props.get("PlaneStatsAverage", 0.0))
                brightness.append((idx, luma))
                del frame

                motion_value = 0.0
                if motion_stats is not None and position > 0:
                    diff_frame = motion_stats.get_frame(position - 1)
                    motion_value = float(diff_frame.props.get("PlaneStatsAverage", 0.0))
                    del diff_frame
                motion.append((idx, motion_value))

                if coalescer is not None:
                    coalescer.add(1)
        else:
            for idx in processed_indices:
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

                if coalescer is not None:
                    coalescer.add(1)
    finally:
        if coalescer is not None:
            coalescer.flush()

    return brightness, motion


def _generate_metrics_fallback(
    indices: Sequence[int],
    cfg: AnalysisConfig,
    progress: Callable[[int], None] | None = None,
) -> tuple[List[tuple[int, float]], List[tuple[int, float]]]:
    """
    Synthesize deterministic metrics when VapourSynth processing is unavailable.

    Parameters:
        indices (Sequence[int]): Frame indices to simulate metrics for.
        cfg (AnalysisConfig): Analysis configuration controlling quantiles and smoothing.
        progress (Callable[[int], None] | None): Optional callback invoked with the count of processed frames.

    Returns:
        tuple[List[tuple[int, float]], List[tuple[int, float]]]: Synthetic brightness and motion metric samples.
    """
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
    """
    Apply a simple moving average of ``radius`` to motion metric samples.

    Parameters:
        values (List[tuple[int, float]]): Motion metric samples as ``(frame, value)`` pairs.
        radius (int): Window radius used for smoothing.

    Returns:
        List[tuple[int, float]]: Smoothed motion metric samples.
    """
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
    color_cfg: Optional[ColorConfig] = None,
) -> List[int] | Tuple[List[int], Dict[int, str], Dict[int, SelectionDetail]]:
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
    min_sep_frames = (
        0
        if cfg.screen_separation_sec <= 0
        else int(round(cfg.screen_separation_sec * fps))
    )
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
        if _is_hdr_source(clip):
            if color_cfg is None:
                raise ValueError("color_cfg must be provided when analyze_in_sdr is enabled")
            result = vs_core.process_clip_for_screenshot(
                clip,
                file_under_analysis,
                color_cfg,
                enable_overlay=False,
                enable_verification=False,
                logger_override=logger,
            )
            analysis_clip = result.clip
        else:
            logger.info("[ANALYSIS] Source detected as SDR; skipping SDR tonemap path")

    step = max(1, int(cfg.step))
    indices = list(range(window_start, window_end, step))

    selection_hash = _selection_fingerprint(cfg)
    selection_details: Dict[int, SelectionDetail] = {}

    def _ensure_detail(
        frame_idx: int,
        *,
        label: Optional[str] = None,
        score: Optional[float] = None,
        note: Optional[str] = None,
    ) -> SelectionDetail:
        existing = selection_details.get(frame_idx)
        if existing is None:
            detail = SelectionDetail(
                frame_index=frame_idx,
                label=label or "Auto",
                score=score,
                source=_SELECTION_SOURCE_ID,
                timecode=_frame_to_timecode(frame_idx, fps),
                clip_role=None,
                notes=note,
            )
            selection_details[frame_idx] = detail
            existing = detail
        else:
            if label and not existing.label:
                existing.label = label
            if score is not None and existing.score is None:
                existing.score = score
            if note and not existing.notes:
                existing.notes = note
            if existing.timecode is None:
                existing.timecode = _frame_to_timecode(frame_idx, fps)
        if existing.clip_role is None:
            existing.clip_role = selection_clip_role
        return selection_details[frame_idx]

    selection_clip_role = "analyze"
    analyze_index_guess = 0
    if files:
        try:
            analyze_index_guess = files.index(file_under_analysis)
        except ValueError:
            analyze_index_guess = 0
        selection_clip_role = _infer_clip_role(
            analyze_index_guess, files[analyze_index_guess], file_under_analysis, len(files)
        )
    for detail in selection_details.values():
        if detail.clip_role is None:
            detail.clip_role = selection_clip_role

    if cache_info is not None:
        sidecar_result = _load_selection_sidecar(cache_info, cfg, selection_hash)
        if sidecar_result is not None:
            sidecar_frames, sidecar_details = sidecar_result
            selection_details.update(sidecar_details)
            frames_sorted = sorted(
                dict.fromkeys(
                    int(frame)
                    for frame in sidecar_frames
                    if window_start <= int(frame) < window_end
                )
            )
            filtered_details = {
                frame: detail for frame, detail in selection_details.items() if frame in frames_sorted
            }
            selection_details.clear()
            selection_details.update(filtered_details)
            if return_metadata:
                label_map: Dict[int, str] = {}
                for frame in frames_sorted:
                    detail = selection_details.get(frame)
                    label = detail.label if detail else "Cached"
                    detail = _ensure_detail(frame, label=label)
                    label_map[frame] = detail.label
                return frames_sorted, label_map, selection_details
            return frames_sorted

    cached_metrics = _load_cached_metrics(cache_info, cfg) if cache_info is not None else None

    cached_selection: Optional[List[int]] = None
    cached_categories: Optional[Dict[int, str]] = None
    cached_details: Optional[Dict[int, SelectionDetail]] = None

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
            cached_details = cached_metrics.selection_details
        if progress is not None:
            progress(len(brightness))
        logger.info(
            "[ANALYSIS] using cached metrics (brightness=%d, motion=%d)",
            len(brightness),
            len(motion),
        )
    else:
        logger.info(
            "[ANALYSIS] collecting metrics (indices=%d, step=%d, analyze_in_sdr=%s)",
            len(indices),
            step,
            cfg.analyze_in_sdr,
        )
        start_metrics = time.perf_counter()
        try:
            brightness, motion = _collect_metrics_vapoursynth(analysis_clip, cfg, indices, progress)
            logger.info(
                "[ANALYSIS] metrics collected via VapourSynth in %.2fs (brightness=%d, motion=%d)",
                time.perf_counter() - start_metrics,
                len(brightness),
                len(motion),
            )
        except Exception as exc:
            logger.warning(
                "[ANALYSIS] VapourSynth metrics collection failed (%s); "
                "falling back to synthetic metrics",
                exc,
            )
            brightness, motion = _generate_metrics_fallback(indices, cfg, progress)
            logger.info(
                "[ANALYSIS] synthetic metrics generated in %.2fs",
                time.perf_counter() - start_metrics,
            )

    if cached_selection is not None:
        frames_sorted = sorted(dict.fromkeys(int(frame) for frame in cached_selection))
        if cached_details:
            selection_details.update({frame: detail for frame, detail in cached_details.items() if frame in frames_sorted})
        if return_metadata:
            categories = cached_categories or {}
            label_map: Dict[int, str] = {}
            for frame in frames_sorted:
                label = categories.get(frame, "Cached")
                detail = _ensure_detail(frame, label=label)
                label_map[frame] = detail.label
            return frames_sorted, label_map, selection_details
        return frames_sorted

    brightness_values = [val for _, val in brightness]

    selected: List[int] = []
    selected_set: set[int] = set()
    frame_categories: Dict[int, str] = {}

    def try_add(
        frame: int,
        enforce_gap: bool = True,
        gap_frames: Optional[int] = None,
        allow_edges: bool = False,
        category: Optional[str] = None,
        score: Optional[float] = None,
        note: Optional[str] = None,
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
        _ensure_detail(frame_idx, label=category, score=score, note=note)
        return True

    dropped_user_frames: List[int] = []
    for frame in cfg.user_frames:
        try:
            frame_int = int(frame)
        except (TypeError, ValueError):
            continue
        if window_start <= frame_int < window_end:
            try_add(
                frame_int,
                enforce_gap=False,
                allow_edges=True,
                category="User",
                note="user_frame",
            )
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
        score_lookup: Dict[int, float] = {}
        for idx, val in candidates:
            score_lookup.setdefault(int(idx), float(val))
        added = 0
        category_label = "Motion" if mode == "motion" else mode.capitalize()
        for frame_idx in filtered_indices:
            if try_add(
                frame_idx,
                enforce_gap=True,
                gap_frames=gap_frames,
                category=category_label,
                score=score_lookup.get(frame_idx),
                note=mode,
            ):
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
        if try_add(candidate, enforce_gap=True, category="Random", note="random"):
            random_count -= 1
        attempts += 1

    final_frames = sorted(selected)

    for frame in final_frames:
        _ensure_detail(frame, label=frame_categories.get(frame, "Auto"))

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
                selection_details=selection_details,
            )
        except Exception:
            pass

    if return_metadata:
        label_map = {frame: frame_categories.get(frame, "Auto") for frame in final_frames}
        return final_frames, label_map, selection_details
    return final_frames
