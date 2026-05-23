"""FFmpeg exception types shared by runtime owners."""

from frame_compare.errors import DependencyError, ErrorContext


class FFmpegNotFoundError(DependencyError):
    """FFmpeg binary not found (FC-2005)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2005",
                name="FFMPEG_NOT_FOUND",
                message="FFmpeg binary not found in PATH",
                hint="Install FFmpeg and add to system PATH",
            )
        )


class FFmpegError(DependencyError):
    """FFmpeg execution failed (FC-2006)."""

    def __init__(self, stderr: str, returncode: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2006",
                name="FFMPEG_ERROR",
                message=f"FFmpeg failed with exit code {returncode}",
                hint="Check input file validity or codec support",
                details={"returncode": returncode, "stderr": stderr},
            )
        )
