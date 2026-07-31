"""Render-owned exception types."""

from pathlib import Path

from frame_compare.errors import ErrorContext, ErrorDetails, ProcessingError


class FrameExtractionError(ProcessingError):
    """Failed to extract specific frame (FC-4001)."""

    def __init__(self, frame_number: int, clip_name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4001",
                name="FRAME_EXTRACTION_ERROR",
                message=f"Failed to extract frame {frame_number} from {clip_name}",
                hint="Check source reliability/seekability",
                details={"frame": frame_number, "clip": clip_name},
            )
        )


class RenderError(ProcessingError):
    """Composition/image encoding failure (FC-4004)."""

    def __init__(self, reason: str | None = None, details: ErrorDetails | None = None) -> None:
        message = "Final render composition failed"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(
            ErrorContext(
                code="FC-4004",
                name="RENDER_ERROR",
                message=message,
                hint=(
                    "Check clip pixel format/bit depth compatibility (screenshots require RGB24/RGBA8) "
                    "and verify the output path is writable"
                ),
                details=details,
            )
        )


class EncodingError(ProcessingError):
    """Output file encoding failed (FC-4013)."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4013",
                name="ENCODING_ERROR",
                message=f"Failed to encode output {path}: {reason}",
                hint="Check disk space or write permissions",
                details={"path": str(path), "reason": reason},
            )
        )


class OverlayError(ProcessingError):
    """Failed to render text overlay (FC-4014)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4014",
                name="OVERLAY_ERROR",
                message=f"Overlay rendering failed: {reason}",
                hint="Check font availability",
                details={"reason": reason},
            )
        )
