"""Configuration schema enums."""

from __future__ import annotations

from enum import StrEnum

# Most enums use lowercase string values (Pydantic accepts lowercase only).
# Exception: LogLevel uses uppercase values per standard Python logging convention.


class OverlayMode(StrEnum):
    """Overlay verbosity level for rendered screenshots."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    DIAGNOSTIC = "diagnostic"
    NONE = "none"


class ScreenshotGeometryMode(StrEnum):
    """Geometry planning mode for rendered screenshots."""

    NATIVE = "native"
    ALIGNED = "aligned"


class ScreenshotActiveRectDetection(StrEnum):
    """Active-image rectangle detection policy for aligned screenshots."""

    PROVIDED = "provided"
    DIMENSION = "dimension"
    ASPECT_RATIO = "aspect_ratio"


class ScreenshotAlignedScalePolicy(StrEnum):
    """Canvas target policy for aligned screenshots."""

    LARGEST_ACTIVE = "largest_active"
    SMALLEST_ACTIVE = "smallest_active"
    REFERENCE_ACTIVE = "reference_active"
    EXPLICIT_SIZE = "explicit_size"


class SourceMatchFpsMode(StrEnum):
    """Source FPS matching policy for mixed-FPS inputs."""

    DISABLED = "disabled"
    ASSUME_REFERENCE = "assume_reference"
    MAJORITY = "majority"


class VsScreenshotWriter(StrEnum):
    """VapourSynth screenshot writer selection."""

    AUTO = "auto"
    PILLOW = "pillow"
    FPNG = "fpng"


class TonemapPreset(StrEnum):
    """Named tonemap preset applied when tonemapping HDR to SDR."""

    REFERENCE = "reference"
    FILMIC = "filmic"
    CONTRAST = "contrast"
    BT2390_SPEC = "bt2390_spec"
    SPLINE = "spline"
    BRIGHT_LIFT = "bright_lift"
    HIGHLIGHT_GUARD = "highlight_guard"


class ToneCurve(StrEnum):
    """Tone curve algorithm used by the tonemap implementation."""

    BT2390 = "bt2390"
    SPLINE = "spline"
    REINHARD = "reinhard"


class Visibility(StrEnum):
    """slow.pics gallery visibility setting."""

    PUBLIC = "public"
    UNLISTED = "unlisted"


class ViewerMode(StrEnum):
    """Default comparison viewer mode for generated HTML reports."""

    SLIDER = "slider"
    OVERLAY = "overlay"
    DIFF = "diff"
    BLINK = "blink"


class LogLevel(StrEnum):
    """Log level using uppercase values per Python logging convention."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogFormat(StrEnum):
    """Logging output format."""

    JSON = "json"
    CONSOLE = "console"


__all__ = [
    "LogFormat",
    "LogLevel",
    "OverlayMode",
    "ScreenshotActiveRectDetection",
    "ScreenshotAlignedScalePolicy",
    "ScreenshotGeometryMode",
    "SourceMatchFpsMode",
    "ToneCurve",
    "TonemapPreset",
    "ViewerMode",
    "Visibility",
    "VsScreenshotWriter",
]
