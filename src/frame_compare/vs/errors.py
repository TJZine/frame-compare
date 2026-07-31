"""Video-source-specific exception types for Frame Compare."""

from __future__ import annotations

from pathlib import Path

from frame_compare.errors import DependencyError, ErrorContext, ProcessingError


class VapourSynthNotFoundError(DependencyError):
    """VapourSynth module not found (FC-2001)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2001",
                name="VAPOURSYNTH_NOT_FOUND",
                message="VapourSynth python module not found",
                hint="Install VapourSynth (pip install VapourSynth) or check PYTHONPATH",
            )
        )


class VapourSynthError(DependencyError):
    """VapourSynth core error (FC-2002)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2002",
                name="VAPOURSYNTH_ERROR",
                message=f"VapourSynth core error: {details}",
                hint="Check script syntax or plugin compatibility",
                details={"vs_error": details},
            )
        )


class PluginNotFoundError(DependencyError):
    """VapourSynth plugin missing (FC-2003)."""

    def __init__(self, namespace: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2003",
                name="PLUGIN_NOT_FOUND",
                message=f"Required VapourSynth plugin missing: {namespace}",
                hint=f"Install plugin providing namespace '{namespace}'",
                details={"namespace": namespace},
            )
        )


class TonemapRequiresVapourSynthError(DependencyError):
    """HDR tonemapping requires VapourSynth rendering (FC-2009)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2009",
                name="TONEMAP_REQUIRES_VAPOURSYNTH",
                message="HDR tonemapping requires VapourSynth rendering",
                hint="Disable [color].enable_tonemap for FFmpeg-only extraction, or use VapourSynth",
            )
        )


class SourceLoadError(ProcessingError):
    """Failed to initialize source engine (FC-4015)."""

    def __init__(self, path: Path, engine_error: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4015",
                name="SOURCE_LOAD_ERROR",
                message=f"Failed to load source {path}: {engine_error}",
                hint="Check file integrity or engine support",
                details={"path": str(path), "engine_error": engine_error},
            )
        )


class TonemapError(ProcessingError):
    """Tonemapping failure (FC-4003)."""

    def __init__(self, reason: str, hint: str | None = None) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4003",
                name="TONEMAP_ERROR",
                message=f"Tonemapping failed: {reason}",
                hint=hint or "Check libplacebo support or config",
                details={"reason": reason},
            )
        )
