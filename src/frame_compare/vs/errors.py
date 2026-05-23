"""VapourSynth subsystem error classes."""

from __future__ import annotations

from frame_compare.errors import DependencyError, ErrorContext


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


class LibplaceboError(DependencyError):
    """vs-placebo specific error (FC-2004)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2004",
                name="LIBPLACEBO_ERROR",
                message=f"Libplacebo error: {details}",
                hint="Check Vulkan drivers or shader support",
                details={"libplacebo_error": details},
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
