"""Shared runtime helpers used by the runner without importing core."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from src.frame_compare.cli_runtime import coerce_str_mapping


def format_seconds(value: float) -> str:
    """
    Format seconds as ``HH:MM:SS.s`` with one decimal place.

    Negative input is treated as zero. The seconds component is rounded to one
    decimal place and carries into minutes/hours when it overflows.
    """
    total = max(0.0, float(value))
    hours = int(total // 3600)
    minutes = int((total - hours * 3600) // 60)
    seconds = total - hours * 3600 - minutes * 60
    seconds = round(seconds, 1)
    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        hours += 1
    return f"{hours:02d}:{minutes:02d}:{seconds:04.1f}"


def fps_to_float(value: tuple[int, int] | None) -> float:
    """Convert an ``(fps_num, fps_den)`` tuple into a float."""
    if not value:
        return 0.0
    num, den = value
    if not den:
        return 0.0
    return float(num) / float(den)


def format_clock(seconds: float | None) -> str:
    """Format seconds as ``H:MM:SS`` (or ``MM:SS``) with ``--:--`` for NaN/None."""
    if seconds is None or not math.isfinite(seconds):
        return "--:--"
    total = max(0, int(seconds + 0.5))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def fold_sequence(
    values: Sequence[object],
    *,
    head: int,
    tail: int,
    joiner: str,
    enabled: bool,
) -> str:
    """Fold long sequences with ``…`` while keeping the specified head/tail."""
    items = [str(item) for item in values]
    if not enabled or len(items) <= head + tail:
        return joiner.join(items)
    head_items = items[: max(0, head)]
    tail_items = items[-max(0, tail) :]
    if not head_items:
        return joiner.join(tail_items)
    if not tail_items:
        return joiner.join(head_items)
    return joiner.join([*head_items, "…", *tail_items])


def evaluate_rule_condition(condition: str | None, *, flags: Mapping[str, Any]) -> bool:
    """
    Evaluate a simple condition string (like ``verbose``/``!verbose``) against flags.
    """
    if not condition:
        return True
    expr = condition.strip()
    if not expr:
        return True
    if expr == "!verbose":
        return not bool(flags.get("verbose"))
    if expr == "verbose":
        return bool(flags.get("verbose"))
    if expr == "upload_enabled":
        return bool(flags.get("upload_enabled"))
    if expr == "!upload_enabled":
        return not bool(flags.get("upload_enabled"))
    return bool(flags.get(expr))


def build_legacy_summary_lines(values: Mapping[str, Any], *, emit_json_tail: bool) -> list[str]:
    """
    Generate the legacy textual summary lines used when the renderer lacks a summary section.
    """

    def _maybe_number(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_number(value: Any, fmt: str, fallback: str) -> str:
        number = _maybe_number(value)
        if number is None:
            return fallback
        return format(number, fmt)

    def _string(value: Any, fallback: str = "n/a") -> str:
        if value is None:
            return fallback
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _bool_text(value: Any) -> str:
        return "true" if bool(value) else "false"

    clips = coerce_str_mapping(values.get("clips"))
    window = coerce_str_mapping(values.get("window"))
    analysis = coerce_str_mapping(values.get("analysis"))
    counts = coerce_str_mapping(analysis.get("counts")) if analysis else {}
    audio = coerce_str_mapping(values.get("audio_alignment"))
    render = coerce_str_mapping(values.get("render"))
    tonemap = coerce_str_mapping(values.get("tonemap"))
    cache = coerce_str_mapping(values.get("cache"))

    lines: list[str] = []

    clip_count = _string(clips.get("count"), "0")
    lead_text = _format_number(window.get("ignore_lead_seconds"), ".2f", "0.00")
    trail_text = _format_number(window.get("ignore_trail_seconds"), ".2f", "0.00")
    step_text = _string(analysis.get("step"), "0")
    downscale_text = _string(analysis.get("downscale_height"), "0")
    lines.append(
        f"Clips: {clip_count}  Window: lead={lead_text}s trail={trail_text}s  step={step_text} downscale={downscale_text}px"
    )

    offsets_text = _format_number(audio.get("offsets_sec"), "+.3f", "+0.000")
    offsets_file = _string(audio.get("offsets_filename"), "n/a")
    lines.append(
        f"Align: audio={_bool_text(audio.get('enabled'))}  offsets={offsets_text}s  file={offsets_file}"
    )

    lines.append(
        "Plan: "
        f"Dark={_string(counts.get('dark'), '0')} "
        f"Bright={_string(counts.get('bright'), '0')} "
        f"Motion={_string(counts.get('motion'), '0')} "
        f"Random={_string(counts.get('random'), '0')} "
        f"User={_string(counts.get('user'), '0')}  "
        f"sep={_format_number(analysis.get('screen_separation_sec'), '.1f', '0.0')}s"
    )

    lines.append(
        "Canvas: "
        f"single_res={_string(render.get('single_res'), '0')} "
        f"upscale={_bool_text(render.get('upscale'))} "
        f"crop=mod{_string(render.get('mod_crop'), '0')} "
        f"pad={_bool_text(render.get('center_pad'))}"
    )

    tonemap_curve = _string(tonemap.get("tone_curve"), "n/a")
    tonemap_target = _format_number(tonemap.get("target_nits"), ".0f", "0")
    tonemap_dst_min = _format_number(tonemap.get("dst_min_nits"), ".2f", "0.00")
    tonemap_knee = _format_number(tonemap.get("knee_offset"), ".2f", "0.00")
    tonemap_preset_label = _string(tonemap.get("dpd_preset"), "n/a")
    tonemap_cutoff = _format_number(tonemap.get("dpd_black_cutoff"), ".3f", "0.000")
    tonemap_gamma = _format_number(tonemap.get("post_gamma"), ".2f", "1.00")
    gamma_flag = "*" if bool(tonemap.get("post_gamma_enabled")) else ""
    dpd_enabled = bool(
        tonemap.get("dpd")
        if "dpd" in tonemap
        else tonemap.get("dynamic_peak_detection")
    )
    preset_suffix = f" ({tonemap_preset_label})" if dpd_enabled and tonemap_preset_label.lower() != "n/a" else ""
    lines.append(
        "Tonemap: "
        f"{tonemap_curve}@{tonemap_target}nits "
        f"dst_min={tonemap_dst_min} knee={tonemap_knee} "
        f"dpd={_bool_text(dpd_enabled)}"
        f"{preset_suffix} black_cutoff={tonemap_cutoff}  "
        f"gamma={tonemap_gamma}{gamma_flag}  "
        f"verify≤{_format_number(tonemap.get('verify_luma_threshold'), '.2f', '0.00')}"
    )

    lines.append(
        f"Output: {_string(render.get('out_dir'), 'n/a')}  compression={_string(render.get('compression'), 'n/a')}"
    )

    lines.append(f"Cache: {_string(cache.get('file'), 'n/a')}  {_string(cache.get('status'), 'unknown')}")

    frame_count = _string(analysis.get("output_frame_count"), "0")
    preview = _string(analysis.get("output_frames_preview"), "")
    preview_display = f"[{preview}]" if preview else "[]"
    if emit_json_tail:
        lines.append(
            f"Output frames: {frame_count}  e.g., {preview_display}  (full list in JSON)"
        )
    else:
        full_list = _string(analysis.get("output_frames_full"), "[]")
        lines.append(f"Output frames ({frame_count}): {full_list}")

    return [line for line in lines if line]


__all__ = [
    "format_seconds",
    "fps_to_float",
    "format_clock",
    "fold_sequence",
    "evaluate_rule_condition",
    "build_legacy_summary_lines",
]
