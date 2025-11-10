"""Audio alignment orchestration helpers."""

from __future__ import annotations

import datetime as _dt
import importlib
import importlib.util
import logging
import math
import os
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
import uuid
from collections.abc import Mapping as MappingABC
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    ContextManager,
    Dict,
    Final,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    cast,
)

import click
from rich.text import Text

from src import audio_alignment
from src.datatypes import AppConfig, ColorConfig
from src.frame_compare.cli_runtime import (
    CLIAppError,
    _ClipPlan,
    _coerce_str_mapping,
    _ensure_audio_alignment_block,
    _normalise_vspreview_mode,
    _plan_label,
)
from src.frame_compare.config_helpers import coerce_config_flag as _coerce_config_flag
from src.frame_compare.metadata import match_override as _match_override
from src.frame_compare.preflight import PROJECT_ROOT, resolve_subdir

if TYPE_CHECKING:
    from src.audio_alignment import AlignmentMeasurement, AudioStreamInfo
    from src.frame_compare.cli_runtime import CliOutputManagerProtocol, JsonTail

logger = logging.getLogger(__name__)

_VSPREVIEW_WINDOWS_INSTALL: Final[str] = (
    "uv add frame-compare --extra preview  # fallback: uv add vspreview PySide6"
)
_VSPREVIEW_POSIX_INSTALL: Final[str] = (
    "uv add frame-compare --extra preview  # fallback: uv add vspreview PySide6"
)
_VSPREVIEW_MANUAL_COMMAND_TEMPLATE: Final[str] = "{python} -m vspreview {script}"


def _format_vspreview_manual_command(script_path: Path) -> str:
    """Build a manual VSPreview command using the active Python interpreter."""

    python_exe = sys.executable or "python"
    script_arg = str(script_path)
    if os.name == "nt":
        if " " in python_exe and not python_exe.startswith('"'):
            python_exe = f'"{python_exe}"'
        if " " in script_arg and not script_arg.startswith('"'):
            script_arg = f'"{script_arg}"'
    else:
        python_exe = shlex.quote(python_exe)
        script_arg = shlex.quote(script_arg)
    return _VSPREVIEW_MANUAL_COMMAND_TEMPLATE.format(
        python=python_exe, script=script_arg
    )


def _fps_to_float(value: tuple[int, int] | None) -> float:
    """Convert an FPS tuple to a float, guarding against missing/zero denominators."""

    if value is None:
        return 0.0
    numerator, denominator = value
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


@dataclass
class _AudioAlignmentSummary:
    """
    Bundle of audio-alignment details used for reporting and persistence.
    """

    offsets_path: Path
    reference_name: str
    measurements: Sequence["AlignmentMeasurement"]
    applied_frames: Dict[str, int]
    baseline_shift: int
    statuses: Dict[str, str]
    reference_plan: _ClipPlan
    final_adjustments: Dict[str, int]
    swap_details: Dict[str, str]
    suggested_frames: Dict[str, int] = field(default_factory=dict)
    suggestion_mode: bool = False
    manual_trim_starts: Dict[str, int] = field(default_factory=dict)
    vspreview_manual_offsets: Dict[str, int] = field(default_factory=dict)
    vspreview_manual_deltas: Dict[str, int] = field(default_factory=dict)
    measured_offsets: Dict[str, "_AudioMeasurementDetail"] = field(default_factory=dict)


@dataclass
class _AudioMeasurementDetail:
    """Snapshot of an audio alignment measurement for CLI/JSON reporting."""

    label: str
    stream: str
    offset_seconds: Optional[float]
    frames: Optional[int]
    correlation: Optional[float]
    status: str
    applied: bool
    note: Optional[str] = None


@dataclass
class _AudioAlignmentDisplayData:
    """
    Pre-rendered data used to present audio alignment results in the CLI.
    """

    stream_lines: List[str]
    estimation_line: Optional[str]
    offset_lines: List[str]
    offsets_file_line: str
    json_reference_stream: Optional[str]
    json_target_streams: Dict[str, str]
    json_offsets_sec: Dict[str, float]
    json_offsets_frames: Dict[str, int]
    warnings: List[str]
    preview_paths: List[str] = field(default_factory=list)
    inspection_paths: List[str] = field(default_factory=list)
    confirmation: Optional[str] = None
    correlations: Dict[str, float] = field(default_factory=dict)
    threshold: float = 0.0
    manual_trim_lines: List[str] = field(default_factory=list)
    measurements: Dict[str, _AudioMeasurementDetail] = field(default_factory=dict)


def _resolve_alignment_reference(
    plans: Sequence[_ClipPlan],
    analyze_path: Path,
    reference_hint: str,
) -> _ClipPlan:
    """Choose the audio alignment reference plan using optional hint and fallbacks."""
    if not plans:
        raise CLIAppError("No clips available for alignment")

    hint = (reference_hint or "").strip().lower()
    if hint:
        if hint.isdigit():
            idx = int(hint)
            if 0 <= idx < len(plans):
                return plans[idx]
        for plan in plans:
            candidates = {
                plan.path.name.lower(),
                plan.path.stem.lower(),
                (plan.metadata.get("label") or "").lower(),
            }
            if hint in candidates and hint:
                return plan

    for plan in plans:
        if plan.path == analyze_path:
            return plan
    return plans[0]



def apply_audio_alignment(
    plans: Sequence[_ClipPlan],
    cfg: AppConfig,
    analyze_path: Path,
    root: Path,
    audio_track_overrides: Mapping[str, int],
    reporter: CliOutputManagerProtocol | None = None,
) -> tuple[_AudioAlignmentSummary | None, _AudioAlignmentDisplayData | None]:
    """Apply audio alignment when enabled, returning summary and display data."""
    audio_cfg = cfg.audio_alignment
    prompt_reuse_offsets = _coerce_config_flag(audio_cfg.prompt_reuse_offsets)
    offsets_path = resolve_subdir(
        root,
        audio_cfg.offsets_filename,
        purpose="audio_alignment.offsets_filename",
    )
    display_data = _AudioAlignmentDisplayData(
        stream_lines=[],
        estimation_line=None,
        offset_lines=[],
        offsets_file_line=f"Offsets file: {offsets_path}",
        json_reference_stream=None,
        json_target_streams={},
        json_offsets_sec={},
        json_offsets_frames={},
        warnings=[],
        correlations={},
        threshold=float(audio_cfg.correlation_threshold),
    )

    def _warn(message: str) -> None:
        display_data.warnings.append(f"[AUDIO] {message}")

    vspreview_enabled = _coerce_config_flag(audio_cfg.use_vspreview)

    reference_plan: _ClipPlan | None = None
    if plans:
        reference_plan = _resolve_alignment_reference(plans, analyze_path, audio_cfg.reference)

    plan_labels: Dict[Path, str] = {plan.path: _plan_label(plan) for plan in plans}
    name_to_label: Dict[str, str] = {plan.path.name: plan_labels[plan.path] for plan in plans}

    existing_entries_cache: tuple[
        str | None, Dict[str, Dict[str, object]]
    ] | None = None

    def _load_existing_entries() -> tuple[str | None, Dict[str, Dict[str, object]]]:
        nonlocal existing_entries_cache
        if existing_entries_cache is None:
            try:
                reference_name, existing_entries_raw = audio_alignment.load_offsets(
                    offsets_path
                )
            except audio_alignment.AudioAlignmentError as exc:
                raise CLIAppError(
                    f"Failed to read audio offsets file: {exc}",
                    rich_message=f"[red]Failed to read audio offsets file:[/red] {exc}",
                ) from exc
            existing_entries_cache = (
                reference_name,
                cast(Dict[str, Dict[str, object]], existing_entries_raw),
            )
        return existing_entries_cache

    def _reuse_vspreview_manual_offsets_if_available(
        reference: _ClipPlan | None,
    ) -> _AudioAlignmentSummary | None:
        if not (vspreview_enabled and reference and plans):
            return None

        try:
            _, existing_entries = _load_existing_entries()
        except CLIAppError:
            if not audio_cfg.enable:
                return None
            raise

        vspreview_reuse: Dict[str, int] = {}
        allowed_keys = {plan.path.name for plan in plans}
        for key, value in existing_entries.items():
            if not isinstance(value, dict):
                continue
            status_obj = value.get("status")
            note_obj = value.get("note")
            frames_obj = value.get("frames")
            if not isinstance(status_obj, str) or not isinstance(frames_obj, (int, float)):
                continue
            if status_obj.strip().lower() != "manual":
                continue
            note_text = str(note_obj or "").strip().lower()
            if "vspreview" not in note_text:
                continue
            if key in allowed_keys:
                vspreview_reuse[key] = int(frames_obj)

        if not vspreview_reuse:
            return None

        if display_data.manual_trim_lines:
            display_data.manual_trim_lines.clear()
        label_map = {plan.path.name: plan_labels.get(plan.path, plan.path.name) for plan in plans}
        manual_trim_starts: Dict[str, int] = {}
        for plan in plans:
            key = plan.path.name
            if key not in vspreview_reuse:
                continue
            raw_frames_value = int(vspreview_reuse[key])
            applied_frames = max(raw_frames_value, 0)
            plan.trim_start = applied_frames
            plan.has_trim_start_override = (
                plan.has_trim_start_override or raw_frames_value != 0
            )
            manual_trim_starts[key] = raw_frames_value
            label = label_map.get(key, key)
            display_data.manual_trim_lines.append(
                f"VSPreview manual trim reused: {label} → {applied_frames}f"
            )

        filtered_vspreview = {key: value for key, value in vspreview_reuse.items() if key in allowed_keys}

        display_data.offset_lines = ["Audio offsets: VSPreview manual offsets applied"]
        if display_data.manual_trim_lines:
            display_data.offset_lines.extend(display_data.manual_trim_lines)

        display_data.json_offsets_frames = {
            label_map.get(key, key): int(value)
            for key, value in filtered_vspreview.items()
        }
        statuses_map = {key: "manual" for key in filtered_vspreview}
        return _AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name=reference.path.name,
            measurements=(),
            applied_frames=dict(filtered_vspreview),
            baseline_shift=0,
            statuses=statuses_map,
            reference_plan=reference,
            final_adjustments=dict(filtered_vspreview),
            swap_details={},
            suggested_frames={},
            suggestion_mode=False,
            manual_trim_starts=manual_trim_starts,
            vspreview_manual_offsets=dict(filtered_vspreview),
        )

    reused_summary = _reuse_vspreview_manual_offsets_if_available(reference_plan)
    if reused_summary is not None:
        if not audio_cfg.enable:
            display_data.warnings.append(
                "[AUDIO] VSPreview manual alignment enabled — audio alignment disabled."
            )
        return reused_summary, display_data

    if not audio_cfg.enable:
        if vspreview_enabled and plans and reference_plan is not None:
            manual_trim_starts = {
                plan.path.name: int(plan.trim_start)
                for plan in plans
                if plan.trim_start > 0
            }
            if manual_trim_starts:
                for plan in plans:
                    trim = manual_trim_starts.get(plan.path.name)
                    if trim:
                        display_data.manual_trim_lines.append(
                            f"Existing manual trim: {plan_labels[plan.path]} → {trim}f"
                        )
            display_data.offset_lines = ["Audio offsets: not computed (manual alignment only)"]
            display_data.offset_lines.extend(display_data.manual_trim_lines)
            display_data.warnings.append(
                "[AUDIO] VSPreview manual alignment enabled — audio alignment disabled."
            )
            summary = _AudioAlignmentSummary(
                offsets_path=offsets_path,
                reference_name=reference_plan.path.name,
                measurements=(),
                applied_frames=dict(manual_trim_starts),
                baseline_shift=0,
                statuses={},
                reference_plan=reference_plan,
                final_adjustments={},
                swap_details={},
                suggested_frames={},
                suggestion_mode=True,
                manual_trim_starts=manual_trim_starts,
            )
            return summary, display_data
        return None, display_data
    if len(plans) < 2:
        _warn("Audio alignment skipped: need at least two clips.")
        return None, display_data

    assert reference_plan is not None
    targets = [plan for plan in plans if plan is not reference_plan]
    if not targets:
        _warn("Audio alignment skipped: no secondary clips to compare.")
        return None, display_data

    measurement_order = [plan.path.name for plan in plans]
    negative_override_notes: Dict[str, str] = {}

    def _maybe_reuse_cached_offsets(
        reference: _ClipPlan,
        candidate_targets: Sequence[_ClipPlan],
    ) -> _AudioAlignmentSummary | None:
        if not prompt_reuse_offsets:
            return None
        if not sys.stdin.isatty():
            return None
        try:
            cached_reference, existing_entries = _load_existing_entries()
        except CLIAppError:
            return None
        if not existing_entries:
            return None
        if cached_reference is not None and cached_reference != reference.path.name:
            return None

        required_names = [plan.path.name for plan in candidate_targets]
        if any(name not in existing_entries for name in required_names):
            return None

        if click.confirm(
            "Recompute audio offsets using current clips?",
            default=True,
            show_default=True,
        ):
            return None

        display_data.estimation_line = (
            f"Audio offsets reused from existing file ({offsets_path.name})."
        )

        plan_map: Dict[str, _ClipPlan] = {plan.path.name: plan for plan in plans}

        def _get_float(value: object) -> float | None:
            if isinstance(value, (int, float)):
                float_value = float(value)
                if math.isnan(float_value):
                    return None
                return float_value
            return None

        def _get_int(value: object) -> int | None:
            if isinstance(value, (int, float)):
                float_value = float(value)
                if math.isnan(float_value):
                    return None
                return int(float_value)
            return None

        reference_entry = existing_entries.get(reference.path.name)
        reference_manual_frames: int | None = None
        reference_manual_seconds: float | None = None
        if isinstance(reference_entry, Mapping):
            status_obj = reference_entry.get("status")
            if isinstance(status_obj, str) and status_obj.strip().lower() == "manual":
                reference_manual_frames = _get_int(reference_entry.get("frames"))
                reference_manual_seconds = _get_float(reference_entry.get("seconds"))
                if (
                    reference_manual_seconds is None
                    and reference_manual_frames is not None
                ):
                    fps_guess = _get_float(reference_entry.get("target_fps")) or _get_float(
                        reference_entry.get("reference_fps")
                    )
                    if fps_guess and fps_guess > 0:
                        reference_manual_seconds = reference_manual_frames / fps_guess

        measurements: list["AlignmentMeasurement"] = []
        swap_details: Dict[str, str] = {}
        negative_offsets: Dict[str, bool] = {}

        def _build_measurement(name: str, entry: Mapping[str, object]) -> "AlignmentMeasurement":
            plan = plan_map[name]
            frames_val = _get_int(entry.get("frames")) if entry else None
            seconds_val = _get_float(entry.get("seconds")) if entry else None
            target_fps = _get_float(entry.get("target_fps")) if entry else None
            reference_fps = _get_float(entry.get("reference_fps")) if entry else None
            status_obj = entry.get("status") if entry else None
            is_manual = isinstance(status_obj, str) and status_obj.strip().lower() == "manual"
            if seconds_val is None and frames_val is not None:
                fps_val = target_fps if target_fps and target_fps > 0 else reference_fps
                if fps_val and fps_val > 0:
                    seconds_val = frames_val / fps_val
            if is_manual and reference_manual_frames is not None:
                if frames_val is not None:
                    frames_val -= reference_manual_frames
                if seconds_val is not None and reference_manual_seconds is not None:
                    seconds_val -= reference_manual_seconds
                elif seconds_val is None and frames_val is not None:
                    fps_val = target_fps if target_fps and target_fps > 0 else reference_fps
                    if fps_val and fps_val > 0:
                        seconds_val = frames_val / fps_val
            correlation_val = _get_float(entry.get("correlation")) if entry else None
            error_obj = entry.get("error") if entry else None
            error_val = str(error_obj).strip() if isinstance(error_obj, str) and error_obj.strip() else None
            measurement = audio_alignment.AlignmentMeasurement(
                file=plan.path,
                offset_seconds=seconds_val if seconds_val is not None else 0.0,
                frames=frames_val,
                correlation=correlation_val if correlation_val is not None else 0.0,
                reference_fps=reference_fps,
                target_fps=target_fps,
                error=error_val,
            )
            note_obj = entry.get("note") if entry else None
            if isinstance(note_obj, str) and note_obj.strip():
                note_text = note_obj.strip()
                swap_details[name] = note_text
                if "opposite clip" in note_text.lower():
                    negative_offsets[name] = True
            return measurement

        for target_plan in candidate_targets:
            entry = existing_entries.get(target_plan.path.name)
            if entry is None:
                return None
            measurements.append(_build_measurement(target_plan.path.name, entry))

        reference_entry = existing_entries.get(reference.path.name)
        if reference_entry is not None:
            measurements.append(_build_measurement(reference.path.name, reference_entry))

        raw_warning_messages: List[str] = []
        for measurement in measurements:
            reasons: List[str] = []
            if measurement.error:
                reasons.append(measurement.error)
            if abs(measurement.offset_seconds) > audio_cfg.max_offset_seconds:
                reasons.append(
                    f"offset {measurement.offset_seconds:.3f}s exceeds limit {audio_cfg.max_offset_seconds:.3f}s"
                )
            if measurement.correlation < audio_cfg.correlation_threshold:
                reasons.append(
                    f"correlation {measurement.correlation:.2f} below threshold {audio_cfg.correlation_threshold:.2f}"
                )
            if measurement.frames is None:
                reasons.append("unable to derive frame offset (missing fps)")

            if reasons:
                measurement.frames = None
                measurement.error = "; ".join(reasons)
                file_key = measurement.file.name
                negative_offsets.pop(file_key, None)
                label = name_to_label.get(file_key, file_key)
                raw_warning_messages.append(f"{label}: {measurement.error}")

        for warning_message in dict.fromkeys(raw_warning_messages):
            _warn(warning_message)

        offset_lines: List[str] = []
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}

        for measurement in measurements:
            clip_name = measurement.file.name
            if clip_name == reference.path.name and len(measurements) > 1:
                continue
            label = name_to_label.get(clip_name, clip_name)
            if measurement.offset_seconds is not None:
                offsets_sec[label] = float(measurement.offset_seconds)
            if measurement.frames is not None:
                offsets_frames[label] = int(measurement.frames)
            display_data.correlations[label] = float(measurement.correlation)

            if measurement.error:
                offset_lines.append(
                    f"Audio offsets: {label}: manual edit required ({measurement.error})"
                )
                continue

            fps_value = 0.0
            if measurement.target_fps and measurement.target_fps > 0:
                fps_value = float(measurement.target_fps)
            elif measurement.reference_fps and measurement.reference_fps > 0:
                fps_value = float(measurement.reference_fps)

            frames_text = "n/a"
            if measurement.frames is not None:
                frames_text = f"{measurement.frames:+d}f"
            fps_text = f"{fps_value:.3f}" if fps_value > 0 else "0.000"
            suffix = ""
            if clip_name in negative_offsets:
                suffix = " (reference advanced; trimming target)"
            offset_lines.append(
                f"Audio offsets: {label}: {measurement.offset_seconds:+.3f}s ({frames_text} @ {fps_text}){suffix}"
            )
            detail = swap_details.get(clip_name)
            if detail:
                offset_lines.append(f"  note: {detail}")

        if not offset_lines:
            offset_lines.append("Audio offsets: none detected")

        display_data.offset_lines = offset_lines
        display_data.json_offsets_sec = offsets_sec
        display_data.json_offsets_frames = offsets_frames

        suggested_frames: Dict[str, int] = {}
        for measurement in measurements:
            if measurement.frames is not None:
                suggested_frames[measurement.file.name] = int(measurement.frames)

        applied_frames: Dict[str, int] = {}
        statuses: Dict[str, str] = {}
        for name, entry in existing_entries.items():
            if name not in plan_map:
                continue
            frames_val = _get_int(entry.get("frames")) if entry else None
            if frames_val is not None:
                applied_frames[name] = frames_val
            status_obj = entry.get("status") if entry else None
            if isinstance(status_obj, str):
                statuses[name] = status_obj

        final_map: Dict[str, int] = {reference.path.name: 0}
        for name, frames in applied_frames.items():
            final_map[name] = frames

        baseline = min(final_map.values()) if final_map else 0
        baseline_shift = int(-baseline) if baseline < 0 else 0

        final_adjustments: Dict[str, int] = {}
        for plan in plans:
            desired = final_map.get(plan.path.name)
            if desired is None:
                continue
            adjustment = int(desired - baseline)
            if adjustment < 0:
                adjustment = 0
            if adjustment:
                plan.trim_start = max(0, plan.trim_start + adjustment)
                plan.alignment_frames = adjustment
                plan.alignment_status = statuses.get(plan.path.name, "auto")
            else:
                plan.alignment_frames = 0
                if plan.path.name in statuses:
                    plan.alignment_status = statuses.get(plan.path.name, "auto")
                else:
                    plan.alignment_status = ""
            final_adjustments[plan.path.name] = adjustment

        if baseline_shift:
            for plan in plans:
                if plan is reference:
                    plan.alignment_status = "baseline"

        summary = _AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name=reference.path.name,
            measurements=measurements,
            applied_frames=applied_frames,
            baseline_shift=baseline_shift,
            statuses=statuses,
            reference_plan=reference,
            final_adjustments=final_adjustments,
            swap_details=swap_details,
            suggested_frames=suggested_frames,
            suggestion_mode=False,
            manual_trim_starts={},
        )
        detail_map = _compose_measurement_details(
            measurements,
            applied_frames_map=applied_frames,
            statuses_map=statuses,
            suggestion_mode_active=False,
            manual_trims={},
            swap_map=swap_details,
            negative_notes=negative_override_notes,
        )
        summary.measured_offsets = detail_map
        _emit_measurement_lines(
            detail_map,
            measurement_order,
            append_manual=bool(display_data.manual_trim_lines),
        )
        return summary

    stream_infos: Dict[Path, List["AudioStreamInfo"]] = {}
    for plan in plans:
        try:
            infos = audio_alignment.probe_audio_streams(plan.path)
        except audio_alignment.AudioAlignmentError as exc:
            logger.warning("ffprobe audio stream probe failed for %s: %s", plan.path.name, exc)
            infos = []
        stream_infos[plan.path] = infos

    forced_streams: set[Path] = set()

    def _match_audio_override(plan: _ClipPlan) -> Optional[int]:
        """Return override index for *plan* when configured, otherwise ``None``."""
        value = _match_override(plans.index(plan), plan.path, plan.metadata, audio_track_overrides)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _pick_default(streams: Sequence["AudioStreamInfo"]) -> int:
        """Return default stream index, falling back to the first entry or zero."""
        if not streams:
            return 0
        for stream in streams:
            if stream.is_default:
                return stream.index
        return streams[0].index

    ref_override = _match_audio_override(reference_plan)
    if ref_override is not None:
        forced_streams.add(reference_plan.path)
    reference_stream_index = ref_override if ref_override is not None else _pick_default(
        stream_infos.get(reference_plan.path, [])
    )

    reference_stream_info = None
    for candidate in stream_infos.get(reference_plan.path, []):
        if candidate.index == reference_stream_index:
            reference_stream_info = candidate
            break

    def _score_candidate(candidate: "AudioStreamInfo") -> float:
        """
        Compute a heuristic quality score for an audio stream candidate relative to the (closure) reference stream.

        Parameters:
            candidate (audio_alignment.AudioStreamInfo): Audio stream metadata to evaluate.

        Returns:
            score (float): Higher values indicate a better match to the reference stream based on language, codec, channels, sample rate, bitrate, and flags (`is_default`, `is_forced`); used for ranking candidate streams.
        """
        base = 0.0
        if reference_stream_info is not None:
            if reference_stream_info.language and candidate.language == reference_stream_info.language:
                base += 100.0
            elif reference_stream_info.language and not candidate.language:
                base += 10.0
            if candidate.codec_name == reference_stream_info.codec_name:
                base += 30.0
            elif candidate.codec_name.split(".")[0] == reference_stream_info.codec_name.split(".")[0]:
                base += 20.0
            if candidate.channels == reference_stream_info.channels:
                base += 10.0
            if reference_stream_info.channel_layout and candidate.channel_layout == reference_stream_info.channel_layout:
                base += 5.0
            if reference_stream_info.sample_rate and candidate.sample_rate == reference_stream_info.sample_rate:
                base += 10.0
            elif reference_stream_info.sample_rate and candidate.sample_rate:
                base -= abs(candidate.sample_rate - reference_stream_info.sample_rate) / 1000.0
            if reference_stream_info.bitrate and candidate.bitrate:
                base -= abs(candidate.bitrate - reference_stream_info.bitrate) / 10000.0
        base += 3.0 if candidate.is_default else 0.0
        base += 1.0 if candidate.is_forced else 0.0
        if candidate.bitrate:
            base += candidate.bitrate / 1e5
        return base

    target_stream_indices: Dict[Path, int] = {}
    for target in targets:
        override_idx = _match_audio_override(target)
        if override_idx is not None:
            target_stream_indices[target.path] = override_idx
            forced_streams.add(target.path)
            continue
        infos = stream_infos.get(target.path, [])
        if not infos:
            target_stream_indices[target.path] = 0
            continue
        best = max(infos, key=_score_candidate)
        target_stream_indices[target.path] = best.index

    def _describe_stream(plan: _ClipPlan, stream_idx: int) -> tuple[str, str]:
        """
        Builds a human-readable label and a concise descriptor for the chosen audio stream of a clip.

        Parameters:
            plan (_ClipPlan): Clip plan whose path and label are used in the returned label.
            stream_idx (int): Index of the audio stream to describe.

        Returns:
            tuple[str, str]: A pair (display_label, descriptor) where `display_label` is formatted as
            "<clip_label>-><codec>/<language>/<layout>" with " (forced)" appended if the stream is marked forced,
            and `descriptor` is the "<codec>/<language>/<layout>" string.
        """
        infos = stream_infos.get(plan.path, [])
        picked = next((info for info in infos if info.index == stream_idx), None)
        codec = (picked.codec_name if picked and picked.codec_name else "unknown").strip() or "unknown"
        language = (picked.language if picked and picked.language else "und").strip() or "und"
        if picked and picked.channel_layout:
            layout = picked.channel_layout.strip()
        elif picked and picked.channels:
            layout = f"{picked.channels}ch"
        else:
            layout = "?"
        descriptor = f"{codec}/{language}/{layout}"
        forced_suffix = " (forced)" if plan.path in forced_streams else ""
        label = plan_labels[plan.path]
        return f"{label}->{descriptor}{forced_suffix}", descriptor

    reference_stream_text, reference_descriptor = _describe_stream(reference_plan, reference_stream_index)
    display_data.json_reference_stream = reference_stream_text
    stream_descriptors: Dict[str, str] = {reference_plan.path.name: reference_descriptor}

    for idx, target in enumerate(targets):
        stream_idx = target_stream_indices.get(target.path, 0)
        target_stream_text, target_descriptor = _describe_stream(target, stream_idx)
        display_data.json_target_streams[plan_labels[target.path]] = target_descriptor
        stream_descriptors[target.path.name] = target_descriptor
        if idx == 0:
            display_data.stream_lines.append(
                f"Audio streams: ref={reference_stream_text}  target={target_stream_text}"
            )
        else:
            display_data.stream_lines.append(f"Audio streams: target={target_stream_text}")

    def _format_measurement_line(detail: _AudioMeasurementDetail) -> str:
        stream_text = detail.stream or "?"
        seconds_text = (
            f"{detail.offset_seconds:+.3f}s"
            if detail.offset_seconds is not None
            else "n/a"
        )
        frames_text = (
            f"{detail.frames:+d}f" if detail.frames is not None else "n/a"
        )
        corr_text = (
            f"{detail.correlation:.2f}"
            if detail.correlation is not None and not math.isnan(detail.correlation)
            else "n/a"
        )
        applied_text = "applied" if detail.applied else "suggested"
        status_bits: List[str] = []
        if detail.status:
            status_bits.append(detail.status)
        status_bits.append(applied_text)
        status_text = "/".join(status_bits)
        return (
            f"Audio offsets: {detail.label}: [{stream_text}] "
            f"{seconds_text} ({frames_text}) corr={corr_text} status={status_text}"
        )

    def _emit_measurement_lines(
        detail_map: Dict[str, _AudioMeasurementDetail],
        order: Sequence[str],
        *,
        append_manual: bool = False,
    ) -> None:
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}
        offset_lines: List[str] = []
        for name in order:
            detail = detail_map.get(name)
            if detail is None:
                continue
            if (
                name == reference_plan.path.name
                and len(detail_map) > 1
            ):
                continue
            if detail.offset_seconds is not None:
                offsets_sec[detail.label] = float(detail.offset_seconds)
            if detail.frames is not None:
                offsets_frames[detail.label] = int(detail.frames)
            offset_lines.append(_format_measurement_line(detail))
            if detail.note:
                offset_lines.append(f"  note: {detail.note}")
        if not offset_lines:
            offset_lines.append("Audio offsets: none detected")
        if append_manual and display_data.manual_trim_lines:
            offset_lines.extend(display_data.manual_trim_lines)
        display_data.offset_lines = offset_lines
        display_data.json_offsets_sec = offsets_sec
        display_data.json_offsets_frames = offsets_frames
        display_data.measurements = {
            detail.label: detail for detail in detail_map.values()
        }
        display_data.correlations = {
            detail.label: detail.correlation
            for detail in detail_map.values()
            if detail.correlation is not None
        }

    fps_lookup: Dict[str, float] = {}
    for plan in plans:
        fps_tuple = plan.effective_fps or plan.source_fps or plan.fps_override
        fps_lookup[plan.path.name] = _fps_to_float(fps_tuple)

    def _compose_measurement_details(
        measurement_seq: Sequence["AlignmentMeasurement"],
        *,
        applied_frames_map: Mapping[str, int] | None,
        statuses_map: Mapping[str, str] | None,
        suggestion_mode_active: bool,
        manual_trims: Mapping[str, int],
        swap_map: Mapping[str, str],
        negative_notes: Mapping[str, str],
    ) -> Dict[str, _AudioMeasurementDetail]:
        """
        Convert raw measurement objects into detail records used for CLI + JSON reporting.

        Parameters:
            measurement_seq: Measurements returned by the alignment pipeline.
            applied_frames_map: Mapping of clip names to frame adjustments actually applied.
            statuses_map: Mapping of clip names to status labels ("auto", "manual", etc.).
            suggestion_mode_active: True when offsets are suggestions only (VSPreview flow).
            manual_trims: Existing manual trims discovered earlier in the run.
            swap_map: Swap/notes per clip (e.g., "reference advanced" notes).
            negative_notes: Notes produced when negative offsets were redirected.

        Returns:
            Dict[str, _AudioMeasurementDetail]: Mapping keyed by clip filename.
        """

        detail_map: Dict[str, _AudioMeasurementDetail] = {}
        for measurement in measurement_seq:
            clip_name = measurement.file.name
            label = name_to_label.get(clip_name, clip_name)
            descriptor = stream_descriptors.get(clip_name, "")
            seconds_value: Optional[float]
            if measurement.offset_seconds is None:
                seconds_value = None
            else:
                seconds_value = float(measurement.offset_seconds)
            frames_value = int(measurement.frames) if measurement.frames is not None else None
            correlation_value: Optional[float]
            if measurement.correlation is None or math.isnan(measurement.correlation):
                correlation_value = None
            else:
                correlation_value = float(measurement.correlation)
            status_text = ""
            if statuses_map and clip_name in statuses_map:
                status_text = statuses_map[clip_name]
            applied_flag = False
            if not suggestion_mode_active and applied_frames_map and clip_name in applied_frames_map:
                applied_flag = True
            note_parts: List[str] = []
            swap_note = swap_map.get(clip_name)
            if swap_note:
                note_parts.append(swap_note)
            negative_note = negative_notes.get(clip_name)
            if negative_note:
                note_parts.append(negative_note)
            if measurement.error:
                note_parts.append(measurement.error)
                if not status_text:
                    status_text = "error"
                applied_flag = False
            note_value = " ".join(note_parts) if note_parts else None
            detail_map[clip_name] = _AudioMeasurementDetail(
                label=label,
                stream=descriptor,
                offset_seconds=seconds_value,
                frames=frames_value,
                correlation=correlation_value,
                status=status_text,
                applied=applied_flag,
                note=note_value,
            )

        for clip_name, trim_frames in manual_trims.items():
            if clip_name in detail_map:
                continue
            label = name_to_label.get(clip_name, clip_name)
            descriptor = stream_descriptors.get(clip_name, "")
            fps_value = fps_lookup.get(clip_name, 0.0)
            seconds_value = (trim_frames / fps_value) if fps_value else None
            detail_map[clip_name] = _AudioMeasurementDetail(
                label=label,
                stream=descriptor,
                offset_seconds=seconds_value,
                frames=int(trim_frames),
                correlation=None,
                status="manual",
                applied=not suggestion_mode_active,
                note=None,
            )
        return detail_map

    reused_cached = _maybe_reuse_cached_offsets(reference_plan, targets)
    if reused_cached is not None:
        summary = reused_cached
        detail_map: Dict[str, _AudioMeasurementDetail] = {}
        for plan in plans:
            key = plan.path.name
            frames_val = summary.applied_frames.get(key)
            seconds_val: Optional[float]
            fps_val = fps_lookup.get(key, 0.0)
            if frames_val is None or not fps_val:
                seconds_val = None
            else:
                seconds_val = frames_val / fps_val if fps_val else None
            descriptor = stream_descriptors.get(key, "")
            detail_map[key] = _AudioMeasurementDetail(
                label=name_to_label.get(key, key),
                stream=descriptor,
                offset_seconds=seconds_val,
                frames=frames_val,
                correlation=None,
                status=summary.statuses.get(key, "manual"),
                applied=True,
            )
        summary.measured_offsets = detail_map
        display_data.measurements = {
            detail.label: detail for detail in detail_map.values()
        }
        _emit_measurement_lines(
            detail_map,
            measurement_order,
            append_manual=bool(display_data.manual_trim_lines),
        )
        return summary, display_data

    reference_fps_tuple = reference_plan.effective_fps or reference_plan.source_fps
    reference_fps = _fps_to_float(reference_fps_tuple)
    max_offset = float(audio_cfg.max_offset_seconds)
    raw_duration = audio_cfg.duration_seconds if audio_cfg.duration_seconds is not None else None
    duration_seconds = float(raw_duration) if raw_duration is not None else None
    start_seconds = float(audio_cfg.start_seconds or 0.0)
    search_text = f"±{max_offset:.2f}s"
    window_text = f"{duration_seconds:.2f}s" if duration_seconds is not None else "auto"
    start_text = f"{start_seconds:.2f}s"
    display_data.estimation_line = (
        f"Estimating audio offsets … fps={reference_fps:.3f} "
        f"search={search_text} start={start_text} window={window_text}"
    )

    try:
        base_start = float(audio_cfg.start_seconds or 0.0)
        base_duration_param: Optional[float]
        if audio_cfg.duration_seconds is None:
            base_duration_param = None
        else:
            base_duration_param = float(audio_cfg.duration_seconds)
        hop_length = max(1, min(audio_cfg.hop_length, max(1, audio_cfg.sample_rate // 100)))

        measurements: List["AlignmentMeasurement"]
        negative_offsets: Dict[str, bool] = {}

        spinner_context: ContextManager[object]
        status_factory = None
        if reporter is not None and not getattr(reporter, "quiet", False):
            status_factory = getattr(reporter.console, "status", None)
        if callable(status_factory):
            spinner_context = cast(
                ContextManager[object],
                status_factory("[cyan]Estimating audio offsets…[/cyan]", spinner="dots"),
            )
        else:
            spinner_context = nullcontext()
        processed = 0
        start_time = time.perf_counter()
        total_targets = len(targets)

        with spinner_context as status:
            def _advance_audio(count: int) -> None:
                """
                Advance the audio-alignment progress by a given number of processed pairs.

                Parameters:
                    count (int): Number of audio pair measurements to add to the processed total.
                """
                nonlocal processed
                processed += count
                if status is None or total_targets <= 0:
                    return
                status_update = getattr(status, "update", None)
                if callable(status_update):
                    elapsed = time.perf_counter() - start_time
                    rate_val = processed / elapsed if elapsed > 0 else 0.0
                    status_update(
                        f"[cyan]Estimating audio offsets… {processed}/{total_targets} ({rate_val:0.2f} pairs/s)[/cyan]"
                    )

            measurements = audio_alignment.measure_offsets(
                reference_plan.path,
                [plan.path for plan in targets],
                sample_rate=audio_cfg.sample_rate,
                hop_length=hop_length,
                start_seconds=base_start,
                duration_seconds=base_duration_param,
                reference_stream=reference_stream_index,
                target_streams=target_stream_indices,
                progress_callback=_advance_audio,
            )

        frame_bias = int(audio_cfg.frame_offset_bias or 0)
        if frame_bias != 0:
            adjust_toward_zero = frame_bias > 0
            bias_magnitude = abs(frame_bias)

            for measurement in measurements:
                frames_val = measurement.frames
                if frames_val is None or frames_val == 0:
                    continue

                sign = 1 if frames_val > 0 else -1
                magnitude = abs(frames_val)

                if adjust_toward_zero:
                    shift = min(bias_magnitude, magnitude)
                    adjusted_magnitude = max(0, magnitude - shift)
                else:
                    adjusted_magnitude = magnitude + bias_magnitude

                if adjusted_magnitude == magnitude:
                    continue

                new_frames = sign * adjusted_magnitude
                measurement.frames = new_frames

                if measurement.target_fps and measurement.target_fps > 0:
                    measurement.offset_seconds = new_frames / measurement.target_fps
                elif measurement.reference_fps and measurement.reference_fps > 0:
                    measurement.offset_seconds = new_frames / measurement.reference_fps

        negative_override_notes.clear()
        swap_details: Dict[str, str] = {}
        swap_candidates: List["AlignmentMeasurement"] = []
        swap_enabled = len(targets) == 1

        for measurement in measurements:
            if measurement.frames is not None and measurement.frames < 0:
                if swap_enabled:
                    swap_candidates.append(measurement)
                    continue
                measurement.frames = abs(int(measurement.frames))
                file_key = measurement.file.name
                negative_offsets[file_key] = True
                negative_override_notes[file_key] = (
                    "Suggested negative offset applied to the opposite clip for trim-first behaviour."
                )

        if swap_enabled and swap_candidates:
            additional_measurements: List["AlignmentMeasurement"] = []
            reference_name: str = reference_plan.path.name
            existing_keys = {m.file.name for m in measurements}

            for measurement in swap_candidates:
                seconds = float(measurement.offset_seconds)
                seconds_abs = abs(seconds)
                target_name: str = measurement.file.name

                original_frames = None
                if measurement.frames is not None:
                    original_frames = abs(int(measurement.frames))

                reference_frames = None
                if measurement.reference_fps and measurement.reference_fps > 0:
                    reference_frames = int(round(seconds_abs * measurement.reference_fps))

                measurement.frames = 0
                measurement.offset_seconds = 0.0

                def _describe(frames: Optional[int], seconds_val: float) -> str:
                    parts: List[str] = []
                    if frames is not None:
                        parts.append(f"{frames} frame(s)")
                    if not math.isnan(seconds_val):
                        parts.append(f"{seconds_val:.3f}s")
                    return " / ".join(parts) if parts else "0.000s"

                measured_desc = _describe(original_frames, seconds_abs)
                applied_desc = _describe(reference_frames, seconds_abs)
                note = (
                    f"Measured negative offset on {target_name}: {measured_desc}; "
                    f"applied to {reference_name} as +{applied_desc}."
                )
                negative_override_notes[target_name] = note
                negative_override_notes[reference_name] = note
                swap_details[target_name] = note
                swap_details[reference_name] = note

                if reference_name not in existing_keys:
                    additional_measurements.append(
                        audio_alignment.AlignmentMeasurement(
                            file=reference_plan.path,
                            offset_seconds=seconds_abs,
                            frames=reference_frames,
                            correlation=measurement.correlation,
                            reference_fps=measurement.reference_fps,
                            target_fps=measurement.reference_fps,
                        )
                    )
                    existing_keys.add(reference_name)

            measurements.extend(additional_measurements)

        raw_warning_messages: List[str] = []
        for measurement in measurements:
            reasons: List[str] = []
            if measurement.error:
                reasons.append(measurement.error)
            if abs(measurement.offset_seconds) > audio_cfg.max_offset_seconds:
                reasons.append(
                    f"offset {measurement.offset_seconds:.3f}s exceeds limit {audio_cfg.max_offset_seconds:.3f}s"
                )
            if measurement.correlation < audio_cfg.correlation_threshold:
                reasons.append(
                    f"correlation {measurement.correlation:.2f} below threshold {audio_cfg.correlation_threshold:.2f}"
                )
            if measurement.frames is None:
                reasons.append("unable to derive frame offset (missing fps)")

            if reasons:
                measurement.frames = None
                measurement.error = "; ".join(reasons)
                file_key = measurement.file.name
                negative_offsets.pop(file_key, None)
                label = name_to_label.get(file_key, file_key)
                raw_warning_messages.append(f"{label}: {measurement.error}")

        for warning_message in dict.fromkeys(raw_warning_messages):
            _warn(warning_message)

        suggested_frames: Dict[str, int] = {}
        for measurement in measurements:
            if measurement.frames is not None:
                suggested_frames[measurement.file.name] = int(measurement.frames)

        manual_trim_starts: Dict[str, int] = {}
        if vspreview_enabled:
            for plan in plans:
                if plan.has_trim_start_override and plan.trim_start > 0:
                    manual_trim_starts[plan.path.name] = int(plan.trim_start)
                    label = plan_labels.get(plan.path, plan.path.name)
                    display_data.manual_trim_lines.append(
                        f"Existing manual trim: {label} → {plan.trim_start}f"
                    )
            display_data.warnings.append(
                "[AUDIO] VSPreview manual alignment enabled — offsets reported for guidance only."
            )
            summary = _AudioAlignmentSummary(
                offsets_path=offsets_path,
                reference_name=reference_plan.path.name,
                measurements=measurements,
                applied_frames=dict(manual_trim_starts),
                baseline_shift=0,
                statuses={m.file.name: "suggested" for m in measurements},
                reference_plan=reference_plan,
                final_adjustments={},
                swap_details=swap_details,
                suggested_frames=suggested_frames,
                suggestion_mode=True,
                manual_trim_starts=manual_trim_starts,
            )
            detail_map = _compose_measurement_details(
                measurements,
                applied_frames_map=summary.applied_frames,
                statuses_map=summary.statuses,
                suggestion_mode_active=True,
                manual_trims=manual_trim_starts,
                swap_map=swap_details,
                negative_notes=negative_override_notes,
            )
            summary.measured_offsets = detail_map
            _emit_measurement_lines(
                detail_map,
                measurement_order,
                append_manual=bool(display_data.manual_trim_lines),
            )
            return summary, display_data

        applied_frames, statuses = audio_alignment.update_offsets_file(
            offsets_path,
            reference_plan.path.name,
            measurements,
            _load_existing_entries()[1],
            negative_override_notes,
        )

        final_map: Dict[str, int] = {reference_plan.path.name: 0}
        for name, frames in applied_frames.items():
            final_map[name] = frames

        baseline = min(final_map.values()) if final_map else 0
        baseline_shift = int(-baseline) if baseline < 0 else 0

        final_adjustments: Dict[str, int] = {}
        for plan in plans:
            desired = final_map.get(plan.path.name)
            if desired is None:
                continue
            adjustment = int(desired - baseline)
            if adjustment < 0:
                adjustment = 0
            if adjustment:
                plan.trim_start = max(0, plan.trim_start + adjustment)
                plan.alignment_frames = adjustment
                plan.alignment_status = statuses.get(plan.path.name, "auto")
            else:
                plan.alignment_frames = 0
                plan.alignment_status = statuses.get(plan.path.name, "auto") if plan.path.name in statuses else ""
            final_adjustments[plan.path.name] = adjustment

        if baseline_shift:
            for plan in plans:
                if plan is reference_plan:
                    plan.alignment_status = "baseline"

        summary = _AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name=reference_plan.path.name,
            measurements=measurements,
            applied_frames=applied_frames,
            baseline_shift=baseline_shift,
            statuses=statuses,
            reference_plan=reference_plan,
            final_adjustments=final_adjustments,
            swap_details=swap_details,
            suggested_frames=suggested_frames,
            suggestion_mode=False,
            manual_trim_starts=manual_trim_starts,
        )
        detail_map = _compose_measurement_details(
            measurements,
            applied_frames_map=applied_frames,
            statuses_map=statuses,
            suggestion_mode_active=False,
            manual_trims=manual_trim_starts,
            swap_map=swap_details,
            negative_notes=negative_override_notes,
        )
        summary.measured_offsets = detail_map
        _emit_measurement_lines(
            detail_map,
            measurement_order,
            append_manual=bool(display_data.manual_trim_lines),
        )
        return summary, display_data
    except audio_alignment.AudioAlignmentError as exc:
        raise CLIAppError(
            f"Audio alignment failed: {exc}",
            rich_message=f"[red]Audio alignment failed:[/red] {exc}",
        ) from exc


def _color_config_literal(color_cfg: ColorConfig) -> str:
    color_dict = asdict(color_cfg)
    items = ",\n    ".join(f"{key}={value!r}" for key, value in color_dict.items())
    return f"ColorConfig(\n    {items}\n)"


def _write_vspreview_script(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary,
    cfg: AppConfig,
    root: Path,
) -> Path:
    reference_plan = summary.reference_plan
    targets = [plan for plan in plans if plan is not reference_plan]
    script_dir = resolve_subdir(root, "vspreview", purpose="vspreview workspace")
    script_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    script_path = script_dir / f"vspreview_{timestamp}_{uuid.uuid4().hex[:8]}.py"
    while script_path.exists():
        logger.warning(
            "VSPreview script %s already exists; generating alternate filename to avoid overwriting",
            script_path.name,
        )
        script_path = script_dir / f"vspreview_{timestamp}_{uuid.uuid4().hex[:8]}.py"
    project_root = PROJECT_ROOT

    search_paths = [
        str(Path(path).expanduser())
        for path in getattr(cfg.runtime, "vapoursynth_python_paths", [])
        if path
    ]
    color_literal = _color_config_literal(cfg.color)

    preview_mode_value = _normalise_vspreview_mode(
        getattr(cfg.audio_alignment, "vspreview_mode", "baseline")
    )
    apply_seeded_offsets = preview_mode_value == "seeded"
    show_overlay = bool(getattr(cfg.audio_alignment, "show_suggested_in_preview", True))
    if summary.measured_offsets:
        measurement_lookup: Dict[str, Optional[float]] = {
            name: detail.offset_seconds for name, detail in summary.measured_offsets.items()
        }
    else:
        measurement_lookup = {
            measurement.file.name: measurement.offset_seconds
            for measurement in summary.measurements
        }

    manual_trims = {}
    if summary.manual_trim_starts:
        manual_trims = {
            _plan_label(plan): summary.manual_trim_starts.get(plan.path.name, 0)
            for plan in plans
        }
    else:
        manual_trims = {_plan_label(plan): int(plan.trim_start) for plan in plans if plan.trim_start > 0}

    reference_label = _plan_label(reference_plan)
    reference_trim_end = reference_plan.trim_end if reference_plan.trim_end is not None else None
    reference_info = textwrap.dedent(
        f"""\
        {{
        'label': {reference_label!r},
        'path': {str(reference_plan.path)!r},
        'trim_start': {int(reference_plan.trim_start)},
        'trim_end': {reference_trim_end!r},
        'fps_override': {tuple(reference_plan.fps_override) if reference_plan.fps_override else None!r},
        }}
        """
    ).strip()

    target_lines: list[str] = []
    offset_lines: list[str] = []
    suggestion_lines: list[str] = []
    if not targets:
        offset_lines.append("    # Add entries like 'Clip Label': 0 once targets are available.")
    for plan in targets:
        label = _plan_label(plan)
        trim_end_value = plan.trim_end if plan.trim_end is not None else None
        fps_override = tuple(plan.fps_override) if plan.fps_override else None
        suggested_frames_value = int(summary.suggested_frames.get(plan.path.name, 0))
        measurement_seconds = measurement_lookup.get(plan.path.name)
        suggested_seconds_value = 0.0
        if measurement_seconds is not None:
            suggested_seconds_value = float(measurement_seconds)
        manual_trim = manual_trims.get(label, int(plan.trim_start))
        manual_note = (
            f"baseline trim {manual_trim}f"
            if manual_trim
            else "no baseline trim"
        )
        target_lines.append(
            textwrap.dedent(
                f"""\
                {label!r}: {{
                    'label': {label!r},
                    'path': {str(plan.path)!r},
                    'trim_start': {int(plan.trim_start)},
                    'trim_end': {trim_end_value!r},
                    'fps_override': {fps_override!r},
                    'manual_trim': {manual_trim},
                    'manual_trim_description': {manual_note!r},
                }},"""
            ).rstrip()
        )
        applied_initial = suggested_frames_value if apply_seeded_offsets else 0
        offset_lines.append(
            f"    {label!r}: {applied_initial},  # Suggested delta {suggested_frames_value:+d}f"
        )
        suggestion_lines.append(
            f"    {label!r}: ({suggested_frames_value}, {suggested_seconds_value!r}),"
        )

    targets_literal = "\n".join(target_lines) if target_lines else ""
    offsets_literal = "\n".join(offset_lines)
    suggestions_literal = "\n".join(suggestion_lines)

    extra_paths = [
        str(project_root),
        str(project_root / "src"),
        str(root),
    ]
    extra_paths_literal = ", ".join(repr(path) for path in extra_paths)
    search_paths_literal = repr(search_paths)

    script = f"""# Auto-generated by Frame Compare to assist with VSPreview alignment.
import sys
from pathlib import Path

try:
    # Prefer UTF-8 on Windows consoles and avoid crashing on encoding errors.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WORKSPACE_ROOT = Path({str(root)!r})
PROJECT_ROOT = Path({str(project_root)!r})
EXTRA_PATHS = [{extra_paths_literal}]
for candidate in EXTRA_PATHS:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import vapoursynth as vs
from src import vs_core
from src.datatypes import ColorConfig

vs_core.configure(
    search_paths={search_paths_literal},
    source_preference={cfg.source.preferred!r},
)

COLOR_CFG = {color_literal}

REFERENCE = {reference_info}

TARGETS = {{
{targets_literal}
}}

OFFSET_MAP = {{
{offsets_literal}
}}

SUGGESTION_MAP = {{
{suggestions_literal}
}}

PREVIEW_MODE = {preview_mode_value!r}
SHOW_SUGGESTED_OVERLAY = {show_overlay!r}

core = vs.core


def safe_print(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("utf-8", "replace").decode("utf-8", "replace"))
        except Exception:
            print("[log message unavailable due to encoding]")


def _load_clip(info):
    clip = vs_core.init_clip(
        str(Path(info['path'])),
        trim_start=int(info.get('trim_start', 0)),
        trim_end=info.get('trim_end'),
        fps_map=tuple(info['fps_override']) if info.get('fps_override') else None,
    )
    processed = vs_core.process_clip_for_screenshot(
        clip,
        info['label'],
        COLOR_CFG,
        enable_overlay=False,
        enable_verification=False,
    ).clip
    return processed


def _apply_offset(reference_clip, target_clip, offset_frames):
    if offset_frames > 0:
        target_clip = target_clip[offset_frames:]
    elif offset_frames < 0:
        reference_clip = reference_clip[abs(offset_frames):]
    return reference_clip, target_clip


def _extract_fps_tuple(clip):
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return int(num), int(den)
    return None


def _harmonise_fps(reference_clip, target_clip, label):
    reference_fps = _extract_fps_tuple(reference_clip)
    target_fps = _extract_fps_tuple(target_clip)
    if not reference_fps or not target_fps:
        return reference_clip, target_clip
    if reference_fps == target_fps:
        return reference_clip, target_clip
    try:
        target_clip = target_clip.std.AssumeFPS(num=reference_fps[0], den=reference_fps[1])
        safe_print(
            "Adjusted FPS for target '%s' to match reference (%s/%s -> %s/%s)"
            % (
                label,
                target_fps[0],
                target_fps[1],
                reference_fps[0],
                reference_fps[1],
            )
        )
    except Exception as exc:
        safe_print("Warning: Failed to harmonise FPS for target '%s': %s" % (label, exc))
    return reference_clip, target_clip


def _format_overlay_text(label, suggested_frames, suggested_seconds, applied_frames):
    applied_label = "baseline" if applied_frames == 0 else "seeded"
    applied_value = "0" if applied_frames == 0 else f"{{applied_frames:+d}}"
    seconds_value = f"{{suggested_seconds:.3f}}"
    if seconds_value == "-0.000":
        seconds_value = "0.000"
    suggested_value = f"{{suggested_frames:+d}}"
    return (
        "{{label}}: {{suggested}}f (~{{seconds}}s) • "
        "Preview applied: {{applied}}f ({{status}}) • "
        "(+ trims target / - pads reference)"
    ).format(
        label=label,
        suggested=suggested_value,
        seconds=seconds_value,
        applied=applied_value,
        status=applied_label,
    )


def _maybe_apply_overlay(clip, label, suggested_frames, suggested_seconds, applied_frames):
    if not SHOW_SUGGESTED_OVERLAY:
        return clip
    try:
        message = _format_overlay_text(label, suggested_frames, suggested_seconds, applied_frames)
    except Exception:
        message = "Suggested offset unavailable"
    try:
        return clip.text.Text(message, alignment=7)
    except Exception as exc:
        safe_print("Warning: Failed to draw overlay text for preview: %s" % (exc,))
        return clip


safe_print("Reference clip: %s" % (REFERENCE['label'],))
safe_print("VSPreview mode: %s" % (PREVIEW_MODE,))
if not TARGETS:
    safe_print("No target clips defined; edit TARGETS and OFFSET_MAP to add entries.")

slot = 0
for label, info in TARGETS.items():
    reference_clip = _load_clip(REFERENCE)
    target_clip = _load_clip(info)
    reference_clip, target_clip = _harmonise_fps(reference_clip, target_clip, label)
    offset_frames = int(OFFSET_MAP.get(label, 0))
    suggested_entry = SUGGESTION_MAP.get(label, (0, 0.0))
    suggested_frames = int(suggested_entry[0])
    suggested_seconds = float(suggested_entry[1])
    ref_view, tgt_view = _apply_offset(reference_clip, target_clip, offset_frames)
    ref_view = _maybe_apply_overlay(
        ref_view,
        REFERENCE['label'],
        suggested_frames,
        suggested_seconds,
        offset_frames,
    )
    tgt_view = _maybe_apply_overlay(
        tgt_view,
        label,
        suggested_frames,
        suggested_seconds,
        offset_frames,
    )
    ref_view.set_output(slot)
    tgt_view.set_output(slot + 1)
    applied_label = "baseline" if offset_frames == 0 else "seeded"
    safe_print(
        "Target '%s': baseline trim=%sf (%s), suggested delta=%+df (~%+.3fs), preview applied=%+df (%s mode)"
        % (
            label,
            info.get('manual_trim', 0),
            info.get('manual_trim_description', 'n/a'),
            suggested_frames,
            suggested_seconds,
            offset_frames,
            applied_label,
        )
    )
    slot += 2

safe_print("VSPreview outputs: reference on even slots, target on odd slots (0<->1, 2<->3, ...).")
safe_print("Edit OFFSET_MAP values and press Ctrl+R in VSPreview to reload the script.")
"""
    script_path.write_text(textwrap.dedent(script), encoding="utf-8")
    return script_path


def _prompt_vspreview_offsets(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary,
    reporter: CliOutputManagerProtocol,
    display: _AudioAlignmentDisplayData | None,
) -> dict[str, int] | None:
    reference_plan = summary.reference_plan
    targets = [plan for plan in plans if plan is not reference_plan]
    if not targets:
        return {}

    baseline_map: Dict[str, int] = {
        plan.path.name: summary.manual_trim_starts.get(plan.path.name, int(plan.trim_start))
        for plan in plans
    }

    reference_label = _plan_label(reference_plan)
    reporter.line(
        "Enter VSPreview frame offsets relative to the reported baselines. Positive trims the target; negative advances the reference."
    )
    offsets: Dict[str, int] = {}
    for plan in targets:
        label = _plan_label(plan)
        baseline_value = baseline_map.get(plan.path.name, int(plan.trim_start))
        suggested = summary.suggested_frames.get(plan.path.name)
        prompt_parts = [
            f"VSPreview offset for {label} relative to {reference_label}",
            f"baseline {baseline_value}f",
        ]
        if suggested is not None:
            prompt_parts.append(f"suggested {suggested:+d}f")
        prompt_message = " (".join([prompt_parts[0], ", ".join(prompt_parts[1:])]) + ")"
        try:
            delta = int(
                click.prompt(
                    prompt_message,
                    type=int,
                    default=0,
                    show_default=True,
                )
            )
        except click.exceptions.Abort:
            reporter.warn("VSPreview offset entry aborted; keeping existing trims.")
            return None
        offsets[plan.path.name] = delta
        if display is not None:
            display.manual_trim_lines.append(
                f"Baseline for {label}: {baseline_value}f"
            )
    return offsets


def _apply_vspreview_manual_offsets(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary,
    deltas: Mapping[str, int],
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
    display: _AudioAlignmentDisplayData | None,
) -> None:
    reference_plan = summary.reference_plan
    reference_name = reference_plan.path.name
    targets = [plan for plan in plans if plan is not reference_plan]

    baseline_map: Dict[str, int] = {
        plan.path.name: summary.manual_trim_starts.get(plan.path.name, int(plan.trim_start))
        for plan in plans
    }
    if reference_name not in baseline_map:
        baseline_map[reference_name] = int(reference_plan.trim_start)

    manual_trim_starts: Dict[str, int] = {}
    delta_map: Dict[str, int] = {}
    manual_lines: List[str] = []

    desired_map: Dict[str, int] = {}
    target_adjustments: List[Tuple[_ClipPlan, int, int]] = []

    for plan in targets:
        key = plan.path.name
        baseline_value = baseline_map.get(key, int(plan.trim_start))
        delta_value = int(deltas.get(key, 0))
        desired_value = baseline_value + delta_value
        desired_map[key] = desired_value
        target_adjustments.append((plan, baseline_value, delta_value))

    reference_baseline = baseline_map.get(reference_name, int(reference_plan.trim_start))
    reference_delta_input = int(deltas.get(reference_name, 0))
    desired_map[reference_name] = reference_baseline + reference_delta_input

    baseline_min = min(baseline_map.values()) if baseline_map else 0
    desired_min = min(desired_map.values()) if desired_map else 0
    baseline_floor = baseline_min if baseline_min < 0 else 0
    desired_floor = desired_min if desired_min < 0 else 0
    shift = 0
    if desired_floor < baseline_floor:
        shift = baseline_floor - desired_floor

    for plan, baseline_value, delta_value in target_adjustments:
        key = plan.path.name
        desired_value = desired_map[key]
        updated = desired_value + shift
        updated_int = int(updated)
        safe_updated = max(0, updated_int)
        plan.trim_start = safe_updated
        plan.has_trim_start_override = (
            plan.has_trim_start_override or safe_updated != 0
        )
        manual_trim_starts[key] = updated_int
        applied_delta = updated_int - baseline_value
        delta_map[key] = applied_delta
        line = (
            f"VSPreview manual offset applied: {_plan_label(plan)} baseline {baseline_value}f "
            f"{delta_value:+d}f → {int(updated)}f"
        )
        manual_lines.append(line)
        reporter.line(line)

    adjusted_reference = desired_map[reference_name] + shift
    adjusted_reference_int = int(adjusted_reference)
    safe_adjusted_reference = max(0, adjusted_reference_int)
    reference_plan.trim_start = safe_adjusted_reference
    reference_plan.has_trim_start_override = (
        reference_plan.has_trim_start_override
        or safe_adjusted_reference != int(reference_baseline)
    )
    manual_trim_starts[reference_name] = adjusted_reference_int
    reference_delta = adjusted_reference_int - reference_baseline
    delta_map[reference_name] = reference_delta
    if reference_delta != 0:
        ref_line = (
            f"VSPreview reference adjustment: {_plan_label(reference_plan)} baseline {reference_baseline}f → {int(adjusted_reference)}f"
        )
        manual_lines.append(ref_line)
        reporter.line(ref_line)

    if display is not None:
        if display.manual_trim_lines is None:
            display.manual_trim_lines = []
        display.manual_trim_lines.extend(manual_lines)
        display.offset_lines = ["Audio offsets: VSPreview manual offsets applied"]
        display.offset_lines.extend(display.manual_trim_lines)

    fps_lookup: Dict[str, Tuple[int, int] | None] = {}
    for plan in plans:
        fps_lookup[plan.path.name] = (
            plan.effective_fps or plan.source_fps or plan.fps_override
        )

    measurement_order = [plan.path.name for plan in plans]
    plan_lookup: Dict[str, _ClipPlan] = {plan.path.name: plan for plan in plans}

    measurements: List["AlignmentMeasurement"] = []
    existing_override_map: Dict[str, Dict[str, object]] = {}
    notes_map: Dict[str, str] = {}
    for plan in plans:
        key = plan.path.name
        frames_value = int(manual_trim_starts.get(key, int(plan.trim_start)))
        fps_tuple = fps_lookup.get(key)
        fps_float = _fps_to_float(fps_tuple) if fps_tuple else 0.0
        seconds_value = float(frames_value) / fps_float if fps_float else 0.0
        measurements.append(
            audio_alignment.AlignmentMeasurement(
                file=plan.path,
                offset_seconds=seconds_value,
                frames=frames_value,
                correlation=1.0,
                reference_fps=fps_float or None,
                target_fps=fps_float or None,
            )
        )
        existing_override_map[key] = {"frames": frames_value, "status": "manual"}
        notes_map[key] = "VSPreview"

    applied_frames, statuses = audio_alignment.update_offsets_file(
        summary.offsets_path,
        reference_plan.path.name,
        tuple(measurements),
        existing_override_map,
        notes_map,
    )

    summary.applied_frames = dict(applied_frames)
    summary.statuses = dict(statuses)
    summary.final_adjustments = dict(manual_trim_starts)
    summary.manual_trim_starts = dict(manual_trim_starts)
    summary.suggestion_mode = False
    summary.vspreview_manual_offsets = dict(manual_trim_starts)
    summary.vspreview_manual_deltas = dict(delta_map)
    summary.measurements = tuple(measurements)

    existing_details = summary.measured_offsets if isinstance(summary.measured_offsets, dict) else {}
    detail_map: Dict[str, _AudioMeasurementDetail] = {}
    for measurement in measurements:
        clip_name = measurement.file.name
        prev_detail = existing_details.get(clip_name) if isinstance(existing_details, dict) else None
        plan = plan_lookup.get(clip_name)
        label = (
            prev_detail.label
            if prev_detail
            else (_plan_label(plan) if plan is not None else clip_name)
        )
        descriptor = prev_detail.stream if prev_detail else ""
        seconds_value = float(measurement.offset_seconds) if measurement.offset_seconds is not None else None
        frames_value = int(measurement.frames) if measurement.frames is not None else None
        correlation_value = (
            float(measurement.correlation) if measurement.correlation is not None else None
        )
        status_text = summary.statuses.get(clip_name, "manual")
        note_text = notes_map.get(clip_name)
        detail_map[clip_name] = _AudioMeasurementDetail(
            label=label,
            stream=descriptor,
            offset_seconds=seconds_value,
            frames=frames_value,
            correlation=correlation_value,
            status=status_text,
            applied=True,
            note=note_text,
        )
    summary.measured_offsets = detail_map

    audio_block = json_tail.setdefault("audio_alignment", {})
    audio_block["suggestion_mode"] = False
    audio_block["manual_trim_starts"] = dict(manual_trim_starts)
    audio_block["vspreview_manual_offsets"] = dict(manual_trim_starts)
    audio_block["vspreview_manual_deltas"] = dict(delta_map)
    audio_block["vspreview_reference_trim"] = int(
        manual_trim_starts.get(reference_name, int(reference_plan.trim_start))
    )

    if display is not None:
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}
        offset_lines: List[str] = []
        for clip_name in measurement_order:
            detail = detail_map.get(clip_name)
            if detail is None:
                continue
            if clip_name == reference_name and len(detail_map) > 1:
                continue
            stream_text = detail.stream or "?"
            seconds_text = (
                f"{detail.offset_seconds:+.3f}s"
                if detail.offset_seconds is not None
                else "n/a"
            )
            frames_text = f"{detail.frames:+d}f" if detail.frames is not None else "n/a"
            corr_text = (
                f"{detail.correlation:.2f}"
                if detail.correlation is not None and not math.isnan(detail.correlation)
                else "n/a"
            )
            status_text = detail.status or "manual"
            offset_lines.append(
                f"Audio offsets: {detail.label}: [{stream_text}] {seconds_text} ({frames_text}) "
                f"corr={corr_text} status={status_text}"
            )
            if detail.note:
                offset_lines.append(f"  note: {detail.note}")
            if detail.offset_seconds is not None:
                offsets_sec[detail.label] = float(detail.offset_seconds)
            if detail.frames is not None:
                offsets_frames[detail.label] = int(detail.frames)
        if not offset_lines:
            offset_lines.append("Audio offsets: VSPreview manual offsets applied")
        else:
            offset_lines.insert(0, "Audio offsets: VSPreview manual offsets applied")
        if display.manual_trim_lines:
            offset_lines.extend(display.manual_trim_lines)
        display.offset_lines = offset_lines
        display.json_offsets_sec = offsets_sec
        display.json_offsets_frames = offsets_frames
        display.measurements = {
            detail.label: detail for detail in detail_map.values()
        }
        display.correlations = {
            detail.label: detail.correlation
            for detail in detail_map.values()
            if detail.correlation is not None
        }

    reporter.line("VSPreview offsets saved to offsets file with manual status.")


def _resolve_vspreview_command(script_path: Path) -> tuple[list[str] | None, str | None]:
    """Return the VSPreview launch command or a reason string when unavailable."""

    executable = shutil.which("vspreview")
    if executable:
        return [executable, str(script_path)], None
    module_spec = importlib.util.find_spec("vspreview")
    if module_spec is None:
        return None, "vspreview-missing"
    backend_spec = importlib.util.find_spec("PySide6") or importlib.util.find_spec("PyQt5")
    if backend_spec is None:
        return None, "vspreview-missing"
    return [sys.executable, "-m", "vspreview", str(script_path)], None


def _activate_vspreview_missing_panel(
    reporter: CliOutputManagerProtocol,
    manual_command: str,
    *,
    reason: str,
) -> None:
    """Update layout state and render the VSPreview missing-dependency panel."""

    vspreview_block = _coerce_str_mapping(reporter.values.get("vspreview"))
    missing_block_obj = vspreview_block.get("missing")
    missing_block: dict[str, object]
    if isinstance(missing_block_obj, MappingABC):
        missing_block = _coerce_str_mapping(missing_block_obj)
    else:
        missing_block = {
            "windows_install": _VSPREVIEW_WINDOWS_INSTALL,
            "posix_install": _VSPREVIEW_POSIX_INSTALL,
        }
    if "windows_install" not in missing_block:
        missing_block["windows_install"] = _VSPREVIEW_WINDOWS_INSTALL
    if "posix_install" not in missing_block:
        missing_block["posix_install"] = _VSPREVIEW_POSIX_INSTALL
    missing_block["command"] = manual_command
    missing_block["reason"] = reason
    missing_block["active"] = True
    vspreview_block["missing"] = missing_block
    vspreview_block["script_command"] = manual_command
    reporter.update_values({"vspreview": vspreview_block})
    reporter.render_sections(["vspreview_missing"])


def _report_vspreview_missing(
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
    manual_command: str,
    *,
    reason: str,
) -> None:
    """Record missing VSPreview dependencies in layout output and JSON tail."""

    _activate_vspreview_missing_panel(reporter, manual_command, reason=reason)
    width_lines = [
        "VSPreview dependency missing. Install with:",
        f"  Windows: {_VSPREVIEW_WINDOWS_INSTALL}",
        f"  Linux/macOS: {_VSPREVIEW_POSIX_INSTALL}",
        f"Then run: {manual_command}",
    ]
    for line in width_lines:
        reporter.console.print(Text(line, no_wrap=True))
    reporter.warn(
        "VSPreview dependencies missing. Install with "
        f"'{_VSPREVIEW_WINDOWS_INSTALL}' (Windows) or "
        f"'{_VSPREVIEW_POSIX_INSTALL}' (Linux/macOS), then run "
        f"'{manual_command}'."
    )
    json_tail["vspreview_offer"] = {"vspreview_offered": False, "reason": reason}


def _launch_vspreview(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary | None,
    display: _AudioAlignmentDisplayData | None,
    cfg: AppConfig,
    root: Path,
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
) -> None:
    audio_block = _ensure_audio_alignment_block(json_tail)
    if "vspreview_script" not in audio_block:
        audio_block["vspreview_script"] = None
    if "vspreview_invoked" not in audio_block:
        audio_block["vspreview_invoked"] = False
    if "vspreview_exit_code" not in audio_block:
        audio_block["vspreview_exit_code"] = None

    if summary is None:
        reporter.warn("VSPreview skipped: no alignment summary available.")
        return

    if len(plans) < 2:
        reporter.warn("VSPreview skipped: need at least two clips to compare.")
        return

    script_path = _write_vspreview_script(plans, summary, cfg, root)
    audio_block["vspreview_script"] = str(script_path)
    reporter.console.print(
        f"[cyan]VSPreview script ready:[/cyan] {script_path}\n"
        "Edit the OFFSET_MAP values inside the script and reload VSPreview (Ctrl+R) after changes."
    )

    manual_command = _format_vspreview_manual_command(script_path)
    vspreview_block = _coerce_str_mapping(reporter.values.get("vspreview"))
    vspreview_block["script_path"] = str(script_path)
    vspreview_block["script_command"] = manual_command
    missing_block_obj = vspreview_block.get("missing")
    missing_block: dict[str, object]
    if isinstance(missing_block_obj, MappingABC):
        missing_block = _coerce_str_mapping(missing_block_obj)
    else:
        missing_block = {
            "windows_install": _VSPREVIEW_WINDOWS_INSTALL,
            "posix_install": _VSPREVIEW_POSIX_INSTALL,
        }
    missing_block["active"] = False
    if "windows_install" not in missing_block:
        missing_block["windows_install"] = _VSPREVIEW_WINDOWS_INSTALL
    if "posix_install" not in missing_block:
        missing_block["posix_install"] = _VSPREVIEW_POSIX_INSTALL
    missing_block["command"] = manual_command
    if "reason" not in missing_block:
        missing_block["reason"] = ""
    vspreview_block["missing"] = missing_block
    reporter.update_values({"vspreview": vspreview_block})

    if not sys.stdin.isatty():
        reporter.warn(
            "VSPreview launch skipped (non-interactive session). Open the script manually if needed."
        )
        return

    env = dict(os.environ)
    search_paths = getattr(cfg.runtime, "vapoursynth_python_paths", [])
    if search_paths:
        env["VAPOURSYNTH_PYTHONPATH"] = os.pathsep.join(str(Path(path).expanduser()) for path in search_paths if path)

    command, missing_reason = _resolve_vspreview_command(script_path)
    if command is None:
        _report_vspreview_missing(
            reporter,
            json_tail,
            manual_command,
            reason=missing_reason or "vspreview-missing",
        )
        return

    verbose_requested = bool(reporter.flags.get("verbose")) or bool(
        reporter.flags.get("debug")
    )

    try:
        if verbose_requested:
            result = subprocess.run(command, env=env, check=False)
        else:
            result = subprocess.run(
                command,
                env=env,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
    except FileNotFoundError:
        _report_vspreview_missing(
            reporter,
            json_tail,
            manual_command,
            reason="vspreview-missing",
        )
        return
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        logger.warning(
            "VSPreview launch failed: %s",
            exc,
            exc_info=True,
        )
        reporter.warn(f"VSPreview launch failed: {exc}")
        return
    audio_block["vspreview_invoked"] = True
    audio_block["vspreview_exit_code"] = int(result.returncode)
    captured_stdout = getattr(result, "stdout", None)
    captured_stderr = getattr(result, "stderr", None)
    if not verbose_requested:
        for stream_value, label in ((captured_stdout, "stdout"), (captured_stderr, "stderr")):
            if isinstance(stream_value, str) and stream_value.strip():
                logger.debug("VSPreview %s (suppressed): %s", label, stream_value.strip())
    if result.returncode != 0:
        reporter.warn(
            f"VSPreview exited with code {result.returncode}."
            + (" Re-run with --verbose to inspect VSPreview output." if not verbose_requested else "")
        )
        return

    offsets = _prompt_vspreview_offsets(plans, summary, reporter, display)
    if offsets is None:
        return
    _apply_vspreview_manual_offsets(plans, summary, offsets, reporter, json_tail, display)


def format_alignment_output(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary | None,
    display: _AudioAlignmentDisplayData | None,
    *,
    cfg: AppConfig,
    root: Path,
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
    vspreview_mode: str,
    collected_warnings: List[str] | None = None,
) -> None:
    """
    Populate json_tail/audio layout data and optionally launch VSPreview.
    """

    audio_block = _ensure_audio_alignment_block(json_tail)

    vspreview_target_plan: _ClipPlan | None = None
    vspreview_suggested_frames_value = 0
    vspreview_suggested_seconds_value = 0.0
    if summary is not None:
        for plan in plans:
            if plan is summary.reference_plan:
                continue
            vspreview_target_plan = plan
            break
        if vspreview_target_plan is not None:
            clip_key = vspreview_target_plan.path.name
            vspreview_suggested_frames_value = int(summary.suggested_frames.get(clip_key, 0))
            measurement_seconds: Optional[float] = None
            if summary.measured_offsets:
                detail = summary.measured_offsets.get(clip_key)
                if detail and detail.offset_seconds is not None:
                    measurement_seconds = float(detail.offset_seconds)
            if measurement_seconds is None and summary.measurements:
                measurement_lookup = {
                    measurement.file.name: measurement for measurement in summary.measurements
                }
                measurement = measurement_lookup.get(clip_key)
                if measurement is not None and measurement.offset_seconds is not None:
                    measurement_seconds = float(measurement.offset_seconds)
            if measurement_seconds is not None:
                vspreview_suggested_seconds_value = measurement_seconds

    json_tail["vspreview_mode"] = vspreview_mode
    json_tail["suggested_frames"] = int(vspreview_suggested_frames_value)
    json_tail["suggested_seconds"] = float(round(vspreview_suggested_seconds_value, 6))

    vspreview_enabled_for_session = _coerce_config_flag(cfg.audio_alignment.use_vspreview)
    if vspreview_enabled_for_session and summary is not None and summary.suggestion_mode:
        try:
            _launch_vspreview(
                plans,
                summary,
                display,
                cfg,
                root,
                reporter,
                json_tail,
            )
        except CLIAppError:
            raise
        except Exception as exc:
            logger.warning(
                "VSPreview launch failed: %s",
                exc,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            reporter.warn(f"VSPreview launch failed: {exc}")

    if display is not None:
        audio_block["offsets_filename"] = display.offsets_file_line.split(": ", 1)[-1]
        audio_block["reference_stream"] = display.json_reference_stream
        target_streams: dict[str, object] = dict(display.json_target_streams.items())
        audio_block["target_stream"] = target_streams
        offsets_sec_source = dict(display.json_offsets_sec)
        offsets_frames_source = dict(display.json_offsets_frames)
        if (
            not offsets_sec_source
            and summary is not None
            and summary.measured_offsets
        ):
            offsets_sec_source = {}
            offsets_frames_source = {}
            for detail in summary.measured_offsets.values():
                if detail.offset_seconds is not None:
                    offsets_sec_source[detail.label] = float(detail.offset_seconds)
                if detail.frames is not None:
                    offsets_frames_source[detail.label] = int(detail.frames)
        audio_block["offsets_sec"] = {key: float(value) for key, value in offsets_sec_source.items()}
        audio_block["offsets_frames"] = {
            key: int(value) for key, value in offsets_frames_source.items()
        }
        stream_lines_output = list(display.stream_lines)
        if display.estimation_line:
            stream_lines_output.append(display.estimation_line)
        audio_block["stream_lines"] = stream_lines_output
        audio_block["stream_lines_text"] = "\n".join(stream_lines_output) if stream_lines_output else ""
        offset_lines_output = list(display.offset_lines)
        audio_block["offset_lines"] = offset_lines_output
        audio_block["offset_lines_text"] = "\n".join(offset_lines_output) if offset_lines_output else ""
        measurement_source = dict(display.measurements)
        if (
            not measurement_source
            and summary is not None
            and summary.measured_offsets
        ):
            measurement_source = {
                detail.label: detail for detail in summary.measured_offsets.values()
            }
        measurements_output: dict[str, dict[str, object]] = {}
        for label, detail in measurement_source.items():
            measurements_output[label] = {
                "stream": detail.stream,
                "seconds": detail.offset_seconds,
                "frames": detail.frames,
                "correlation": detail.correlation,
                "status": detail.status,
                "applied": detail.applied,
                "note": detail.note,
            }
        audio_block["measurements"] = measurements_output
        if display.manual_trim_lines:
            audio_block["manual_trim_summary"] = list(display.manual_trim_lines)
        else:
            audio_block["manual_trim_summary"] = []
        if display.warnings and collected_warnings is not None:
            collected_warnings.extend(display.warnings)
    else:
        audio_block["reference_stream"] = None
        audio_block["target_stream"] = cast(dict[str, object], {})
        audio_block["offsets_sec"] = cast(dict[str, object], {})
        audio_block["offsets_frames"] = cast(dict[str, object], {})
        audio_block["manual_trim_summary"] = []
        audio_block["stream_lines"] = []
        audio_block["stream_lines_text"] = ""
        audio_block["offset_lines"] = []
        audio_block["offset_lines_text"] = ""
        audio_block["measurements"] = {}

    audio_block["enabled"] = bool(cfg.audio_alignment.enable)
    audio_block["suggestion_mode"] = bool(summary.suggestion_mode if summary else False)
    audio_block["suggested_frames"] = dict(summary.suggested_frames) if summary else {}
    audio_block["manual_trim_starts"] = dict(summary.manual_trim_starts) if summary else {}
    audio_block["vspreview_manual_offsets"] = (
        dict(summary.vspreview_manual_offsets) if summary else {}
    )
    audio_block["vspreview_manual_deltas"] = (
        dict(summary.vspreview_manual_deltas) if summary else {}
    )
    if (
        summary is not None
        and summary.vspreview_manual_offsets
        and summary.reference_plan.path.name in summary.vspreview_manual_offsets
    ):
        audio_block["vspreview_reference_trim"] = int(
            summary.vspreview_manual_offsets[summary.reference_plan.path.name]
        )
