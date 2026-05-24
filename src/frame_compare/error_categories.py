"""Shared Frame Compare error category base classes."""

from __future__ import annotations

from frame_compare.error_context import FrameCompareError


class DependencyError(FrameCompareError):
    """Base class for dependency failures (VapourSynth, FFmpeg, plugins)."""


class InputError(FrameCompareError):
    """Base class for invalid input/arguments."""


class ProcessingError(FrameCompareError):
    """Base class for pipeline failures."""


class NetworkError(FrameCompareError):
    """Base class for network failures."""


class InternalError(FrameCompareError):
    """Base class for bugs/invariants."""


__all__ = [
    "DependencyError",
    "InputError",
    "InternalError",
    "NetworkError",
    "ProcessingError",
]
