"""AlignmentWorkflow service that wraps alignment_runner side effects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from src.datatypes import AppConfig
from src.frame_compare.cli_runtime import (
    AudioAlignmentDisplayData,
    AudioAlignmentSummary,
    CliOutputManagerProtocol,
    ClipPlan,
    JsonTail,
)

from .metadata import CliPromptProtocol

__all__ = [
    "AlignmentRequest",
    "AlignmentResult",
    "AlignmentWorkflow",
]


class ApplyAlignmentFn(Protocol):
    """Protocol describing apply_audio_alignment signature."""

    def __call__(
        self,
        plans: Sequence[ClipPlan],
        cfg: AppConfig,
        analyze_path: Path,
        root: Path,
        audio_track_overrides: Mapping[str, int],
        *,
        reporter: CliPromptProtocol | None,
    ) -> tuple[AudioAlignmentSummary | None, AudioAlignmentDisplayData | None]: ...


class FormatAlignmentFn(Protocol):
    """Protocol describing format_alignment_output signature."""

    def __call__(
        self,
        plans: Sequence[ClipPlan],
        summary: AudioAlignmentSummary | None,
        display: AudioAlignmentDisplayData | None,
        *,
        cfg: AppConfig,
        root: Path,
        reporter: CliPromptProtocol,
        json_tail: JsonTail,
        vspreview_mode: str,
        collected_warnings: list[str] | None,
    ) -> None: ...
ConfirmAlignmentFn = Callable[
    [
        Sequence[ClipPlan],
        AudioAlignmentSummary,
        AppConfig,
        Path,
        CliOutputManagerProtocol,
        AudioAlignmentDisplayData,
    ],
    None,
]


@dataclass(slots=True)
class AlignmentRequest:
    """Inputs required to execute the alignment workflow."""

    plans: Sequence[ClipPlan]
    cfg: AppConfig
    root: Path
    analyze_path: Path
    audio_track_overrides: Mapping[str, int]
    reporter: CliPromptProtocol
    json_tail: JsonTail
    vspreview_mode: str
    collected_warnings: list[str]


@dataclass(slots=True)
class AlignmentResult:
    """Outputs returned from alignment processing."""

    plans: list[ClipPlan]
    summary: AudioAlignmentSummary | None
    display: AudioAlignmentDisplayData | None


class AlignmentWorkflow:
    """Encapsulate audio-alignment orchestration."""

    def __init__(
        self,
        *,
        apply_alignment: ApplyAlignmentFn,
        format_output: FormatAlignmentFn,
        confirm_alignment: ConfirmAlignmentFn,
    ) -> None:
        self._apply_alignment = apply_alignment
        self._format_output = format_output
        self._confirm_alignment = confirm_alignment

    def run(self, request: AlignmentRequest) -> AlignmentResult:
        """Execute the alignment workflow and return the resulting context."""

        summary, display = self._apply_alignment(
            request.plans,
            request.cfg,
            request.analyze_path,
            request.root,
            request.audio_track_overrides,
            reporter=request.reporter,
        )
        self._format_output(
            request.plans,
            summary,
            display,
            cfg=request.cfg,
            root=request.root,
            reporter=request.reporter,
            json_tail=request.json_tail,
            vspreview_mode=request.vspreview_mode,
            collected_warnings=request.collected_warnings,
        )
        if (
            summary is not None
            and display is not None
            and request.cfg.audio_alignment.enable
            and not summary.suggestion_mode
        ):
            self._confirm_alignment(
                request.plans,
                summary,
                request.cfg,
                request.root,
                request.reporter,
                display,
            )
        return AlignmentResult(
            plans=list(request.plans),
            summary=summary,
            display=display,
        )
