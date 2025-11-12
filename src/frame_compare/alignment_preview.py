"""Audio-alignment preview and confirmation helpers."""

from __future__ import annotations

import random
import re
import sys
from datetime import datetime as _dt
from pathlib import Path
from typing import List, Sequence

import click

from src.datatypes import AppConfig
from src.frame_compare.cli_runtime import (
    AudioAlignmentDisplayData,
    AudioAlignmentSummary,
    CLIAppError,
    CliOutputManagerProtocol,
    ClipPlan,
)
from src.frame_compare.vs import ClipProcessError
from src.screenshot import ScreenshotError, generate_screenshots

from .preflight import resolve_subdir

__all__ = ["_confirm_alignment_with_screenshots", "confirm_alignment_with_screenshots"]


def _pick_preview_frames(clip: object, count: int, seed: int) -> List[int]:
    """
    Select preview frame indices evenly spread across a clip when possible.

    If the clip exposes an integer ``num_frames`` attribute, indices are spaced across the clip.
    Otherwise, the first ``count`` indices are returned.
    """

    total = getattr(clip, "num_frames", 0)
    if not isinstance(total, int) or total <= 0:
        return [i for i in range(count)]
    if total <= count:
        return list(range(total))
    step = max(total // (count + 1), 1)
    frames = [min(total - 1, step * (idx + 1)) for idx in range(count)]
    deduped = sorted(set(frames))
    while len(deduped) < count:
        next_frame = min(total - 1, deduped[-1] + 1 if deduped else 0)
        if next_frame not in deduped:
            deduped.append(next_frame)
        else:
            break
    return deduped[:count]


def _sample_random_frames(clip: object, count: int, seed: int, exclude: Sequence[int]) -> List[int]:
    """
    Select a deterministic sample of frame indices from a clip, excluding specified indices.
    """

    total = getattr(clip, "num_frames", 0)
    if not isinstance(total, int) or total <= 0:
        return [i for i in range(count)]
    exclude_set = set(exclude)
    available = [idx for idx in range(total) if idx not in exclude_set]
    if not available:
        return list(range(min(count, total)))
    rng = random.Random(seed)
    if len(available) <= count:
        return sorted(available)
    return sorted(rng.sample(available, count))


def _confirm_alignment_with_screenshots(
    plans: Sequence[ClipPlan],
    summary: AudioAlignmentSummary | None,
    cfg: AppConfig,
    root: Path,
    reporter: CliOutputManagerProtocol,
    display: AudioAlignmentDisplayData | None,
) -> None:
    """
    Prompt the user to confirm audio alignment by generating preview screenshots.
    """

    if summary is None or display is None:
        return
    if not cfg.audio_alignment.confirm_with_screenshots:
        display.confirmation = display.confirmation or "auto"
        return

    def _alignment_pivot_note(message: str) -> None:
        reporter.console.log(message, markup=False)

    clips = [plan.clip for plan in plans]
    if any(clip is None for clip in clips):
        display.confirmation = display.confirmation or "auto"
        return

    reference_clip = summary.reference_plan.clip
    if reference_clip is None:
        display.confirmation = display.confirmation or "auto"
        return

    timestamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    base_dir = resolve_subdir(root, cfg.screenshots.directory_name, purpose="screenshots.directory_name")
    metadata = summary.reference_plan.metadata
    name_candidates = [
        metadata.get("label"),
        metadata.get("title"),
        metadata.get("anime_title"),
        metadata.get("file_name"),
        summary.reference_name,
        summary.reference_plan.path.stem,
    ]
    base_name = next((str(value).strip() for value in name_candidates if value and str(value).strip()), "clip")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._-") or "clip"
    preview_folder = f"{safe_name}-{timestamp}"
    preview_dir = (base_dir / "audio_alignment" / preview_folder).resolve()

    initial_frames = _pick_preview_frames(reference_clip, 2, cfg.audio_alignment.random_seed)

    try:
        generated = generate_screenshots(
            clips,
            initial_frames,
            [str(plan.path) for plan in plans],
            [plan.metadata for plan in plans],
            preview_dir,
            cfg.screenshots,
            cfg.color,
            trim_offsets=[plan.trim_start for plan in plans],
            pivot_notifier=_alignment_pivot_note,
            debug_color=bool(getattr(cfg.color, "debug_color", False)),
        )
    except ClipProcessError as exc:
        hint = "Run 'frame-compare doctor' for dependency diagnostics."
        raise CLIAppError(
            f"Alignment preview failed: {exc}\nHint: {hint}",
            rich_message=f"[red]Alignment preview failed:[/red] {exc}\n[yellow]Hint:[/yellow] {hint}",
        ) from exc
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Alignment preview failed: {exc}",
            rich_message=f"[red]Alignment preview failed:[/red] {exc}",
        ) from exc

    preview_paths = [str(path) for path in generated]
    display.preview_paths = preview_paths
    if preview_paths:
        reporter.line(f"Preview saved: {', '.join(preview_paths)}")

    reporter.line("Awaiting alignment confirmation. (press y/n)")

    if not sys.stdin.isatty():  # pragma: no cover - runtime-dependent
        display.confirmation = "auto"
        reporter.line("confirm=auto")
        display.warnings.append("[AUDIO] Audio alignment confirmation skipped (non-interactive session).")
        return

    if click.confirm(
        "Do the preview frames look aligned?",
        default=True,
        show_default=True,
    ):
        display.confirmation = "yes"
        reporter.line("confirm=yes")
        return

    display.confirmation = "no"
    reporter.line("confirm=no")

    inspection_dir = preview_dir / "inspection"
    extra_frames = _sample_random_frames(
        reference_clip,
        5,
        cfg.audio_alignment.random_seed + 1,
        exclude=initial_frames,
    )
    try:
        extra_paths = generate_screenshots(
            clips,
            extra_frames,
            [str(plan.path) for plan in plans],
            [plan.metadata for plan in plans],
            inspection_dir,
            cfg.screenshots,
            cfg.color,
            trim_offsets=[plan.trim_start for plan in plans],
            pivot_notifier=_alignment_pivot_note,
            debug_color=bool(getattr(cfg.color, "debug_color", False)),
        )
    except ClipProcessError as exc:
        hint = "Run 'frame-compare doctor' for dependency diagnostics."
        raise CLIAppError(
            f"Alignment inspection failed: {exc}\nHint: {hint}",
            rich_message=f"[red]Alignment inspection failed:[/red] {exc}\n[yellow]Hint:[/yellow] {hint}",
        ) from exc
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Alignment inspection failed: {exc}",
            rich_message=f"[red]Alignment inspection failed:[/red] {exc}",
        ) from exc


    if extra_paths:
        reporter.line(
            f"Additional inspection frames saved: {', '.join(str(path) for path in extra_paths)}"
        )

    display.inspection_paths = [str(path) for path in extra_paths]
    display.warnings.append(
        "[AUDIO] Alignment rejected; additional inspection frames rendered for manual review."
    )

    reporter.console.print(
        "[yellow]Audio alignment not confirmed.[/yellow] Adjust the offsets in the generated file and rerun."
    )
    try:
        click.launch(str(summary.offsets_path))
    except Exception:
        reporter.console.print(f"[yellow]Open and edit:[/yellow] {summary.offsets_path}")

    raise CLIAppError(
        "Audio alignment requires manual adjustment.",
        rich_message=(
            "[red]Audio alignment requires manual adjustment.[/red] "
            f"Edit {summary.offsets_path} and rerun."
        ),
    )


confirm_alignment_with_screenshots = _confirm_alignment_with_screenshots
