from __future__ import annotations

__all__ = ["ScreenshotError", "ScreenshotGeometryError", "ScreenshotWriterError"]


class ScreenshotError(RuntimeError):
    """Base class for screenshot related issues."""


class ScreenshotGeometryError(ScreenshotError):
    """Raised when geometry or cropping cannot be satisfied."""


class ScreenshotWriterError(ScreenshotError):
    """Raised when exporting screenshots or overlays fails."""
