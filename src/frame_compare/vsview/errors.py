"""VSView-specific exception types for Frame Compare."""

from frame_compare.errors import DependencyError, ErrorContext, ProcessingError


class VSViewNotFoundError(DependencyError):
    """VSView not found (FC-2008)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2008",
                name="VSVIEW_NOT_FOUND",
                message="VSView alignment-review environment is unavailable",
                hint=(
                    "Install frame-compare[vsview] so VSView, PySide6, and the "
                    "Frame Compare panel share one Python environment"
                ),
            )
        )


class VSViewError(ProcessingError):
    """VSView failed to launch or run (FC-4019)."""

    def __init__(
        self,
        reason: str,
        *,
        missing_module: str | None = None,
        command: tuple[str, ...] = (),
        returncode: int | None = None,
        startup_stderr: str | None = None,
    ) -> None:
        self.public_reason = reason
        self.missing_module = missing_module
        self.command = command
        self.returncode = returncode
        self.startup_stderr = startup_stderr
        super().__init__(
            ErrorContext(
                code="FC-4019",
                name="VSVIEW_ERROR",
                message=f"VSView failed: {reason}",
                hint=(
                    "Install frame-compare[vsview] in this environment and ensure a GUI "
                    "backend is available"
                ),
            )
        )
