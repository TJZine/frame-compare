"""Producer-authored warnings carried through a run without parsing display text."""

from dataclasses import dataclass
from typing import Literal

type WarningSource = Literal[
    "alignment",
    "frame selection",
    "render",
    "sources",
    "analysis",
    "active-rect auto detection",
    "analysis source",
    "slow.pics",
    "cleanup",
    "history",
]
type WarningSeverity = Literal["warning", "skipped"]


@dataclass(frozen=True, slots=True)
class RunWarning:
    source: WarningSource
    severity: WarningSeverity
    message: str
    detail: str | None = None

    @property
    def text(self) -> str:
        """Project the exact producer-authored text at an emitted-string boundary."""
        return self.message if self.detail is None else f"{self.message} {self.detail}"
