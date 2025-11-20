"""Audio-alignment preview and confirmation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.datatypes import AppConfig
from src.frame_compare.cli_runtime import (
    AudioAlignmentDisplayData,
    AudioAlignmentSummary,
    CliOutputManagerProtocol,
    ClipPlan,
)

__all__ = ["_confirm_alignment_with_screenshots", "confirm_alignment_with_screenshots"]


def _confirm_alignment_with_screenshots(
    _plans: Sequence[ClipPlan],
    summary: AudioAlignmentSummary | None,
    _cfg: AppConfig,
    _root: Path,
    _reporter: CliOutputManagerProtocol,
    display: AudioAlignmentDisplayData | None,
) -> None:
    """
    Mark alignment as auto-confirmed when a display context is available.
    """

    if summary is None or display is None:
        return

    display.confirmation = display.confirmation or "auto"


confirm_alignment_with_screenshots = _confirm_alignment_with_screenshots
