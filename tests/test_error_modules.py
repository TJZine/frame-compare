from pathlib import Path

import pytest

import frame_compare.error_context as error_context
import frame_compare.error_dependency as error_dependency
import frame_compare.error_formatting as error_formatting
import frame_compare.error_input as error_input
import frame_compare.error_internal as error_internal
import frame_compare.error_processing as error_processing
import frame_compare.errors as error_facade


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
                "message": f"Failed to open video: {Path('/media/source.mkv')}",
                "hint": "Check file permissions and format",
                "details": {"path": str(Path("/media/source.mkv"))},
            },
        ),
        (
            error_facade.VideoCorruptError,
            error_input.VideoCorruptError,
            (Path("/media/bad.mkv"),),
            {
                "code": "FC-3003",
                "name": "VIDEO_CORRUPT",
                "message": f"Video file corrupt: {Path('/media/bad.mkv')}",
                "hint": "Re-encode or check source integrity",
                "details": {"path": str(Path("/media/bad.mkv"))},
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
                "message": f"Directory not writable: {Path('/readonly')}",
                "hint": "Check filesystem permissions",
                "details": {"path": str(Path("/readonly"))},
            },
        ),
        (
            error_facade.FileTooLargeError,
            error_input.FileTooLargeError,
            (Path("/media/huge.mkv"), 2048, 1024),
            {
                "code": "FC-3008",
                "name": "FILE_TOO_LARGE",
                "message": f"File {Path('/media/huge.mkv')} too large (2048 > 1024)",
                "hint": "Use smaller file or increase limit",
                "details": {"path": str(Path("/media/huge.mkv")), "size": 2048, "limit": 1024},
            },
        ),
        (
            error_facade.PathEscapesRootError,
            error_input.PathEscapesRootError,
            (Path("../escape"), Path("/workspace")),
            {
                "code": "FC-3009",
                "name": "PATH_ESCAPES_ROOT",
                "message": f"Path {Path('../escape')} escapes root {Path('/workspace')}",
                "hint": "Do not use .. in paths",
                "details": {"path": str(Path("../escape")), "root": str(Path("/workspace"))},
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
                "message": f"Dolby Vision error for {Path('/media/dv.mkv')}: missing RPU",
                "hint": "Check RPU validity or dovi_tool version",
                "details": {"path": str(Path("/media/dv.mkv")), "reason": "missing RPU"},
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
            "ctx": {"limit": 100, "path": str(Path("/config.toml"))},
        }
    ]
    assert error_facade.normalize_pydantic_errors(raw_errors) == normalized
