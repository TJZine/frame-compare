from pathlib import Path

import pytest

import frame_compare.error_context as error_context
import frame_compare.error_dependency as error_dependency
import frame_compare.error_formatting as error_formatting
import frame_compare.error_input as error_input
import frame_compare.error_internal as error_internal
import frame_compare.error_processing as error_processing
import frame_compare.errors as error_facade
from frame_compare.analysis.errors import (
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


@pytest.mark.parametrize(
    "facade_class,module_class,args,expected",
    [
        (
            error_facade.DoviToolNotFoundError,
            error_dependency.DoviToolNotFoundError,
            (),
            {
                "code": "FC-2007",
                "name": "DOVI_TOOL_NOT_FOUND",
                "message": "dovi_tool binary not found",
                "hint": "Install dovi_tool and add to PATH or config",
                "details": None,
            },
        ),
        (
            error_facade.PythonVersionError,
            error_dependency.PythonVersionError,
            ("3.12.1",),
            {
                "code": "FC-2010",
                "name": "PYTHON_VERSION_ERROR",
                "message": "Python version 3.12.1 not supported",
                "hint": "Use Python 3.13+",
                "details": {"current_version": "3.12.1"},
            },
        ),
        (
            error_facade.VideoOpenError,
            error_input.VideoOpenError,
            (Path("/media/source.mkv"),),
            {
                "code": "FC-3002",
                "name": "VIDEO_OPEN_ERROR",
                "message": "Failed to open video: /media/source.mkv",
                "hint": "Check file permissions and format",
                "details": {"path": "/media/source.mkv"},
            },
        ),
        (
            error_facade.VideoCorruptError,
            error_input.VideoCorruptError,
            (Path("/media/bad.mkv"),),
            {
                "code": "FC-3003",
                "name": "VIDEO_CORRUPT",
                "message": "Video file corrupt: /media/bad.mkv",
                "hint": "Re-encode or check source integrity",
                "details": {"path": "/media/bad.mkv"},
            },
        ),
        (
            error_facade.IncompatibleVideosError,
            error_input.IncompatibleVideosError,
            ("resolution mismatch",),
            {
                "code": "FC-3005",
                "name": "INCOMPATIBLE_VIDEOS",
                "message": "Videos incompatible: resolution mismatch",
                "hint": "Ensure all videos match dimensions/colorspace",
                "details": {"reason": "resolution mismatch"},
            },
        ),
        (
            error_facade.DirectoryNotWritableError,
            error_input.DirectoryNotWritableError,
            (Path("/readonly"),),
            {
                "code": "FC-3007",
                "name": "DIRECTORY_NOT_WRITABLE",
                "message": "Directory not writable: /readonly",
                "hint": "Check filesystem permissions",
                "details": {"path": "/readonly"},
            },
        ),
        (
            error_facade.FileTooLargeError,
            error_input.FileTooLargeError,
            (Path("/media/huge.mkv"), 2048, 1024),
            {
                "code": "FC-3008",
                "name": "FILE_TOO_LARGE",
                "message": "File /media/huge.mkv too large (2048 > 1024)",
                "hint": "Use smaller file or increase limit",
                "details": {"path": "/media/huge.mkv", "size": 2048, "limit": 1024},
            },
        ),
        (
            error_facade.PathEscapesRootError,
            error_input.PathEscapesRootError,
            (Path("../escape"), Path("/workspace")),
            {
                "code": "FC-3009",
                "name": "PATH_ESCAPES_ROOT",
                "message": "Path ../escape escapes root /workspace",
                "hint": "Do not use .. in paths",
                "details": {"path": "../escape", "root": "/workspace"},
            },
        ),
        (
            error_facade.ProcessingOutOfMemoryError,
            error_processing.ProcessingOutOfMemoryError,
            (),
            {
                "code": "FC-4010",
                "name": "MEMORY_ERROR",
                "message": "Out of memory during processing",
                "hint": "Reduce thread count or frame count",
                "details": None,
            },
        ),
        (
            error_facade.ProcessingTimeoutError,
            error_processing.ProcessingTimeoutError,
            ("render", 12.5),
            {
                "code": "FC-4011",
                "name": "TIMEOUT_ERROR",
                "message": "Operation 'render' timed out after 12.5s",
                "hint": "Increase timeout in config",
                "details": {"operation": "render", "timeout": 12.5},
            },
        ),
        (
            error_facade.DoviError,
            error_processing.DoviError,
            (Path("/media/dv.mkv"), "missing RPU"),
            {
                "code": "FC-4018",
                "name": "DOVI_ERROR",
                "message": "Dolby Vision error for /media/dv.mkv: missing RPU",
                "hint": "Check RPU validity or dovi_tool version",
                "details": {"path": "/media/dv.mkv", "reason": "missing RPU"},
            },
        ),
        (
            error_facade.GenericInternalError,
            error_internal.GenericInternalError,
            ("unreachable branch",),
            {
                "code": "FC-9001",
                "name": "INTERNAL_ERROR",
                "message": "Internal error: unreachable branch",
                "hint": "Report this bug",
                "details": {"reason": "unreachable branch"},
            },
        ),
        (
            error_facade.InvariantViolationError,
            error_internal.InvariantViolationError,
            ("frame index sorted",),
            {
                "code": "FC-9002",
                "name": "ASSERTION_ERROR",
                "message": "Assertion failed: frame index sorted",
                "hint": "Report this bug",
                "details": {"assertion": "frame index sorted"},
            },
        ),
        (
            error_facade.UnexpectedStateError,
            error_internal.UnexpectedStateError,
            ("finalized before render",),
            {
                "code": "FC-9003",
                "name": "UNEXPECTED_STATE",
                "message": "Unexpected state: finalized before render",
                "hint": "Report this bug",
                "details": {"state": "finalized before render"},
            },
        ),
    ],
)
def test_extracted_error_modules_match_facade_contexts(
    facade_class, module_class, args, expected
) -> None:
    assert facade_class is module_class

    error = module_class(*args)

    assert error.context.code == expected["code"]
    assert error.context.name == expected["name"]
    assert error.context.message == expected["message"]
    assert error.context.hint == expected["hint"]
    assert error.context.details == expected["details"]
    assert str(error).startswith(f"[{expected['code']}] {expected['message']}")


def test_error_context_to_dict_omits_non_public_cause_and_empty_fields() -> None:
    cause = RuntimeError("secret stack detail")
    context = error_context.ErrorContext(
        code="FC-0001",
        name="SAMPLE",
        message="Sample failure",
        details={},
        hint="",
        cause=cause,
    )

    assert context.to_dict() == {
        "code": "FC-0001",
        "name": "SAMPLE",
        "message": "Sample failure",
    }

    error = error_context.FrameCompareError(context)
    assert error.code == "FC-0001"
    assert error.name == "SAMPLE"
    assert error.hint == ""
    assert "secret stack detail" not in str(error)
    assert repr(error).startswith("FrameCompareError(ErrorContext(")


def test_error_formatting_helpers_are_exported_and_json_safe() -> None:
    url = "https://user:secret@[2001:db8::1]:443/path?api_key=secret#frag"
    assert error_formatting.redact_url_for_error(url) == "https://[2001:db8::1]:443/path"
    assert error_facade.redact_url_for_error(url) == "https://[2001:db8::1]:443/path"

    raw_errors: list[dict[str, object]] = [
        {
            "loc": ("analysis", "frame_count"),
            "msg": "bad input",
            "ctx": {"limit": 100, "path": Path("/config.toml")},
        }
    ]
    normalized = error_formatting.normalize_pydantic_errors(raw_errors)

    assert normalized == [
        {
            "loc": ["analysis", "frame_count"],
            "msg": "bad input",
            "ctx": {"limit": 100, "path": "/config.toml"},
        }
    ]
    assert error_facade.normalize_pydantic_errors(raw_errors) == normalized


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
    output = format_error_console(error)
    assert f"✗ Error [{error.code}]:" in output
    assert error.context.message in output
    assert "Hint:" in output
    # Since it has no details, it shouldn't say "For more details" or "Details:"
    assert "Details:" not in output
    assert "For more details, run with --verbose" not in output


def test_format_error_console_verbose_with_details():
    cache_path = Path("/cache")
    error = CacheCorruptionError(cache_path)
    output = format_error_console(error, verbose=True)
    assert f"✗ Error [{error.code}]:" in output
    assert "Details:" in output
    assert "'path'" in output or "path" in output
    # Path string formatting is platform-dependent (POSIX: "/cache", Windows: "\\cache").
    assert str(cache_path) in output


def test_format_error_console_non_verbose_with_details():
    error = CacheCorruptionError(Path("/cache"))
    output = format_error_console(error, verbose=False)
    assert f"✗ Error [{error.code}]:" in output
    assert "Details:" not in output
    assert "For more details, run with --verbose" in output


def test_format_error_console_verbose_no_details():
    error = RenderError()
    output = format_error_console(error, verbose=True)
    assert f"✗ Error [{error.code}]:" in output
    assert "Details:" not in output


def test_format_error_json():
    error = RenderError()
    data = format_error_json(error)
    assert data["success"] is False
    payload = data["error"]
    assert isinstance(payload, dict)
    assert payload["code"] == "FC-4004"
