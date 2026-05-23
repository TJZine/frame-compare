"""VSPreview-specific exception types for Frame Compare."""

from frame_compare.errors import DependencyError, ErrorContext, ProcessingError


class VSPreviewNotFoundError(DependencyError):
    """VSPreview not found (FC-2008)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2008",
                name="VSPREVIEW_NOT_FOUND",
                message="VSPreview not installed",
                hint="Install vspreview (and a Qt backend) for interactive alignment verification",
            )
        )


class VSPreviewError(ProcessingError):
    """VSPreview failed to launch or run (FC-4019)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4019",
                name="VSPREVIEW_ERROR",
                message=f"VSPreview error: {details}",
                hint="Install a Qt backend (PySide6/PyQt5) and ensure a GUI backend is available",
                details={"error": details},
            )
        )
