"""Exception hierarchy for the tonemapping subsystem."""

from __future__ import annotations

from dataclasses import dataclass


class TonemapError(RuntimeError):
    """Base class for all tonemapping related failures."""


class HDRDetectError(TonemapError):
    """Raised when HDR detection cannot determine an input state."""


class VerificationError(TonemapError):
    """Raised when verification metrics cannot be computed."""


@dataclass(slots=True)
class TonemapConfigError(TonemapError):
    """Raised when tonemap configuration fails validation."""

    field: str
    problem: str

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.field}: {self.problem}"
