from pathlib import Path

import pytest
from rich.console import Console

from frame_compare.analysis.errors import (
    AnalysisError,
    InsufficientFramesError,
    MetricsCalculationError,
    SelectionError,
)
from frame_compare.cli.errors import (
    ExitCode,
    format_error_console,
    format_error_json,
    get_exit_code,
)
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.errors import (
    DirectoryNotWritableError,
    DoviError,
    DoviToolNotFoundError,
    ErrorContext,
    FileTooLargeError,
    FrameCompareError,
    GenericInternalError,
    IncompatibleVideosError,
    InvariantViolationError,
    PathEscapesRootError,
    ProcessingOutOfMemoryError,
    ProcessingTimeoutError,
    PythonVersionError,
    UnexpectedStateError,
    VideoCorruptError,
    VideoOpenError,
)
from frame_compare.orchestration.errors import (
    DirectoryNotFoundError,
    InputDiscoveryError,
    NoVideosFoundError,
)
from frame_compare.render.errors import (
    EncodingError,
    FrameExtractionError,
    OverlayError,
    RenderError,
)
from frame_compare.services.errors import (
    AudioAlignmentError,
    MetadataError,
    NetworkTimeoutError,
    NetworkUnreachableError,
    ReportError,
    SlowpicsError,
    SlowpicsRateLimitedError,
    SlowpicsUnavailableError,
    SSLError,
    TmdbError,
    TmdbRateLimitedError,
)
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.vs.errors import (
    LibplaceboError,
    PluginNotFoundError,
    SourceLoadError,
    TonemapError,
    TonemapRequiresVapourSynthError,
    VapourSynthError,
    VapourSynthNotFoundError,
)
from frame_compare.vspreview.errors import (
    VSPreviewError,
    VSPreviewNotFoundError,
)


def _render_rich_markup(markup: str) -> str:
    console = Console(record=True, no_color=True, width=200)
    console.print(markup)
    return console.export_text(styles=False)


@pytest.mark.parametrize(
    "error_class,args,expected_code",
    [
        # DependencyError (FC-2xxx)
        (VapourSynthNotFoundError, (), "FC-2001"),
        (VapourSynthError, ("test",), "FC-2002"),
        (PluginNotFoundError, ("lsmas",), "FC-2003"),
        (LibplaceboError, ("test",), "FC-2004"),
        (FFmpegNotFoundError, (), "FC-2005"),
        (FFmpegError, ("test", 1), "FC-2006"),
        (DoviToolNotFoundError, (), "FC-2007"),
        (VSPreviewNotFoundError, (), "FC-2008"),
        (TonemapRequiresVapourSynthError, (), "FC-2009"),
        (PythonVersionError, ("3.11",), "FC-2010"),
        # InputError (FC-3xxx)
        (NoVideosFoundError, (Path("/test"),), "FC-3001"),
        (VideoOpenError, (Path("/test"),), "FC-3002"),
        (VideoCorruptError, (Path("/test"),), "FC-3003"),
        (InsufficientFramesError, (Path("/test"), 10, 20), "FC-3004"),
        (IncompatibleVideosError, ("test",), "FC-3005"),
        (DirectoryNotFoundError, (Path("/test"),), "FC-3006"),
        (DirectoryNotWritableError, (Path("/test"),), "FC-3007"),
        (FileTooLargeError, (Path("/test"), 100, 50), "FC-3008"),
        (PathEscapesRootError, (Path("/root"), Path("/other")), "FC-3009"),
        # ProcessingError (FC-4xxx)
        (FrameExtractionError, (42, "clip.mkv"), "FC-4001"),
        (MetricsCalculationError, ("test",), "FC-4002"),
        (TonemapError, ("test",), "FC-4003"),
        (RenderError, (), "FC-4004"),
        (AudioAlignmentError, ("test",), "FC-4005"),
        (CacheCorruptionError, (Path("/cache"),), "FC-4006"),
        (CacheVersionMismatchError, ("1.0", "2.0"), "FC-4007"),
        (ProcessingOutOfMemoryError, (), "FC-4010"),
        (ProcessingTimeoutError, ("op", 30.0), "FC-4011"),
        (SelectionError, ("reason", 10, 5), "FC-4012"),
        (EncodingError, (Path("/out.png"), "test"), "FC-4013"),
        (OverlayError, ("test",), "FC-4014"),
        (SourceLoadError, (Path("/src"), "test"), "FC-4015"),
        (MetadataError, ("test",), "FC-4016"),
        (ReportError, ("test",), "FC-4017"),
        (DoviError, (Path("/dv"), "test"), "FC-4018"),
        (VSPreviewError, ("test",), "FC-4019"),
        # NetworkError (FC-5xxx)
        (NetworkUnreachableError, (), "FC-5001"),
        (SlowpicsError, ("test",), "FC-5002"),
        (SlowpicsRateLimitedError, (), "FC-5003"),
        (SlowpicsUnavailableError, (), "FC-5004"),
        (TmdbError, ("test",), "FC-5005"),
        (TmdbRateLimitedError, (), "FC-5006"),
        (NetworkTimeoutError, ("slow.pics", 30.0), "FC-5007"),
        (SSLError, ("test",), "FC-5008"),
        # InternalError (FC-9xxx)
        (GenericInternalError, ("test",), "FC-9001"),
        (InvariantViolationError, ("test",), "FC-9002"),
        (UnexpectedStateError, ("test",), "FC-9003"),
    ],
)
def test_exception_class_contract(error_class, args, expected_code):
    """Every exception has correct code, non-empty name, non-empty hint, valid to_dict()."""
    error = error_class(*args)
    assert error.code == expected_code
    assert error.name
    assert error.hint
    ctx_dict = error.context.to_dict()
    assert ctx_dict["code"] == expected_code
    assert "message" in ctx_dict


@pytest.mark.parametrize(
    "error_class,owner_module",
    [
        (MetricsCalculationError, "frame_compare.analysis.errors"),
        (NoVideosFoundError, "frame_compare.orchestration.errors"),
        (DirectoryNotFoundError, "frame_compare.orchestration.errors"),
        (InputDiscoveryError, "frame_compare.orchestration.errors"),
        (FrameExtractionError, "frame_compare.render.errors"),
        (RenderError, "frame_compare.render.errors"),
        (EncodingError, "frame_compare.render.errors"),
        (OverlayError, "frame_compare.render.errors"),
        (CacheCorruptionError, "frame_compare.utils.cache_errors"),
        (CacheVersionMismatchError, "frame_compare.utils.cache_errors"),
        (FFmpegNotFoundError, "frame_compare.utils.ffmpeg_errors"),
        (FFmpegError, "frame_compare.utils.ffmpeg_errors"),
    ],
)
def test_active_domain_errors_live_in_owner_modules(error_class, owner_module):
    assert error_class.__module__ == owner_module


def test_metrics_calculation_error_is_analysis_error_marker() -> None:
    assert isinstance(MetricsCalculationError("test"), AnalysisError)


def test_insufficient_frames_error_details_shape():
    """Verify FC-3004 payload shape uses correct count/required keys."""
    path = Path("/video.mkv")
    count = 5
    required = 10

    error = InsufficientFramesError(path, count, required)

    assert error.code == "FC-3004"
    details = error.context.details
    assert details is not None
    assert set(details.keys()) == {"path", "count", "required"}
    assert details["path"] == str(path)
    assert details["count"] == count
    assert details["required"] == required


def test_network_timeout_error_redacts_sensitive_url_components() -> None:
    error = NetworkTimeoutError(
        "https://user:secret@example.com/path/to/api?token=abc123#fragment",
        7.5,
    )

    assert "secret" not in error.context.message
    assert "abc123" not in error.context.message
    assert "fragment" not in error.context.message
    assert "https://example.com/path/to/api" in error.context.message

    details = error.context.details
    assert details == {
        "url": "https://example.com/path/to/api",
        "timeout": 7.5,
    }


def test_vspreview_error_omits_public_details() -> None:
    error = VSPreviewError("launch exited with code 3")

    assert error.context.message == "VSPreview failed: launch exited with code 3"
    assert error.context.details is None


def test_exit_code_enum_values():
    assert ExitCode.SUCCESS == 0
    assert ExitCode.GENERAL_ERROR == 1
    assert ExitCode.CONFIG_ERROR == 2
    assert ExitCode.DEPENDENCY_ERROR == 3
    assert ExitCode.INPUT_ERROR == 4
    assert ExitCode.PROCESSING_ERROR == 5
    assert ExitCode.NETWORK_ERROR == 6
    assert ExitCode.INTERRUPTED == 130


def test_get_exit_code_config():
    assert get_exit_code(ConfigNotFoundError(Path("/test"))) == ExitCode.CONFIG_ERROR


def test_get_exit_code_dependency():
    assert get_exit_code(VapourSynthNotFoundError()) == ExitCode.DEPENDENCY_ERROR


def test_get_exit_code_input():
    assert get_exit_code(NoVideosFoundError(Path("/test"))) == ExitCode.INPUT_ERROR


def test_get_exit_code_processing():
    assert get_exit_code(RenderError()) == ExitCode.PROCESSING_ERROR


def test_get_exit_code_network():
    assert get_exit_code(SlowpicsError("test")) == ExitCode.NETWORK_ERROR


def test_get_exit_code_internal():
    assert get_exit_code(GenericInternalError("test")) == ExitCode.GENERAL_ERROR


def test_get_exit_code_unknown():
    error = FrameCompareError(ErrorContext(code="FC-0000", name="UNKNOWN", message="test"))
    assert get_exit_code(error) == ExitCode.GENERAL_ERROR


@pytest.mark.parametrize(
    "code,expected",
    [
        ("FC-1000", ExitCode.CONFIG_ERROR),
        ("FC-2000", ExitCode.DEPENDENCY_ERROR),
        ("FC-3000", ExitCode.INPUT_ERROR),
        ("FC-4000", ExitCode.PROCESSING_ERROR),
        ("FC-5000", ExitCode.NETWORK_ERROR),
    ],
)
def test_get_exit_code_maps_by_error_code_prefix_for_generic_error(code, expected):
    error = FrameCompareError(ErrorContext(code=code, name="GENERIC", message="test"))
    assert get_exit_code(error) == expected


def test_format_error_console_basic():
    error = VapourSynthNotFoundError()
    rendered = _render_rich_markup(format_error_console(error))

    assert f"Error [{error.code}]: {error.context.message}" in rendered
    assert "Hint:" in rendered
    # Since it has no details, it shouldn't say "For more details" or "Details:"
    assert "Details:" not in rendered
    assert "For more details, run with --verbose" not in rendered


def test_format_error_console_verbose_with_details():
    cache_path = Path("/cache")
    error = CacheCorruptionError(cache_path)
    rendered = _render_rich_markup(format_error_console(error, verbose=True))

    assert f"Error [{error.code}]: {error.context.message}" in rendered
    assert "Details:" in rendered
    assert "path:" in rendered
    # Path string formatting is platform-dependent (POSIX: "/cache", Windows: "\\cache").
    assert str(cache_path) in rendered


def test_format_error_console_non_verbose_with_details():
    error = CacheCorruptionError(Path("/cache"))
    rendered = _render_rich_markup(format_error_console(error, verbose=False))

    assert f"Error [{error.code}]: {error.context.message}" in rendered
    assert "Details:" not in rendered
    assert "For more details, run with --verbose" in rendered


def test_format_error_console_without_verbose_hint_shows_details() -> None:
    error = CacheCorruptionError(Path("/cache"))
    rendered = _render_rich_markup(format_error_console(error, verbose=False, verbose_hint=None))

    assert f"Error [{error.code}]: {error.context.message}" in rendered
    assert "Details:" in rendered
    assert "path:" in rendered
    assert "For more details, run with --verbose" not in rendered


def test_format_error_console_verbose_no_details():
    error = RenderError()
    rendered = _render_rich_markup(format_error_console(error, verbose=True))

    assert f"Error [{error.code}]: {error.context.message}" in rendered
    assert "Details:" not in rendered


def test_format_error_console_rendered_output_preserves_literal_brackets() -> None:
    error = FrameCompareError(
        ErrorContext(
            code="FC-3001",
            name="BRACKETED_VALUE",
            message="File [1080p] missing",
            hint="Try [literal] brackets",
            details={"path": "C:/videos/[sample].mkv"},
        )
    )

    rendered = _render_rich_markup(format_error_console(error, verbose=True))

    assert "Error [FC-3001]: File [1080p] missing" in rendered
    assert "[[FC-3001]]" not in rendered
    assert "Hint: Try [literal] brackets" in rendered
    assert "path: C:/videos/[sample].mkv" in rendered


def test_format_error_json():
    error = RenderError()
    data = format_error_json(error)
    assert data["success"] is False
    payload = data["error"]
    assert isinstance(payload, dict)
    assert payload["code"] == "FC-4004"
