"""Consolidated FPS diagnostics reporting helpers."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import structlog

from frame_compare.orchestration.context import ClipState

log = structlog.get_logger()


@dataclass(frozen=True)
class FpsReportClip:
    """Immutable per-clip FPS diagnostics entry."""

    path: Path
    label: str
    source_fps: Fraction
    effective_fps: Fraction
    fps_divergent: bool
    note: str | None


def build_consolidated_fps_report(
    reference: ClipState, comparisons: Sequence[ClipState]
) -> tuple[FpsReportClip, ...]:
    """Return a deterministic, ordered per-clip FPS report.

    Reference first, then comparisons in input order.
    """
    ordered = [reference, *comparisons]
    clips: list[FpsReportClip] = []
    for clip in ordered:
        clips.append(
            FpsReportClip(
                path=clip.path,
                label=clip.label,
                source_fps=clip.source_fps,
                effective_fps=clip.effective_fps,
                fps_divergent=clip.effective_fps != clip.source_fps,
                note=None,
            )
        )
    return tuple(clips)


def _fraction_parts(value: Fraction) -> tuple[int, int]:
    return value.numerator, value.denominator


def _serialize_clip(clip: FpsReportClip) -> dict[str, Any]:
    source_num, source_den = _fraction_parts(clip.source_fps)
    effective_num, effective_den = _fraction_parts(clip.effective_fps)
    return {
        "path": str(clip.path),
        "label": clip.label,
        "source_fps_num": source_num,
        "source_fps_den": source_den,
        "effective_fps_num": effective_num,
        "effective_fps_den": effective_den,
        "fps_divergent": clip.fps_divergent,
        "note": clip.note,
    }


def _format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def emit_consolidated_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    json_output: bool,
    quiet: bool,
) -> None:
    """Emit the consolidated FPS report in JSON or human-readable form."""
    if quiet:
        return

    if json_output:
        payload = [_serialize_clip(clip) for clip in clips]
        log.info("fps_report", stage=stage, clips=payload)
        return

    print(f"FPS report ({stage})", file=sys.stderr)
    for clip in clips:
        note = clip.note if clip.note is not None else "-"
        print(
            f"- {clip.label}: {clip.path} | source={_format_fraction(clip.source_fps)} "
            f"effective={_format_fraction(clip.effective_fps)} divergent={clip.fps_divergent} "
            f"note={note}",
            file=sys.stderr,
        )
